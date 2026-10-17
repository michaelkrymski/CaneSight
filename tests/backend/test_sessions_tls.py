"""Real certificate-verified HTTPS/WSS rehearsal using generated fixtures only."""
import asyncio
import io
import json
from pathlib import Path
import secrets
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import httpx
from PIL import Image
import trustme
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from backend.app import create_app
from backend.sessions import SessionManager


class TLSIntegrationTests(unittest.TestCase):
    def test_real_https_wss_pairing_isolation_upload_and_revocation(self):
        # Generated CA/keys are temporary and never printed or put in Git.
        with tempfile.TemporaryDirectory(prefix='canesight-cs029-tls-') as folder:
            ca = trustme.CA()
            cert = ca.issue_cert('127.0.0.1')
            key_path = str(Path(folder) / 'server.key')
            cert_path = str(Path(folder) / 'server.pem')
            cert.private_key_pem.write_to_path(key_path)
            cert.cert_chain_pems[0].write_to_path(cert_path)
            context = ssl.create_default_context()
            ca.configure_trust(context)
            manager = SessionManager(secrets.token_urlsafe(32))
            app = create_app(session_manager=manager)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen(128)
                port = listener.getsockname()[1]
                server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port,
                    ssl_keyfile=key_path, ssl_certfile=cert_path, log_config=None,
                    log_level='critical', access_log=False, ws_max_size=8192))
                thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
                thread.start()
                try:
                    deadline = time.monotonic() + 10
                    while not server.started:
                        if not thread.is_alive() or time.monotonic() >= deadline:
                            self.fail('TLS test server failed to start')
                        time.sleep(.02)
                    asyncio.run(self.exercise(port, context, manager))
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive(), 'TLS test server did not stop')

    async def exercise(self, port, context, manager):
        https = f'https://127.0.0.1:{port}'
        wss = f'wss://127.0.0.1:{port}'
        operator = {'Authorization': 'Bearer ' + manager._operator_token}
        async with httpx.AsyncClient(base_url=https, verify=context, trust_env=False, timeout=5) as client:
            self.assertEqual((await client.get('/healthz')).status_code, 200)
            self.assertEqual((await client.get('/readyz')).status_code, 503)
            body = {'mode': 'replay', 'phone': {'source_id': 'phone-1', 'boot_id': 'phone-boot-1'},
                    'pi': {'source_id': 'pi-camera-1', 'boot_id': 'pi-boot-1'}}
            self.assertEqual((await client.post('/v1/sessions', json=body)).status_code, 401)
            first = (await client.post('/v1/sessions', json=body, headers=operator)).json()
            second = (await client.post('/v1/sessions', json=body, headers=operator)).json()
            for token in (None, 'invalid-fixture-token-with-enough-length-0001'):
                headers = {} if token is None else {'Authorization': 'Bearer '+token}
                with self.assertRaises(InvalidStatus) as denied:
                    async with connect(wss+'/v1/events', ssl=context, additional_headers=headers,
                                       proxy=None, open_timeout=3):
                        pass
                self.assertEqual(denied.exception.response.status_code, 403)
            def auth(pair, role):
                return {'Authorization': 'Bearer '+pair[role]['token']}
            options = {'ssl': context, 'proxy': None, 'open_timeout': 3, 'close_timeout': 1}
            async with connect(wss+'/v1/events', additional_headers=auth(first, 'pi'), **options) as pi:
                async with connect(wss+'/v1/events', additional_headers=auth(second, 'pi'), **options) as other_pi:
                    async with connect(wss+'/v1/telemetry', additional_headers=auth(first, 'phone'), **options) as phone:
                        root = Path(__file__).resolve().parents[2]
                        depth = json.loads((root/'shared/protocol/v1/examples/depth.json').read_text())
                        depth['session_id'] = first['session_id']
                        await phone.send(json.dumps(depth))
                        self.assertEqual(json.loads(await asyncio.wait_for(pi.recv(), 2)), depth)
                        with self.assertRaises(TimeoutError):
                            await asyncio.wait_for(other_pi.recv(), .15)
                        image = io.BytesIO()
                        Image.new('RGB', (16, 16)).save(image, format='JPEG')
                        metadata = json.loads((root/'shared/protocol/v1/examples/frame.json').read_text())
                        metadata.update(session_id=first['session_id'], image={'width':16, 'height':16}, jpeg_bytes=len(image.getvalue()))
                        response = await client.post('/v1/frames', headers=auth(first, 'pi'),
                            files={'metadata': (None, json.dumps(metadata)),
                                   'image': ('generated.jpg', image.getvalue(), 'image/jpeg')})
                        self.assertEqual(response.status_code, 202)
                        self.assertEqual(response.json()['frame_id'], metadata['frame_id'])
                        self.assertEqual((await client.delete('/v1/sessions/'+first['session_id'], headers=operator)).status_code, 204)
                        await asyncio.wait_for(pi.wait_closed(), 2)
                        await asyncio.wait_for(phone.wait_closed(), 2)
                        self.assertEqual(pi.close_code, 1000)
                        self.assertEqual(phone.close_code, 1000)
            async with httpx.AsyncClient(base_url=https, trust_env=False, timeout=3) as untrusted:
                with self.assertRaises(httpx.ConnectError):
                    await untrusted.get('/healthz')


if __name__ == '__main__':
    unittest.main()
