"""Generated TLS/provider fixtures; real Pi HTTP child, synthetic speech only."""
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
from backend.context.consumer import ContextNarration
from backend.context.server import install_context
from backend.context.service import ContextService
from backend.server import server_config
from backend.sessions import SessionManager
from edge.context_client import ContextClient
if __package__:
    from .test_consumer import generated_frame, Sink
else:
    from test_consumer import generated_frame, Sink


class PipelineTLSTests(unittest.TestCase):
    def test_full_provider_route_to_narration_then_hazard_preemption(self):
        operator = secrets.token_urlsafe(40)
        calls = []
        async def runner(model, jpeg):
            if jpeg is None: return {'available': True}
            calls.append(jpeg)
            return {'objects': ['chair'], 'uncertain': True}
        class SignalledSink(Sink):
            def __init__(self):
                super().__init__()
                self.spoke = threading.Event()
            def speak(self, text):
                super().speak(text)
                self.spoke.set()
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
            consumer = None
            try:
                deadline = time.monotonic() + 5
                while not server.started:
                    self.assertTrue(thread.is_alive())
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.01)
                with httpx.Client(base_url=base, verify=context, trust_env=False) as http:
                    response = http.post('/v1/sessions', headers={'Authorization': 'Bearer '+operator},
                        json=dict(mode='replay', pi=dict(source_id='pi', boot_id='pi-boot'),
                                  phone=dict(source_id='phone', boot_id='phone-boot')))
                    response.raise_for_status()
                    pair = response.json()
                clock = lambda: time.monotonic() * 1000
                session = dict(base_url=base, session_id=pair['session_id'], mode='replay',
                    **{k: pair['pi'][k] for k in ('source_id', 'boot_id', 'token')})
                frame = generated_frame(clock())
                frame.metadata.update(**{k: session[k] for k in ('session_id', 'source_id', 'boot_id', 'mode')})
                sink = SignalledSink()
                hazard = threading.Event()
                consumer = ContextNarration(lambda: frame,
                    ContextClient(session, ca_file=str(root/'ca.pem')), sink,
                    priority=lambda: (True, hazard.is_set()), consent=lambda: True, clock=clock)
                consumer.start()
                consumer.sample(False)
                time.sleep(.06)
                consumer.sample(True)
                self.assertTrue(sink.spoke.wait(5))
                self.assertEqual(sink.spoken, ['AI description, uncertain: Possible chair.'])
                self.assertEqual(calls, [frame.jpeg])
                sink.stopped.clear()
                hazard.set()
                self.assertTrue(sink.stopped.wait(.5))
                self.assertIsNone(sink.current)
                hazard.clear()
                consumer.tick()
                self.assertEqual(len(sink.spoken), 1)
            finally:
                if consumer: consumer.close()
                server.should_exit = True
                thread.join(5)
                self.assertFalse(thread.is_alive())
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)
