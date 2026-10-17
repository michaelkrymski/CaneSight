import asyncio
import io
import json
from pathlib import Path
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from backend.app import create_app
from backend.context.server import install_context
from backend.context.service import ContextService
from backend.sessions import SessionManager

ROOT = Path(__file__).resolve().parents[2]
OPERATOR = 'synthetic-operator-credential-not-for-deployment-00001'


class ContextHTTPTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.fail = False
        self.revoke_during_request = False
        async def runner(model, jpeg):
            if jpeg is None: return {'available': True}
            self.calls.append(jpeg)
            if self.fail: raise RuntimeError('private-provider-error-never-echo')
            if self.revoke_during_request:
                self.manager.revoke(self.pair['session_id'])
                await asyncio.sleep(.15)
            return {'objects': ['chair'], 'uncertain': True}
        self.manager = SessionManager(OPERATOR)
        self.service = ContextService('gemini-fixture', runner=runner)
        self.app = install_context(create_app(session_manager=self.manager), self.service)
        self.client = TestClient(self.app, base_url='https://testserver')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.pair = self.client.post('/v1/sessions', headers={'Authorization': 'Bearer ' + OPERATOR},
            json={'mode': 'replay', 'phone': {'source_id': 'phone', 'boot_id': 'phone-boot'},
                  'pi': {'source_id': 'pi', 'boot_id': 'pi-boot'}}).json()
        self.headers = {'Authorization': 'Bearer ' + self.pair['pi']['token']}
        out = io.BytesIO()
        Image.new('RGB', (32, 24), 'gray').save(out, 'JPEG')
        self.jpeg = out.getvalue()
        self.frame = json.loads((ROOT/'shared/protocol/v1/examples/frame.json').read_text())
        self.frame.update(session_id=self.pair['session_id'], source_id='pi', boot_id='pi-boot',
            image={'width': 32, 'height': 24}, jpeg_bytes=len(self.jpeg))

    def upload(self, *, metadata=None, headers=None, jpeg=None):
        return self.client.post('/v1/context', headers=self.headers if headers is None else headers,
            files={'metadata': (None, json.dumps(metadata if metadata is not None else
                {'request_id': 'context-one', 'consent': True, 'frame': self.frame}), 'application/json'),
                'image': ('synthetic.jpg', self.jpeg if jpeg is None else jpeg, 'image/jpeg')})

    def test_authenticated_context_preserves_lineage_but_never_claims_capture_age_or_readiness(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value['frame'], self.frame)
        self.assertFalse(value['capture_age_bounded'])
        self.assertEqual(value['description'], {'objects': ['chair'], 'uncertain': True})
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.get('/readyz').status_code, 503)
        with self.manager.lock:
            session = self.manager.sessions[self.pair['session_id']]
            self.assertEqual(session.ingress.latest, {})
        self.assertEqual(len(self.calls), 1)

    def test_missing_credentials_wrong_role_and_plain_http_are_rejected(self):
        self.assertEqual(self.upload(headers={}).status_code, 401)
        phone = {'Authorization': 'Bearer ' + self.pair['phone']['token']}
        self.assertEqual(self.upload(headers=phone).status_code, 403)
        response = self.client.post('http://testserver/v1/context', headers=self.headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.calls, [])

    def test_consent_and_exact_shape_required_before_provider(self):
        value = {'request_id': 'one', 'consent': False, 'frame': self.frame}
        self.assertEqual(self.upload(metadata=value).status_code, 422)
        self.assertEqual(self.calls, [])

    def test_cross_session_and_boot_substitution_rejected(self):
        frame = dict(self.frame, session_id='different-session')
        self.assertEqual(self.upload(metadata={'request_id': 'one', 'consent': True,
                                               'frame': frame}).status_code, 403)
        self.assertEqual(self.calls, [])

    def test_invalid_jpeg_cannot_reach_provider(self):
        self.assertEqual(self.upload(jpeg=b'not-a-jpeg').status_code, 422)
        self.assertEqual(self.calls, [])

    def test_cooldown_applies_before_body_parsing(self):
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(self.client.post('/v1/context', headers=self.headers).status_code, 429)
        self.assertEqual(len(self.calls), 1)

    def test_revocation_denies_future_context(self):
        self.client.delete('/v1/sessions/' + self.pair['session_id'],
            headers={'Authorization': 'Bearer ' + OPERATOR})
        self.assertEqual(self.upload().status_code, 401)

    def test_unavailable_model_keeps_transport_alive_and_refuses_context(self):
        self.service.ready = False
        self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(self.client.get('/healthz').status_code, 200)
        self.assertEqual(self.calls, [])

    def test_provider_failure_is_generic_and_never_echoes_error(self):
        self.fail = True
        response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-provider-error', response.text)

    def test_revocation_during_generation_cannot_deliver(self):
        self.revoke_during_request = True
        response = self.upload()
        self.assertIn(response.status_code, (401, 503))
        self.assertNotIn('description', response.json())


if __name__ == '__main__': unittest.main()
