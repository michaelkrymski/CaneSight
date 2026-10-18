"""Production request composition with generated frames, virtual time and no devices."""
import importlib.util
import io
import types
import unittest
from unittest.mock import patch

from edge.context_runtime import ManualContext
from edge import uploader
from test_buttons import fixture_frame, Handle, reply
from test_context_client import configuration
from test_context_audio import Sink

HAS_BRIDGE = importlib.util.find_spec('backend.context.speech_channels') is not None


class HealthySink(Sink):
    def healthy(self): return not self.closed


@unittest.skipUnless(HAS_BRIDGE, 'Requires CS-040 completed-gesture API and speech channels')
class MenuRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.ready = self.route = True
        self.hazard = False
        self.jobs = []
        self.sink = HealthySink()
        frame = fixture_frame(self.now)
        def start(request_id, frame):
            handle = Handle(); handle.bound_reply = reply(request_id, frame)
            self.jobs.append(handle)
            return handle
        self.runtime = ManualContext(configuration(frame), lambda: (self.ready, self.hazard),
            consent=True, clock=lambda: self.now, client=types.SimpleNamespace(start=start),
            audio=True, speech_sink=self.sink, menu=True, audio_ready=lambda: self.route)
        self.addCleanup(self.runtime.close)
        self.runtime.set_camera_ready(True)
        self.step(0); self.step(30)

    def step(self, delta):
        self.now += delta
        self.runtime.offer(fixture_frame(self.now))
        self.runtime.tick()

    def level(self, value):
        self.runtime.command('press' if value else 'release')
        self.step(0); self.step(30)

    def enter(self):
        self.level(True); self.step(3000)
        self.assertEqual(self.runtime.snapshot()['menu']['state'], 'menu_entry')
        self.level(False)

    def test_short_release_dispatches_once_and_preserves_capture_cooldown_and_cancel(self):
        self.level(True)
        self.assertEqual(self.jobs, [])
        self.level(False)
        self.assertEqual(len(self.jobs), 1)
        self.jobs[0].reply = self.jobs[0].bound_reply
        self.step(0)
        self.assertEqual(self.sink.current, 'AI description, uncertain: Possible chair.')
        self.level(True)
        self.assertIsNone(self.sink.current)
        self.level(False)
        self.assertEqual(len(self.jobs), 1)
        self.step(10000)
        self.level(True); self.level(False)
        self.assertEqual(len(self.jobs), 2)
        self.runtime.command('cancel')
        self.assertTrue(self.jobs[1].cancelled.is_set())
        self.jobs[1].reply = self.jobs[1].bound_reply
        self.step(0)
        self.assertIsNone(self.sink.current)

    def test_long_hold_never_requests_and_unsupported_confirmation_cannot_activate(self):
        self.enter()
        self.assertEqual(self.jobs, [])
        self.level(True); self.level(False)
        self.assertEqual(self.sink.current, 'Pedestrian walk-and-hand signal')
        self.step(10)  # Context timer must not stop the menu owner.
        self.assertEqual(self.sink.current, 'Pedestrian walk-and-hand signal')
        self.level(True); self.step(1000)
        self.assertEqual(self.sink.current, 'Crossing observations unavailable.')
        self.assertNotEqual(self.runtime.snapshot()['menu']['state'], 'active')
        self.assertEqual(self.jobs, [])

    def test_route_loss_preempts_menu_and_recovery_requires_fresh_release_hold(self):
        self.enter()
        self.route = False; self.step(0)
        self.assertIsNone(self.sink.current)
        self.route = True; self.step(0)
        self.assertNotEqual(self.runtime.snapshot()['menu']['state'], 'menu')
        self.assertIsNone(self.sink.current)
        self.level(False); self.enter()
        self.assertIn('does not tell you when to cross', self.sink.current)
        self.runtime.command('audio-off')
        self.assertIsNone(self.sink.current)
        self.assertFalse(self.runtime.command('audio-on'))
        self.level(False); self.level(True); self.step(3000)
        self.assertIsNone(self.sink.current)

    def test_hazard_and_shutdown_stop_without_replay(self):
        self.enter()
        self.hazard = True; self.step(0)
        self.assertIsNone(self.sink.current)
        self.hazard = False; self.step(0)
        self.assertIsNone(self.sink.current)
        self.runtime.close()
        self.assertTrue(self.sink.closed)
        self.assertFalse(self.runtime.command('press'))

    def test_expiry_and_consent_loss_cannot_deliver_old_result(self):
        self.level(True); self.level(False)
        self.step(8000)
        self.jobs[0].reply = self.jobs[0].bound_reply
        self.step(0)
        self.assertIsNone(self.sink.current)
        self.runtime.withdraw()
        self.step(0)
        self.assertFalse(self.runtime.snapshot()['consent'])
        self.assertIsNone(self.sink.current)

    def test_entry_cancels_old_request_and_late_reply_cannot_interrupt_menu(self):
        self.level(True); self.level(False)
        self.enter()
        self.assertTrue(self.jobs[0].cancelled.is_set())
        self.jobs[0].reply = self.jobs[0].bound_reply
        self.step(0)
        self.assertIn('does not tell you when to cross', self.sink.current)
        self.assertEqual(len(self.jobs), 1)

    def test_startup_held_and_missing_route_readiness_never_dispatch(self):
        self.runtime.cancel()
        self.level(True); self.step(3000)
        self.assertEqual(self.jobs, [])
        self.assertIsNone(self.sink.current)
        self.level(False)
        self.runtime._route_ready = lambda: None
        self.level(True); self.level(False)
        self.assertEqual(self.jobs, [])

    def test_single_clock_read_failure_is_latched_even_if_next_read_recovers(self):
        self.enter()
        original = self.runtime._clock
        readings = iter([RuntimeError(), self.now])
        def clock():
            value = next(readings, self.now)
            if isinstance(value, Exception): raise value
            return value
        self.runtime._clock = clock
        self.runtime.tick()
        self.runtime._clock = original
        self.step(0)
        self.assertEqual(self.runtime.snapshot()['menu']['state'], 'failed')
        self.assertIsNone(self.sink.current)

    def test_failed_fixed_audio_gate_cannot_dispatch_even_with_route_confirmation(self):
        with patch.object(self.runtime._menu_audio, 'update', return_value=False):
            self.level(True); self.level(False)
        self.assertEqual(self.jobs, [])

    def test_clock_failure_closes_menu_and_cancels_pending_work(self):
        self.enter()
        self.now = -100
        self.runtime.tick()
        self.assertEqual(self.runtime.snapshot()['menu']['state'], 'failed')
        self.assertIsNone(self.sink.current)


class MenuArgumentTests(unittest.TestCase):
    def test_menu_requires_audio_and_explicit_route_confirmation_before_camera(self):
        for flags in (['--context-menu'], ['--context-menu-audio-confirmed']):
            with patch('sys.argv', ['uploader', '--capture-only', *flags]), \
                 patch('sys.stderr', io.StringIO()):
                with self.assertRaises(SystemExit): uploader.main()
