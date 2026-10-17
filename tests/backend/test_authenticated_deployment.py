"""Deployment acceptance probe against a certificate-verified real session app."""
import asyncio
import os
from pathlib import Path
import secrets
import socket
import ssl
import tempfile
import threading
import time
import unittest

import trustme
import uvicorn
from backend.app import create_app
from backend.server import server_config
from backend.sessions import SessionManager
from backend.deploy.session_probe import operator_token, run
from backend.deploy.smoke import ProbeError


class AuthenticatedDeploymentTests(unittest.TestCase):
    def test_private_operator_input_rejects_missing_duplicate_invalid_or_public_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backend.env'
            for text in ('OTHER=fixture', 'CANESIGHT_OPERATOR_TOKEN=short',
                         'CANESIGHT_OPERATOR_TOKEN=' + 'x' * 40 + '\nCANESIGHT_OPERATOR_TOKEN=' + 'y' * 40):
                path.write_text(text)
                path.chmod(0o600)
                with self.assertRaises(ProbeError):
                    operator_token(path)
            path.write_text('CANESIGHT_OPERATOR_TOKEN=' + secrets.token_urlsafe(40))
            path.chmod(0o600)
            self.assertTrue(operator_token(path))
            if os.name != 'nt':
                path.chmod(0o644)
                with self.assertRaises(ProbeError):
                    operator_token(path)

    def test_full_https_wss_upload_expiry_and_disconnect_probe_keeps_model_unready(self):
        with tempfile.TemporaryDirectory(prefix='canesight-deploy-probe-') as directory:
            root = Path(directory)
            ca = trustme.CA()
            cert = ca.issue_cert('127.0.0.1')
            cert.private_key_pem.write_to_path(root / 'server.key')
            cert.cert_chain_pems[0].write_to_path(root / 'server.pem')
            context = ssl.create_default_context()
            ca.configure_trust(context)
            token = secrets.token_urlsafe(40)
            manager = SessionManager(token)
            app = create_app(session_manager=manager)
            @app.middleware('http')
            async def proxy_cache_header(request, call_next):
                response = await call_next(request)
                if response.headers.get('cache-control') == 'no-store':
                    # A proxy and backend may both emit this valid directive.
                    response.headers['cache-control'] = 'no-store, no-store'
                return response
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen(128)
                port = listener.getsockname()[1]
                config = server_config(app, port=port, ssl_keyfile=str(root / 'server.key'),
                                       ssl_certfile=str(root / 'server.pem'))
                server = uvicorn.Server(config)
                thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
                thread.start()
                try:
                    deadline = time.monotonic() + 10
                    while not server.started:
                        if not thread.is_alive() or time.monotonic() >= deadline:
                            self.fail('Probe TLS server did not start')
                        time.sleep(.01)
                    result = asyncio.run(run(f'https://127.0.0.1:{port}', token, context=context))
                    self.assertTrue(result['verified_https_wss'])
                    self.assertTrue(result['matching_frame_ack'])
                    self.assertTrue(result['expired_credential_rejected'])
                    self.assertTrue(result['disconnect_invalidated_peer'])
                    self.assertFalse(result['ready'])
                    self.assertFalse(result['readiness_checks']['model_available'])
                    self.assertEqual(manager.sessions, {})
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive())
