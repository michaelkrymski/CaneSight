import asyncio
import concurrent.futures
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import anyio
from fastapi.testclient import TestClient
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from backend.app import FrameIngress, SourceGrant, create_app
from backend.limits import Limits, RateTable, TrafficGuard, TrafficLimits, strict_object


class BucketTests(unittest.TestCase):
    def test_exact_refill_idle_expiry_and_capacity_without_eviction(self):
        now = [0.0]
        limiter = RateTable(1, 2, capacity=2, idle_seconds=5, clock=lambda: now[0])
        self.assertTrue(limiter.allow('a'))
        self.assertTrue(limiter.allow('a'))
        self.assertFalse(limiter.allow('a'))
        now[0] = .999
        self.assertFalse(limiter.allow('a'))
        now[0] = 1
        self.assertTrue(limiter.allow('a'))
        self.assertTrue(limiter.allow('b'))
        for n in range(10000):
            self.assertFalse(limiter.allow(('new', n)))
        self.assertEqual(limiter.size(), 2)
        self.assertFalse(limiter.allow('a'))  # identity flood did not reset its tokens
        now[0] = 6
        self.assertTrue(limiter.allow('c'))
        self.assertEqual(limiter.size(), 1)

    def test_concurrent_admission_is_atomic(self):
        limiter = RateTable(1, 3, clock=lambda: 0)
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            self.assertEqual(sum(executor.map(lambda _: limiter.allow('same'), range(200))), 3)

    def test_regressed_or_invalid_clock_does_not_renew_budget(self):
        now = [10.0]
        limiter = RateTable(1, 1, clock=lambda: now[0])
        self.assertTrue(limiter.allow('a'))
        for value in (9, 10, float('nan'), float('inf')):
            now[0] = value
            self.assertFalse(limiter.allow('a'))
        now[0] = 11
        self.assertTrue(limiter.allow('a'))

    def test_invalid_or_unbounded_configuration_is_rejected(self):
        for rate, burst, capacity in [(0, 1, 1), (float('nan'), 1, 1),
                                      (float('inf'), 1, 1), (1, 0, 1), (1, 1, 10000)]:
            with self.assertRaises(ValueError):
                RateTable(rate, burst, capacity=capacity)

    def test_authenticated_source_budget_survives_reconnect_and_sources_are_separate(self):
        limits = TrafficLimits(clock=lambda: 0)
        grant = SourceGrant('synthetic-only-token-' * 3, 'session', 'phone', 'boot', 'replay', 300, 'phone')
        self.assertEqual(sum(limits.telemetry_allowed(grant) for _ in range(11)), 10)
        renewed_connection = SourceGrant(grant.token, 'session', 'phone', 'boot', 'replay', 300, 'phone')
        self.assertFalse(limits.telemetry_allowed(renewed_connection))
        other = SourceGrant(grant.token, 'session', 'other', 'boot', 'replay', 300, 'phone')
        self.assertTrue(limits.telemetry_allowed(other))


class WireTests(unittest.TestCase):
    def test_json_rejections_and_multibyte_limits(self):
        for raw in (b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'{"x":1,"x":2}',
                    b'[]', b'\xff', b'{"x":' + b'[' * 13 + b'0' + b']' * 13 + b'}', b' ' * 8193):
            with self.assertRaises((ValueError, UnicodeError)):
                strict_object(raw)
        self.assertEqual(strict_object(b'{"x":"[[[\\\"{{{"}'), {'x': '[[["{{{'})
        self.assertEqual(strict_object(b'{}' + b' ' * 8190), {})


class EndpointLimitTests(unittest.TestCase):
    def setUp(self):
        self.now = [0.0]
        self.limits = TrafficLimits(clock=lambda: self.now[0])
        self.grant = SourceGrant('fixture-only-token-' * 3, 'demo-session', 'pi-camera-1', 'pi-boot-1', 'replay', 300)
        self.app = create_app(ingress=FrameIngress([self.grant], clock=lambda: self.now[0]),
                              traffic_limits=self.limits)
        self.client = TestClient(self.app)

    def test_source_flood_rejected_before_body_processing_and_health_remains_available(self):
        headers = {'Authorization': 'Bearer ' + self.grant.token}
        for _ in range(8):
            self.assertEqual(self.client.post('/v1/frames', headers=headers).status_code, 415)
        with patch('backend.app.read_parts', side_effect=AssertionError('Body must not be read')):
            response = self.client.post('/v1/frames', headers=headers)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['retry-after'], '1')
        self.assertEqual(self.client.get('/healthz').status_code, 200)
        self.assertEqual(self.client.get('/readyz').status_code, 503)
        self.assertEqual(self.app.state.ingress.latest, {})
        self.assertEqual(self.limits.snapshot()['frame_rejected'], 1)
        self.now[0] = 1
        self.assertEqual(self.client.post('/v1/frames', headers=headers).status_code, 415)

    def test_unauthenticated_flood_is_bounded_and_forwarded_headers_cannot_reset_peer(self):
        small = TrafficLimits(Limits(peer_rate=1, peer_burst=2), clock=lambda: 0)
        client = TestClient(create_app(traffic_limits=small))
        self.assertEqual(client.post('/v1/frames').status_code, 401)
        self.assertEqual(client.post('/v1/frames').status_code, 401)
        for n in range(100):
            response = client.post('/v1/frames', headers={'X-Forwarded-For': str(n)})
            self.assertEqual(response.status_code, 429)
        self.assertEqual(small.peers.size(), 1)
        self.assertEqual(client.get('/healthz').status_code, 200)

    def socket_app(self):
        @self.app.websocket('/v1/telemetry')
        async def fixture_socket(websocket: WebSocket):
            await websocket.accept()
            try:
                while True:
                    text = await websocket.receive_text()
                    await websocket.send_text(text)
            except WebSocketDisconnect:
                pass
        return TestClient(self.app)

    def test_websocket_bytes_and_nonfinite_json_never_reach_downstream(self):
        client = self.socket_app()
        for payload, code in [('{"x":NaN}', 1008), ('{"x":1e999}', 1008),
                              ('{"x":1,"x":2}', 1008), ('x' * 8193, 1009),
                              ('{"x":"' + '\u00e9' * 4096 + '"}', 1009)]:
            with client.websocket_connect('/v1/telemetry') as websocket:
                websocket.send_text(payload)
                with self.assertRaises(WebSocketDisconnect) as error:
                    websocket.receive_text()
                self.assertEqual(error.exception.code, code)
        self.assertEqual(self.limits.snapshot()['active_websockets'], 0)
        self.assertEqual(client.get('/healthz').status_code, 200)

    def test_depth_flood_is_closed_without_retiming_valid_messages(self):
        client = self.socket_app()
        raw = '{"type":"depth_observation","capture_monotonic_ms":7}'
        with client.websocket_connect('/v1/telemetry') as websocket:
            for _ in range(10):
                websocket.send_text(raw)
                self.assertEqual(websocket.receive_text(), raw)
            websocket.send_text(raw)
            with self.assertRaises(WebSocketDisconnect) as error:
                websocket.receive_text()
            self.assertEqual(error.exception.code, 1008)

    def test_websocket_capacity_is_released_on_close(self):
        self.limits.policy = Limits(websocket_capacity=1)
        client = self.socket_app()
        with client.websocket_connect('/v1/telemetry') as first:
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect('/v1/telemetry'):
                    pass
            first.send_text('{}')
            self.assertEqual(first.receive_text(), '{}')
        with client.websocket_connect('/v1/telemetry') as next_socket:
            next_socket.send_text('{}')
            self.assertEqual(next_socket.receive_text(), '{}')
        self.assertEqual(self.limits.snapshot()['active_websockets'], 0)


class AsyncFloodTests(unittest.TestCase):
    def test_flood_keeps_event_loop_watchdog_scheduled_and_maps_bounded(self):
        async def run():
            limits = TrafficLimits(Limits(peer_rate=10, peer_burst=10), clock=lambda: 0)
            handled, ticks = [], []
            async def downstream(scope, receive, send):
                handled.append(scope['client'][0])
                await anyio.sleep(0)
                await send({'type': 'http.response.start', 'status': 401, 'headers': []})
                await send({'type': 'http.response.body', 'body': b''})
            guarded = TrafficGuard(downstream, limits)
            async def receive():
                raise AssertionError('Body read under pre-admission guard')
            async def discard(_message):
                pass
            async def watchdog():
                for _ in range(20):
                    await anyio.sleep(0)
                    ticks.append(1)
            async def flood():
                for n in range(2000):
                    await guarded({'type': 'http', 'path': '/v1/frames', 'client': (str(n), 1)}, receive, discard)
                    await anyio.sleep(0)
            await asyncio.gather(flood(), watchdog())
            self.assertEqual(len(ticks), 20)
            self.assertLessEqual(limits.peers.size(), 128)
            self.assertEqual(limits.total.size(), 1)
            self.assertLessEqual(len(handled), 128)
            self.assertGreater(limits.snapshot()['http_rejected'], 1800)
        anyio.run(run)


if __name__ == '__main__':
    unittest.main()
