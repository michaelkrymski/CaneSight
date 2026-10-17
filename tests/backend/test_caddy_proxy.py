"""Opt-in real Caddy test on Linux Docker hosts, using loopback and fixture data.

Set CS_CADDY_TEST_IMAGE to a reviewed pulled image digest to run this test.
No public ports, public certificates or real application credentials are used.
"""
import importlib.util
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location('deployment_fixtures', Path(__file__).with_name('test_deployment.py'))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


@unittest.skipUnless(os.name == 'posix' and os.environ.get('CS_CADDY_TEST_IMAGE'),
                     'Opt-in Linux Docker integration; requires CS_CADDY_TEST_IMAGE digest')
class CaddyProxyTests(unittest.TestCase):
    def test_real_https_wss_proxy_and_unavailable_readiness(self):
        image = os.environ['CS_CADDY_TEST_IMAGE']
        self.assertIn('@sha256:', image, 'Use an immutable pulled test image.')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = ThreadingHTTPServer(('127.0.0.1', 0), fixtures.Handler)
            upstream.daemon_threads = True
            upstream.ready, upstream.allow_anonymous, upstream.bad_upgrade = True, False, False
            thread = threading.Thread(target=upstream.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(thread.join, 5)
            self.addCleanup(upstream.server_close)
            self.addCleanup(upstream.shutdown)
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1', 0))
                port = reserve.getsockname()[1]
            config = root / 'Caddyfile'
            config.write_text(
                '{\n admin off\n auto_https disable_redirects\n}\n'
                f'https://localhost:{port} {{\n bind 127.0.0.1\n tls internal\n'
                f' reverse_proxy 127.0.0.1:{upstream.server_port}\n}}\n')
            data, runtime = root / 'data', root / 'config'
            data.mkdir()
            runtime.mkdir()
            name = 'canesight-cs033-test-' + uuid.uuid4().hex[:10]
            command = ['docker', 'run', '--rm', '-d', '--name', name, '--network', 'host',
                       '-v', f'{config}:/etc/caddy/Caddyfile:ro', '-v', f'{data}:/data',
                       '-v', f'{runtime}:/config', image]
            result = subprocess.run(command, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, 'Caddy fixture container did not start; details suppressed.')
            try:
                cert = data / 'caddy/pki/authorities/local/root.crt'
                deadline = time.monotonic() + 20
                while not cert.exists() and time.monotonic() < deadline:
                    time.sleep(0.1)
                self.assertTrue(cert.exists(), 'Caddy internal test CA did not initialize.')
                context = ssl.create_default_context(cafile=str(cert))
                base = f'https://localhost:{port}'
                # Wait for certificate provisioning/listen readiness, without hiding final failures.
                while True:
                    try:
                        fixtures.smoke.https_status('localhost', port, '/healthz', context)
                        break
                    except (OSError, fixtures.smoke.ProbeError):
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.1)
                fixtures.smoke.run(base, '/v1/events?session_id=fixture', 'fixture-token', context)
                upstream.ready = False
                with self.assertRaisesRegex(fixtures.smoke.ProbeError, '/readyz'):
                    fixtures.smoke.run(base, '/v1/events?session_id=fixture', 'fixture-token', context)
            finally:
                subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20, check=True)


if __name__ == '__main__':
    unittest.main()
