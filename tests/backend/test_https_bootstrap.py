"""Validate bootstrap inputs and exercise its actual health-only Caddy routes."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / 'backend/deploy'
spec = importlib.util.spec_from_file_location('bootstrap_check', DEPLOY / 'bootstrap_check.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapInputTests(unittest.TestCase):
    def test_public_address_and_immutable_image_only(self):
        image = 'caddy@sha256:' + 'a' * 64
        for address in ('64.177.50.116', 'api.canesight.example.org'):
            self.assertEqual(bootstrap.validate(address, image), [])
        for address in ('', '127.0.0.1', '10.0.0.1', '192.168.1.1', '169.254.169.254',
                        '0.0.0.0', '::1', 'localhost', 'demo.localhost', 'demo.test',
                        'https://api.example.org', 'example.org:443', 'example.org/path',
                        'example.org { respond 200 }', 'example.org\nadmin :2019'):
            self.assertTrue(bootstrap.validate(address, image), address)
        self.assertTrue(bootstrap.validate('api.example.org', 'caddy:latest'))


class HealthFixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        self.server.paths.append(self.path)
        self.send_response(200 if self.path == '/healthz' else 503)
        self.end_headers()
        self.wfile.write(b'{"status":"fixture-only"}')


@unittest.skipUnless(os.name == 'posix' and os.environ.get('CS_CADDY_TEST_IMAGE'),
                     'Opt-in Linux Docker bootstrap route integration')
class BootstrapProxyTests(unittest.TestCase):
    def test_actual_health_only_routes_and_tls(self):
        image = os.environ['CS_CADDY_TEST_IMAGE']
        self.assertEqual(bootstrap.validate('64.177.50.116', image), [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = ThreadingHTTPServer(('127.0.0.1', 0), HealthFixture)
            upstream.paths = []
            thread = threading.Thread(target=upstream.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(thread.join, 5)
            self.addCleanup(upstream.server_close)
            self.addCleanup(upstream.shutdown)
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1', 0))
                port = reserve.getsockname()[1]
            production = (DEPLOY / 'Caddyfile.bootstrap').read_text()
            issuer = ('tls {\n        issuer acme https://acme-v02.api.letsencrypt.org/directory {\n'
                      '            profile shortlived\n            disable_tlsalpn_challenge\n        }\n    }')
            self.assertEqual(production.count(issuer), 1)
            # Test only: internal CA and loopback. Keep production routes intact.
            config = production.replace(issuer, 'tls internal').replace(
                '{$CANESIGHT_ADDRESS} {', f'https://localhost:{port} {{\n    bind 127.0.0.1').replace(
                '{$CANESIGHT_ADDRESS}', 'localhost').replace(
                'admin off', 'admin off\n    auto_https disable_redirects').replace(
                'backend:8000', f'127.0.0.1:{upstream.server_port}')
            (root / 'Caddyfile').write_text(config)
            (root / 'data').mkdir()
            (root / 'config').mkdir()
            name = 'canesight-bootstrap-test-' + uuid.uuid4().hex[:10]
            result = subprocess.run(['docker', 'run', '--rm', '-d', '--name', name, '--network', 'host',
                                     '-v', f'{root / "Caddyfile"}:/etc/caddy/Caddyfile:ro',
                                     '-v', f'{root / "data"}:/data', '-v', f'{root / "config"}:/config', image],
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, 'Bootstrap test proxy failed; details suppressed.')
            try:
                cert = root / 'data/caddy/pki/authorities/local/root.crt'
                deadline = time.monotonic() + 20
                while not cert.exists() and time.monotonic() < deadline:
                    time.sleep(.1)
                self.assertTrue(cert.exists())
                context = ssl.create_default_context(cafile=str(cert))

                def status(method, path, headers=None):
                    connection = http.client.HTTPSConnection('localhost', port, context=context, timeout=3)
                    try:
                        connection.request(method, path, headers=headers or {})
                        response = connection.getresponse()
                        result = (response.status, response.getheader('Cache-Control'))
                        response.read(8192)
                        return result
                    finally:
                        connection.close()

                while True:
                    try:
                        self.assertEqual(status('GET', '/healthz'), (200, 'no-store'))
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(.1)
                self.assertEqual(status('GET', '/readyz'), (503, 'no-store'))
                count = len(upstream.paths)
                for method, path in (('POST', '/v1/sessions'), ('POST', '/v1/frames'),
                                     ('GET', '/v1/events'), ('GET', '/v1/telemetry'),
                                     ('HEAD', '/healthz'), ('GET', '/'), ('GET', '/admin')):
                    self.assertEqual(status(method, path), (503, 'no-store'))
                self.assertEqual(status('GET', '/v1/events', {'Connection': 'Upgrade', 'Upgrade': 'websocket'}),
                                 (503, 'no-store'))
                self.assertEqual(len(upstream.paths), count, 'API request reached private upstream')
            finally:
                subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20, check=True)
