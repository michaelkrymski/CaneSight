"""Real HTTP checks for the loopback fixture preview, not a production API."""
import http.client
from html.parser import HTMLParser
import threading
import unittest

from backend.telemetry.dashboard import create_server


class FixtureServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, method, path, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_only_loopback_listener_and_allowlisted_assets_with_private_headers(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        for path in ('/', '/app.js', '/model.js', '/style.css', '/icon.svg'):
            status, headers, body = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertTrue(body)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertIn("connect-src 'none'", headers['Content-Security-Policy'])
            self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
            self.assertEqual(headers['Referrer-Policy'], 'no-referrer')
            self.assertNotIn('Access-Control-Allow-Origin', headers)
            self.assertNotIn('Set-Cookie', headers)

    def test_repository_files_and_traversal_are_not_served(self):
        for path in ('/.env', '/secrets/backend.env', '/../AGENTS.md', '/%2e%2e/AGENTS.md', '/backend/app.py'):
            status, _, body = self.request('GET', path)
            self.assertEqual(status, 404)
            self.assertEqual(body, b'')

    def test_no_mutation_api_and_no_query_credential_transport(self):
        for method in ('POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'):
            self.assertEqual(self.request(method, '/v1/sessions')[0], 405)
        self.assertEqual(self.request('GET', '/?token=synthetic-only')[0], 400)
        self.assertEqual(self.request('GET', '/v1/events')[0], 404)
        self.assertEqual(self.request('GET', '/', {'Host': 'untrusted.example'})[0], 403)

    def test_head_and_explicit_fixture_limitation_are_present(self):
        status, headers, body = self.request('HEAD', '/')
        self.assertEqual(status, 200)
        self.assertGreater(int(headers['Content-Length']), 0)
        self.assertEqual(body, b'')
        html = self.request('GET', '/')[2].decode('utf-8')
        self.assertIn('Research prototype — no crossing permission.', html)
        self.assertIn('No live devices or backend connected', html)
        self.assertIn('Live adapter requires reviewed activation', html)
        self.assertNotIn('CANESIGHT_OPERATOR_TOKEN', html)

    def test_without_javascript_object_evidence_starts_hidden(self):
        class PreviewParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.elements = {}

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get('id') in ('preview-boxes', 'preview-unavailable'):
                    self.elements[attrs['id']] = attrs

        parser = PreviewParser()
        parser.feed(self.request('GET', '/')[2].decode('utf-8'))
        self.assertEqual(parser.elements['preview-boxes'].get('visibility'), 'hidden')
        self.assertNotEqual(parser.elements['preview-unavailable'].get('visibility'), 'hidden')


if __name__ == '__main__':
    unittest.main()
