"""Real spawned-process worker tests with explicitly synthetic model adapters."""
import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from backend.app import FrameIngress, SourceGrant, create_app, protocol
from backend.inference_worker import InferenceWorker
from backend.sessions import SessionManager
from test_app import encoded_image
from test_sessions import OPERATOR, specification


@dataclass
class FileFlag:
    """Test-only process gate without a lock a killed child could retain."""
    path: str

    def set(self):
        Path(self.path).touch()

    def wait(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if Path(self.path).exists():
                return True
            time.sleep(0.005)
        return False


@dataclass
class FixtureFactory:
    kind: str = 'normal'
    entered: object = None
    release: object = None

    def __call__(self):
        if self.kind == 'load_failure':
            raise RuntimeError('private loader detail')
        if self.kind == 'load_hang':
            time.sleep(60)
        return FixtureModel(self.kind, self.entered, self.release)


class FixtureModel:
    version = 'synthetic-worker-fixture-no-yolo'

    def __init__(self, kind, entered, release):
        self.kind, self.entered, self.release = kind, entered, release

    def predict(self, frame):
        if self.entered is not None:
            self.entered.set()
            self.release.wait(60)
        if self.kind == 'crash':
            raise RuntimeError('private prediction detail')
        if self.kind == 'mutate':
            frame.metadata['capture_monotonic_ms'] += 1000
            frame.metadata['frame_id'] = 'rewritten-by-adapter'
            frame.metadata['image']['width'] += 10
            frame.metadata['image']['height'] += 10
        signal = {'candidate_count': 0, 'symbol': 'unknown', 'confidence': None, 'countdown_s': None}
        if self.kind == 'invalid':
            signal['confidence'] = float('nan')
        return {'detections': [], 'signal': signal}


def wait_for(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError('Worker condition did not arrive within bounded test deadline')


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.jpeg = encoded_image()
        self.metadata = json.loads((Path(__file__).resolve().parents[2] /
                                    'shared/protocol/v1/examples/frame.json').read_text())
        self.metadata.update(jpeg_bytes=len(self.jpeg), image={'width': 32, 'height': 24})
        self.grant = SourceGrant('worker-fixture-token-000000000000000000',
                                 'demo-session', 'pi-camera-1', 'pi-boot-1', 'replay', time.monotonic() + 120)

    def worker(self, kind='normal', gated=False, **kwargs):
        entered, release = self.flags() if gated else (None, None)
        worker = InferenceWorker(FixtureFactory(kind, entered, release), **kwargs)
        self.addCleanup(worker.stop)
        if release is not None:
            self.addCleanup(release.set)
        worker.start()
        if kind not in ('load_failure', 'load_hang'):
            wait_for(lambda: worker.health()['worker_healthy'])
        return worker, entered, release

    def flags(self):
        directory = tempfile.TemporaryDirectory(prefix='canesight-worker-test-')
        self.addCleanup(directory.cleanup)
        return FileFlag(str(Path(directory.name) / 'entered')), FileFlag(str(Path(directory.name) / 'release'))

    def submit(self, worker, seq=9, grant=None):
        grant = grant or self.grant
        metadata = dict(self.metadata, seq=seq, frame_id='frame-' + str(seq),
                        session_id=grant.session_id, source_id=grant.source_id,
                        boot_id=grant.boot_id, mode=grant.mode)
        return worker.submit(grant, metadata, self.jpeg)

    def test_one_load_latest_per_source_and_original_lineage(self):
        worker, entered, release = self.worker(gated=True, job_timeout=10)
        worker.start()
        self.assertTrue(self.submit(worker))
        self.assertTrue(entered.wait(5))
        other = SourceGrant('unused-trusted-fixture', 'demo-session', 'pi-2', 'boot-2', 'replay', self.grant.expires_at)
        self.assertTrue(self.submit(worker, grant=other))
        self.assertTrue(self.submit(worker, seq=10))
        self.assertTrue(self.submit(worker, seq=11))
        metrics = worker.metrics()
        self.assertEqual((metrics['pending'], metrics['active'], metrics['sources']), (2, 1, 2))
        self.assertEqual(metrics['superseded_pending'], 1)
        release.set()
        wait_for(lambda: worker.metrics()['completed'] == 2)
        result = worker.take_result(self.grant)
        self.assertEqual(result['seq'], 11)
        for key in ('capture_monotonic_ms', 'capture_utc', 'image', 'session_id', 'boot_id', 'mode'):
            self.assertEqual(result[key], self.metadata[key])
        self.assertEqual(result['signal']['symbol'], 'unknown')
        protocol.validate_message(result)
        self.assertEqual(worker.take_result(other)['source_id'], 'pi-2')
        self.assertIsNone(worker.take_result(self.grant))
        self.assertEqual(worker.metrics()['model_loads'], 1)
        self.assertEqual(worker.metrics()['superseded_result'], 1)

    def test_source_flood_and_pending_memory_are_bounded(self):
        worker, entered, release = self.worker(gated=True, max_sources=1, job_timeout=10)
        self.assertTrue(self.submit(worker))
        self.assertTrue(entered.wait(5))
        for seq in range(10, 1010):
            self.assertTrue(self.submit(worker, seq))
            other = SourceGrant('unused-trusted-fixture', 'demo-session', 'other-' + str(seq), 'boot', 'replay', self.grant.expires_at)
            self.assertFalse(self.submit(worker, seq, other))
        metrics = worker.metrics()
        self.assertEqual((metrics['sources'], metrics['pending'], metrics['active']), (1, 1, 1))
        self.assertEqual(metrics['source_capacity'], 1000)
        self.assertEqual(metrics['superseded_pending'], 999)
        release.set()
        wait_for(lambda: worker.metrics()['completed'] == 1)
        self.assertEqual(worker.take_result(self.grant)['seq'], 1009)

    def test_adapter_mutation_cannot_rewrite_original_provenance(self):
        worker, _, _ = self.worker('mutate')
        original = copy.deepcopy(self.metadata)
        self.assertTrue(worker.submit(self.grant, self.metadata, self.jpeg))
        wait_for(lambda: worker.metrics()['completed'] == 1)
        result = worker.take_result(self.grant)
        for key, value in original.items():
            if key not in ('type', 'jpeg_bytes'):
                self.assertEqual(result[key], value, key)
        self.assertEqual(self.metadata, original)
        protocol.validate_message(result)

    def session_pair(self, client, body=None):
        response = client.post('/v1/sessions', json=specification() if body is None else body,
                               headers={'Authorization': 'Bearer ' + OPERATOR})
        self.assertEqual(response.status_code, 201, response.text)
        pair = response.json()
        metadata = dict(self.metadata, session_id=pair['session_id'], mode=pair['mode'],
                        source_id=pair['pi']['source_id'], boot_id=pair['pi']['boot_id'])
        return pair, metadata

    def session_upload(self, client, pair, metadata, *, role='pi', url='/v1/frames'):
        return client.post(url, headers={'Authorization': 'Bearer ' + pair[role]['token']},
                           files={'metadata': (None, json.dumps(metadata), 'application/json'),
                                  'image': ('synthetic.jpg', self.jpeg, 'image/jpeg')})

    def test_paired_worker_auth_tls_isolation_provenance_and_lifespans(self):
        worker = InferenceWorker(FixtureFactory('mutate'), job_timeout=10)
        self.addCleanup(worker.stop)
        manager = SessionManager(OPERATOR)
        with TestClient(create_app(session_manager=manager, inference_worker=worker),
                        base_url='https://testserver') as client:
            wait_for(lambda: worker.health()['worker_healthy'])
            self.assertEqual(client.get('/readyz').status_code, 503)
            pair, metadata = self.session_pair(client)
            other, _ = self.session_pair(client)
            self.assertEqual(client.get('/readyz').status_code, 200)
            self.assertEqual(self.session_upload(client, pair, metadata, url='http://testserver/v1/frames').status_code, 403)
            self.assertEqual(self.session_upload(client, pair, metadata, role='phone').status_code, 403)
            self.assertEqual(client.post('/v1/frames').status_code, 401)
            self.assertEqual(self.session_upload(client, other, metadata).status_code, 403)
            self.assertEqual(worker.metrics()['submitted'], 0)
            self.assertEqual(self.session_upload(client, pair, metadata).status_code, 202)
            self.assertEqual(self.session_upload(client, pair, metadata).status_code, 409)
            wait_for(lambda: worker.metrics()['completed'] == 1)
            _, other_grant = manager.authenticate('Bearer ' + other['pi']['token'], 'pi')
            self.assertIsNone(worker.take_result(other_grant))
            _, grant = manager.authenticate('Bearer ' + pair['pi']['token'], 'pi')
            result = worker.take_result(grant)
            for key, value in metadata.items():
                if key not in ('type', 'jpeg_bytes'):
                    self.assertEqual(result[key], value, key)
            protocol.validate_message(result)
            self.assertEqual(worker.metrics()['model_loads'], 1)
        self.assertFalse(worker.health()['worker_healthy'])
        self.assertEqual(manager.sessions, {})

    def test_session_revocation_drops_pending_and_inflight_then_allows_new_epoch(self):
        entered, release = self.flags()
        worker = InferenceWorker(FixtureFactory('normal', entered, release), job_timeout=10)
        self.addCleanup(worker.stop)
        manager = SessionManager(OPERATOR)
        with TestClient(create_app(session_manager=manager, inference_worker=worker),
                        base_url='https://testserver') as client:
            wait_for(lambda: worker.health()['worker_healthy'])
            pair, metadata = self.session_pair(client)
            _, grant = manager.authenticate('Bearer ' + pair['pi']['token'], 'pi')
            self.assertEqual(self.session_upload(client, pair, metadata).status_code, 202)
            self.assertTrue(entered.wait(5))
            self.assertEqual(self.session_upload(client, pair, dict(metadata, seq=10, frame_id='frame-10')).status_code, 202)
            self.assertEqual(worker.metrics()['pending'], 1)
            response = client.delete('/v1/sessions/' + pair['session_id'],
                                     headers={'Authorization': 'Bearer ' + OPERATOR})
            self.assertEqual(response.status_code, 204)
            self.assertEqual(worker.metrics()['pending'], 0)
            self.assertEqual(worker.metrics()['sources'], 0)
            release.set()
            wait_for(lambda: worker.metrics()['active'] == 0)
            self.assertIsNone(worker.take_result(grant))
            self.assertEqual(worker.metrics()['completed'], 0)
            self.assertEqual(self.session_upload(client, pair, metadata).status_code, 401)
            body = specification()
            body['pi']['boot_id'] = 'new-pi-epoch'
            replacement, new_metadata = self.session_pair(client, body)
            self.assertEqual(self.session_upload(client, replacement, new_metadata).status_code, 202)
            wait_for(lambda: worker.metrics()['completed'] == 1)
            _, replacement_grant = manager.authenticate('Bearer ' + replacement['pi']['token'], 'pi')
            self.assertEqual(worker.take_result(replacement_grant)['boot_id'], 'new-pi-epoch')
            self.assertEqual(worker.metrics()['revoked'], 1)

    def test_session_expiry_sweeper_discards_worker_without_new_requests(self):
        entered, release = self.flags()
        worker = InferenceWorker(FixtureFactory('normal', entered, release), job_timeout=10)
        self.addCleanup(worker.stop)
        offset = [0]
        manager = SessionManager(OPERATOR, clock=lambda: time.monotonic() + offset[0])
        with TestClient(create_app(session_manager=manager, inference_worker=worker),
                        base_url='https://testserver') as client:
            wait_for(lambda: worker.health()['worker_healthy'])
            pair, metadata = self.session_pair(client)
            _, grant = manager.authenticate('Bearer ' + pair['pi']['token'], 'pi')
            self.assertEqual(self.session_upload(client, pair, metadata).status_code, 202)
            self.assertTrue(entered.wait(5))
            offset[0] = 301
            wait_for(lambda: not manager.sessions)
            self.assertEqual(worker.metrics()['revoked'], 1)
            release.set()
            wait_for(lambda: worker.metrics()['active'] == 0)
            self.assertIsNone(worker.take_result(grant))
            self.assertEqual(worker.metrics()['completed'], 0)

    def test_prediction_timeout_kills_child_without_reload(self):
        worker, entered, release = self.worker(gated=True, job_timeout=0.25)
        self.submit(worker)
        self.assertTrue(entered.wait(5))
        wait_for(lambda: worker.metrics()['failed'] == 1)
        worker.start()
        self.assertFalse(worker.health()['worker_healthy'])
        self.assertFalse(self.submit(worker, 10))
        self.assertIsNone(worker.take_result(self.grant))
        self.assertEqual(worker.metrics()['timeouts'], 1)
        self.assertEqual(worker.metrics()['model_loads'], 1)
        self.assertTrue(worker.stop())
        self.assertEqual(worker.metrics()['active'], 0)

    def test_revoked_inflight_source_cannot_publish(self):
        worker, entered, release = self.worker(gated=True, job_timeout=10)
        self.submit(worker)
        self.assertTrue(entered.wait(5))
        self.submit(worker, 10)
        worker.discard_source(self.grant)
        self.assertEqual(worker.metrics()['pending'], 0)
        release.set()
        wait_for(lambda: worker.metrics()['active'] == 0)
        self.assertIsNone(worker.take_result(self.grant))
        self.assertEqual(worker.metrics()['revoked'], 1)
        self.assertEqual(worker.metrics()['completed'], 0)

    def test_expiry_during_inference_discards_result(self):
        worker, entered, release = self.worker(gated=True, job_timeout=10)
        grant = SourceGrant('fixture', 'demo-session', 'pi-camera-1', 'pi-boot-1', 'replay', time.monotonic() + 0.2)
        self.assertTrue(self.submit(worker, grant=grant))
        self.assertTrue(entered.wait(5))
        wait_for(lambda: time.monotonic() >= grant.expires_at)
        release.set()
        wait_for(lambda: worker.metrics()['active'] == 0)
        self.assertIsNone(worker.take_result(grant))
        self.assertEqual(worker.metrics()['sources'], 0)
        self.assertEqual(worker.metrics()['completed'], 0)

    def test_failed_or_hung_load_stays_unavailable(self):
        for kind in ('load_failure', 'load_hang'):
            with self.subTest(kind=kind):
                worker, _, _ = self.worker(kind, load_timeout=0.5 if kind == 'load_hang' else 15)
                wait_for(lambda: worker.metrics()['failed'] == 1)
                self.assertEqual(worker.health(), {'model_available': False, 'worker_healthy': False})
                self.assertEqual(worker.metrics()['model_loads'], 0)
                self.assertFalse(self.submit(worker))
                self.assertTrue(worker.stop())

    def test_model_exception_and_invalid_output_never_publish(self):
        for kind in ('crash', 'invalid'):
            with self.subTest(kind=kind):
                worker, _, _ = self.worker(kind)
                self.submit(worker)
                wait_for(lambda: worker.metrics()['failed'] == 1)
                self.assertIsNone(worker.take_result(self.grant))
                self.assertEqual(worker.metrics()['completed'], 0)
                self.assertNotIn('private', repr(worker.metrics()))
                self.assertTrue(worker.stop())

    def test_expired_or_mismatched_grants_and_stop_clear_buffers(self):
        worker, entered, release = self.worker(gated=True, job_timeout=10)
        bad = copy.copy(self.metadata)
        bad['source_id'] = 'wrong'
        with self.assertRaises(ValueError):
            worker.submit(self.grant, bad, self.jpeg)
        expired = SourceGrant('fixture', 'demo-session', 'pi-camera-1', 'pi-boot-1', 'replay', time.monotonic() - 1)
        self.assertFalse(self.submit(worker, grant=expired))
        self.assertTrue(self.submit(worker))
        self.assertTrue(entered.wait(5))
        self.assertTrue(self.submit(worker, 10))
        self.assertTrue(worker.stop())
        self.assertEqual(worker.metrics()['pending'], 0)
        self.assertEqual(worker.metrics()['results'], 0)
        self.assertEqual(worker.metrics()['sources'], 0)
        self.assertFalse(worker.health()['model_available'])
        self.assertFalse(self.submit(worker, 11))

    def test_async_software_watchdog_runs_during_slow_process_and_flood(self):
        worker, entered, release = self.worker(gated=True, job_timeout=10)
        self.submit(worker)
        self.assertTrue(entered.wait(5))

        async def exercise():
            ticks = []
            async def watchdog():
                for _ in range(30):
                    ticks.append(time.monotonic())
                    await asyncio.sleep(0.005)
            async def flood():
                for seq in range(10, 2010):
                    self.submit(worker, seq)
                    if seq % 10 == 0:
                        await asyncio.sleep(0)
            await asyncio.gather(watchdog(), flood())
            return ticks

        ticks = asyncio.run(exercise())
        self.assertEqual(len(ticks), 30)
        self.assertEqual(worker.metrics()['pending'], 1)
        self.assertEqual(worker.metrics()['superseded_pending'], 1999)
        release.set()
        wait_for(lambda: worker.metrics()['completed'] == 1)
        self.assertEqual(worker.take_result(self.grant)['seq'], 2009)

    def test_endpoint_lifespan_and_truthful_readiness(self):
        entered, release = self.flags()
        worker = InferenceWorker(FixtureFactory('normal', entered, release), job_timeout=10)
        self.addCleanup(worker.stop)
        ingress = FrameIngress([self.grant])
        with TestClient(create_app(ingress=ingress, inference_worker=worker,
                                  dependency_health=lambda: {'model_available': True, 'worker_healthy': True})) as client:
            wait_for(lambda: worker.health()['worker_healthy'])
            self.assertEqual(client.get('/readyz').status_code, 200)
            response = client.post('/v1/frames', headers={'Authorization': 'Bearer ' + self.grant.token},
                                   files={'metadata': (None, json.dumps(self.metadata), 'application/json'),
                                          'image': ('synthetic.jpg', self.jpeg, 'image/jpeg')})
            self.assertEqual(response.status_code, 202)
            self.assertTrue(entered.wait(5))
            self.assertEqual(client.get('/healthz').status_code, 200)
            release.set()
            wait_for(lambda: worker.metrics()['completed'] == 1)
        self.assertFalse(worker.health()['worker_healthy'])
        self.assertTrue(worker.stop())

    def test_invalid_worker_configuration(self):
        for kwargs in ({'max_sources': 17}, {'max_sources': True}, {'job_timeout': float('nan')},
                       {'job_timeout': 0}, {'load_timeout': float('inf')}):
            with self.assertRaises(ValueError):
                InferenceWorker(FixtureFactory(), **kwargs)
