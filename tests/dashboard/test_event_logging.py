"""CS-042: synthetic admissions and fake/blocked DB, never public deployment."""
import contextlib
from dataclasses import asdict, replace
import io
import json
import multiprocessing
from pathlib import Path
import queue
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from backend.sessions import SessionRequest
from backend.telemetry.event_store import Event, PostgresStore, INSERT, DELETE, PURGE, private_config
from backend.telemetry.event_writer import EventWriter
from backend.telemetry.logging_app import LoggingManager, build_app

OPERATOR = 'synthetic-operator-only-' + 'o' * 40
ORIGIN = 'https://dashboard.example.test'


class MemoryWriter:
    def __init__(self):
        self.calls = []
        self.available = True

    def submit(self, event):
        self.calls.append(('event', event))
        return self.available

    def delete(self, identifier):
        self.calls.append(('delete', identifier))
        return self.available

    def deletion_status(self, identifier):
        from backend.telemetry.event_store import stream_id
        stream_id(identifier)
        return 'queued'


def pair(manager):
    return manager.create(SessionRequest.model_validate(dict(mode='replay', ttl_seconds=60,
        pi=dict(source_id='private-pi', boot_id='private-pi-boot'),
        phone=dict(source_id='private-phone', boot_id='private-phone-boot'))))


class LoggingTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.writer = MemoryWriter()
        self.manager = LoggingManager(OPERATOR, self.writer, clock=lambda: self.now,
                                      wall_clock=lambda: 1800000017)
        self.pair = pair(self.manager)
        self.session, self.phone = self.manager.authenticate('Bearer ' + self.pair['phone']['token'], 'phone')
        self.phone_socket = self.manager.attach(self.session, 'phone')
        self.pi_socket = self.manager.attach(self.session, 'pi')
        self.app = build_app(self.manager, ORIGIN)
        self.client = TestClient(self.app, base_url=ORIGIN)
        self.headers = {'Authorization': 'Bearer ' + OPERATOR}

    def depth(self, sequence):
        message = dict(schema_version=1, type='depth_observation', session_id=self.session.session_id,
            source_id='private-phone', boot_id='private-phone-boot', mode='replay', seq=sequence,
            capture_monotonic_ms=sequence * 100, capture_utc=None, tracking='normal',
            sectors={key: dict(distance_m=1.2, valid_fraction=.9) for key in ('left', 'center', 'right')})
        self.manager.relay(self.session, self.phone, self.phone_socket, message)
        self.assertEqual(self.pi_socket.queue.get_nowait(), message)

    def consent(self, action='enable'):
        return self.client.post('/v1/event-logging/consent',
            json=dict(session_id=self.session.session_id, action=action), headers=self.headers)

    def test_default_off_then_minimal_coarse_record_after_explicit_consent(self):
        self.depth(1)
        self.assertEqual(self.writer.calls, [])
        response = self.consent()
        self.assertEqual(response.status_code, 200)
        self.depth(2)
        kind, event = self.writer.calls[-1]
        self.assertEqual(kind, 'event')
        self.assertEqual(set(asdict(event)), {'event_id', 'stream_id', 'observed_minute', 'mode', 'role', 'kind'})
        self.assertEqual(event.observed_minute, 1800000000)
        self.assertEqual(event.mode, 'replay')
        self.assertEqual(event.kind, 'depth_admitted')
        self.assertEqual(event.stream_id, response.json()['stream_id'])
        self.assertNotIn(self.session.session_id, json.dumps(asdict(event)))
        self.assertNotIn('private-phone', json.dumps(asdict(event)))

    def test_sampling_caps_each_kind_and_rejected_replay_is_not_logged(self):
        self.consent()
        self.depth(1); self.depth(2)
        self.assertEqual(len(self.writer.calls), 1)
        self.now += 1
        self.depth(3)
        self.assertEqual(len(self.writer.calls), 2)
        with self.assertRaises(ValueError):
            self.depth(3)
        self.assertEqual(len(self.writer.calls), 2)

    def test_http_frame_and_offered_vision_log_no_pixels_lineage_or_model_payload(self):
        class Worker:
            value = None
            def submit(inner, grant, metadata, jpeg):
                inner.value = {key: value for key, value in metadata.items() if key != 'jpeg_bytes'}
                inner.value.update(type='vision_observation', model_version='private-model-label',
                    processing_ms=1, detections=[], signal=dict(candidate_count=0, symbol='unknown',
                                                              confidence=None, countdown_s=None))
            def discard_source(inner, grant): inner.value = None
            def take_result(inner, grant):
                value = inner.value; inner.value = None; return value
        self.manager.bind_inference_worker(Worker())
        self.consent()
        data = io.BytesIO(); Image.new('RGB', (8, 8), 'black').save(data, format='JPEG')
        jpeg = data.getvalue()
        metadata = dict(schema_version=1, type='frame_metadata', session_id=self.session.session_id,
            source_id='private-pi', boot_id='private-pi-boot', mode='replay', seq=1, frame_id='private-frame',
            capture_monotonic_ms=9000, capture_utc=None, image=dict(width=8, height=8), jpeg_bytes=len(jpeg))
        response = self.client.post('/v1/frames',
            headers={'Authorization': 'Bearer ' + self.pair['pi']['token']},
            data={'metadata': json.dumps(metadata)}, files={'image': ('frame.jpg', jpeg, 'image/jpeg')})
        self.assertEqual(response.status_code, 202)
        _, pi = self.manager.authenticate('Bearer ' + self.pair['pi']['token'], 'pi')
        self.assertEqual(self.manager.take_vision(self.session, pi, self.pi_socket)['frame_id'], 'private-frame')
        self.assertIsNone(self.manager.take_vision(self.session, pi, self.pi_socket))
        events = [asdict(event) for kind, event in self.writer.calls if kind == 'event']
        self.assertEqual([event['kind'] for event in events], ['frame_accepted', 'vision_offered'])
        self.assertNotIn('private-', json.dumps(events))
        self.assertNotIn('capture_monotonic_ms', json.dumps(events))
        viewer = self.manager.issue_viewer(self.session.session_id)['viewer_token']
        snapshot = self.manager.snapshot(viewer)
        self.assertNotIn('stream_id', json.dumps(snapshot))
        self.assertIsNone(snapshot['sources'][1]['capture_age_upper_ms'])

    def test_withdrawal_stops_new_events_even_when_delete_queue_is_full(self):
        self.consent(); self.depth(1)
        self.writer.available = False
        response = self.consent('disable')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['enabled'])
        self.assertEqual(response.json()['deletion_status'], 'retry_required')
        self.now += 1
        self.depth(2)
        self.assertEqual([kind for kind, _ in self.writer.calls], ['event', 'delete'])
        self.assertEqual(self.consent().status_code, 409)
        self.writer.available = True
        self.assertEqual(self.consent('disable').status_code, 202)

    def test_delete_before_event_and_expiry_cannot_reenable_old_consent(self):
        identifier = self.consent().json()['stream_id']
        result = self.client.post('/v1/event-logging/delete', json={'stream_id': identifier}, headers=self.headers)
        self.assertEqual(result.status_code, 202)
        self.depth(1)
        self.assertEqual(len(self.writer.calls), 1)
        self.now += 60
        self.manager.expire()
        self.assertEqual(self.manager.consent, {})
        new_pair = pair(self.manager)
        self.assertNotIn(new_pair['session_id'], self.manager.consent)
        # Historical deletion remains possible after the native session expires.
        self.assertEqual(self.client.post('/v1/event-logging/delete', json={'stream_id': identifier},
                                         headers=self.headers).status_code, 202)

    def test_operator_only_https_closed_body_and_no_browser_origin_or_query(self):
        body = dict(session_id=self.session.session_id, action='enable')
        for token in ('', self.pair['phone']['token'], self.pair['pi']['token']):
            self.assertEqual(self.client.post('/v1/event-logging/consent', json=body,
                headers={'Authorization': 'Bearer ' + token}).status_code, 401)
        for path in ('consent', 'delete', 'deletion-status'):
            self.assertEqual(self.client.post('/v1/event-logging/' + path, json=body,
                headers={**self.headers, 'Origin': ORIGIN}).status_code, 403)
            self.assertEqual(self.client.post('/v1/event-logging/' + path + '?x=y', json=body,
                headers=self.headers).status_code, 403)
        for content in ('{"session_id":"x","action":"enable","extra":"x"}',
                        '{"session_id":"x","action":"enable","action":"disable"}'):
            self.assertEqual(self.client.post('/v1/event-logging/consent', content=content,
                headers={**self.headers, 'Content-Type': 'application/json'}).status_code, 400)
        self.assertEqual(self.consent('automatic').status_code, 422)
        response = self.consent()
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertNotIn('access-control-allow-origin', response.headers)
        with TestClient(self.app, base_url='http://dashboard.example.test') as insecure:
            self.assertEqual(insecure.post('/v1/event-logging/consent', json=body, headers=self.headers).status_code, 403)

    def test_consent_is_session_specific_and_revoke_drops_in_memory_binding(self):
        self.consent()
        other = pair(self.manager)
        session, phone = self.manager.authenticate('Bearer ' + other['phone']['token'], 'phone')
        socket = self.manager.attach(session, 'phone')
        self.manager.relay(session, phone, socket, dict(schema_version=1, type='heartbeat',
            state='degraded', mode='replay', session_id=session.session_id,
            source_id='private-phone', boot_id='private-phone-boot', seq=1,
            capture_monotonic_ms=100, capture_utc=None))
        self.assertEqual(self.writer.calls, [])
        self.manager.revoke(self.session.session_id)
        self.assertEqual(self.manager.consent, {})

    def test_viewer_cannot_grant_consent_and_invalid_stream_is_rejected(self):
        viewer = self.manager.issue_viewer(self.session.session_id)['viewer_token']
        self.assertEqual(self.client.post('/v1/event-logging/consent', json={
            'session_id': self.session.session_id, 'action': 'enable'},
            headers={'Authorization': 'Bearer ' + viewer}).status_code, 401)
        for path in ('delete', 'deletion-status'):
            self.assertEqual(self.client.post('/v1/event-logging/' + path,
                json={'stream_id': "x';DROP TABLE events;--"}, headers=self.headers).status_code, 422)

    def test_writer_exception_cannot_break_native_admission_or_health(self):
        self.consent()
        with patch.object(self.writer, 'submit', side_effect=RuntimeError('private DB failure')):
            self.depth(1)
        self.assertEqual(self.client.get('/healthz').status_code, 200)
        self.assertIsNone(self.manager.projections[self.session.session_id]['sources']['phone']['model_version'])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        ca = Path(self.directory.name) / 'ca.pem'; ca.write_text('synthetic-test-ca', encoding='utf-8')
        self.config = Path(self.directory.name) / 'private.json'
        self.config.write_text(json.dumps(dict(host='db.example.test', port=5432, dbname='events',
            user='events-writer', password='synthetic-secret', sslrootcert=str(ca))), encoding='utf-8')
        self.config.chmod(0o600)
        self.event = Event(str(uuid.uuid4()), str(uuid.uuid4()), 1800000000, 'replay', 'phone', 'depth_admitted')

    def test_verified_tls_timeouts_and_parameterized_insert_delete_and_retention(self):
        calls = []
        class Connection:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def execute(self, query, params): calls.append((query, params))
        def connect(**config):
            self.assertEqual(config['sslmode'], 'verify-full')
            self.assertEqual(config['connect_timeout'], 3)
            self.assertIn('statement_timeout=2000', config['options'])
            self.assertTrue(config['autocommit'])
            return Connection()
        store = PostgresStore(self.config, connect=connect)
        store.insert(self.event); store.delete(self.event.stream_id); store.purge()
        self.assertEqual(calls[0], (INSERT, self.event.values()))
        self.assertEqual(calls[1], (DELETE, (self.event.stream_id,)))
        self.assertEqual(calls[2], (PURGE, None))
        self.assertNotIn(self.event.stream_id, calls[0][0])
        self.assertEqual((calls[0][1][6] - calls[0][1][2]).total_seconds(), 86400)
        self.assertIn('CURRENT_TIMESTAMP', calls[0][0])

    def test_rejects_arbitrary_payloads_dsn_overrides_and_unrounded_times(self):
        for change in (dict(observed_minute=1800000001), dict(mode='unknown'),
                       dict(kind='latitude=40.123'), dict(role='operator'), dict(stream_id='private-session')):
            with self.assertRaises(ValueError): replace(self.event, **change).values()
        config = json.loads(self.config.read_text(encoding='utf-8'))
        for change in (dict(sslmode='disable'), dict(options='anything'), dict(host='host1,host2'),
                       dict(port=True), dict(sslrootcert='relative-ca.pem')):
            self.config.write_text(json.dumps({**config, **change}), encoding='utf-8')
            with self.assertRaises(ValueError): private_config(self.config)

    def test_administration_suppresses_private_connection_exception(self):
        from backend.telemetry import event_store
        with patch('sys.argv', ['events', '--config-file', str(self.config), 'purge']), \
                patch.object(PostgresStore, 'execute', side_effect=RuntimeError('SECRET-MUST-NOT-PRINT')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(event_store.main(), 1)
            self.assertNotIn('SECRET-MUST-NOT-PRINT', output.getvalue())

    def test_operator_helper_requires_consent_uses_verified_https_and_private_receipt(self):
        from backend.telemetry import event_control
        import httpx
        receipt = Path(self.directory.name) / 'receipt.json'
        identifier = str(uuid.uuid4())
        calls = []
        class Client:
            def __init__(inner, **kwargs):
                self.assertEqual(kwargs, dict(verify=True, trust_env=False, follow_redirects=False, timeout=5))
            def __enter__(inner): return inner
            def __exit__(inner, *_): pass
            def post(inner, url, **kwargs):
                calls.append((url, kwargs))
                return httpx.Response(200, headers={'Cache-Control': 'no-store'},
                    json={'enabled': True, 'stream_id': identifier, 'deletion_status': 'not_requested'})
        with patch.object(event_control.httpx, 'Client', Client), \
                patch.object(event_control, 'operator_token', return_value=OPERATOR):
            with self.assertRaises(ValueError):
                event_control.control(ORIGIN, self.config, 'enable', receipt, session_id='session')
            self.assertFalse(receipt.exists())
            state = event_control.control(ORIGIN, self.config, 'enable', receipt,
                                          session_id='session', consent_acknowledged=True)
            self.assertEqual(state, 'consent_enabled_storage_unverified')
            self.assertEqual(json.loads(receipt.read_text(encoding='utf-8')), {'stream_id': identifier})
            self.assertEqual(calls[0][1]['headers']['Authorization'], 'Bearer ' + OPERATOR)
            with self.assertRaises(FileExistsError):
                event_control.control(ORIGIN, self.config, 'enable', receipt,
                                      session_id='session', consent_acknowledged=True)
        self.assertEqual(len(calls), 1)

    def test_operator_helper_suppresses_exception_and_denies_plain_http(self):
        from backend.telemetry import event_control
        with self.assertRaises(ValueError):
            event_control.control('http://insecure.example.test', 'private.env', 'enable',
                Path(self.directory.name) / 'receipt.json', session_id='session', consent_acknowledged=True)
        with patch('sys.argv', ['control', 'status', '--base', ORIGIN, '--operator-file', 'private.env',
                               '--receipt-file', 'private.json']), \
                patch.object(event_control, 'control', side_effect=RuntimeError('SECRET-MUST-NOT-PRINT')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(event_control.main(), 1)
            self.assertNotIn('SECRET-MUST-NOT-PRINT', output.getvalue())


class BlockingFactory:
    """Spawn-picklable fake DB that blocks inside insert until killed."""
    def __init__(self, entered): self.entered = entered
    def __call__(self): return self
    def purge(self): pass
    def insert(self, event):
        self.entered.set()
        time.sleep(60)
    def delete(self, identifier): pass


class RecordingFactory:
    def __init__(self, output): self.output = output
    def __call__(self): return self
    def purge(self): pass
    def insert(self, event): self.output.put(('event', event.stream_id))
    def delete(self, identifier): self.output.put(('delete', identifier))


class FailingFactory:
    def __call__(self): return self
    def purge(self): raise RuntimeError('PRIVATE-CONNECTION-DETAILS')
    def insert(self, event): raise RuntimeError('PRIVATE-CONNECTION-DETAILS')
    def delete(self, identifier): raise RuntimeError('PRIVATE-CONNECTION-DETAILS')


class ProcessTests(unittest.TestCase):
    def event(self, identifier=None):
        return Event(str(uuid.uuid4()), identifier or str(uuid.uuid4()), 1800000000,
                     'replay', 'phone', 'depth_admitted')

    def test_hung_database_queue_is_bounded_native_path_responds_and_close_kills_worker(self):
        context = multiprocessing.get_context('spawn')
        entered = context.Event()
        writer = EventWriter(factory=BlockingFactory(entered), capacity=2)
        self.addCleanup(writer.close)
        writer.start(); self.assertTrue(writer.submit(self.event()))
        self.assertTrue(entered.wait(10), 'Fake DB did not reach the blocking insert')
        manager = LoggingManager(OPERATOR, writer)
        pairing = pair(manager)
        manager.set_consent(pairing['session_id'], 'enable')
        session, phone = manager.authenticate('Bearer ' + pairing['phone']['token'], 'phone')
        socket = manager.attach(session, 'phone')
        message = dict(schema_version=1, type='heartbeat', state='degraded', mode='replay',
            session_id=session.session_id, source_id='private-phone', boot_id='private-phone-boot',
            seq=1, capture_monotonic_ms=100, capture_utc=None)
        started = time.monotonic()
        manager.relay(session, phone, socket, message)
        for _ in range(1000): writer.submit(self.event())
        with TestClient(build_app(manager, ORIGIN), base_url=ORIGIN) as client:
            self.assertEqual(client.get('/healthz').status_code, 200)
        self.assertLess(time.monotonic() - started, 2)
        self.assertGreater(writer.dropped, 990)
        started = time.monotonic(); writer.close()
        self.assertLess(time.monotonic() - started, 3)
        self.assertFalse(writer.process.is_alive())
        self.assertFalse(writer.submit(self.event()))

    def test_fifo_delete_acknowledged_only_after_store_completion(self):
        context = multiprocessing.get_context('spawn')
        output = context.Queue()
        writer = EventWriter(factory=RecordingFactory(output))
        self.addCleanup(writer.close)
        writer.start()
        event = self.event()
        self.assertTrue(writer.submit(event))
        self.assertTrue(writer.delete(event.stream_id))
        self.assertEqual(output.get(timeout=10), ('event', event.stream_id))
        self.assertEqual(output.get(timeout=10), ('delete', event.stream_id))
        deadline = time.monotonic() + 5
        status = 'queued'
        while time.monotonic() < deadline and status != 'deleted':
            status = writer.deletion_status(event.stream_id)
            time.sleep(.01)
        self.assertEqual(status, 'deleted')
        output.cancel_join_thread(); output.close()

    def test_stale_delete_receipt_cannot_confirm_a_new_attempt(self):
        writer = EventWriter()
        self.addCleanup(writer.close)
        identifier = str(uuid.uuid4())
        writer.attempts[identifier] = 'new-attempt'
        writer._receipt(identifier, 'queued')
        # A synchronous stand-in isolates receipt ordering without feeder timing.
        original = writer.results
        writer.results = queue.Queue()
        writer.results.put((identifier, 'old-attempt', 'deleted'))
        self.assertEqual(writer.deletion_status(identifier), 'queued')
        writer.results = original

    def test_database_failure_reports_failed_deletion_without_private_exception(self):
        writer = EventWriter(factory=FailingFactory())
        self.addCleanup(writer.close)
        writer.start()
        identifier = str(uuid.uuid4())
        self.assertTrue(writer.submit(self.event(identifier)))
        self.assertTrue(writer.delete(identifier))
        deadline = time.monotonic() + 10
        status = 'queued'
        while time.monotonic() < deadline and status == 'queued':
            status = writer.deletion_status(identifier)
            time.sleep(.01)
        self.assertEqual(status, 'failed')
        self.assertNotIn('PRIVATE', repr(writer.receipts))


if __name__ == '__main__':
    unittest.main()
