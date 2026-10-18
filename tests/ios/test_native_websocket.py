"""macOS URLSession tests against temporary loopback TLS/TCP listeners.

No trust-store edits, device control, external server, images or real grants.
The generated certificate must fail OS verification before HTTP authentication.
"""
import os
from pathlib import Path
import shutil
import socketserver
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import trustme

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == 'darwin' and shutil.which('swift'),
                     'Requires macOS URLSession and Swift; no iPhone is used')
class NativeWebSocketTests(unittest.TestCase):
    def test_os_tls_rejection_and_cancellation_of_stalled_native_dial(self):
        requests = []
        accepted = threading.Event()
        stop = threading.Event()

        class HTTPHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(True)
                self.send_error(500)

            def log_message(self, *args):
                pass

        class StalledHandler(socketserver.BaseRequestHandler):
            def handle(self):
                accepted.set()
                stop.wait(10)

        with tempfile.TemporaryDirectory(prefix='canesight-native-tls-') as folder:
            ca = trustme.CA()
            cert = ca.issue_cert('127.0.0.1')
            key = Path(folder)/'server.key'
            chain = Path(folder)/'server.pem'
            cert.private_key_pem.write_to_path(key)
            cert.cert_chain_pems[0].write_to_path(chain)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(chain, key)
            with ThreadingHTTPServer(('127.0.0.1', 0), HTTPHandler) as tls, \
                    socketserver.ThreadingTCPServer(('127.0.0.1', 0), StalledHandler) as stalled:
                tls.socket = context.wrap_socket(tls.socket, server_side=True)
                threads = [threading.Thread(target=server.serve_forever, daemon=True)
                           for server in (tls, stalled)]
                for thread in threads:
                    thread.start()
                try:
                    env = dict(os.environ)
                    env['CANESIGHT_NATIVE_UNTRUSTED_ORIGIN'] = f'https://127.0.0.1:{tls.server_port}'
                    env['CANESIGHT_NATIVE_STALLED_ORIGIN'] = f'https://127.0.0.1:{stalled.server_address[1]}'
                    result = subprocess.run(['swift', 'test', '--package-path', str(ROOT/'ios/CaneSightTelemetry'),
                        '--jobs', '2', '-Xswiftc', '-strict-concurrency=complete',
                        '-Xswiftc', '-warnings-as-errors', '--filter', 'NativeWebSocketTests'],
                        env=env, text=True, capture_output=True, timeout=120)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('Executed 2 tests, with 0 failures', result.stdout)
                    self.assertNotIn('skipped', result.stdout.lower())
                    self.assertTrue(accepted.is_set(), 'Cancellation test must reach an actual TCP peer')
                    self.assertEqual(requests, [], 'Untrusted TLS must fail before an HTTP request')
                finally:
                    stop.set()
                    for server in (tls, stalled):
                        server.shutdown()
                    for thread in threads:
                        thread.join(timeout=5)
                        self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
