"""Synthetic OS route evidence, bounded helpers and no Bluetooth hardware."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from backend.context.bluetooth_route import (RouteProbe, BluetoothRouteMonitor,
    MAX_AGE_S, command, target, main)
from backend.context.pi_speech import EspeakSink

SINK = 'bluez_output.01_02_03_04_05_06.1'
DEVICE = '/org/bluez/hci0/dev_01_02_03_04_05_06'


def route():
    return dict(index=42, name=SINK, state='SUSPENDED', mute=False,
                properties={'device.api': 'bluez5'}, volume={'mono': {'value': 65536}})


class ProbeTests(unittest.TestCase):
    def probe(self, entries=None, connected='b true\n'):
        run = Mock(side_effect=[json.dumps([route()] if entries is None else entries), connected])
        probe = RouteProbe(SINK, DEVICE, run=run)
        return probe, run

    def test_connected_suspended_idle_and_running_are_eligible_without_setting_routes(self):
        for state in ('SUSPENDED', 'IDLE', 'RUNNING'):
            data = route(); data['state'] = state
            probe, run = self.probe([data])
            self.assertTrue(probe())
            self.assertEqual(run.call_args_list[0].args[0],
                ['/usr/bin/pactl', '--format=json', 'list', 'sinks'])
            self.assertEqual(run.call_args_list[1].args[0],
                ['/usr/bin/busctl', '--system', 'get-property', 'org.bluez',
                 DEVICE, 'org.bluez.Device1', 'Connected'])

    def test_disconnected_missing_duplicate_muted_zero_volume_or_wrong_api_refused(self):
        for connected in ('b false', '', 'true', 'b true\nPRIVATE'):
            probe, _ = self.probe(connected=connected)
            self.assertFalse(probe())
        for mutation in ({'mute': True}, {'mute': None}, {'state': 'UNKNOWN'},
                         {'properties': {}}, {'volume': {}}, {'volume': {'x': {'value': 0}}},
                         {'volume': {'x': {'value': True}}}, {'name': 'other'}):
            data = route(); data.update(mutation)
            probe, run = self.probe([data])
            self.assertFalse(probe())
            self.assertEqual(run.call_count, 1)
        for entries in ([], [route(), route()]):
            probe, _ = self.probe(entries)
            self.assertFalse(probe())

    def test_live_stream_must_remain_on_the_configured_sink(self):
        for sink, expected in ((42, True), (43, False), ('42', False)):
            run = Mock(side_effect=[json.dumps([route()]), 'b true',
                json.dumps([{'sink': sink, 'properties': {'media.name': 'fixture-stream'}}])])
            probe = RouteProbe(SINK, DEVICE, run=run, stream=lambda: 'fixture-stream')
            self.assertIs(probe(), expected)

    def test_missing_stream_registration_is_bounded_and_duplicate_binding_refused(self):
        now = [0.]
        inputs = []
        def run(args):
            if args[-1] == 'sinks': return json.dumps([route()])
            if args[-1] == 'Connected': return 'b true'
            return json.dumps(inputs)
        probe = RouteProbe(SINK, DEVICE, run=run, stream=lambda: 'fixture-stream', clock=lambda: now[0])
        self.assertTrue(probe())
        now[0] = .200
        self.assertFalse(probe())
        inputs.extend([{'sink': 42, 'properties': {'media.name': 'fixture-stream'}}]*2)
        self.assertFalse(probe())

    def test_target_must_be_bluetooth_and_match_exact_device_address(self):
        for sink, device in [('default', DEVICE), (SINK, '/org/bluez/hci0/dev_FF_FF_FF_FF_FF_FF'),
                             (SINK+'; command', DEVICE), (SINK, DEVICE+'/extra'), (None, DEVICE)]:
            with self.assertRaisesRegex(ValueError, '^Configure matching'):
                target(sink, device)


class MonitorTests(unittest.TestCase):
    def test_failure_diagnostics_preserve_reason_without_reprobing_or_rearming(self):
        run = Mock(side_effect=[json.dumps([route()]), 'b true',
            json.dumps([{'sink': 43, 'properties': {'media.name': 'fixture-stream'}}])])
        probe = RouteProbe(SINK, DEVICE, run=run, stream=lambda: 'fixture-stream')
        m = self.make(probe)
        with self.assertRaises(ValueError): m.start()
        calls = run.call_count
        for _ in range(3):
            diagnostic = m.diagnostics()
            self.assertEqual(diagnostic['failure'], 'probe_rejected')
            self.assertEqual(diagnostic['probe_stage'], 'stream_binding')
            self.assertTrue(diagnostic['fault'])
        self.assertEqual(run.call_count, calls)
        text = json.dumps(diagnostic)
        for private in (SINK, DEVICE, 'fixture-stream'):
            self.assertNotIn(private, text)
        probe.failure_stage = None
        self.assertFalse(m.refresh())
        self.assertEqual(m.diagnostics()['probe_stage'], 'stream_binding')

    def test_query_error_and_stale_cache_have_distinct_closed_diagnostics(self):
        probe = RouteProbe(SINK, DEVICE, run=Mock(side_effect=ValueError('PRIVATE-SENTINEL')))
        m = self.make(probe)
        with self.assertRaises(ValueError): m.start()
        self.assertEqual(m.diagnostics()['failure'], 'probe_query_failed')
        self.assertEqual(m.diagnostics()['probe_stage'], 'sink_query')
        self.assertNotIn('PRIVATE-SENTINEL', json.dumps(m.diagnostics()))
        m.close()
        m = self.make(); m.start(); self.now += MAX_AGE_S+.001
        self.assertFalse(m.ready())
        self.assertEqual(m.diagnostics()['failure'], 'observation_expired')

    def test_untrusted_probe_diagnostic_attribute_cannot_leak_or_prevent_latching(self):
        class Probe:
            def __call__(self): return False
            @property
            def failure_stage(self): raise ValueError('PRIVATE-SENTINEL')
        m = self.make(Probe())
        with self.assertRaises(ValueError): m.start()
        self.assertTrue(m.diagnostics()['fault'])
        self.assertIsNone(m.diagnostics()['probe_stage'])
        self.loss.assert_called_once()

    def make(self, probe=lambda: True):
        self.now = 10.
        self.loss = Mock()
        self.monitor = BluetoothRouteMonitor(probe, self.loss, clock=lambda: self.now)
        self.addCleanup(self.monitor.close)
        return self.monitor

    def test_capture_start_age_expires_and_reconnect_never_rearms(self):
        m = self.make(); m.start()
        self.assertTrue(m.ready())
        self.now += MAX_AGE_S+.001
        self.assertFalse(m.ready())
        self.loss.assert_called_once()
        self.assertFalse(m.refresh())
        self.assertFalse(m.ready())
        with self.assertRaises(ValueError): m.start()

    def test_exact_cache_deadline_is_unavailable(self):
        m = self.make(); self.now = 0.; m.start()
        self.now = MAX_AGE_S
        self.assertFalse(m.ready())
        self.loss.assert_called_once()

    def test_slow_probe_cannot_renew_observation_age(self):
        def probe(): self.now += MAX_AGE_S+.001; return True
        m = self.make(probe)
        with self.assertRaises(ValueError): m.start()
        self.assertFalse(m.ready())
        self.loss.assert_called_once()

    def test_probe_error_and_clock_reversal_or_failure_latch(self):
        for bad in ('probe', 'reverse', 'clock'):
            m = self.make(); m.start()
            if bad == 'probe': m.probe = Mock(side_effect=ValueError('PRIVATE'))
            elif bad == 'reverse': self.now -= 1
            else: m.clock = Mock(side_effect=RuntimeError('PRIVATE'))
            self.assertFalse(m.refresh())
            self.assertFalse(m.ready())
            self.loss.assert_called_once()
            m.close()

    def test_watchdog_cancels_while_probe_is_blocked_and_callback_can_read_state(self):
        entered, release, lost = threading.Event(), threading.Event(), threading.Event()
        calls = [0]
        def probe():
            calls[0] += 1
            if calls[0] > 1:
                entered.set(); release.wait(1)
            return True
        m = self.make(probe)
        def loss():
            self.assertFalse(m.ready())  # Callback is outside the monitor lock.
            lost.set()
        m.on_loss = loss
        try:
            m.start()
            self.assertTrue(entered.wait(.5))
            self.now += MAX_AGE_S+.001
            self.assertTrue(lost.wait(.3))
            release.set()
            self.assertFalse(m.ready())
        finally:
            release.set(); m.close()

    def test_close_suppresses_late_probe_and_never_notifies_after_close(self):
        m = self.make(); m.start(); m.close()
        self.assertFalse(m.refresh())
        self.assertFalse(m.ready())
        self.loss.assert_not_called()


@unittest.skipUnless(os.name == 'posix', 'Owned helper process groups require POSIX')
class CommandTests(unittest.TestCase):
    def test_timeout_oversize_and_nonzero_are_sanitized(self):
        for code in ('import time; time.sleep(10)', 'print("x"*70000)',
                     'import sys; print("PRIVATE"); sys.exit(1)'):
            with self.assertRaisesRegex(ValueError, '^Bluetooth route observation unavailable$'):
                command([sys.executable, '-c', code])
        self.assertEqual(command([sys.executable, '-c', 'print("b true")']).strip(), 'b true')


class CheckCliTests(unittest.TestCase):
    def test_check_requires_opt_in_and_suppresses_configuration_or_helper_details(self):
        with patch('backend.context.bluetooth_route.RouteProbe') as probe, patch('sys.stderr', io.StringIO()):
            with self.assertRaises(SystemExit): main([])
            probe.assert_not_called()
        with patch('backend.context.bluetooth_route.RouteProbe', side_effect=ValueError('PRIVATE-SENTINEL')), \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(['--check']), 1)
        result = json.loads(output.getvalue())
        self.assertFalse(result['complete'])
        self.assertFalse(result['physical_audio_accepted'])
        self.assertNotIn('PRIVATE-SENTINEL', output.getvalue())

    def test_success_is_one_observation_not_monitor_or_audio_acceptance(self):
        with patch('backend.context.bluetooth_route.RouteProbe', return_value=lambda: True), \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(['--check']), 0)
        result = json.loads(output.getvalue())
        self.assertTrue(result['route_observed'])
        self.assertFalse(result['automatic_monitor_running'])
        self.assertFalse(result['physical_audio_accepted'])


class FakeMonitor:
    def __init__(self, probe, on_loss): self.on_loss = on_loss; self.ok = True
    def start(self): return self
    def ready(self): return self.ok
    def close(self): self.ok = False
    def lose(self): self.ok = False; self.on_loss()


@unittest.skipUnless(os.name == 'posix', 'Owned audio process groups require POSIX')
class MonitoredSpeechTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.engine, self.player = root/'engine', root/'player'
        self.engine.write_text('#!'+sys.executable+'\nimport sys,time\nsys.stdin.read()\nsys.stdout.buffer.write(b"fixture wav"); sys.stdout.flush()\ntime.sleep(10)\n')
        self.player.write_text('#!'+sys.executable+'\nimport sys,time\nsys.stdin.buffer.read(1)\ntime.sleep(10)\n')
        self.engine.chmod(0o700); self.player.chmod(0o700)
        self.sink = EspeakSink(str(self.engine), bluetooth_sink=SINK, bluez_device=DEVICE,
            paplay=str(self.player), monitor_factory=FakeMonitor)
        self.addCleanup(self.sink.close)

    def test_loss_kills_both_owned_processes_and_reconnect_cannot_speak(self):
        self.sink.speak('AI description, uncertain: Possible chair.')
        engine, player = self.sink._process, self.sink._playback
        self.assertIn('--device='+SINK, player.args)
        self.assertIn('--stdout', engine.args)
        self.sink._route.lose()
        self.assertIsNotNone(player.poll())
        self.assertIsNotNone(engine.poll())
        self.sink._route.ok = True
        self.assertFalse(self.sink.healthy())
        with self.assertRaises(ValueError): self.sink.speak('Description unavailable.')

    def test_generator_failure_is_preserved_after_owned_process_cleanup(self):
        self.engine.write_text('#!'+sys.executable+'\nimport sys\nsys.stdin.read()\nsys.exit(23)\n')
        self.sink.speak('Description unavailable.')
        self.sink._process.wait(timeout=2)
        self.assertFalse(self.sink.healthy())
        diagnostic = self.sink.diagnostics()
        self.assertEqual(diagnostic['failure'], 'generator_exit')
        self.assertEqual(diagnostic['exit_codes']['generator'], 23)
        self.assertTrue(diagnostic['fault'])
        self.assertTrue(diagnostic['automatic_route_monitoring'])
        for private in (SINK, DEVICE, str(self.engine), str(self.player)):
            self.assertNotIn(private, json.dumps(diagnostic))
        self.sink.close()
        self.assertEqual(self.sink.diagnostics()['exit_codes']['generator'], 23)

    def test_narration_cancels_pending_provider_and_cannot_deliver_after_route_reconnect(self):
        if __package__:
            from . import test_consumer as fixtures
        else:
            import test_consumer as fixtures
        from backend.context.consumer import ContextNarration
        import types
        frame = fixtures.generated_frame(1000)
        handles = []
        def start(request_id, frame):
            handle = fixtures.Handle(request_id, frame)
            handles.append(handle); return handle
        consumer = ContextNarration(lambda: frame, types.SimpleNamespace(start=start), self.sink,
            priority=lambda: (True, False), consent=lambda: True, clock=lambda: 1000)
        self.addCleanup(consumer.close)
        self.assertTrue(consumer.request())
        self.sink._route.lose(); consumer.tick()
        self.assertTrue(handles[0].cancelled)
        self.sink._route.ok = True
        handles[0].value = handles[0].reply
        consumer.tick()
        self.assertFalse(consumer.request())
        self.assertIsNone(self.sink._playback)
        self.assertIsNone(self.sink._process)

    def test_partial_environment_config_refuses_before_process_or_monitor_start(self):
        with patch.dict(os.environ, {'CANESIGHT_BLUETOOTH_SINK': SINK}, clear=True), \
             patch('backend.context.pi_speech.subprocess.Popen') as process:
            with self.assertRaises(ValueError): EspeakSink(str(self.engine))
            process.assert_not_called()
