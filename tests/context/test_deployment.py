"""Actual accepted factory composition with synthetic provider/writer/model inputs."""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from PIL import Image
from backend.context.deployment import create_deployment_app, main
from backend.context.service import ContextService

OPERATOR = 'synthetic-deployment-operator-not-real-'+'x'*32
ORIGIN = 'https://context.example.test'
ROOT = Path(__file__).resolve().parents[2]


class DeploymentTests(unittest.TestCase):
    def setup_app(self, mode, *, available=True, inference=False):
        stack = self.enterContext(ExitStack())
        folder = stack.enter_context(tempfile.TemporaryDirectory())
        stack.enter_context(patch.dict(os.environ, {
            'CANESIGHT_CONTEXT_BASE': mode, 'CANESIGHT_OPERATOR_TOKEN': OPERATOR,
            'GEMINI_API_KEY': 'synthetic-key-never-used', 'CANESIGHT_GEMINI_MODEL': 'gemini-fixture',
            'CANESIGHT_DASHBOARD_ORIGIN': ORIGIN,
            'CANESIGHT_EVENT_DB_CONFIG': str(Path(folder)/'private-runtime.json'),
            'CANESIGHT_VISION_WEIGHTS': str(Path(folder)/'synthetic-model.pt') if inference else '',
        }, clear=True))
        calls = []
        async def runner(model, jpeg):
            if jpeg is None:
                if not available: raise RuntimeError('PRIVATE-PROVIDER-ERROR')
                return {'available': True}
            calls.append(jpeg)
            return {'objects': ['chair'], 'uncertain': True}
        service = ContextService('gemini-fixture', runner=runner)
        stack.enter_context(patch('backend.context.server.ContextService', return_value=service))
        writer = Mock()
        stack.enter_context(patch('backend.telemetry.logging_app.EventWriter', return_value=writer))
        worker = Mock()
        worker.health.return_value = dict(model_available=True, worker_healthy=True)
        stack.enter_context(patch('backend.inference_worker.InferenceWorker', return_value=worker))
        yolo = stack.enter_context(patch('backend.vision.observations.YoloFactory'))
        app = create_deployment_app()
        client = stack.enter_context(TestClient(app, base_url=ORIGIN))
        pair = client.post('/v1/sessions', headers={'Authorization': 'Bearer '+OPERATOR}, json={
            'mode': 'replay', 'pi': {'source_id':'pi','boot_id':'pi-boot'},
            'phone': {'source_id':'phone','boot_id':'phone-boot'}}).json()
        self.assertIn(pair['session_id'], app.state.sessions.sessions)
        return app, client, pair, service, writer, worker, yolo, calls

    def request(self, client, pair):
        out = io.BytesIO(); Image.new('RGB', (32,24), 'gray').save(out, 'JPEG')
        frame = json.loads((ROOT/'shared/protocol/v1/examples/frame.json').read_text())
        frame.update(session_id=pair['session_id'], source_id='pi', boot_id='pi-boot',
                     image={'width':32,'height':24}, jpeg_bytes=len(out.getvalue()))
        return client.post('/v1/context', headers={'Authorization':'Bearer '+pair['pi']['token']},
            files={'metadata':(None,json.dumps({'request_id':'fixture-one','consent':True,'frame':frame}),'application/json'),
                   'image':('generated.jpg',out.getvalue(),'image/jpeg')})

    def test_each_existing_base_shares_session_authority_and_retains_routes(self):
        for mode in ('sessions','dashboard','logging'):
            with self.subTest(mode=mode):
                app, client, pair, service, writer, _, _, calls = self.setup_app(mode)
                self.assertIs(app.state.context, service)
                result = self.request(client, pair)
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.json()['description'],{'objects':['chair'],'uncertain':True})
                self.assertFalse(result.json()['capture_age_bounded'])
                self.assertEqual(len(calls),1)
                self.assertEqual(client.get('/healthz').status_code,200)
                self.assertEqual(client.get('/readyz').status_code,503)
                self.assertEqual(client.get('/v1/context/status', headers={
                    'Authorization':'Bearer '+pair['phone']['token']}).status_code,403)
                if mode in ('dashboard','logging'):
                    issued = client.post('/v1/dashboard-viewers', json={'session_id':pair['session_id']},
                        headers={'Authorization':'Bearer '+OPERATOR})
                    self.assertEqual(issued.status_code,201,issued.text)
                    self.assertEqual(client.get('/v1/context/status',headers={
                        'Authorization':'Bearer '+issued.json()['viewer_token']}).status_code,401)
                    self.assertEqual(client.post('/dashboard/api/login',
                        json={'viewer_token':issued.json()['viewer_token']},
                        headers={'Origin':ORIGIN}).status_code,204)
                    self.assertEqual(client.get('/dashboard/api/snapshot').status_code,200)
                if mode == 'logging':
                    writer.start.assert_called_once()
                    self.assertEqual(client.post('/v1/event-logging/consent',
                        json={'session_id':pair['session_id'],'action':'enable'},
                        headers={'Authorization':'Bearer '+OPERATOR}).status_code,200)

    def test_provider_verification_failure_preserves_native_and_viewer_service(self):
        app, client, pair, service, writer, _, _, _ = self.setup_app('logging', available=False, inference=True)
        self.assertFalse(service.ready)
        self.assertEqual(client.get('/readyz').status_code,200)
        self.assertEqual(client.get('/healthz').status_code,200)
        status = client.get('/v1/context/status',headers={'Authorization':'Bearer '+pair['pi']['token']})
        self.assertEqual(status.status_code,200)
        self.assertFalse(status.json()['available'])
        result = self.request(client,pair)
        self.assertEqual(result.status_code,503)
        self.assertNotIn('PRIVATE-PROVIDER-ERROR',result.text)
        self.assertEqual(client.post('/v1/dashboard-viewers',json={'session_id':pair['session_id']},
            headers={'Authorization':'Bearer '+OPERATOR}).status_code,201)
        writer.start.assert_called_once()

    def test_native_wss_heartbeat_relay_still_operates_when_context_is_unavailable(self):
        _, client, pair, _, _, _, _, _ = self.setup_app('logging',available=False)
        message = json.loads((ROOT/'shared/protocol/v1/examples/heartbeat.json').read_text())
        message.update(session_id=pair['session_id'],source_id='phone',boot_id='phone-boot',mode='replay')
        with client.websocket_connect('wss://context.example.test/v1/events',
                headers={'Authorization':'Bearer '+pair['pi']['token']}) as pi:
            with client.websocket_connect('wss://context.example.test/v1/telemetry',
                    headers={'Authorization':'Bearer '+pair['phone']['token']}) as phone:
                phone.send_json(message)
                self.assertEqual(pi.receive_json(),message)

    def test_existing_vision_factory_and_worker_lifecycle_are_preserved(self):
        app, client, pair, _, writer, worker, yolo, _ = self.setup_app('logging', inference=True)
        self.assertIs(app.state.inference_worker,worker)
        yolo.assert_called_once_with(os.environ['CANESIGHT_VISION_WEIGHTS'])
        worker.start.assert_called_once()
        self.assertEqual(client.get('/readyz').status_code,200)
        result = self.request(client,pair)
        frame = result.json()['frame']
        out = io.BytesIO(); Image.new('RGB',(32,24),'gray').save(out,'JPEG')
        upload = client.post('/v1/frames',headers={'Authorization':'Bearer '+pair['pi']['token']},
            files={'metadata':(None,json.dumps(frame),'application/json'),
                   'image':('generated.jpg',out.getvalue(),'image/jpeg')})
        self.assertEqual(upload.status_code,202,upload.text)
        worker.submit.assert_called_once()
        client.__exit__(None,None,None)
        worker.stop.assert_called_once()
        writer.close.assert_called_once()

    def test_invalid_base_or_missing_key_fails_before_any_base_factory(self):
        with patch('backend.server.create_session_app') as native, \
             patch('backend.telemetry.live.create_dashboard_app') as dashboard, \
             patch('backend.telemetry.logging_app.create_logging_app') as logging:
            for mode in ('', 'unknown', 'backend.server:create_session_app'):
                with patch.dict(os.environ, {'CANESIGHT_CONTEXT_BASE':mode},clear=True):
                    with self.assertRaises(ValueError): create_deployment_app()
            with patch.dict(os.environ, {'CANESIGHT_CONTEXT_BASE':'logging',
                    'CANESIGHT_GEMINI_MODEL':'gemini-fixture'},clear=True):
                with self.assertRaises(RuntimeError): create_deployment_app()
            native.assert_not_called(); dashboard.assert_not_called(); logging.assert_not_called()

    def test_launcher_keeps_loopback_and_existing_transport_bounds(self):
        app = Mock()
        with patch('backend.context.deployment.create_deployment_app',return_value=app), \
             patch('uvicorn.Server') as server:
            main([])
        config = server.call_args.args[0]
        self.assertIs(config.app,app)
        self.assertEqual((config.host,config.port,config.workers),('127.0.0.1',18083,1))
        self.assertFalse(config.access_log)
        self.assertEqual(config.ws_max_size,8192)
        self.assertEqual(config.forwarded_allow_ips,'127.0.0.1/32')
        with patch('sys.stderr',io.StringIO()):
            with self.assertRaises(SystemExit): main(['--host','0.0.0.0'])
