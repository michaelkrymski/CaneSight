"""Deployment tests use synthetic credentials and a temporary local TLS server."""
import base64
import contextlib
import hashlib
import http.server
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
original_connect = socket.create_connection


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'backend' / 'deploy' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = load('check_config')
smoke = load('smoke')
readiness = load('readiness')


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.shell = patch.dict(os.environ, {}, clear=True)
        self.shell.start()
        self.addCleanup(self.shell.stop)
        self.values = {'CANESIGHT_DOMAIN': 'demo.example.org',
                       'BACKEND_IMAGE': 'registry.example.org/canesight@sha256:' + 'a' * 64,
                       'CADDY_IMAGE': 'caddy@sha256:' + 'b' * 64}
        (self.root / 'secrets').mkdir()
        self.secret = self.root / 'secrets' / 'backend.env'
        self.secret.write_text('FIXTURE_ONLY=synthetic\n')
        self.secret.chmod(0o600)

    def write_config(self):
        (self.root / '.env').write_text(''.join(f'{k}={v}\n' for k, v in self.values.items()))

    def test_requires_inputs_and_real_configuration(self):
        self.assertTrue(config.validate(self.root))
        self.write_config()
        self.assertEqual(config.validate(self.root), [])
        self.secret.write_text('# comments only\n')
        self.assertTrue(config.validate(self.root))

    def test_rejects_mutable_images_and_domain_injection(self):
        self.values['BACKEND_IMAGE'] = 'canesight:latest'
        self.values['CANESIGHT_DOMAIN'] = 'demo.example.org { respond 200 }'
        self.write_config()
        errors = config.validate(self.root)
        self.assertEqual(len(errors), 2)
        self.assertNotIn(self.values['CANESIGHT_DOMAIN'], '\n'.join(errors))

    def test_shell_override_cannot_bypass_validation(self):
        self.write_config()
        with patch.dict(os.environ, {'CADDY_IMAGE': 'caddy:latest'}):
            self.assertTrue(config.validate(self.root))

    @unittest.skipIf(os.name == 'nt', 'POSIX mode enforcement is Linux-specific')
    def test_rejects_world_readable_secret(self):
        self.write_config()
        self.secret.chmod(0o644)
        self.assertTrue(config.validate(self.root))

    def test_readiness_connection_failure_is_unavailable(self):
        with patch.object(readiness.http.client, 'HTTPConnection') as cls:
            cls.return_value.request.side_effect = OSError('synthetic failure')
            self.assertFalse(readiness.ready())
            cls.return_value.close.assert_called_once()

    def test_readiness_does_not_accept_liveness_or_redirects(self):
        with patch.object(readiness.http.client, 'HTTPConnection') as cls:
            for status in (200, 302, 503):
                cls.return_value.getresponse.return_value.status = status
                self.assertEqual(readiness.ready(), status == 200)
            cls.return_value.request.assert_called_with('GET', '/readyz')


@unittest.skipUnless(shutil.which('docker'), 'Docker CLI required for Compose configuration validation')
class ComposeTests(unittest.TestCase):
    def test_private_backend_and_raw_secret_configuration(self):
        if subprocess.run(['docker', 'compose', 'version'], capture_output=True).returncode:
            self.skipTest('Docker Compose plugin unavailable')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copy(ROOT / 'backend/deploy/compose.yaml', root / 'compose.yaml')
            (root / 'secrets').mkdir()
            (root / 'secrets/backend.env').write_text('FIXTURE_ONLY=dollar$sign\n')
            env = dict(os.environ, CANESIGHT_DOMAIN='demo.example.org',
                       BACKEND_IMAGE='example/backend@sha256:' + 'a' * 64,
                       CADDY_IMAGE='caddy@sha256:' + 'b' * 64)
            result = subprocess.run(['docker', 'compose', '-f', str(root / 'compose.yaml'),
                                     'config', '--format', 'json'], env=env, capture_output=True,
                                    text=True, timeout=30)
            self.assertEqual(result.returncode, 0, 'Compose configuration validation failed (details suppressed).')
            services = json.loads(result.stdout)['services']
            backend, proxy = services['backend'], services['proxy']
            self.assertFalse(backend.get('ports'))
            # Compose may escape dollars for round-trippable config output.
            self.assertIn(backend['environment']['FIXTURE_ONLY'], ('dollar$sign', 'dollar$$sign'))
            self.assertNotIn('FIXTURE_ONLY', proxy['environment'])
            self.assertEqual({port['target'] for port in proxy['ports']}, {80, 443})
            self.assertEqual(proxy['depends_on']['backend']['condition'], 'service_healthy')
            self.assertTrue(backend['read_only'])
            self.assertEqual(backend['user'], '10001:10001')


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path in ('/healthz', '/readyz'):
            self.send_response(503 if self.path == '/readyz' and not self.server.ready else 200)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        authorized = self.headers.get('Authorization') == 'Bearer fixture-token'
        if not authorized and not self.server.allow_anonymous:
            self.send_response(401)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        key = self.headers.get('Sec-WebSocket-Key', '')
        accept = base64.b64encode(hashlib.sha1(
            (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('ascii')).digest()).decode('ascii')
        self.send_response(101)
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', 'invalid' if self.server.bad_upgrade else accept)
        self.end_headers()
        self.close_connection = True


@unittest.skipUnless(shutil.which('openssl'), 'OpenSSL executable required for temporary TLS fixture')
class TLSProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        folder = Path(cls.temporary.name)
        cls.certificate = folder / 'cert.pem'
        key = folder / 'key.pem'
        openssl_config = folder / 'openssl.cnf'
        openssl_config.write_text('[req]\ndistinguished_name=dn\n[dn]\n')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-config', str(openssl_config),
                        '-keyout', str(key), '-out', str(cls.certificate), '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                       check=True, capture_output=True, timeout=30)
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.daemon_threads = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cls.certificate, key)
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.thread.join, 5)
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)

    def setUp(self):
        self.server.ready = True
        self.server.allow_anonymous = False
        self.server.bad_upgrade = False
        self.context = ssl.create_default_context(cafile=str(self.certificate))
        self.base = f'https://127.0.0.1:{self.server.server_port}'

    def probe(self, **kwargs):
        smoke.run(self.base, '/v1/events?session_id=fixture', 'fixture-token', **kwargs)

    def test_https_and_authenticated_wss_with_rejected_anonymous_and_invalid_token(self):
        self.probe(context=self.context)

    def test_healthy_process_does_not_hide_unready_worker(self):
        self.server.ready = False
        with self.assertRaisesRegex(smoke.ProbeError, '/readyz'):
            self.probe(context=self.context)

    def test_fails_if_anonymous_websocket_is_allowed(self):
        self.server.allow_anonymous = True
        with self.assertRaisesRegex(smoke.ProbeError, 'not rejected'):
            self.probe(context=self.context)

    def test_bad_websocket_accept_is_rejected(self):
        self.server.bad_upgrade = True
        with self.assertRaisesRegex(smoke.ProbeError, 'Invalid WebSocket'):
            self.probe(context=self.context)

    def test_untrusted_certificate_is_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.probe()

    def test_hostname_mismatch_is_rejected(self):
        with patch.object(smoke, 'target', return_value=('wrong-host.invalid', self.server.server_port)), \
                patch.object(smoke.socket, 'create_connection',
                             side_effect=lambda *_args, **_kwargs: original_connect(('127.0.0.1', self.server.server_port), timeout=5)):
            with self.assertRaises(ssl.SSLCertVerificationError):
                self.probe(context=self.context)

    def test_disabled_verification_is_rejected(self):
        with self.assertRaisesRegex(smoke.ProbeError, 'verification'):
            self.probe(context=ssl._create_unverified_context())

    def test_cli_failure_suppresses_token_and_url(self):
        output = io.StringIO()
        with patch.dict(os.environ, {'CS_SMOKE_TOKEN': 'private-synthetic-value',
                                     'CS_SMOKE_BASE_URL': 'https://private.invalid'}), \
                contextlib.redirect_stdout(output), patch.object(smoke, 'run', side_effect=OSError('private-synthetic-value')):
            self.assertEqual(smoke.main(), 1)
        self.assertNotIn('private-synthetic-value', output.getvalue())
        self.assertNotIn('private.invalid', output.getvalue())

    def test_rejects_cleartext_and_header_injection(self):
        for base, path, token in [('http://localhost', '/v1/events', 'fixture'),
                                  (self.base, '/v1/events\r\nInjected: header', 'fixture'),
                                  (self.base, '/v1/events', 'fixture\r\nInjected: header')]:
            with self.assertRaises(smoke.ProbeError):
                smoke.run(base, path, token, context=self.context)


if __name__ == '__main__':
    unittest.main()
