"""Issue #68 input wiring and fail-closed integration, using synthetic GPIO only."""
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

from edge.context_gpio import GPIO21Input, main
from edge.context_runtime import ManualContext
from test_buttons import Handle, fixture_frame, reply
from test_context_client import configuration


class Input:
    def __init__(self, level=False):
        self.level, self.fault = level, False
        self.block = threading.Event()
        self.block.set()
    def read(self):
        self.block.wait(1)
        if self.fault:
            raise RuntimeError('private device detail')
        return self.level


class GPIOTests(unittest.TestCase):
    def test_only_reported_input_pin_and_configuration_are_requested(self):
        device = Mock(value=0)
        factory = Mock(return_value=device)
        adapter = GPIO21Input(device_factory=factory)
        factory.assert_called_once_with(21, pull_up=None, active_state=True, bounce_time=None)
        self.assertFalse(adapter.read())
        device.value = 1
        self.assertTrue(adapter.read())
        for value in (None, '1', float('nan'), .5):
            device.value = value
            with self.assertRaisesRegex(RuntimeError, '^GPIO21 input unavailable$'):
                adapter.read()
        adapter.close(); adapter.close()
        device.close.assert_called_once()
        with self.assertRaises(RuntimeError): adapter.read()

    def test_driver_failures_do_not_disclose_details(self):
        with self.assertRaisesRegex(RuntimeError, '^GPIO21 input unavailable;') as error:
            GPIO21Input(device_factory=Mock(side_effect=RuntimeError('private details')))
        self.assertNotIn('private', str(error.exception))

    def runtime(self, source, *, audio=False, sink=None):
        jobs = []
        now = lambda: time.monotonic()*1000
        def start(request_id, frame):
            handle = Handle(); handle.request_id = request_id; handle.frame = frame
            jobs.append(handle); return handle
        frame = fixture_frame(now())
        runtime = ManualContext(configuration(frame), lambda: (True, False), consent=True,
            clock=now, client=types.SimpleNamespace(start=start), emit=lambda *a: None,
            **({"audio": True, "speech_sink": sink} if audio else {}))
        self.addCleanup(runtime.close)
        self.addCleanup(source.block.set)
        runtime.set_camera_ready(True); runtime.offer(frame)
        runtime.start(gpio_input=source)
        return runtime, jobs

    def wait(self, predicate):
        deadline = time.monotonic()+.8
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.005)
        self.fail('Timed out waiting for input worker')

    def test_startup_held_requires_real_release_and_repress_and_holding_never_repeats(self):
        source = Input(True)
        runtime, jobs = self.runtime(source)
        time.sleep(.08)
        self.assertEqual(jobs, [])
        source.level = False
        time.sleep(.08)
        source.level = True
        self.wait(lambda: len(jobs) == 1)
        time.sleep(.08)
        self.assertEqual(len(jobs), 1)
        self.assertTrue(runtime.snapshot()['gpio_used'])
        self.assertEqual(runtime.snapshot()['input_mode'], 'gpio21')
        # Second debounced physical press cancels, even during cooldown.
        source.level = False; time.sleep(.08)
        source.level = True
        self.wait(jobs[0].cancelled.is_set)
        self.assertEqual(len(jobs), 1)

    def test_stalled_input_read_cancels_without_camera_or_reader_progress(self):
        source = Input(False)
        runtime, jobs = self.runtime(source)
        time.sleep(.08); source.level = True
        self.wait(lambda: len(jobs) == 1)
        source.block.clear()
        self.wait(jobs[0].cancelled.is_set)
        self.assertFalse(runtime.button.snapshot()['enabled'])
        source.block.set()

    def test_read_exception_withdraws_consent_and_cancels(self):
        source = Input(False)
        runtime, jobs = self.runtime(source)
        time.sleep(.08); source.level = True
        self.wait(lambda: len(jobs) == 1)
        source.fault = True
        self.wait(lambda: runtime.snapshot()['input_closed'])
        self.assertTrue(jobs[0].cancelled.is_set())
        self.assertFalse(runtime.snapshot()['consent'])
        self.assertEqual(runtime.snapshot()['fault'], 'Context input unavailable')

    def test_initial_read_failure_never_starts_runtime_workers(self):
        source = Input(); source.fault = True
        frame = fixture_frame()
        runtime = ManualContext(configuration(frame), lambda: (True, False), consent=True, clock=lambda: 1000)
        self.addCleanup(runtime.close)
        with self.assertRaisesRegex(RuntimeError, '^GPIO21 input unavailable$'):
            runtime.start(gpio_input=source)
        self.assertIsNone(runtime._thread)
        self.assertFalse(runtime.snapshot()['consent'])

    def test_observer_requires_opt_in_before_constructing_device(self):
        with patch('edge.context_gpio.GPIO21Input') as factory, patch('sys.stderr', io.StringIO()):
            with self.assertRaises(SystemExit): main(['--output', '/unused/report'])
            factory.assert_not_called()

    def test_observation_report_is_incomplete_on_driver_failure_and_contains_no_exception(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'input.json'
            with patch('edge.context_gpio.GPIO21Input', side_effect=RuntimeError('private detail')), patch('sys.stdout', io.StringIO()):
                self.assertEqual(main(['--observe', '--output', str(path)]), 1)
            report = json.loads(path.read_text())
            self.assertFalse(report['complete'])
            self.assertFalse(report['motor_gpio_used'])
            self.assertFalse(report['context_requests_used'])
            self.assertIsNone(report['gpio_used'])
            self.assertTrue(report['gpio_input_requested'])
            self.assertNotIn('private', path.read_text())

    @unittest.skipUnless(importlib.util.find_spec('backend.context.consumer'), 'Requires unmerged narration dependency PR #41')
    def test_gpio_press_uses_single_narrator_and_second_press_stops_speech(self):
        from test_context_audio import Sink
        source, sink = Input(False), Sink()
        runtime, jobs = self.runtime(source, audio=True, sink=sink)
        time.sleep(.08); source.level = True
        self.wait(lambda: len(jobs) == 1)
        jobs[0].reply = reply(jobs[0].request_id, jobs[0].frame)
        self.wait(lambda: sink.current is not None)
        self.assertIsNone(runtime.button)
        self.assertEqual(runtime.snapshot()['button']['requests'], 1)
        source.level = False; time.sleep(.08)
        source.level = True
        self.wait(lambda: sink.current is None)
        self.assertEqual(len(jobs), 1)
        runtime.close()
        self.assertTrue(sink.closed)

    def test_exact_observer_cli_records_raw_edges_and_closes_input_without_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'input.json'
            device = Mock()
            device.read.side_effect = [False, True, False]
            with patch('edge.context_gpio.GPIO21Input', return_value=device), \
                 patch('time.monotonic', side_effect=[0, 0, .01, .02, 2]), \
                 patch('time.sleep'), patch('sys.stdout', io.StringIO()):
                self.assertEqual(main(['--observe', '--seconds', '1', '--output', str(path)]), 0)
            data = json.loads(path.read_text())
            self.assertTrue(data['complete'])
            self.assertEqual(data['samples'], 3)
            self.assertEqual(data['raw_rising_edges'], 1)
            self.assertEqual(data['raw_falling_edges'], 1)
            self.assertTrue(data['gpio_used'])
            self.assertFalse(data['gpio_input_verified'])
            self.assertFalse(data['physical_audio_accepted'])
            device.close.assert_called_once()
