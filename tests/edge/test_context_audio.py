"""Audio opt-in wiring; real narration cases require draft PR #41 dependency."""
import importlib.util
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

from edge.context_runtime import ManualContext
from test_buttons import Handle, fixture_frame, reply
from test_context_client import configuration
from test_context_runtime import Stream

HAS_NARRATION = importlib.util.find_spec('backend.context.consumer') is not None


class Sink:
    def __init__(self):
        self.current = None
        self.spoken = []
        self.stopped = threading.Event()
        self.closed = False
    def speak(self, text):
        self.current = text
        self.spoken.append(text)
    def stop(self):
        self.current = None
        self.stopped.set()
    def close(self):
        self.stop()
        self.closed = True


class AudioWiringTests(unittest.TestCase):
    def runtime(self, sink=None, factory=None):
        frame = fixture_frame()
        sink = sink if sink is not None else Sink()
        engine = Mock()
        factory = factory if factory is not None else Mock(return_value=engine)
        runtime = ManualContext(configuration(frame), lambda: (True, False), consent=True,
            clock=lambda: 1000, audio=True, speech_sink=sink, narration_factory=factory)
        self.addCleanup(runtime.close)
        return runtime, sink, factory, engine

    def test_audio_owns_one_engine_and_uses_camera_consent_and_original_frame(self):
        runtime, sink, factory, engine = self.runtime()
        self.assertIsNone(runtime.button)  # No second button/client request loop.
        priority, consent = factory.call_args.kwargs['priority'], factory.call_args.kwargs['consent']
        self.assertEqual(priority(), (False, False))
        self.assertTrue(consent())
        runtime.set_camera_ready(True)
        frame = fixture_frame()
        runtime.offer(frame)
        self.assertEqual(factory.call_args.args[0]().metadata, frame.metadata)
        self.assertEqual(priority(), (True, False))
        runtime.command('press')
        runtime.tick()
        engine.sample.assert_called_once_with(True)
        runtime.command('off')
        self.assertFalse(consent())
        self.assertIsNone(runtime.latest())
        self.assertFalse(runtime.command('press'))
        self.assertGreaterEqual(engine.cancel.call_count, 1)
        self.assertIsNone(runtime.snapshot()['audio_used'])

    def test_eof_camera_loss_and_close_cancel_and_release_owned_audio_resources(self):
        runtime, sink, _, engine = self.runtime()
        stream = Stream()
        self.addCleanup(stream.queue.put, '')
        runtime.start(stream)
        self.assertTrue(stream.wait_reads(1))
        engine.start.assert_called_once()
        runtime.set_camera_ready(False)
        stream.queue.put('')
        runtime._input_thread.join(1)
        self.assertTrue(runtime.snapshot()['input_closed'])
        self.assertGreaterEqual(engine.cancel.call_count, 2)
        runtime.close()
        engine.close.assert_called_once()
        self.assertTrue(sink.closed)

    def test_failed_narration_initialization_closes_sink_and_sanitizes_error(self):
        sink = Sink()
        with self.assertRaisesRegex(RuntimeError, '^Context audio unavailable;') as error:
            self.runtime(sink=sink, factory=Mock(side_effect=RuntimeError('private setup detail')))
        self.assertNotIn('private', str(error.exception))
        self.assertTrue(sink.closed)

    def test_failed_audio_stop_records_unknown_and_does_not_interrupt_primary_cleanup(self):
        sink = Sink()
        runtime, _, _, engine = self.runtime(sink=sink)
        engine.close.side_effect = RuntimeError('private process failure')
        sink.close = Mock(side_effect=RuntimeError('private routing detail'))
        runtime.close()
        self.assertEqual(runtime.snapshot()['fault'], 'Audio stop unavailable; inspect device')

    def test_text_default_never_loads_or_constructs_audio_adapters(self):
        frame = fixture_frame()
        runtime = ManualContext(configuration(frame), lambda: (True, False), consent=True,
                                clock=lambda: 1000)
        self.addCleanup(runtime.close)
        self.assertIsNotNone(runtime.button)
        self.assertFalse(runtime.snapshot()['audio_enabled'])
        with self.assertRaises(ValueError):
            ManualContext(configuration(frame), lambda: (True, False), consent=True, speech_sink=Sink())

    def test_missing_narration_dependency_refuses_audio_without_silent_fallback(self):
        frame = fixture_frame()
        with patch.dict(sys.modules, {'backend.context.consumer': None}):
            with self.assertRaisesRegex(RuntimeError, '^Context audio unavailable;'):
                ManualContext(configuration(frame), lambda: (True, False), consent=True, audio=True)


@unittest.skipUnless(HAS_NARRATION, 'Requires unmerged narration dependency PR #41')
class NarrationRuntimeTests(unittest.TestCase):
    def setUp(self):
        from backend.context.consumer import ContextNarration
        self.now, self.hazard = 1000, False
        self.sink, self.jobs = Sink(), []
        def start(request_id, frame):
            handle = Handle()
            self.jobs.append((request_id, frame, handle))
            return handle
        self.runtime = ManualContext(configuration(fixture_frame()), lambda: (True, self.hazard),
            consent=True, clock=lambda: self.now, audio=True, speech_sink=self.sink,
            narration_factory=ContextNarration, client=types.SimpleNamespace(start=start))
        self.addCleanup(self.runtime.close)
        self.runtime.set_camera_ready(True)
        self.runtime.offer(fixture_frame(self.now))

    def press(self):
        self.runtime.command('release')
        self.runtime.tick()
        self.now += 30
        self.runtime.tick()
        self.runtime.command('press')
        self.runtime.tick()
        self.now += 30
        self.runtime.tick()

    def deliver(self):
        request_id, frame, handle = self.jobs[0]
        handle.reply = reply(request_id, frame)
        self.runtime.tick()

    def test_terminal_press_speaks_once_and_manual_cancel_cannot_restart_reply(self):
        self.press()
        self.deliver()
        self.assertEqual(self.sink.spoken, ['AI description, uncertain: Possible chair.'])
        self.runtime.tick()
        self.assertEqual(len(self.jobs), 1)
        self.runtime.command('cancel')
        self.assertIsNone(self.sink.current)
        self.runtime.tick()
        self.assertEqual(len(self.sink.spoken), 1)

    def test_latest_frame_never_renews_audio_capture_expiry(self):
        self.press()
        self.deliver()
        self.now = 8999
        self.runtime.offer(fixture_frame(self.now))
        self.runtime.tick()
        self.assertIsNotNone(self.sink.current)
        self.now = 9000
        self.runtime.offer(fixture_frame(self.now))
        self.runtime.tick()
        self.assertIsNone(self.sink.current)

    def test_hazard_and_off_preempt_without_replaying_on_recovery(self):
        self.press()
        self.deliver()
        self.hazard = True
        self.runtime.tick()
        self.assertIsNone(self.sink.current)
        self.hazard = False
        self.runtime.tick()
        self.assertEqual(len(self.sink.spoken), 1)
        self.runtime.command('off')
        self.assertIsNone(self.runtime.latest())
        self.assertFalse(self.runtime.command('press'))

    def test_independent_worker_stops_audio_when_camera_capture_stalls(self):
        self.press()
        self.deliver()
        stream = Stream()
        self.addCleanup(stream.queue.put, '')
        self.runtime.start(stream)
        self.assertTrue(stream.wait_reads(1))
        self.sink.stopped.clear()
        self.now = 2501
        self.assertTrue(self.sink.stopped.wait(.5))
        self.assertIsNone(self.sink.current)
