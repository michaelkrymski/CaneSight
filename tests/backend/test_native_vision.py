"""Native result authorization/lifecycle and real certificate-verified transport."""
import asyncio
import copy
import json
import os
from pathlib import Path
import secrets
import socket
import shutil
import subprocess
import ssl
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
import trustme
import uvicorn

from backend.app import create_app
from backend.inference_worker import InferenceWorker
from backend.server import create_session_app, server_config
from backend.sessions import SessionManager, SessionRequest, send_current
from backend.deploy.vision_probe import run
from backend.vision.baseline import manifest
from test_sessions import OPERATOR, specification, fixture
from test_app import encoded_image


def observation(metadata):
    value = {key: copy.deepcopy(v) for key, v in metadata.items() if key != 'jpeg_bytes'}
    value.update(type='vision_observation', processing_ms=1,
        model_version=manifest()['model'] + '-sha256-' + manifest()['artifact']['sha256'],
        detections=[], signal={'candidate_count': 0, 'symbol': 'unknown',
                              'confidence': None, 'countdown_s': None})
    return value


class SyntheticModel:
    version = manifest()['model'] + '-sha256-' + manifest()['artifact']['sha256']

    def predict(self, frame):
        return {'detections': [], 'signal': {'candidate_count': 0, 'symbol': 'unknown',
                                            'confidence': None, 'countdown_s': None}}


def synthetic_factory():
    return SyntheticModel()


class StubWorker:
    def __init__(self):
        self.results, self.discards, self.takes = {}, [], 0

    def submit(self, grant, metadata, jpeg):
        self.results[grant.session_id] = observation(metadata)

    def discard_source(self, grant):
        self.discards.append(grant.session_id)
        self.results.pop(grant.session_id, None)

    def take_result(self, grant):
        self.takes += 1
        return self.results.pop(grant.session_id, None)


class NativeVisionTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.manager = SessionManager(OPERATOR, clock=lambda: self.now)
        self.worker = StubWorker()
        self.manager.bind_inference_worker(self.worker)
        self.pair = self.manager.create(SessionRequest.model_validate(specification()))
        self.session, self.grant = self.manager.authenticate('Bearer ' + self.pair['pi']['token'], 'pi')
        self.connection = self.manager.attach(self.session, 'pi')
        self.jpeg = encoded_image()

    def upload(self, seq=9):
        metadata = dict(fixture('frame'), session_id=self.pair['session_id'], seq=seq,
            frame_id='frame-' + str(seq), jpeg_bytes=len(self.jpeg), image={'width': 32, 'height': 24})
        self.manager.accept_frame(self.session, self.grant, metadata, self.jpeg)
        return metadata

    def take(self, connection=None):
        return self.manager.take_vision(self.session, self.grant, connection or self.connection)

    def test_latest_original_lineage_one_result_and_no_client_vision_publish(self):
        original = self.upload()
        expected = observation(original)
        self.assertEqual(self.take(), expected)
        self.assertIsNone(self.take())
        self.worker.results[self.grant.session_id] = expected
        self.assertIsNone(self.take())
        newer = self.upload(10)
        self.worker.results[self.grant.session_id] = expected
        self.assertIsNone(self.take())
        bad = observation(newer)
        bad['capture_monotonic_ms'] += 1
        self.worker.results[self.grant.session_id] = bad
        self.assertIsNone(self.take())
        with self.assertRaises(ValueError):
            self.manager.relay(self.session, self.grant, self.connection, observation(newer))

    def test_other_session_and_phone_never_consume_the_pi_result(self):
        self.upload()
        pair = self.manager.create(SessionRequest.model_validate(specification()))
        session, grant = self.manager.authenticate('Bearer ' + pair['pi']['token'], 'pi')
        other = self.manager.attach(session, 'pi')
        self.assertIsNone(self.manager.take_vision(session, grant, other))
        _, phone = self.manager.authenticate('Bearer ' + self.pair['phone']['token'], 'phone')
        phone_connection = self.manager.attach(self.session, 'phone')
        self.assertIsNone(self.manager.take_vision(self.session, phone, phone_connection))
        self.assertIsNotNone(self.take())

    def test_reconnect_discards_old_work_and_late_cleanup_preserves_replacement(self):
        self.upload()
        old = self.connection
        self.manager.detach(self.session, old)
        replacement = self.manager.attach(self.session, 'pi')
        self.assertIsNone(self.take(replacement))
        self.upload(10)
        count = len(self.worker.discards)
        self.manager.detach(self.session, old)
        self.assertEqual(len(self.worker.discards), count)
        with self.assertRaises(HTTPException):
            self.take(old)
        self.assertIsNotNone(self.take(replacement))

    def test_phone_interruption_discards_results_and_invalidates_current_pi(self):
        phone = self.manager.attach(self.session, 'phone')
        self.upload()
        self.manager.detach(self.session, phone)
        self.assertEqual(self.connection.close_code, 1012)
        self.assertNotIn(self.grant.session_id, self.worker.results)
        with self.assertRaises(HTTPException):
            self.take()

    def test_relay_queue_overflow_discards_pending_inference(self):
        phone = self.manager.attach(self.session, 'phone')
        _, phone_grant = self.manager.authenticate('Bearer ' + self.pair['phone']['token'], 'phone')
        self.upload()
        for _ in range(8):
            self.connection.queue.put_nowait({'synthetic': True})
        message = dict(fixture('depth'), session_id=self.pair['session_id'])
        with self.assertRaises(ValueError):
            self.manager.relay(self.session, phone_grant, phone, message)
        self.assertEqual(self.connection.close_code, 1013)
        self.assertTrue(self.connection.queue.empty())
        self.assertEqual(self.worker.results, {})

    def test_expiry_and_revocation_discard_before_dequeue(self):
        self.upload()
        self.now += 301
        with self.assertRaises(HTTPException):
            self.take()
        self.assertEqual(self.worker.results, {})
        self.assertEqual(self.connection.close_code, 4401)

    def test_backpressured_send_is_cancelled_on_revocation_or_supersession(self):
        async def exercise(revoke):
            entered = asyncio.Event()
            class SlowSocket:
                committed = False
                cancelled = False
                async def send_json(socket, message):
                    entered.set()
                    try:
                        await asyncio.sleep(10)
                        socket.committed = True
                    except asyncio.CancelledError:
                        socket.cancelled = True
                        raise
            self.upload(20 if revoke else 11)
            message = self.take()
            socket = SlowSocket()
            task = asyncio.create_task(send_current(socket, self.manager, self.session,
                                                    self.grant, self.connection, message))
            await entered.wait()
            if revoke:
                self.manager.revoke(self.session.session_id)
                with self.assertRaises(HTTPException):
                    await asyncio.wait_for(task, .5)
            else:
                self.upload(12)
                await asyncio.wait_for(task, .5)
            self.assertFalse(socket.committed)
            self.assertTrue(socket.cancelled)
        asyncio.run(exercise(False))
        asyncio.run(exercise(True))

    def test_send_deadline_cancels_slow_consumer(self):
        async def exercise():
            class SlowSocket:
                async def send_json(self, message):
                    await asyncio.sleep(10)
            self.upload()
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(send_current(SlowSocket(), self.manager, self.session,
                    self.grant, self.connection, self.take()), 2)
        asyncio.run(exercise())

    def test_factory_default_remains_unconfigured_and_requires_absolute_opt_in(self):
        with patch.dict(os.environ, {'CANESIGHT_OPERATOR_TOKEN': OPERATOR, 'CANESIGHT_VISION_WEIGHTS': ''}):
            self.assertIsNone(create_session_app().state.inference_worker)
            os.environ['CANESIGHT_VISION_WEIGHTS'] = 'unreviewed-relative.pt'
            with self.assertRaises(RuntimeError):
                create_session_app()

    def test_missing_opt_in_weights_leave_enrolled_service_unready(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,
                CANESIGHT_OPERATOR_TOKEN=OPERATOR,
                CANESIGHT_VISION_WEIGHTS=str(Path(directory) / 'absent.pt')):
            app = create_session_app()
            with TestClient(app, base_url='https://testserver') as client:
                response = client.post('/v1/sessions', json=specification(),
                                       headers={'Authorization': 'Bearer ' + OPERATOR})
                self.assertEqual(response.status_code, 201)
                deadline = time.monotonic() + 10
                while not app.state.inference_worker.metrics()['failed']:
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.01)
                ready = client.get('/readyz')
                self.assertEqual(ready.status_code, 503)
                self.assertTrue(ready.json()['checks']['ingestion_configured'])
                self.assertFalse(ready.json()['checks']['model_available'])
                self.assertFalse(ready.json()['checks']['worker_healthy'])

    @unittest.skipUnless(shutil.which('docker'), 'Docker Compose required')
    def test_opt_in_compose_preserves_isolation_and_read_only_weights(self):
        if subprocess.run(['docker', 'compose', 'version'], capture_output=True).returncode:
            self.skipTest('Docker Compose unavailable')
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name in ('compose.yaml', 'compose.vision.yaml'):
                shutil.copy(root / 'backend/deploy' / name, folder / name)
            (folder / 'secrets').mkdir()
            (folder / 'secrets/backend.env').write_text('FIXTURE_ONLY=not-an-operator\n')
            env = dict(os.environ, CANESIGHT_DOMAIN='demo.example.org', BACKEND_IMAGE='sha256:' + 'a' * 64,
                CADDY_IMAGE='caddy@sha256:' + 'b' * 64, CANESIGHT_VISION_HOST_WEIGHTS='/operator/yolov8n.pt')
            response = subprocess.run(['docker', 'compose', '-f', str(folder / 'compose.yaml'),
                '-f', str(folder / 'compose.vision.yaml'), 'config', '--format', 'json'],
                env=env, capture_output=True, timeout=30)
            self.assertEqual(response.returncode, 0, 'Vision Compose validation failed; details suppressed')
            config = json.loads(response.stdout)['services']
            backend = config['backend']
            self.assertTrue(backend['read_only'])
            self.assertFalse(backend.get('ports'))
            weights = next(v for v in backend['volumes'] if v['target'].endswith('/yolov8n.pt'))
            self.assertTrue(weights['read_only'])
            # Older compose-go omits false booleans in normalized JSON (#836).
            # The source overlay still explicitly denies host-path creation.
            self.assertIn('create_host_path: false', (folder / 'compose.vision.yaml').read_text())
            self.assertIs(weights.get('bind', {}).get('create_host_path', False), False)
            self.assertIn('CANESIGHT_VISION_WEIGHTS', backend['environment'])
            self.assertNotIn('CANESIGHT_VISION_WEIGHTS', config['proxy']['environment'])


class NativeVisionTlsTests(unittest.TestCase):
    def exercise(self, actual=False):
        token = secrets.token_urlsafe(40)
        if actual:
            with patch.dict(os.environ, CANESIGHT_OPERATOR_TOKEN=token,
                            CANESIGHT_VISION_WEIGHTS=os.environ['CS_VISION_TEST_WEIGHTS']):
                app = create_session_app()
        else:
            app = create_app(session_manager=SessionManager(token),
                             inference_worker=InferenceWorker(synthetic_factory))
        with tempfile.TemporaryDirectory(prefix='canesight-vision-tls-') as directory:
            root = Path(directory)
            ca = trustme.CA()
            cert = ca.issue_cert('127.0.0.1')
            cert.private_key_pem.write_to_path(root / 'key.pem')
            cert.cert_chain_pems[0].write_to_path(root / 'cert.pem')
            context = ssl.create_default_context()
            ca.configure_trust(context)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen(128)
                port = listener.getsockname()[1]
                server = uvicorn.Server(server_config(app, port=port,
                    ssl_keyfile=str(root / 'key.pem'), ssl_certfile=str(root / 'cert.pem')))
                thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
                thread.start()
                try:
                    deadline = time.monotonic() + 10
                    while not server.started:
                        if not thread.is_alive() or time.monotonic() >= deadline:
                            self.fail('TLS service startup failed')
                        time.sleep(.01)
                    report = asyncio.run(run('https://127.0.0.1:' + str(port), token, context=context, samples=1))
                    self.assertTrue(report['original_lineage_preserved'])
                    self.assertTrue(report['phone_and_other_session_isolated'])
                    self.assertTrue(report['revocation_and_expiry_closed'])
                    self.assertEqual(app.state.sessions.sessions, {})
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive())
                    self.assertFalse(app.state.inference_worker.health()['worker_healthy'])

    def test_generated_detector_through_real_https_wss(self):
        self.exercise()

    @unittest.skipUnless(os.environ.get('CS_VISION_TEST_WEIGHTS'), 'Explicit pinned ML runtime/weights required')
    def test_actual_configured_model_through_real_https_wss(self):
        self.exercise(actual=True)
