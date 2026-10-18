"""Synthetic speaker bench control/report tests; no audible output."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from backend.context import speaker_bench
from backend.context.pi_speech import EspeakSink


class SilentSink:
    def __init__(self):
        self.current = None
        self.spoken = []
        self.closed = False
    def speak(self, text):
        self.current = text
        self.spoken.append(text)
    def stop(self): self.current = None
    def healthy(self): return True
    def close(self):
        self.stop()
        self.closed = True


class SpeakerBenchTests(unittest.TestCase):
    def test_diagnostic_failure_cannot_skip_audio_cleanup_or_expose_exception(self):
        sink = Mock(spec=EspeakSink)
        sink.diagnostics.side_effect = ValueError('PRIVATE-SENTINEL')
        fixture = dict(complete=True, software_checks_passed=False,
                       operator_reported_all_passed=False, physical_audio_accepted=False)
        with patch.object(speaker_bench, 'EspeakSink', return_value=sink), \
             patch.object(speaker_bench, 'run_bench', return_value=fixture), \
             patch('sys.stdout', io.StringIO()) as output:
            self.assertEqual(speaker_bench.main(['--speak']), 2)
        sink.close.assert_called_once()
        self.assertTrue(json.loads(output.getvalue())['sink_diagnostics_unavailable'])
        self.assertNotIn('PRIVATE-SENTINEL', output.getvalue())

    def run_fixture(self, observation=True):
        sink = SilentSink()
        now = [100.0]
        def pause(seconds):
            now[0] += seconds
            # Real timer remains independent of the main/operator thread.
            threading.Event().wait(.04)
        result = speaker_bench.run_bench(sink, observe=lambda *a: observation,
            emit=lambda *a: None, clock=lambda: now[0], pause=pause, repetitions=1)
        self.assertIsNone(sink.current)
        return sink, result

    def test_all_cases_capture_independent_expiry_and_human_observations(self):
        sink, result = self.run_fixture()
        self.assertEqual([r['case'] for r in result['records']],
            ['manual_cancel', 'hazard', 'unavailable', 'expiry', 'late_result'])
        self.assertEqual(len(sink.spoken), 4)
        self.assertTrue(result['software_checks_passed'])
        self.assertTrue(result['operator_reported_all_passed'])
        self.assertFalse(result['physical_audio_accepted'])
        for key in ('phone_used', 'backend_used', 'gemini_used', 'gpio_used',
                    'bluetooth_disconnect_reconnect_verified'):
            self.assertFalse(result[key])
        self.assertNotIn('audible_latency_ms', json.dumps(result))

    def test_recovery_requires_operator_observations_and_new_ticket(self):
        sink = SilentSink()
        cases = []
        def observe(case, question):
            cases.append(case)
            if case == 'bluetooth_reconnect':
                self.assertIsNone(sink.current)
            return True
        result = speaker_bench.run_bench(sink, observe=observe, emit=lambda *a: None,
            pause=lambda *a: None, bluetooth_recovery=True)
        record = result['records'][-1]
        self.assertEqual(record['case'], 'bluetooth_operator_recovery')
        self.assertTrue(record['software_pass'])
        self.assertTrue(record['operator_pass'])
        self.assertEqual(cases[-3:], ['bluetooth_disconnect', 'bluetooth_reconnect', 'bluetooth_fresh'])
        self.assertFalse(record['automatic_route_detection'])
        self.assertFalse(result['bluetooth_disconnect_reconnect_verified'])
        self.assertFalse(result['physical_audio_accepted'])
        self.assertIsNone(sink.current)

    def test_unknown_recovery_never_starts_fresh_audio(self):
        for answer in (None, False):
            sink = SilentSink()
            cases = []
            def observe(case, question):
                cases.append(case)
                return answer if case == 'bluetooth_reconnect' else True
            result = speaker_bench.run_bench(sink, observe=observe, emit=lambda *a: None,
                pause=lambda *a: None, bluetooth_recovery=True)
            self.assertNotIn('bluetooth_fresh', cases)
            self.assertFalse(result['records'][-1]['operator_pass'])
            self.assertFalse(result['records'][-1]['software_pass'])
            self.assertFalse(result['software_checks_passed'])
            self.assertIsNone(sink.current)

    def test_recovery_interruption_closes_current_narration(self):
        sink = SilentSink()
        def observe(case, question):
            if case == 'bluetooth_reconnect': raise EOFError()
            return True
        with self.assertRaises(EOFError):
            speaker_bench.run_bench(sink, observe=observe, emit=lambda *a: None,
                pause=lambda *a: None, bluetooth_recovery=True)
        self.assertIsNone(sink.current)

    def test_manual_subset_records_only_requested_cases_and_preserves_failed_observations(self):
        for observation in (True, False, None):
            sink = SilentSink()
            result = speaker_bench.run_bench(sink, observe=lambda *a: observation,
                emit=lambda *a: None, pause=lambda *a: None, manual_only=True, repetitions=3)
            self.assertEqual(result['case_selection'], 'manual-only')
            self.assertEqual([r['case'] for r in result['records']], ['manual_cancel']*3)
            self.assertEqual(len(sink.spoken), 3)
            self.assertTrue(result['software_checks_passed'])
            self.assertEqual(result['operator_reported_all_passed'], observation is True)
            self.assertFalse(result['physical_audio_accepted'])
            self.assertIsNone(sink.current)

    def test_manual_subset_refuses_recovery_combination_before_audio(self):
        with patch.object(speaker_bench, 'EspeakSink') as factory, patch('sys.stderr', io.StringIO()):
            with self.assertRaises(SystemExit):
                speaker_bench.main(['--speak', '--manual-only', '--bluetooth-recovery'])
            factory.assert_not_called()

    def test_no_or_unknown_observation_never_becomes_a_pass(self):
        for answer in (False, None):
            with self.subTest(answer=answer):
                _, result = self.run_fixture(answer)
                self.assertTrue(result['software_checks_passed'])
                self.assertFalse(result['operator_reported_all_passed'])

    def test_interrupted_observation_stops_current_speech(self):
        sink = SilentSink()
        def interrupted(*args): raise EOFError()
        with self.assertRaises(EOFError):
            speaker_bench.run_bench(sink, observe=interrupted, emit=lambda *a: None,
                                    pause=lambda *a: None)
        self.assertIsNone(sink.current)

    def test_cli_requires_explicit_speech_opt_in_before_constructing_sink(self):
        with patch.object(speaker_bench, 'EspeakSink') as factory, patch('sys.stderr', io.StringIO()):
            for args in ([], ['--speak', '--repetitions', '0'], ['--speak', '--interrupt-after', 'nan']):
                with self.assertRaises(SystemExit): speaker_bench.main(args)
            factory.assert_not_called()

    @unittest.skipUnless(os.name == 'posix', 'Private Pi report permissions require POSIX')
    def test_private_exclusive_report_and_no_checkout_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root/'report.json'
            with speaker_bench.open_report(target) as report:
                report.write('{}')
            if os.name == 'posix':
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError): speaker_bench.open_report(target)
            with self.assertRaises(ValueError):
                speaker_bench.open_report(Path(speaker_bench.__file__).with_name('fixture-report.json'))

    def test_cli_does_not_automatically_accept_audio_or_hide_unknown_observation(self):
        sink = SilentSink()
        fixture = dict(complete=True, software_checks_passed=True,
                       operator_reported_all_passed=False, physical_audio_accepted=False)
        with patch.object(speaker_bench, 'EspeakSink', return_value=sink), \
             patch.object(speaker_bench, 'run_bench', return_value=fixture), \
             patch('sys.stdout', io.StringIO()) as output:
            self.assertEqual(speaker_bench.main(['--speak']), 2)
            self.assertFalse(json.loads(output.getvalue())['physical_audio_accepted'])
            self.assertTrue(sink.closed)

    @unittest.skipUnless(os.name == 'posix', 'Real speech process fixture requires POSIX')
    def test_exact_cli_flow_with_real_adapter_and_silent_executable_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            executable = root/'silent-speech-fixture'
            executable.write_text(f'#!{sys.executable}\nimport sys,time\nsys.stdin.read()\ntime.sleep(60)\n')
            executable.chmod(0o700)
            report = root/'results.json'
            with patch.object(speaker_bench, 'EspeakSink', side_effect=lambda: EspeakSink(str(executable))), \
                 patch('sys.stdin', io.StringIO('y\ny\ny\ny\ny\n')), patch('sys.stdout', io.StringIO()):
                code = speaker_bench.main(['--speak', '--interrupt-after', '.2', '--output', str(report)])
            result = json.loads(report.read_text())
            self.assertEqual(code, 0)
            self.assertEqual(len(result['records']), 5)
            self.assertTrue(result['complete'])
            self.assertTrue(result['software_checks_passed'])
            self.assertFalse(result['physical_audio_accepted'])
            self.assertIn('sink_diagnostics', result)
            self.assertFalse(result['sink_diagnostics']['closed'])
