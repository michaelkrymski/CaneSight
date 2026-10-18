"""CS-025 live-policy wiring with synthetic packets and fake GPIO devices only."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

from backend.freshness import CaptureAgeGate
from edge import uploader
from edge.haptic_gpio import GPIOOutput
from edge.haptics import CHANNELS, HapticScheduler
from edge.policy import LocalPolicy, PhoneBinding
from edge.receiver import VisionReceiver
from edge.trace import DecisionTrace
from edge.watchdog import PolicyWatchdog


class FakePin:
    def __init__(self, pin, *, active_high, initial_value):
        assert active_high is True and initial_value is False
        self.pin, self.value, self.closed = pin, False, False
    def on(self):
        if self.closed: raise RuntimeError('Closed fake pin')
        self.value = True
    def off(self):
        if self.closed: raise RuntimeError('Closed fake pin')
        self.value = False
    def close(self): self.closed = True


class GPIOPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.clock = lambda: self.now
        self.pins = {}
        def factory(pin, **kwargs):
            self.pins[pin] = FakePin(pin, **kwargs)
            return self.pins[pin]
        self.output = GPIOOutput(left_bcm=17, right_bcm=27, active_high=True, device_factory=factory)
        self.addCleanup(self.output.close)
        self.gate = CaptureAgeGate('session', 'live', 'pi', 'pi-boot', clock_ms=self.clock, relative_drift_ppm=0)
        self.gate.enroll('phone', 'phone-boot', {'depth_observation', 'heartbeat'})
        self.gate.enroll('pi', 'pi-boot', {'frame_metadata', 'vision_observation'})
        probe = self.gate.start_probe('phone')
        self.gate.finish_probe(dict(probe, type='clock_reply', t2_ms=self.now, t3_ms=self.now))
        self.scheduler = HapticScheduler(self.output, clock=self.clock)
        self.addCleanup(self.scheduler.close)
        self.watchdog = PolicyWatchdog(self.scheduler.trip, clock=self.clock)
        self.scheduler.set_guard(self.watchdog.deadline)
        self.addCleanup(self.watchdog.close)
        self.policy = LocalPolicy(self.gate, 'phone', self.scheduler, clock=self.clock,
                                  watchdog=self.watchdog, enable_gpio=True)
        self.addCleanup(self.policy.close)
        self.seq = 0
        self.heartbeat()
        self.policy.arm(True)
        self.advance(210)

    def advance(self, duration):
        end = self.now + duration
        while self.now < end:
            self.now = min(end, self.now + 10)
            self.watchdog.feed()
            self.scheduler.tick()

    def packet(self, kind, **fields):
        self.seq += 1
        return dict(schema_version=1, type=kind, session_id='session', mode='live',
            source_id='phone', boot_id='phone-boot', seq=self.seq,
            capture_monotonic_ms=self.now, capture_utc=None, **fields)

    def heartbeat(self, state='ready'):
        self.gate.receive(self.packet('heartbeat', state=state))

    def depth(self, side='left', *, age=0, tracking='normal'):
        message = self.packet('depth_observation', tracking=tracking,
            sectors={name: dict(distance_m=(.7 if name == side else 2) if tracking == 'normal' else None,
                               valid_fraction=1 if tracking == 'normal' else 0)
                     for name in ('left', 'center', 'right')})
        message['capture_monotonic_ms'] -= age
        self.gate.receive(message)
        return self.policy.tick()

    def states(self):
        return dict(left=self.pins[17].value, right=self.pins[27].value)

    def test_repeated_left_center_right_reaches_real_adapter_interface(self):
        for side, expected in [('left', dict(left=True, right=False)),
                               ('center', dict(left=True, right=True)),
                               ('right', dict(left=False, right=True))]:
            self.policy.arm(False)
            self.policy.arm(True)
            self.depth(side)
            self.advance(100)
            result = self.depth(side)
            self.assertEqual(result['output_mode'], 'gpio')
            self.assertEqual(self.states(), expected)
            self.advance(100)
            self.assertEqual(self.states(), dict.fromkeys(CHANNELS, False))
            self.advance(210)
        self.assertEqual(self.scheduler.accepted, 3)

    def test_original_capture_expiry_stops_gpio_and_heartbeat_cannot_retrigger(self):
        self.advance(500)  # Original capture must follow the calibration/recovery floor.
        self.depth(age=420)
        self.advance(10)
        self.depth(age=420)
        self.assertTrue(self.states()['left'])
        self.advance(80)
        self.assertFalse(any(self.states().values()))
        for _ in range(3):
            self.heartbeat()
            self.policy.tick()
        self.assertEqual(self.scheduler.accepted, 1)

    def test_interruption_unknown_tracking_and_disconnect_remove_actuation(self):
        self.depth(); self.advance(10); self.depth()
        self.assertTrue(self.states()['left'])
        self.heartbeat('degraded'); self.policy.tick()
        self.assertFalse(any(self.states().values()))
        self.heartbeat(); self.advance(210)
        self.depth(tracking='limited')
        self.assertFalse(any(self.states().values()))
        self.gate.interrupt(); self.policy.tick()
        self.assertFalse(any(self.states().values()))

    def test_watchdog_expiry_disarms_adapter_and_cannot_recover(self):
        self.depth(); self.advance(10); self.depth()
        self.now += 201  # No completed tick/lease feed.
        self.watchdog.tick()
        self.assertFalse(any(self.states().values()))
        self.assertFalse(self.watchdog.feed())
        self.assertFalse(self.scheduler.set_ready(True))

    def test_gpio_requires_opt_in_live_identity_drift_and_attached_watchdog(self):
        options = dict(clock=self.clock, watchdog=self.watchdog, enable_gpio=True)
        for changes in ({'enable_gpio': False}, {'enable_gpio': 1}, {'watchdog': None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                LocalPolicy(self.gate, 'phone', self.scheduler, **dict(options, **changes))
        with self.assertRaises(ValueError):
            LocalPolicy(self.gate, None, self.scheduler, **options)
        for field, value in (('mode', 'replay'), ('drift', None)):
            original = getattr(self.gate, field)
            setattr(self.gate, field, value)
            try:
                with self.assertRaises(ValueError):
                    LocalPolicy(self.gate, 'phone', self.scheduler, **options)
            finally: setattr(self.gate, field, original)
        self.assertEqual(self.scheduler.accepted, 0)

    def test_trace_gpio_label_and_mode_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            simulation = DecisionTrace(Path(folder)/'simulation.jsonl')
            try:
                with self.assertRaises(ValueError):
                    LocalPolicy(self.gate, 'phone', self.scheduler, clock=self.clock,
                                watchdog=self.watchdog, enable_gpio=True, trace=simulation)
            finally: simulation.close()
            trace = DecisionTrace(Path(folder)/'gpio.jsonl', output_mode='gpio')
            self.policy.trace = trace
            try:
                self.depth(); self.advance(10); self.depth()
            finally: summary = trace.close(); self.policy.trace = None
            self.assertTrue(summary['complete'])
            self.assertEqual(summary['output_mode'], 'gpio')
            events = [json.loads(row) for row in (Path(folder)/'gpio.jsonl').read_text().splitlines()]
            self.assertTrue(events[-1]['accepted'])
            self.assertTrue(all(event['output_mode'] == 'gpio' for event in events))
            self.assertTrue(all(event['capture_age_interval_ms'][1] <= 500 for event in events))


class GPIOUploaderTests(unittest.TestCase):
    base = ['uploader', '--session-file', '/private/session', '--receive-vision', '--gpio-policy']
    pins = ['--motor-left-bcm', '17', '--motor-right-bcm', '27', '--motor-active-high']

    def test_invalid_gpio_options_fail_before_enrollment_camera_or_gpio(self):
        for args in (self.base, self.base + self.pins,
                     self.base + self.pins + ['--simulate-policy'],
                     ['uploader', '--capture-only'] + self.pins):
            with self.subTest(args=args), patch('sys.argv', args), \
                    patch.object(uploader, 'load_session') as load, \
                    patch('edge.haptic_gpio.GPIOOutput.__init__') as init, \
                    redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): uploader.main()
                load.assert_not_called(); init.assert_not_called()

    def test_unknown_drift_refused_before_enrollment_or_gpio(self):
        with patch('sys.argv', self.base + self.pins + ['--phone-binding-file', '/private/phone']), \
                patch('edge.policy.PhoneBinding.load', return_value=PhoneBinding('phone', 'phone-boot', None)), \
                patch.object(uploader, 'load_session') as load, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): uploader.main()
            load.assert_not_called()

    def test_camera_failure_stops_all_gpio_before_other_cleanup(self):
        devices, events = [], []
        class Pin(FakePin):
            def off(self): events.append('off'); super().off()
            def close(self): events.append('pin-close'); super().close()
        def device(pin, **kwargs):
            result = Pin(pin, **kwargs); devices.append(result); return result
        close_policy = LocalPolicy.close
        def closed(policy):
            events.append('policy-close')
            return close_policy(policy)
        session = dict(base_url='https://127.0.0.1', session_id='session', source_id='pi-camera',
                       boot_id='pi-boot', mode='live', token='synthetic-'+'t'*40)
        clock = lambda: time.monotonic()*1000
        receiver_class = VisionReceiver
        camera = Mock()
        camera.Picamera2.side_effect = RuntimeError('Synthetic camera unavailable')
        stdout = io.StringIO()
        with patch('sys.argv', self.base + self.pins + ['--phone-binding-file', '/private/phone']), \
                patch('edge.policy.PhoneBinding.load', return_value=PhoneBinding('phone', 'phone-boot', 0)), \
                patch.object(uploader, 'load_session', return_value=session), \
                patch.object(uploader, 'clock_ms', clock), patch.object(uploader, 'Transport'), \
                patch('edge.receiver.VisionReceiver', side_effect=lambda *a, **kw: receiver_class(*a, clock=clock, **kw)), \
                patch.object(receiver_class, 'start', lambda receiver: setattr(receiver, 'connected', True)), \
                patch.object(LocalPolicy, 'close', closed), \
                patch.dict('sys.modules', picamera2=camera,
                           gpiozero=types.SimpleNamespace(DigitalOutputDevice=device)), redirect_stdout(stdout):
            with self.assertRaisesRegex(RuntimeError, 'Synthetic camera'):
                uploader.main()
        self.assertEqual(events[0], 'off')  # Scheduler initializes both outputs off.
        self.assertLess(events.index('policy-close'), events.index('pin-close'))
        self.assertTrue(all(pin.closed and not pin.value for pin in devices))
        self.assertIn('gpio_used=true', stdout.getvalue())
        self.assertNotIn(session['token'], stdout.getvalue())


if __name__ == '__main__': unittest.main()
