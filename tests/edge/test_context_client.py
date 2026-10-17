"""Generated JPEGs, synthetic grants and an in-process HTTPS-scheme adapter.

Only process lifecycle tests spawn real children; no physical camera/cloud/GPIO.
"""
import io
import json
import multiprocessing
import ssl
import time
import unittest
import urllib.error

from fastapi.testclient import TestClient
from backend.app import create_app
from backend.context.server import install_context
from backend.context.service import ContextService
from backend.sessions import SessionManager
from edge.context_client import ContextError, ContextHTTP, ProcessRequest, unique_json
from edge.uploader import NoRedirect
from test_buttons import fixture_frame, reply


TOKEN = 'fixture-pi-token-only-never-deploy-00001'


def configuration(frame, token=TOKEN):
    return dict(base_url='https://testserver', token=token,
        **{k: frame.metadata[k] for k in ('session_id', 'source_id', 'boot_id', 'mode')})


class Response:
    def __init__(self, value, status=200):
        self.raw = json.dumps(value).encode()
        self.status = status
    def read(self, size): return self.raw[:size]
    def __enter__(self): return self
    def __exit__(self, *args): pass


class Opener:
    def __init__(self, value):
        self.value = value
        self.calls = []
        self.error = None
    def open(self, request, timeout):
        self.calls.append(request)
        if self.error: raise self.error
        return Response(self.value)


def sleeping_child(send, session, ca_file, request_id, frame):
    time.sleep(30)


def successful_child(send, session, ca_file, request_id, frame):
    send.send_bytes(json.dumps(reply(request_id, frame)).encode())
    send.close()


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.frame = fixture_frame()
        self.session = configuration(self.frame)
        self.request_id = 'fixture-request'

    def test_header_only_pi_credential_and_original_metadata(self):
        opener = Opener(reply(self.request_id, self.frame))
        client = ContextHTTP(self.session, opener=opener)
        value = client.send(self.request_id, self.frame, consent=True)
        self.assertEqual(value['frame'], self.frame.metadata)
        request = opener.calls[0]
        self.assertNotIn(TOKEN, request.full_url)
        self.assertNotIn(TOKEN.encode(), request.data)
        self.assertNotIn(TOKEN, repr(client))
        self.assertEqual(request.headers['Authorization'], 'Bearer '+TOKEN)
        self.assertIn(b'"consent":true', request.data)
        self.assertIn(self.frame.jpeg, request.data)

    def test_no_consent_or_changed_source_never_sends(self):
        opener = Opener(reply(self.request_id, self.frame))
        client = ContextHTTP(self.session, opener=opener)
        with self.assertRaises(ContextError): client.send(self.request_id, self.frame, consent=False)
        self.frame.metadata['boot_id'] = 'other-boot'
        with self.assertRaises(ContextError) as error: client.send(self.request_id, self.frame, consent=True)
        self.assertTrue(error.exception.fatal)
        self.assertEqual(opener.calls, [])

    def test_https_origin_and_certificate_verification_cannot_be_disabled(self):
        for url in ('http://example.com', 'https://user:pass@example.com',
                    'https://example.com/private', 'https://example.com?key=value',
                    'https://example.com/#fragment'):
            with self.assertRaises(ValueError): ContextHTTP(dict(self.session, base_url=url))
        client = ContextHTTP(self.session)
        handlers = [h for h in client.opener.handlers if hasattr(h, '_context')]
        self.assertEqual(len(handlers), 1)
        self.assertEqual(handlers[0]._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(handlers[0]._context.check_hostname)
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, None, None, 'https://other.invalid'))

    def test_foreign_prose_retiming_and_bad_schema_are_rejected(self):
        for mutate in (lambda v: v.update(request_id='other'),
                       lambda v: v['frame'].update(capture_monotonic_ms=2000),
                       lambda v: v['frame'].update(seq=True),
                       lambda v: v['description'].update(objects=['walk forward']),
                       lambda v: v['description'].update(uncertain=False),
                       lambda v: v.update(capture_age_bounded=True),
                       lambda v: v.update(extra='private text')):
            value = reply(self.request_id, self.frame)
            mutate(value)
            with self.assertRaises(ContextError):
                ContextHTTP(self.session, opener=Opener(value)).send(self.request_id, self.frame, consent=True)

    def test_failure_has_no_retry_or_raw_error_and_fatal_status_stops_session(self):
        for code in (302, 401, 403, 409, 429, 503):
            opener = Opener(None)
            opener.error = urllib.error.HTTPError('https://testserver', code,
                'private server failure', {}, io.BytesIO(b'private response'))
            with self.assertRaises(ContextError) as error:
                ContextHTTP(self.session, opener=opener).send(self.request_id, self.frame, consent=True)
            self.assertEqual(error.exception.fatal, code in (302, 401, 403, 409))
            self.assertEqual(len(opener.calls), 1)
            self.assertNotIn('private', str(error.exception))

    def test_duplicate_json_and_oversized_response_are_rejected(self):
        with self.assertRaises(ValueError): unique_json('{"request_id":1,"request_id":2}')
        with self.assertRaises(ValueError): unique_json('{"x":NaN}')
        value = reply(self.request_id, self.frame)
        value['model'] = 'x' * 17000
        with self.assertRaises(ContextError):
            ContextHTTP(self.session, opener=Opener(value)).send(self.request_id, self.frame, consent=True)

    def test_real_context_route_parses_multipart_with_session_and_role_binding(self):
        operator = 'fixture-operator-token-only-never-deploy-00001'
        manager = SessionManager(operator)
        calls = []
        async def runner(model, jpeg):
            if jpeg is None: return {'available': True}
            calls.append(jpeg)
            return {'objects': ['chair'], 'uncertain': True}
        app = install_context(create_app(session_manager=manager), ContextService('gemini-fixture', runner=runner))
        with TestClient(app, base_url='https://testserver') as backend:
            pair = backend.post('/v1/sessions', headers={'Authorization': 'Bearer '+operator},
                json={'mode': 'replay', 'phone': {'source_id': 'phone', 'boot_id': 'phone-boot'},
                      'pi': {'source_id': 'pi', 'boot_id': 'pi-boot'}}).json()
            frame = fixture_frame()
            frame.metadata.update(session_id=pair['session_id'], source_id='pi', boot_id='pi-boot')
            class InProcess:
                def open(self, request, timeout):
                    response = backend.post(request.full_url, headers=dict(request.header_items()), content=request.data)
                    if response.status_code >= 400:
                        raise urllib.error.HTTPError(request.full_url, response.status_code, '', {}, io.BytesIO())
                    return Response(response.json(), response.status_code)
            value = ContextHTTP(configuration(frame, pair['pi']['token']), opener=InProcess()).send(
                'route-fixture', frame, consent=True)
            self.assertEqual(value['frame'], frame.metadata)
            self.assertEqual(calls, [frame.jpeg])
            self.assertEqual(backend.get('/readyz').status_code, 503)
            with self.assertRaises(ContextError) as error:
                ContextHTTP(configuration(frame, pair['phone']['token']), opener=InProcess()).send(
                    'wrong-role', frame, consent=True)
            self.assertTrue(error.exception.fatal)

    def test_real_hung_child_is_killed_and_reaped_on_cancel(self):
        before = {p.pid for p in multiprocessing.active_children()}
        handle = ProcessRequest(self.session, None, self.request_id, self.frame, target=sleeping_child)
        self.addCleanup(handle.cancel)
        self.assertIsNone(handle.poll())
        start = time.monotonic()
        handle.cancel()
        self.assertLess(time.monotonic() - start, 1)
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)

    def test_spawned_reply_is_bounded_and_reaped_after_delivery(self):
        handle = ProcessRequest(self.session, None, self.request_id, self.frame, target=successful_child)
        self.addCleanup(handle.cancel)
        value = None
        deadline = time.monotonic() + 3
        while value is None and time.monotonic() < deadline:
            value = handle.poll()
            time.sleep(.01)
        self.assertEqual(value, reply(self.request_id, self.frame))


if __name__ == '__main__': unittest.main()
