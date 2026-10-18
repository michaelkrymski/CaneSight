import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('pi_depth_probe', Path(__file__).with_name('pi_phone_depth_probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
ROOT = Path(__file__).resolve().parents[2]


class DepthProbeTests(unittest.TestCase):
    def state(self):
        value = probe.DepthState('s', 'phone', 'phone-boot')
        value.opened()
        return value

    def packet(self, kind='depth_observation', **changes):
        name = 'depth' if kind == 'depth_observation' else 'heartbeat'
        value = json.loads((ROOT / ('shared/protocol/v1/examples/' + name + '.json')).read_text())
        value.update(session_id='s', source_id='phone', boot_id='phone-boot', mode='live')
        if kind == 'heartbeat':
            value['state'] = 'ready'
        value.update(changes)
        return json.dumps(value)

    def test_reconnect_retains_per_type_sequence_and_original_capture_high_water(self):
        state = self.state()
        state.receive(self.packet(seq=3, capture_monotonic_ms=100), 1000)
        state.opened()
        for updates in [dict(seq=3, capture_monotonic_ms=200), dict(seq=4, capture_monotonic_ms=100)]:
            with self.assertRaises(ValueError):
                state.receive(self.packet(**updates), 1100)
        state.receive(self.packet(seq=5, capture_monotonic_ms=200), 1200)
        self.assertEqual([r['depth'] for r in state.connections], [1, 1])
        self.assertFalse(state.ready)

    def test_foreign_role_epoch_and_mode_rejected(self):
        for updates in [dict(boot_id='other'), dict(source_id='other'), dict(mode='replay'), dict(session_id='other')]:
            with self.assertRaises(ValueError):
                self.state().receive(self.packet(**updates), 100)

    def test_clock_correlation_is_one_use_and_never_establishes_drift_or_age(self):
        state = self.state()
        state.receive(self.packet('heartbeat', seq=0), 10)
        request = json.loads(state.probe(dict(source_id='pi', boot_id='pi-boot'), 100))
        reply = dict(request, type='clock_reply', t2_ms=200, t3_ms=205)
        state.receive(json.dumps(reply), 120)
        self.assertEqual(state.rtts, [20])
        self.assertEqual(state.clock_widths, [15])
        self.assertEqual(state.summary()['capture_age_eligibility'], 'unknown')
        self.assertFalse(state.summary()['drift_budget_justified'])
        with self.assertRaises(ValueError):
            state.receive(json.dumps(reply), 125)

    def test_disconnect_clears_pending_probe_and_ready_but_not_sequence(self):
        state = self.state()
        state.receive(self.packet('heartbeat', seq=2), 10)
        request = json.loads(state.probe(dict(source_id='pi', boot_id='pi-boot'), 100))
        state.opened()
        self.assertFalse(state.ready)
        with self.assertRaises(ValueError):
            state.receive(json.dumps(dict(request, type='clock_reply', t2_ms=105, t3_ms=110)), 120)
        with self.assertRaises(ValueError):
            state.receive(self.packet('heartbeat', seq=1), 130)

    def test_source_and_arrival_rates_are_separate_not_latency_or_eligibility(self):
        state = self.state()
        state.receive(self.packet(seq=1, capture_monotonic_ms=100), 1000)
        state.receive(self.packet(seq=2, capture_monotonic_ms=200), 1200)
        result = state.summary()
        row = result['per_connection'][0]
        self.assertEqual(row['source_capture_rate_hz'], 10)
        self.assertEqual(row['receiver_arrival_rate_hz'], 5)
        self.assertEqual(row['depth_before_ready_heartbeat'], 2)
        self.assertFalse(result['pi_camera_used'])
        self.assertEqual(result['capture_age_eligibility'], 'unknown')


class DepthProbeLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_observer_loop_waits_for_second_close_and_checks_clock_replies(self):
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest.mock import patch
        from websockets.exceptions import ConnectionClosedError
        from websockets.frames import Close
        packets = DepthProbeTests().packet
        current = 100
        def clock():
            nonlocal current
            current += .02
            return current

        class Socket:
            def __init__(self, index):
                self.index, self.count, self.heartbeat = index, 0, False
                self.replies = []
            async def recv(self):
                if self.replies:
                    return self.replies.pop(0)
                if not self.heartbeat:
                    self.heartbeat = True
                    return packets('heartbeat', seq=self.index)
                if self.count == 30:
                    raise ConnectionClosedError(Close(1012, ''), Close(1012, ''), True)
                seq = self.index * 30 + self.count
                self.count += 1
                return packets(seq=seq, capture_monotonic_ms=100 + seq * 100)
            async def send(self, data):
                request = json.loads(data)
                self.replies.append(json.dumps(dict(request, type='clock_reply', t2_ms=2500, t3_ms=2501)))

        class Context:
            def __init__(self, index): self.socket = Socket(index)
            async def __aenter__(self): return self.socket
            async def __aexit__(self, *args): return False
        calls = []
        def connect(url, **options):
            self.assertTrue(options['ssl'].check_hostname)
            self.assertIsNone(options['proxy'])
            index = len(calls); calls.append(index)
            return Context(index)
        output = io.StringIO()
        with patch.object(probe, 'time', SimpleNamespace(monotonic=clock)), contextlib.redirect_stdout(output):
            await probe.observe(dict(session_id='s', source_id='pi', boot_id='pi-boot', token='x'*40),
                                'phone', 'phone-boot', connector=connect)
        result = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(result['connections'], 2)
        self.assertEqual([r['depth_packets'] for r in result['per_connection']], [30, 30])
        self.assertGreaterEqual(result['clock_round_trip']['count'], 2)
        self.assertEqual(result['capture_age_eligibility'], 'unknown')
        self.assertNotIn('x'*40, output.getvalue())
