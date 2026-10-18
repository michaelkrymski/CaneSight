"""Composition with virtual time and silent speech; optional draft dependency."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest
from edge.menu_bench import MenuBench, SilentMenuSink

HAS_AUDIO = importlib.util.find_spec('backend.context.menu_audio') is not None


@unittest.skipUnless(HAS_AUDIO, 'Requires draft CS-040 fixed menu audio')
class BenchTests(unittest.TestCase):
    def test_terminal_gestures_audio_loss_and_recovery_require_fresh_entry(self):
        now = [0]
        sink = SilentMenuSink()
        bench = MenuBench(sink, synthetic_adapters=True, clock=lambda: now[0])
        self.addCleanup(bench.close)
        def tick(delta): now[0] += delta; bench.tick()
        bench.tick(); tick(30)
        bench.command('press'); tick(30); tick(3000)
        self.assertEqual(bench.core.state, 'menu_entry')
        self.assertIn('does not tell you when to cross', sink.current)
        bench.command('release'); tick(30)
        bench.command('press'); tick(30); bench.command('release'); tick(30)
        self.assertEqual(bench.core.snapshot()['selected'], 'pedestrian_signal')
        bench.command('press'); tick(30); tick(1000)
        self.assertEqual(bench.core.state, 'confirm_release')
        bench.command('release'); tick(30)
        self.assertEqual(bench.core.state, 'active')
        bench.command('audio-off')
        self.assertIsNone(sink.current)
        bench.command('audio-on'); tick(100)
        self.assertNotEqual(bench.core.state, 'active')
        self.assertFalse(bench.snapshot()['context_requests_used'])
        self.assertFalse(bench.snapshot()['automatic_audio_route_detection'])

    def test_default_capabilities_announce_unavailable_without_activation(self):
        now = [0]; sink = SilentMenuSink(); bench = MenuBench(sink, clock=lambda: now[0])
        self.addCleanup(bench.close)
        def cmd(command, advance):
            bench.command(command); now[0] += advance; bench.tick()
        bench.tick(); now[0] = 30; bench.tick()
        cmd('press',30); now[0] += 3000; bench.tick(); cmd('release',30)
        cmd('press',30); cmd('release',30); cmd('press',30)
        now[0] += 1000; bench.tick()
        self.assertEqual(sink.current, 'Crossing observations unavailable.')
        self.assertNotEqual(bench.core.state, 'active')

    @unittest.skipUnless(os.name == 'posix', 'Private report files require POSIX permissions; Windows ACL support is not implemented')
    def test_exact_silent_cli_writes_private_synthetic_report_without_requests(self):
        from edge.menu_bench import main
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'report.json'
            with patch('sys.stdin', io.StringIO('status\nquit\n')), patch('sys.stdout', io.StringIO()):
                self.assertEqual(main(['--simulate-audio','--consent','--synthetic-adapters','--output',str(output)]), 0)
            report = json.loads(output.read_text())
            self.assertTrue(report['complete'])
            self.assertEqual(report['state'], 'closed')
            self.assertEqual(report['scenario_capabilities'], 'synthetic interaction only')
            self.assertFalse(report['context_requests_used'])
            self.assertFalse(report['motor_gpio_used'])
            self.assertFalse(report['physical_audio_accepted'])

    def test_source_loss_announces_unavailable_and_hazard_preempts_without_optional_audio(self):
        now = [0]; sink = SilentMenuSink(); bench = MenuBench(sink, synthetic_adapters=True, clock=lambda: now[0])
        self.addCleanup(bench.close)
        bench.tick(); now[0] = 30; bench.tick()
        bench.command('press'); now[0] += 30; bench.tick(); now[0] += 3000; bench.tick()
        bench.command('source-off')
        self.assertEqual(sink.current, 'Crossing observations unavailable.')
        bench.command('hazard-on')
        self.assertIsNone(sink.current)
        bench.command('source-on'); bench.command('hazard-off')
        self.assertNotEqual(bench.core.state, 'active')

    def test_quit_cannot_start_a_menu_or_reopen_closed_audio(self):
        now = [0]; sink = SilentMenuSink(); bench = MenuBench(sink, synthetic_adapters=True, clock=lambda: now[0])
        self.addCleanup(bench.close)
        bench.tick(); now[0] = 30; bench.tick()
        bench.command('press'); now[0] += 30; bench.tick(); now[0] += 3000
        bench.command('quit')
        self.assertEqual(bench.core.state, 'closed')
        self.assertIsNone(sink.current)
        self.assertEqual(bench.counts['entry'], 0)


class ReportPlatformTests(unittest.TestCase):
    def test_unsupported_report_platform_never_starts_bench_audio_or_gpio(self):
        from edge.menu_bench import main
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'report.json'
            with patch('edge.context_report.REPORT_FILES_SUPPORTED', False), \
                 patch('edge.menu_bench.MenuBench') as bench, \
                 patch('edge.menu_bench.SilentMenuSink') as sink, \
                 patch('edge.context_gpio.GPIO21Input') as gpio, \
                 patch('sys.stdout', new_callable=io.StringIO) as stdout:
                self.assertEqual(main(['--simulate-audio', '--consent', '--gpio21',
                                       '--output', str(output)]), 1)
            bench.assert_not_called()
            sink.assert_not_called()
            gpio.assert_not_called()
            self.assertFalse(output.exists())
            self.assertIn('require a POSIX host', stdout.getvalue())
