"""Backend endpoint conformance; required CI explicitly discovers this test root."""
import concurrent.futures
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from PIL import Image
from backend.app import FrameIngress, SourceGrant, create_app, MAX_BODY, MAX_JPEG

TOKEN = 'fixture-only-token-never-use-in-deployment-00001'


def encoded_image(size=(32, 24), format='JPEG'):
    target = io.BytesIO()
    Image.new('RGB', size, color=(100, 60, 10)).save(target, format=format)
    return target.getvalue()


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.grant = SourceGrant(TOKEN, 'demo-session', 'pi-camera-1', 'pi-boot-1', 'replay', 1300)
        self.ingress = FrameIngress([self.grant], clock=lambda: self.now)
        self.health = {'model_available': False, 'worker_healthy': False}
        self.client = TestClient(create_app(ingress=self.ingress, dependency_health=lambda: self.health))
        self.jpeg = encoded_image()
        self.metadata = json.loads((Path(__file__).resolve().parents[2] /
                                    'shared/protocol/v1/examples/frame.json').read_text())
        self.metadata.update(source_id='pi-camera-1', boot_id='pi-boot-1', jpeg_bytes=len(self.jpeg),
                             image={'width': 32, 'height': 24})
        self.headers = {'Authorization': 'Bearer ' + TOKEN}

    def upload(self, metadata=None, jpeg=None, headers=None, raw=None):
        return self.client.post('/v1/frames', headers=self.headers if headers is None else headers,
                                files={'metadata': (None, raw if raw is not None else json.dumps(
                                    self.metadata if metadata is None else metadata), 'application/json'),
                                       'image': ('synthetic.jpg', self.jpeg if jpeg is None else jpeg, 'image/jpeg')})

    def test_liveness_does_not_imply_dependency_readiness(self):
        self.assertEqual(self.client.get('/healthz').json(), {'status': 'alive'})
        response = self.client.get('/readyz')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['ready'])
        self.health.update(model_available=True, worker_healthy=True)
        self.assertEqual(self.client.get('/readyz').status_code, 200)
        self.health['worker_healthy'] = False
        self.assertEqual(self.client.get('/readyz').status_code, 503)
        self.assertEqual(self.client.get('/healthz').status_code, 200)

    def test_default_app_is_unconfigured_and_rejects_uploads(self):
        client = TestClient(create_app())
        self.assertEqual(client.get('/healthz').status_code, 200)
        self.assertEqual(client.get('/readyz').status_code, 503)
        self.assertEqual(client.post('/v1/frames').status_code, 401)

    def test_model_health_provider_failure_is_unavailable(self):
        client = TestClient(create_app(ingress=self.ingress,
                           dependency_health=lambda: (_ for _ in ()).throw(RuntimeError('private info'))))
        response = client.get('/readyz')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private info', response.text)

    def test_valid_upload_preserves_entire_original_metadata(self):
        response = self.upload()
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json(), {'schema_version': 1, 'frame_id': self.metadata['frame_id'],
                                           'status': 'accepted'})
        key = ('demo-session', 'pi-camera-1')
        self.assertEqual(self.ingress.latest[key].metadata, self.metadata)
        self.assertEqual(self.ingress.latest[key].jpeg, self.jpeg)
        self.assertEqual(self.ingress.ledger[key][0], self.metadata)
        # Receipt is not a freshness or inference verdict.
        self.assertEqual(self.client.get('/readyz').status_code, 503)

    def test_missing_invalid_and_expired_credentials(self):
        for headers in ({}, {'Authorization': 'Bearer bad'}, {'Authorization': 'Basic abc'}):
            with self.subTest(headers=headers):
                self.assertEqual(self.upload(headers=headers).status_code, 401)
        self.assertEqual(self.upload().status_code, 202)
        self.now = 1300
        self.assertEqual(self.upload().status_code, 401)
        self.assertEqual(self.ingress.latest, {})
        self.assertEqual(self.ingress.ledger, {})

    def test_phone_role_cannot_upload(self):
        grant = SourceGrant(TOKEN, 'demo-session', 'phone-1', 'phone-boot-1', 'replay', 1300, 'phone')
        client = TestClient(create_app(ingress=FrameIngress([grant], clock=lambda: self.now)))
        self.assertEqual(client.post('/v1/frames', headers=self.headers).status_code, 403)

    def test_enrolled_identity_epoch_and_mode_required(self):
        for key, value, code in [('session_id', 'other', 403), ('source_id', 'other', 403),
                                 ('mode', 'live', 403), ('boot_id', 'old-boot', 409)]:
            with self.subTest(key=key):
                self.assertEqual(self.upload(metadata=dict(self.metadata, **{key: value})).status_code, code)
        self.assertEqual(self.ingress.latest, {})

    def test_duplicate_sequence_frame_id_and_reordered_uploads(self):
        self.assertEqual(self.upload().status_code, 202)
        for metadata in (self.metadata, dict(self.metadata, seq=self.metadata['seq']-1, frame_id='older'),
                         dict(self.metadata, seq=self.metadata['seq']+1)):
            self.assertEqual(self.upload(metadata=metadata).status_code, 409)

    def test_retention_is_bounded_and_superseded_ids_cannot_return(self):
        for n in range(4):
            metadata = dict(self.metadata, seq=100+n, frame_id=f'frame-{n}')
            self.assertEqual(self.upload(metadata=metadata).status_code, 202)
        key = ('demo-session', 'pi-camera-1')
        self.assertEqual(len(self.ingress.latest), 1)
        self.assertEqual(len(self.ingress.ledger[key]), 2)
        self.assertEqual(self.ingress.latest[key].metadata['frame_id'], 'frame-3')
        self.assertEqual(self.upload(metadata=dict(self.metadata, seq=104, frame_id='frame-0')).status_code, 409)
        with patch('backend.app.MAX_FRAMES_PER_EPOCH', 4):
            self.assertEqual(self.upload(metadata=dict(self.metadata, seq=104, frame_id='frame-4')).status_code, 409)

    def test_invalid_image_does_not_consume_sequence_or_store_frame(self):
        self.assertEqual(self.upload(jpeg=b'X'*len(self.jpeg)).status_code, 422)
        self.assertEqual(self.ingress.latest, {})
        self.assertEqual(self.upload().status_code, 202)

    def test_compressed_raster_truncation_is_rejected(self):
        jpeg = self.jpeg[:-40]
        self.assertEqual(self.upload(metadata=dict(self.metadata, jpeg_bytes=len(jpeg)), jpeg=jpeg).status_code, 422)

    def test_png_cannot_masquerade_as_jpeg(self):
        png = encoded_image(format='PNG')
        self.assertEqual(self.upload(metadata=dict(self.metadata, jpeg_bytes=len(png)), jpeg=png).status_code, 422)

    def test_dimensions_and_byte_count_must_match_actual_jpeg(self):
        for metadata in (dict(self.metadata, image={'width': 31, 'height': 24}),
                         dict(self.metadata, jpeg_bytes=len(self.jpeg)+1)):
            self.assertEqual(self.upload(metadata=metadata).status_code, 422)
        # Small compressed payload with oversized actual dimensions, lying metadata.
        self.assertEqual(self.upload(metadata=dict(self.metadata, jpeg_bytes=len(encoded_image((1921, 1)))),
                                     jpeg=encoded_image((1921, 1))).status_code, 413)

    def test_json_schema_and_wire_rejections(self):
        for raw in ('{"seq":1,"seq":2}', '{"bad":NaN}', '{"bad":1e999}',
                    '['*20+'0'+']'*20, ' '*8193, json.dumps(dict(self.metadata, go=True)),
                    json.dumps(dict(self.metadata, schema_version=2))):
            with self.subTest(raw=raw[:50]):
                self.assertEqual(self.upload(raw=raw).status_code, 422)
        self.assertEqual(self.ingress.latest, {})

    def test_body_limits_even_without_content_length(self):
        self.assertEqual(self.upload(jpeg=b'x'*(MAX_JPEG+1)).status_code, 413)
        response = self.client.post('/v1/frames', headers={**self.headers, 'content-type': 'multipart/form-data; boundary=x'},
                                    content=iter([b'x'*600_000, b'x'*600_000]))
        self.assertEqual(response.status_code, 413)
        for length, status in [('bad', 422), (str(MAX_BODY+1), 413), ('9'*5000, 413)]:
            response = self.client.post('/v1/frames', content=b'', headers={**self.headers,
                       'content-type': 'multipart/form-data; boundary=x', 'content-length': length})
            self.assertEqual(response.status_code, status)

    def test_extra_missing_wrong_and_duplicate_parts(self):
        image = ('x.jpg', self.jpeg, 'image/jpeg')
        meta = (None, json.dumps(self.metadata))
        for files in ([('image', image)], [('metadata', meta), ('image', image), ('extra', (None, 'x'))],
                      [('metadata', meta), ('metadata', meta), ('image', image)],
                      [('metadata', ('x.json', json.dumps(self.metadata))), ('image', image)],
                      [('metadata', meta), ('image', ('x.jpg', self.jpeg, 'image/png'))]):
            self.assertEqual(self.client.post('/v1/frames', headers=self.headers, files=files).status_code, 422)
        self.assertEqual(self.client.post('/v1/frames', headers=self.headers, json={}).status_code, 415)

    def test_concurrent_duplicate_acceptance_is_atomic(self):
        def accept():
            try:
                self.ingress.accept(self.grant, copy.deepcopy(self.metadata), self.jpeg)
                return 202
            except Exception as error:
                return error.status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: accept(), range(4)))
        self.assertEqual(sorted(results), [202, 409, 409, 409])

    def test_exact_dimension_limit_and_five_second_upload_deadline(self):
        jpeg = encoded_image((1920, 1080))
        metadata = dict(self.metadata, image={'width': 1920, 'height': 1080}, jpeg_bytes=len(jpeg))
        self.assertEqual(self.upload(metadata=metadata, jpeg=jpeg).status_code, 202)
        import anyio
        from backend.app import read_parts
        from starlette.requests import Request
        async def receive():
            await anyio.sleep(.05)
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        scope = {'type': 'http', 'method': 'POST', 'path': '/v1/frames',
                 'headers': [(b'content-type', b'multipart/form-data; boundary=x')]}
        fail_after = anyio.fail_after
        with patch('backend.app.anyio.fail_after', side_effect=lambda _: fail_after(.001)):
            with self.assertRaises(Exception) as caught:
                anyio.run(read_parts, Request(scope, receive))
        self.assertEqual(caught.exception.status_code, 408)

    def test_overload_rejects_fifth_request_before_body_processing(self):
        import threading
        from backend.app import validate_jpeg
        entered = threading.Barrier(5)
        release = threading.Event()
        def blocked_decoder(jpeg, metadata):
            entered.wait(timeout=10)
            if not release.wait(timeout=10):
                raise RuntimeError('Test release timed out')
            validate_jpeg(jpeg, metadata)
        with patch('backend.app.validate_jpeg', side_effect=blocked_decoder):
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(self.upload) for _ in range(4)]
                try:
                    entered.wait(timeout=10)
                    self.assertEqual(self.upload().status_code, 503)
                finally:
                    release.set()
                self.assertEqual(sorted(f.result().status_code for f in futures), [202, 409, 409, 409])


if __name__ == '__main__':
    unittest.main()
