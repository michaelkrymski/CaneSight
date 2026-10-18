"""Synthetic executable fixtures exercise speech process I/O/kill, no audio."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

from backend.context.pi_speech import EspeakSink, permitted_text


@unittest.skipUnless(os.name == 'posix', 'Pi speech process groups require POSIX')
class PiSpeechTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.record = self.root/'record.json'
        self.binary = self.root/'fixture-espeak'
        self.text = 'AI description, uncertain: Possible chair.'

    def executable(self, *, fail=False):
        script = (f'#!{sys.executable}\nimport json, pathlib, sys, time\n'
            f'pathlib.Path({str(self.record)!r}).write_text(json.dumps(dict(args=sys.argv[1:],text=sys.stdin.read())))\n'
            + ('sys.exit(7)\n' if fail else 'time.sleep(60)\n'))
        self.binary.write_text(script)
        self.binary.chmod(0o700)
        sink = EspeakSink(str(self.binary))
        self.addCleanup(sink.close)
        return sink

    def await_record(self):
        deadline = time.monotonic()+2
        while not self.record.exists():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.005)
        return json.loads(self.record.read_text())

    def test_text_is_bounded_stdin_and_cancel_kills_reaps_only_owned_process(self):
        sink = self.executable()
        sink.speak(self.text)
        process = sink._process
        record = self.await_record()
        self.assertEqual(record, dict(args=['--stdin'], text=self.text))
        self.assertIsNone(process.poll())
        started = time.monotonic()
        sink.stop()
        self.assertLess(time.monotonic()-started, .5)
        self.assertIsNotNone(process.poll())
        self.assertIsNone(sink._process)
        self.assertTrue(sink.healthy())

    def test_replacement_and_close_cannot_leave_queued_or_resurrected_speech(self):
        sink = self.executable()
        sink.speak(self.text)
        first = sink._process
        self.await_record()
        sink.speak('Description unavailable.')
        second = sink._process
        self.assertIsNot(first, second)
        self.assertIsNotNone(first.poll())
        sink.close()
        self.assertIsNotNone(second.poll())
        self.assertFalse(sink.healthy())
        with self.assertRaises(ValueError): sink.speak(self.text)

    def test_engine_failure_latches_unavailable_without_retries_or_error_text(self):
        sink = self.executable(fail=True)
        sink.speak(self.text)
        self.await_record()
        deadline = time.monotonic()+2
        while sink.healthy():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.005)
        with self.assertRaisesRegex(ValueError, '^Speech unavailable$'):
            sink.speak(self.text)
        self.assertIsNone(sink._process)

    def test_non_template_or_shell_like_text_never_starts_process(self):
        sink = self.executable()
        for text in ('go forward', 'safe to cross', '<speak>chair</speak>',
                     'AI description, uncertain: Possible chair; $(touch file).',
                     'AI description, uncertain: Possible chair and chair.', 'x'*1000, None):
            self.assertFalse(permitted_text(text))
            with self.assertRaises(ValueError): sink.speak(text)
        self.assertFalse(self.record.exists())
        self.assertIsNone(sink._process)

    def test_missing_or_relative_engine_fails_before_audio_activation(self):
        for executable in ('espeak-ng', str(self.root/'missing'), str(self.root)):
            with self.assertRaises(ValueError): EspeakSink(executable)
