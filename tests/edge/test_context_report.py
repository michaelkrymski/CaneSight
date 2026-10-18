"""Private evidence output and diagnostics; no camera, network or sound."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from edge.context_report import ContextRunReport, UnsupportedReportPlatform, bounded_status
from edge import uploader
from edge.context_runtime import ManualContext
from test_buttons import fixture_frame
from test_context_client import configuration


class ReportTests(unittest.TestCase):
    def test_unsupported_platform_refuses_before_path_or_file_access(self):
        report = ContextRunReport()
        with patch('edge.context_report.REPORT_FILES_SUPPORTED', False), \
             patch('edge.context_report.Path') as path, \
             patch('edge.context_report.os.open') as opened, \
             patch('edge.context_report.revision') as revision:
            with self.assertRaisesRegex(UnsupportedReportPlatform, 'require a POSIX host'):
                report.open('unused/run.json', audio=True)
            path.assert_not_called()
            opened.assert_not_called()
            revision.assert_not_called()
        self.assertIsNone(report.file)

    def test_optional_report_remains_disabled_on_unsupported_platform(self):
        with patch('edge.context_report.REPORT_FILES_SUPPORTED', False):
            report = ContextRunReport()
            report.open(None, audio=False)
            report.finish()
            self.assertIsNone(report.file)

    def test_allowlist_drops_credentials_images_device_ids_and_arbitrary_errors(self):
        status = bounded_status(dict(token='private', frame='image', session_id='private',
            fault='private exception', audio_enabled=True, button=dict(requests=3, token='private',
            fault='private error', failed=True, cancelled=-1)))
        self.assertNotIn('private', json.dumps(status))
        self.assertTrue(status['fault_present'])
        self.assertEqual(status['button']['requests'], 3)
        self.assertIsNone(status['button']['failed'])
        self.assertIsNone(status['button']['cancelled'])

    @unittest.skipUnless(os.name == 'posix', 'POSIX private report permissions')
    def test_private_exclusive_output_never_accepts_audio_or_integration_automatically(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'run.json'
            report = ContextRunReport(); report.open(path, audio=True)
            report.capture(Mock(snapshot=lambda: dict(closed=True, token='private')))
            report.finish()
            data = json.loads(path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(data['complete'])
            self.assertFalse(data['physical_audio_accepted'])
            self.assertFalse(data['phone_backend_verified'])
            self.assertNotIn('private', path.read_text())
            with self.assertRaises(FileExistsError): ContextRunReport().open(path, audio=False)
            path.unlink(); path.symlink_to(Path(folder)/'target')
            with self.assertRaises(FileExistsError): ContextRunReport().open(path, audio=False)
            self.assertFalse((Path(folder)/'target').exists())

    @unittest.skipUnless(os.name == 'posix', 'POSIX private report permissions')
    def test_public_directory_and_checkout_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder).chmod(0o755)
            with self.assertRaises(ValueError): ContextRunReport().open(Path(folder)/'run', audio=True)
        with self.assertRaises(ValueError): ContextRunReport().open(Path(uploader.__file__).with_name('run.json'), audio=True)

    @unittest.skipUnless(os.name == 'posix', 'Private report files require POSIX permissions; Windows ACL support is not implemented')
    def test_main_writes_incomplete_sanitized_report_after_startup_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'run.json'
            def fail(report):
                report.open(path, audio=True)
                raise RuntimeError('private credential detail')
            with patch.object(uploader, '_main', side_effect=fail):
                with self.assertRaises(RuntimeError): uploader.main()
            data = json.loads(path.read_text())
            self.assertFalse(data['complete'])
            self.assertEqual(data['outcome'], 'unavailable')
            self.assertNotIn('private', path.read_text())

    @unittest.skipUnless(os.name == 'posix', 'Private report files require POSIX permissions; Windows ACL support is not implemented')
    def test_main_marks_normal_return_separately_from_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'run.json'
            with patch.object(uploader, '_main', side_effect=lambda report: report.open(path, audio=True)):
                uploader.main()
            data = json.loads(path.read_text())
            self.assertTrue(data['complete'])
            self.assertFalse(data['phone_backend_verified'])

    def test_status_command_is_allowlisted_and_does_not_press_button(self):
        messages = []
        frame = fixture_frame()
        runtime = ManualContext(configuration(frame), lambda: (True, False),
            consent=True, clock=lambda: 1000, emit=messages.append)
        self.addCleanup(runtime.close)
        self.assertTrue(runtime.command('status'))
        self.assertEqual(runtime.button.requests, 0)
        self.assertEqual(len(messages), 1)
        self.assertNotIn(configuration(frame)['token'], messages[0])
        self.assertEqual(json.loads(messages[0].removeprefix('Context status '))['button']['requests'], 0)

    def test_report_flag_requires_manual_context_before_camera_or_network(self):
        with patch('sys.argv', ['uploader', '--capture-only', '--context-report', '/unused/run']), \
             patch('sys.stderr', io.StringIO()), patch.object(ContextRunReport, 'open') as opened:
            with self.assertRaises(SystemExit): uploader.main()
            opened.assert_not_called()
