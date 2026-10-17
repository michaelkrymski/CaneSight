"""Manual terminal adapter and uploader integration; all devices are synthetic."""
import copy
import io
import queue
import runpy
import threading
import types
import unittest
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from unittest.mock import Mock, patch

from PIL import Image

from edge import uploader
from edge.context_runtime import ManualContext, policy_priority
from test_buttons import Handle, fixture_frame, reply
from test_context_client import configuration


class Stream:
    def __init__(self):
        self.queue = queue.Queue()
        self.condition = threading.Condition()
        self.reads = 0
    def readline(self, limit):
        if limit != 65: raise AssertionError('Input must be bounded')
        with self.condition:
            self.reads += 1
            self.condition.notify_all()
        return self.queue.get()
    def wait_reads(self, count):
        with self.condition:
            return self.condition.wait_for(lambda: self.reads >= count, timeout=1)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.ready, self.hazard = True, False
        self.messages, self.jobs = [], []
        def start(request_id, frame):
            handle = Handle()
            self.jobs.append((request_id, frame, handle))
            return handle
        frame = fixture_frame(self.now)
        self.runtime = ManualContext(configuration(frame), lambda: (self.ready, self.hazard),
            consent=True, clock=lambda: self.now, client=types.SimpleNamespace(start=start),
            emit=self.messages.append)
        self.addCleanup(self.runtime.close)
        self.runtime.set_camera_ready(True)
        self.runtime.offer(frame)

    def press(self):
        self.runtime.tick()
        self.now += 30
        self.runtime.tick()
        self.runtime.command('press')
        self.runtime.tick()
        self.now += 30
        self.runtime.tick()

    def test_manual_press_uses_original_frame_and_only_prints_closed_uncertain_labels(self):
        self.press()
        request_id, frame, handle = self.jobs[0]
        self.assertEqual(frame.metadata['capture_monotonic_ms'], 1000)
        handle.reply = reply(request_id, frame)
        self.runtime.tick()
        self.assertEqual(self.messages, ['Context (manual input; AI; uncertain): possible chair.'])
        self.runtime.tick()
        self.assertEqual(len(self.messages), 1)
        self.assertNotIn(configuration(frame)['token'], str(self.runtime.snapshot()))

    def test_unknown_primary_state_or_hazard_preempts_and_does_not_resume_held_input(self):
        self.press()
        handle = self.jobs[0][2]
        self.hazard = None
        self.runtime.tick()
        self.assertTrue(handle.cancelled.is_set())
        self.hazard = False
        self.now += 11000
        self.runtime.offer(fixture_frame(self.now))
        self.runtime.tick()
        self.now += 40
        self.runtime.tick()
        self.assertEqual(len(self.jobs), 1)
        self.assertEqual(self.messages, [])

    def test_stalled_camera_or_explicit_loss_cancels_request(self):
        self.press()
        handle = self.jobs[0][2]
        self.now = 2501
        self.runtime.tick()
        self.assertTrue(handle.cancelled.is_set())
        self.runtime.set_camera_ready(False)
        self.assertIsNone(self.runtime.latest())

    def test_latest_frame_replacement_never_retimes_the_inflight_request(self):
        self.press()
        request_id, frame, handle = self.jobs[0]
        self.now = 1400
        newer = fixture_frame(1400)
        newer.metadata['frame_id'] = 'newer-frame'
        self.runtime.offer(newer)
        handle.reply = reply(request_id, frame)
        self.runtime.tick()
        self.assertEqual(frame.metadata['capture_monotonic_ms'], 1000)
        self.assertEqual(len(self.messages), 1)

    def test_consent_off_purges_frame_cancels_and_cannot_be_reenabled_by_input(self):
        self.press()
        self.assertTrue(self.runtime.command('off'))
        self.assertTrue(self.jobs[0][2].cancelled.is_set())
        self.assertIsNone(self.runtime.latest())
        self.assertFalse(self.runtime.command('press'))
        self.runtime.offer(fixture_frame(self.now))
        self.assertIsNone(self.runtime.latest())
        self.assertFalse(self.runtime.snapshot()['consent'])

    def test_foreign_epoch_and_mutable_source_metadata_cannot_replace_original(self):
        frame = fixture_frame(self.now)
        self.runtime.offer(frame)
        frame.metadata['capture_monotonic_ms'] = 900000
        self.assertEqual(self.runtime.latest().metadata['capture_monotonic_ms'], 1000)
        frame.metadata['boot_id'] = 'different-boot'
        with self.assertRaises(ValueError): self.runtime.offer(frame)
        self.assertFalse(self.runtime.snapshot()['consent'])

    def test_module_entry_frame_is_normalized_without_retiming(self):
        entry = runpy.run_path(uploader.__file__, run_name='uploader_entry_fixture')
        frame = fixture_frame(self.now)
        entry_frame = entry['Frame'](frame.metadata, entry['Mapping'](), frame.jpeg)
        self.assertNotIsInstance(entry_frame, uploader.Frame)
        self.runtime.offer(entry_frame)
        stored = self.runtime.latest()
        self.assertIsInstance(stored, uploader.Frame)
        self.assertEqual(stored.metadata, frame.metadata)
        self.assertEqual(stored.jpeg, frame.jpeg)
        self.press()
        self.assertEqual(self.jobs[0][1].metadata, frame.metadata)

    def test_bounded_input_discards_long_lines_and_never_echoes_pasted_data(self):
        stream = Stream()
        self.addCleanup(stream.queue.put, '')
        self.runtime.start(stream)
        self.assertTrue(stream.wait_reads(1))
        stream.queue.put('private-token-like-input' * 3)
        self.assertTrue(stream.wait_reads(2))
        stream.queue.put('press\n')  # Remainder of long line: must be drained.
        self.assertTrue(stream.wait_reads(3))
        self.now += 40
        self.runtime.tick()
        self.assertEqual(self.jobs, [])
        self.assertEqual(self.messages, [])
        stream.queue.put('')
        self.runtime._input_thread.join(1)
        self.assertTrue(self.runtime.snapshot()['input_closed'])
        self.assertIsNone(self.runtime.latest())

    def test_input_failure_or_close_never_restarts_context(self):
        class Broken:
            def readline(self, limit): raise OSError('private device detail')
        self.runtime.start(Broken())
        self.runtime._input_thread.join(1)
        self.assertTrue(self.runtime.snapshot()['input_closed'])
        self.runtime.close()
        self.assertFalse(self.runtime.command('press'))
        self.assertEqual(self.messages, [])


class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(fault=None, armed=True, health={'depth': 'fresh'},
            hazards={'left': 'not-nearby-observed', 'center': 'not-nearby-observed',
                     'right': 'not-nearby-observed'})
        self.observation = types.SimpleNamespace(message={'seq': 12}, deadline_ms=1400)
        self.policy = types.SimpleNamespace(lock=threading.RLock(), closed=False,
            snapshot=lambda: copy.deepcopy(self.state), phone_id='phone', last_seq=12,
            last_deadline=1400, gate=types.SimpleNamespace(lock=threading.RLock(), current=lambda *a: self.observation))
        self.receiver = types.SimpleNamespace(connected=True, error=None)
        self.sender = types.SimpleNamespace(error=None)
        self.watchdog = types.SimpleNamespace(lock=threading.RLock(), deadline=lambda: 1250)

    def current(self):
        return policy_priority(self.policy, self.receiver, self.sender, self.watchdog)

    def test_known_priority_and_observed_hazard_are_separate(self):
        self.assertEqual(self.current(), (True, False))
        self.state['hazards']['center'] = 'nearby'
        self.assertEqual(self.current(), (True, True))

    def test_unknown_expired_unprocessed_and_unverified_state_is_unavailable(self):
        for change in (lambda: self.state['hazards'].update(left='unknown'),
                       lambda: setattr(self.policy, 'last_seq', 11),
                       lambda: setattr(self.policy, 'last_deadline', 1300),
                       lambda: setattr(self, 'observation', None),
                       lambda: setattr(self.receiver, 'connected', False),
                       lambda: setattr(self.sender, 'error', 'unavailable'),
                       lambda: setattr(self.watchdog, 'deadline', lambda: None),
                       lambda: self.state['health'].update(depth='unconfigured')):
            self.setUp()
            change()
            self.assertEqual(self.current(), (False, True))

    def test_contended_policy_gate_or_watchdog_is_immediately_unavailable(self):
        for lock in (self.policy.lock, self.policy.gate.lock, self.watchdog.lock):
            held, release, finished = threading.Event(), threading.Event(), threading.Event()
            results = []
            def hold():
                with lock:
                    held.set()
                    release.wait(2)
            def read():
                results.append(self.current())
                finished.set()
            holder = threading.Thread(target=hold, daemon=True)
            reader = threading.Thread(target=read, daemon=True)
            holder.start()
            try:
                self.assertTrue(held.wait(1))
                reader.start()
                self.assertTrue(finished.wait(.5), 'Priority reader blocked on a stalled worker')
                self.assertEqual(results, [(False, True)])
            finally:
                release.set()
                holder.join(1)
                if reader.ident is not None:
                    reader.join(1)
            self.assertEqual(self.current(), (True, False))


class UploaderContextTests(unittest.TestCase):
    def run_uploader(self, *, context_enabled=True, camera_error=False, audio=False, runtime_error=False):
        frame_request = Mock()
        frame_request.get_metadata.return_value = {'SensorTimestamp': 1000000000, 'ExposureTime': 1000}
        frame_request.make_image.return_value = Image.new('RGB', (640, 480), 'gray')
        camera = Mock()
        camera.capture_request.return_value = frame_request
        if camera_error: camera.start.side_effect = RuntimeError('synthetic startup failure')
        receiver = Mock(error=None, phone_binding=None, accepted=0, rejected=0, expired=0)
        watchdog = Mock(fault=None)
        policy = Mock()
        policy.snapshot.return_value = {'output_mode': 'simulation'}
        scheduler = Mock()
        scheduler.start.return_value = scheduler
        scheduler.snapshot.return_value = {'outputs': {'left': False, 'right': False}}
        runtime = Mock()
        runtime.snapshot.return_value = {'input_mode': 'manual-terminal', 'gpio_used': False}
        def session(path, source, boot):
            return dict(base_url='https://testserver', token='fixture-pi-token-never-deploy-000001',
                        session_id='session', source_id=source, boot_id=boot, mode='live')
        args = ['uploader', '--frames', '1', '--session-file', '/private/synthetic-session']
        if context_enabled:
            args += ['--receive-vision', '--simulate-policy', '--phone-binding-file', '/private/synthetic-binding',
                     '--context-stdin', '--context-consent']
        if audio:
            args += ['--context-audio']
        with ExitStack() as stack:
            stack.enter_context(patch('sys.argv', args))
            stack.enter_context(patch.dict('sys.modules', {'picamera2': types.SimpleNamespace(Picamera2=lambda: camera)}))
            stack.enter_context(patch.object(uploader, 'load_session', side_effect=session))
            stack.enter_context(patch.object(uploader, 'clock_ms', return_value=1000))
            stack.enter_context(patch.object(uploader.time, 'sleep'))
            stack.enter_context(patch.object(uploader, 'Transport'))
            stack.enter_context(patch('edge.receiver.VisionReceiver', return_value=receiver))
            stack.enter_context(patch('edge.policy.PhoneBinding.load', return_value=object()))
            stack.enter_context(patch('edge.haptics.HapticScheduler', return_value=scheduler))
            stack.enter_context(patch('edge.watchdog.PolicyWatchdog', return_value=watchdog))
            stack.enter_context(patch('edge.policy.LocalPolicy', return_value=policy))
            factory = stack.enter_context(patch('edge.context_runtime.ManualContext', return_value=runtime))
            if runtime_error:
                factory.side_effect = RuntimeError('synthetic audio startup failure')
            stack.enter_context(redirect_stdout(io.StringIO()))
            if camera_error or runtime_error:
                with self.assertRaisesRegex(RuntimeError, 'synthetic.*failure'):
                    uploader.main()
            else:
                uploader.main()
        if runtime_error:
            policy.close.assert_called_once()
            scheduler.close.assert_called_once()
            watchdog.close.assert_called_once()
            receiver.stop.assert_called_once()
        return runtime, factory, camera

    def test_uploader_binds_same_process_frame_clock_and_cleans_up(self):
        runtime, factory, camera = self.run_uploader()
        session = factory.call_args.args[0]
        self.assertEqual(runtime.offer.call_count, 1)
        frame = runtime.offer.call_args.args[0]
        for key in ('session_id', 'source_id', 'boot_id', 'mode'):
            self.assertEqual(frame.metadata[key], session[key])
        self.assertEqual(frame.metadata['capture_monotonic_ms'], 999)
        self.assertTrue(factory.call_args.kwargs['consent'])
        runtime.set_camera_ready.assert_called_once_with(True)
        runtime.close.assert_called_once()
        camera.close.assert_called_once()

    def test_context_disabled_by_default_and_closed_on_camera_start_failure(self):
        _, factory, _ = self.run_uploader(context_enabled=False)
        factory.assert_not_called()
        runtime, _, _ = self.run_uploader(camera_error=True)
        runtime.close.assert_called_once()
        runtime.offer.assert_not_called()

    def test_context_flags_require_explicit_consent_policy_and_phone_binding(self):
        for extra in (['--context-consent'], ['--context-stdin'],
                      ['--context-stdin', '--context-consent'], ['--context-audio']):
            with patch('sys.argv', ['uploader', '--session-file', '/private/session'] + extra), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error: uploader.main()
                self.assertEqual(error.exception.code, 2)

    def test_audio_requires_explicit_flag_and_uses_existing_runtime_cleanup(self):
        runtime, factory, _ = self.run_uploader(audio=True)
        self.assertIs(factory.call_args.kwargs['audio'], True)
        runtime.start.assert_called_once()
        runtime.close.assert_called_once()
        _, factory, _ = self.run_uploader()
        self.assertNotIn('audio', factory.call_args.kwargs)

    def test_failed_audio_startup_unwinds_primary_components_before_camera(self):
        runtime, factory, camera = self.run_uploader(audio=True, runtime_error=True)
        self.assertIs(factory.call_args.kwargs['audio'], True)
        camera.start.assert_not_called()
        runtime.start.assert_not_called()


if __name__ == '__main__': unittest.main()
