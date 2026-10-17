"""Private issuer files never contain native credentials."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from backend.telemetry.viewer import issue, main

class ViewerFileTests(unittest.TestCase):
    def test_private_output_and_verified_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'viewer.json'
            response = MagicMock(status_code=201, headers={'cache-control':'no-store'})
            response.json.return_value = {'viewer_token':'synthetic-viewer-'+'v'*40,'expires_in_seconds':600}
            with patch('backend.telemetry.viewer.httpx.Client') as client, patch('backend.telemetry.viewer.operator_token',return_value='synthetic-operator'):
                client.return_value.__enter__.return_value.post.return_value=response
                issue('https://example.test',Path(folder)/'operator', 'session',output)
                client.assert_called_once_with(verify=True,trust_env=False,follow_redirects=False,timeout=5)
            data=json.loads(output.read_text())
            self.assertEqual(set(data),{'base_url','viewer_token','expires_in_seconds'})
            self.assertNotIn('synthetic-operator',output.read_text())
            with self.assertRaises(ValueError): issue('https://example.test',None,'session',output)

    def test_reject_checkout_and_plain_http_before_network(self):
        with patch('backend.telemetry.viewer.httpx.Client') as client:
            for base, output in [('http://example.test',Path('/tmp/viewer.json')),('https://example.test',Path(__file__).parent/'forbidden-viewer.json')]:
                with self.assertRaises(ValueError): issue(base,None,'session',output)
            client.assert_not_called()

    def test_cli_suppresses_secret_in_exception(self):
        with patch('sys.argv',['viewer','--base','https://example.test','--operator-file','private','--session-id','session','--out','private-output']), patch('backend.telemetry.viewer.issue',side_effect=ValueError('do-not-display-secret')):
            output=io.StringIO()
            with contextlib.redirect_stdout(output): self.assertEqual(main(),1)
            self.assertNotIn('do-not-display-secret',output.getvalue())

    def test_invalid_response_creates_no_file(self):
        with tempfile.TemporaryDirectory() as folder, patch('backend.telemetry.viewer.httpx.Client') as client, patch('backend.telemetry.viewer.operator_token',return_value='synthetic-operator'):
            output=Path(folder)/'viewer.json'
            response=MagicMock(status_code=201,headers={'cache-control':'no-store'})
            client.return_value.__enter__.return_value.post.return_value=response
            for data in [{'viewer_token':'v'*40,'expires_in_seconds':601},{'viewer_token':'v'*40,'expires_in_seconds':True},{'viewer_token':'v'*40,'expires_in_seconds':60,'operator_token':'forbidden'}]:
                response.json.return_value=data
                with self.assertRaises(ValueError): issue('https://example.test',None,'session',output)
                self.assertFalse(output.exists())
