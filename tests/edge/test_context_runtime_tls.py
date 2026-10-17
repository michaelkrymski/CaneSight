"""Manual input -> real spawned HTTPS client -> local service, fake provider."""
import multiprocessing
from pathlib import Path
import secrets
import socket
import ssl
import tempfile
import threading
import time
import unittest

import httpx
import trustme
import uvicorn

from backend.app import create_app
from backend.context.server import install_context
from backend.context.service import ContextService
from backend.server import server_config
from backend.sessions import SessionManager
from edge.context_runtime import ManualContext
from test_buttons import fixture_frame
from test_context_runtime import Stream


class ManualTLSTests(unittest.TestCase):
    def test_manual_request_delivers_original_generated_image_over_verified_tls(self):
        operator = secrets.token_urlsafe(40)
        calls, messages = [], []
        delivered = threading.Event()
        async def runner(model, jpeg):
            if jpeg is None:
                return {'available': True}
            calls.append(jpeg)
            return {'objects': ['chair'], 'uncertain': True}
        def emit(message):
            messages.append(message)
            delivered.set()
        before = {p.pid for p in multiprocessing.active_children()}
        with tempfile.TemporaryDirectory() as directory, socket.socket() as listener:
            root = Path(directory)
            ca = trustme.CA()
            cert = ca.issue_cert('127.0.0.1')
            cert.private_key_pem.write_to_path(root/'key.pem')
            cert.cert_chain_pems[0].write_to_path(root/'cert.pem')
            ca.cert_pem.write_to_path(root/'ca.pem')
            context = ssl.create_default_context()
            ca.configure_trust(context)
            listener.bind(('127.0.0.1', 0))
            listener.listen(128)
            base = 'https://127.0.0.1:' + str(listener.getsockname()[1])
            app = install_context(create_app(session_manager=SessionManager(operator)),
                                  ContextService('gemini-fixture', runner=runner))
            server = uvicorn.Server(server_config(app, ssl_keyfile=str(root/'key.pem'),
                                                   ssl_certfile=str(root/'cert.pem')))
            thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
            thread.start()
            runtime = None
            stream = Stream()
            try:
                deadline = time.monotonic() + 5
                while not server.started:
                    self.assertTrue(thread.is_alive())
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.01)
                with httpx.Client(base_url=base, verify=context, trust_env=False) as client:
                    response = client.post('/v1/sessions', headers={'Authorization': 'Bearer '+operator},
                        json=dict(mode='replay', pi=dict(source_id='pi', boot_id='pi-boot'),
                                  phone=dict(source_id='phone', boot_id='phone-boot')))
                    response.raise_for_status()
                    pair = response.json()
                clock = lambda: time.monotonic() * 1000
                session = dict(base_url=base, session_id=pair['session_id'], mode='replay',
                               **{k: pair['pi'][k] for k in ('source_id', 'boot_id', 'token')})
                frame = fixture_frame(clock())
                frame.metadata.update(**{k: session[k] for k in ('session_id', 'source_id', 'boot_id', 'mode')})
                runtime = ManualContext(session, lambda: (True, False), consent=True,
                    ca_file=str(root/'ca.pem'), clock=clock, emit=emit)
                runtime.set_camera_ready(True)
                runtime.offer(frame)
                runtime.start(stream)
                self.assertTrue(stream.wait_reads(1))
                time.sleep(.1)  # Observe the initial stable released level.
                stream.queue.put('press\n')
                self.assertTrue(delivered.wait(5), runtime.snapshot())
                self.assertEqual(messages, ['Context (manual input; AI; uncertain): possible chair.'])
                self.assertEqual(calls, [frame.jpeg])
            finally:
                if runtime:
                    runtime.close()
                stream.queue.put('')
                server.should_exit = True
                thread.join(5)
                self.assertFalse(thread.is_alive())
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)
