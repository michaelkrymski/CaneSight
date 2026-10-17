"""CS-032 accepted sessions/worker integration; all images/models are synthetic."""
import asyncio
import gc
import json
from pathlib import Path
import secrets
import socket
import ssl
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import httpx
import trustme
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from backend.app import MAX_BODY, create_app
from backend.inference_worker import InferenceWorker
from backend.limits import Limits, TrafficLimits
from backend.sessions import SessionManager
from backend.server import server_config
from test_app import encoded_image
from test_sessions import OPERATOR, fixture, specification
from test_worker import FileFlag, FixtureFactory


async def until(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError('Async worker condition timed out')
        await asyncio.sleep(.01)


class PairedFrameLimitTests(unittest.TestCase):
    def test_unrestricted_forwarded_header_trust_cannot_be_configured(self):
        for value in ('*', '0.0.0.0/0', '::/0', '', 'not-an-address', '127.0.0.1,*'):
            with self.assertRaises(ValueError):
                server_config(forwarded_allow_ips=value)

    def test_paired_frame_quota_is_after_auth_before_body_and_does_not_commit_rejection(self):
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        now = [0.0]
        limits = TrafficLimits(clock=lambda: now[0])
        manager = SessionManager(OPERATOR)
        app = create_app(session_manager=manager, traffic_limits=limits)
        with TestClient(app, base_url='https://testserver') as client:
            pair = client.post('/v1/sessions', json=specification(),
                               headers={'Authorization': 'Bearer ' + OPERATOR}).json()
            headers = {'Authorization': 'Bearer ' + pair['pi']['token']}
            self.assertEqual(client.post('/v1/frames').status_code, 401)
            self.assertEqual(client.post('/v1/frames', headers={'Authorization': 'Bearer ' + pair['phone']['token']}).status_code, 403)
            self.assertEqual(limits.frames.size(), 0)
            for _ in range(8):
                self.assertEqual(client.post('/v1/frames', headers=headers).status_code, 415)
            with patch('backend.app.read_parts', side_effect=AssertionError('Rejected frame body was read')):
                self.assertEqual(client.post('/v1/frames', headers=headers).status_code, 429)
            record, _ = manager.authenticate(headers['Authorization'], 'pi')
            self.assertEqual(record.ingress.latest, {})
            self.assertEqual(record.ingress.last_sequence, {})
            self.assertEqual(limits.snapshot()['frame_rejected'], 1)
            now[0] += 1
            self.assertEqual(client.post('/v1/frames',
                headers={**headers, 'Content-Type': 'multipart/form-data',
                         'Content-Length': str(MAX_BODY + 1)}, content=b'').status_code, 413)


class SlowInferenceFloodTests(unittest.TestCase):
    def test_authenticated_flood_keeps_latest_work_heap_and_same_loop_watchdog_bounded(self):
        with tempfile.TemporaryDirectory(prefix='canesight-limits-load-') as directory:
            entered = FileFlag(str(Path(directory) / 'entered'))
            release = FileFlag(str(Path(directory) / 'release'))
            worker = InferenceWorker(FixtureFactory('normal', entered, release), job_timeout=10)
            self.addCleanup(worker.stop)
            limits = TrafficLimits(clock=lambda: 0)
            manager = SessionManager(OPERATOR)
            app = create_app(session_manager=manager, inference_worker=worker, traffic_limits=limits)
            jpeg = encoded_image()

            async def exercise():
                async with app.router.lifespan_context(app):
                    await until(lambda: worker.health()['worker_healthy'])
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                                 base_url='https://testserver', trust_env=False) as client:
                        response = await client.post('/v1/sessions', json=specification(),
                                                      headers={'Authorization': 'Bearer ' + OPERATOR})
                        self.assertEqual(response.status_code, 201)
                        pair = response.json()
                        headers = {'Authorization': 'Bearer ' + pair['pi']['token']}
                        metadata = dict(fixture('frame'), session_id=pair['session_id'],
                                        image={'width': 32, 'height': 24}, jpeg_bytes=len(jpeg))

                        async def upload(seq):
                            message = dict(metadata, seq=seq, frame_id='frame-' + str(seq))
                            return await client.post('/v1/frames', headers=headers,
                                files={'metadata': (None, json.dumps(message), 'application/json'),
                                       'image': ('synthetic.jpg', jpeg, 'image/jpeg')})

                        self.assertEqual((await upload(9)).status_code, 202)
                        self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                        ticks, accepted, rejected = [], [], []

                        async def watchdog():
                            for _ in range(30):
                                ticks.append(time.monotonic())
                                self.assertEqual((await client.get('/healthz')).status_code, 200)
                                await asyncio.sleep(.005)

                        async def flood():
                            for seq in range(10, 210):
                                result = await upload(seq)
                                if result.status_code == 202:
                                    accepted.append(seq)
                                else:
                                    self.assertEqual(result.status_code, 429)
                                    rejected.append(seq)
                                await asyncio.sleep(0)

                        # ASGI requests and watchdog run on this same event loop;
                        # prediction is deliberately blocked in a real child.
                        await asyncio.gather(watchdog(), flood())
                        self.assertEqual(len(ticks), 30)
                        gaps = [1000 * (b - a) for a, b in zip(ticks, ticks[1:])]
                        # Generous software regression bound, not a haptic age
                        # budget or capture-to-motor latency acceptance target.
                        self.assertLess(max(gaps), 1000)
                        self.assertTrue(accepted)
                        self.assertGreater(len(rejected), 150)
                        metrics = worker.metrics()
                        self.assertEqual((metrics['sources'], metrics['pending'], metrics['active']), (1, 1, 1))
                        self.assertLessEqual(metrics['results'], 1)
                        self.assertGreater(metrics['superseded_pending'], 0)
                        self.assertGreater(limits.snapshot()['frame_rejected'], 0)
                        self.assertGreater(limits.snapshot()['http_rejected'], 0)
                        record, grant = manager.authenticate(headers['Authorization'], 'pi')
                        self.assertEqual(record.ingress.last_sequence[(pair['session_id'], grant.source_id)], max(accepted))
                        self.assertEqual(len(record.ingress.latest), 1)
                        self.assertEqual(len(record.ingress.ledger[(pair['session_id'], grant.source_id)]), 2)
                        release.set()
                        await until(lambda: worker.metrics()['completed'] == 1)
                        result = worker.take_result(grant)
                        self.assertEqual(result['seq'], max(accepted))
                        self.assertEqual(result['capture_monotonic_ms'], metadata['capture_monotonic_ms'])

                        # Warmed, rejected traffic must not accumulate retained
                        # request bodies or identities across repeated batches.
                        async def rejected_batch():
                            for _ in range(500):
                                self.assertEqual((await client.post('/v1/frames', headers=headers,
                                                                   content=b'x' * 8192)).status_code, 429)
                        tracemalloc.start()
                        try:
                            await rejected_batch()
                            gc.collect()
                            baseline = tracemalloc.get_traced_memory()[0]
                            await rejected_batch()
                            gc.collect()
                            retained = tracemalloc.get_traced_memory()[0] - baseline
                            self.assertLess(retained, 1_000_000, 'Rejected traffic retained excessive Python heap')
                            self.evidence = {'watchdog_gap_samples': len(gaps),
                                'median_gap_ms': round(statistics.median(gaps), 3),
                                'p95_gap_ms': round(sorted(gaps)[int(.95 * (len(gaps) - 1))], 3),
                                'max_gap_ms': round(max(gaps), 3), 'retained_heap_growth_bytes': retained,
                                'flood_frames': 200, 'rejected_heap_probe_requests': 1000}
                        finally:
                            tracemalloc.stop()
                        self.assertLessEqual(limits.peers.size(), 128)
                        self.assertEqual(limits.frames.size(), 1)
                        self.assertEqual(limits.total.size(), 1)
                        self.assertEqual(worker.metrics()['model_loads'], 1)
                        await asyncio.to_thread(worker.stop)
                        self.assertEqual((await client.get('/readyz')).status_code, 503)
                        self.assertEqual((await client.get('/healthz')).status_code, 200)
                self.assertFalse(worker.health()['worker_healthy'])
                self.assertEqual(manager.sessions, {})

            asyncio.run(exercise())


class TLSQuotaTests(unittest.TestCase):
    def test_real_wss_source_quota_survives_reconnect_and_rejects_invalid_input(self):
        with tempfile.TemporaryDirectory(prefix='canesight-quota-tls-') as directory:
            root = Path(directory)
            ca = trustme.CA()
            certificate = ca.issue_cert('127.0.0.1')
            certificate.private_key_pem.write_to_path(root / 'server.key')
            certificate.cert_chain_pems[0].write_to_path(root / 'server.pem')
            context = ssl.create_default_context()
            ca.configure_trust(context)
            manager = SessionManager(secrets.token_urlsafe(32))
            limits = TrafficLimits(Limits(peer_rate=1000, peer_burst=1000,
                                           global_rate=1000, global_burst=1000), clock=lambda: 0)
            app = create_app(session_manager=manager, traffic_limits=limits)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen(128)
                port = listener.getsockname()[1]
                server = uvicorn.Server(server_config(app, host='127.0.0.1', port=port,
                    ssl_keyfile=str(root / 'server.key'), ssl_certfile=str(root / 'server.pem'),
                    forwarded_allow_ips='127.0.0.1'))
                thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
                thread.start()
                try:
                    deadline = time.monotonic() + 10
                    while not server.started:
                        if not thread.is_alive() or time.monotonic() >= deadline:
                            self.fail('Quota TLS test server failed to start')
                        time.sleep(.01)
                    asyncio.run(self.exercise(port, context, manager, limits))
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive(), 'Quota TLS server failed to stop')

    async def exercise(self, port, context, manager, limits):
        options = {'ssl': context, 'proxy': None, 'open_timeout': 3, 'close_timeout': 1}
        https, wss = f'https://127.0.0.1:{port}', f'wss://127.0.0.1:{port}'
        async with httpx.AsyncClient(base_url=https, verify=context, trust_env=False, timeout=5) as client:
            async def pair():
                result = await client.post('/v1/sessions', json=specification(),
                    headers={'Authorization': 'Bearer ' + manager._operator_token})
                self.assertEqual(result.status_code, 201)
                return result.json()

            def auth(pair, role):
                return {'Authorization': 'Bearer ' + pair[role]['token']}

            first = await pair()
            message = dict(fixture('depth'), session_id=first['session_id'])
            # A new per-connection bucket exists each time; source quota persists.
            for seq in range(104, 114):
                async with connect(wss + '/v1/events', additional_headers=auth(first, 'pi'), **options) as pi:
                    async with connect(wss + '/v1/telemetry', additional_headers=auth(first, 'phone'), **options) as phone:
                        message['seq'] = seq
                        await phone.send(json.dumps(message))
                        self.assertEqual(json.loads(await asyncio.wait_for(pi.recv(), 2)), message)
                await until(lambda: not manager.sessions[first['session_id']].connections)
            async with connect(wss + '/v1/telemetry', additional_headers=auth(first, 'phone'), **options) as phone:
                await phone.send(json.dumps(dict(message, seq=114)))
                with self.assertRaises(ConnectionClosed):
                    await asyncio.wait_for(phone.recv(), 2)
                self.assertEqual(phone.close_code, 1008)
            record, grant = manager.authenticate('Bearer ' + first['phone']['token'], 'phone')
            self.assertEqual(record.gate.last[(grant.source_id, grant.boot_id, 'depth_observation')], 113)
            self.assertEqual(limits.snapshot()['ws_rate_rejected'], 1)

            second = await pair()
            original = dict(fixture('depth'), session_id=second['session_id'])
            async with connect(wss + '/v1/events', additional_headers=auth(second, 'pi'), **options) as pi:
                async with connect(wss + '/v1/telemetry', additional_headers=auth(second, 'phone'), **options) as phone:
                    await phone.send(json.dumps(original))
                    self.assertEqual(json.loads(await asyncio.wait_for(pi.recv(), 2)), original)
            for raw, code in (('{"x":NaN}', 1008), ('{"x":1e999}', 1008),
                              ('{"x":1,"x":2}', 1008), ('x' * 8193, 1009),
                              (json.dumps(dict(original, source_id='impersonated', seq=105)), 1008)):
                async with connect(wss + '/v1/telemetry', additional_headers=auth(second, 'phone'), **options) as phone:
                    await phone.send(raw)
                    with self.assertRaises(ConnectionClosed):
                        await asyncio.wait_for(phone.recv(), 2)
                    self.assertEqual(phone.close_code, code)
            self.assertEqual(limits.telemetry.size(), 2)
            record, grant = manager.authenticate('Bearer ' + second['phone']['token'], 'phone')
            self.assertEqual(record.gate.last[(grant.source_id, grant.boot_id, 'depth_observation')], 104)
            self.assertEqual((await client.get('/healthz')).status_code, 200)
            self.assertEqual((await client.get('/readyz')).status_code, 503)
        await until(lambda: limits.snapshot()['active_websockets'] == 0)
