"""Synthetic button/frame/jobs; no GPIO, microphone, audio or cloud calls."""
import copy
import io
import json
import math
from pathlib import Path
import threading
import unittest

from PIL import Image

from edge.buttons import ContextButton, COOLDOWN_MS
from edge.context_client import ContextError
from edge.uploader import Frame, Mapping

ROOT = Path(__file__).resolve().parents[2]


def fixture_frame(captured=1000):
    output = io.BytesIO()
    Image.new('RGB', (32, 24), 'gray').save(output, 'JPEG')
    jpeg = output.getvalue()
    metadata = json.loads((ROOT/'shared/protocol/v1/examples/frame.json').read_text())
    metadata.update(capture_monotonic_ms=captured, jpeg_bytes=len(jpeg),
                    image={'width': 32, 'height': 24})
    return Frame(metadata, Mapping(), jpeg)


def reply(request_id, frame):
    return {'request_id': request_id, 'frame': copy.deepcopy(frame.metadata),
            'model': 'gemini-fixture', 'description': {'objects': ['chair'], 'uncertain': True},
            'capture_age_bounded': False}


class Handle:
    def __init__(self):
        self.reply = None
        self.error = None
        self.cancelled = threading.Event()
    def poll(self):
        if self.error: raise self.error
        if self.cancelled.is_set(): raise AssertionError('Polled a cancelled request')
        return self.reply
    def cancel(self):
        self.cancelled.set()


class ButtonTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.jobs = []
        self.source = lambda: fixture_frame(self.now - 100)
        def factory(request_id, frame):
            handle = Handle()
            self.jobs.append((self.now, request_id, frame, handle))
            return handle
        self.factory = factory
        self.button = ContextButton(lambda: self.source(), lambda *args: self.factory(*args),
                                    clock=lambda: self.now)
        self.addCleanup(self.button.close)

    def ready(self):
        self.button.set_state(ready=True, consent=True, hazard=False)

    def level(self, pressed):
        self.button.sample(pressed)
        self.now += 30
        self.button.tick()

    def press(self):
        self.level(False)
        self.level(True)

    def test_startup_unknown_consent_and_held_button_do_not_request(self):
        self.press()
        self.assertEqual(self.jobs, [])
        self.ready()
        self.level(True)
        self.now += 20000
        self.button.tick()
        self.assertEqual(self.jobs, [])
        self.press()
        self.assertEqual(len(self.jobs), 1)

    def test_contact_bounce_and_long_hold_produce_one_request(self):
        self.ready()
        self.level(False)
        for pressed in [True, False, True, False, True]:
            self.button.sample(pressed)
            self.now += 5
        self.assertEqual(self.jobs, [])
        self.now += 30
        self.button.tick()
        self.assertEqual(len(self.jobs), 1)
        self.now += 20000
        self.button.sample(True)
        self.button.tick()
        self.assertEqual(len(self.jobs), 1)

    def test_second_press_cancels_outstanding_without_starting_another(self):
        self.ready()
        self.press()
        handle = self.jobs[0][3]
        self.press()
        self.assertTrue(handle.cancelled.is_set())
        self.assertEqual(len(self.jobs), 1)
        handle.reply = reply(self.jobs[0][1], self.jobs[0][2])
        self.button.tick()
        self.assertIsNone(self.button.take_result())

    def test_cancellation_and_health_toggles_never_reset_cooldown(self):
        self.ready()
        self.press()
        first = self.jobs[0][0]
        self.button.cancel()
        self.button.set_state(ready=False, consent=True, hazard=False)
        self.now += 5000
        self.ready()
        self.press()
        self.assertEqual(len(self.jobs), 1)
        self.now = first + COOLDOWN_MS
        self.press()
        self.assertEqual(len(self.jobs), 2)

    def test_repeated_presses_obey_minimum_interval_with_one_outstanding(self):
        self.ready()
        for _ in range(1000): self.press()
        starts = [job[0] for job in self.jobs]
        self.assertGreater(len(starts), 1)
        self.assertLessEqual(len(starts), 7)
        self.assertTrue(all(b-a >= COOLDOWN_MS for a, b in zip(starts, starts[1:])))

    def test_complete_bound_result_is_single_use_and_keeps_capture_time(self):
        self.ready()
        self.press()
        _, request_id, frame, handle = self.jobs[0]
        captured = frame.metadata['capture_monotonic_ms']
        handle.reply = reply(request_id, frame)
        self.now += 100
        value = self.button.take_result()
        self.assertEqual(value['frame']['capture_monotonic_ms'], captured)
        self.assertFalse(value['capture_age_bounded'])
        self.assertEqual(value['description']['objects'], ['chair'])
        self.assertIsNone(self.button.take_result())
        self.assertEqual(self.button.snapshot()['cancelled'], 0)

    def test_original_capture_deadline_expires_pending_and_completed_results(self):
        for completed in (False, True):
            with self.subTest(completed=completed):
                self.now += 20000
                self.ready()
                self.press()
                _, request_id, frame, handle = self.jobs[-1]
                if completed:
                    handle.reply = reply(request_id, frame)
                    self.button.tick()
                self.now = frame.metadata['capture_monotonic_ms'] + 8000
                self.assertIsNone(self.button.take_result())
                self.assertTrue(handle.cancelled.is_set())

    def test_stale_future_and_missing_local_frames_never_start_request(self):
        self.ready()
        for source in (lambda: None, lambda: fixture_frame(self.now-1501),
                       lambda: fixture_frame(self.now+1)):
            self.source = source
            self.press()
        self.assertEqual(self.jobs, [])

    def test_unknown_hazard_consent_and_unavailability_preempt(self):
        for state in ({'ready': False, 'consent': True, 'hazard': False},
                      {'ready': True, 'consent': False, 'hazard': False},
                      {'ready': True, 'consent': True, 'hazard': True},
                      {'ready': True, 'consent': True, 'hazard': None}):
            self.now += 20000
            self.ready()
            self.press()
            handle = self.jobs[-1][3]
            self.button.set_state(**state)
            self.assertTrue(handle.cancelled.is_set())
            self.assertIsNone(self.button.take_result())
            self.now += 20000
            self.button.sample(True)
            self.button.tick()
            self.ready()
            self.level(True)  # Recovery while held cannot dispatch.
            self.assertFalse(self.button.snapshot()['requesting'])

    def test_wrong_request_frame_or_advice_is_suppressed(self):
        for mutate in (lambda v: v.update(request_id='different'),
                       lambda v: v['frame'].update(boot_id='different'),
                       lambda v: v['description'].update(objects=['go forward']),
                       lambda v: v.update(capture_age_bounded=True)):
            self.now += 20000
            self.ready()
            self.press()
            _, request_id, frame, handle = self.jobs[-1]
            handle.reply = reply(request_id, frame)
            mutate(handle.reply)
            self.assertIsNone(self.button.take_result())

    def test_factory_failure_consumes_cooldown_without_echoing_error(self):
        attempts = []
        def fail(*args):
            attempts.append(args)
            raise OSError('private transport detail')
        self.factory = fail
        self.ready()
        self.press()
        self.press()
        self.assertEqual(len(attempts), 1)
        self.assertNotIn('private', str(self.button.snapshot()))

    def test_fatal_auth_error_disables_new_requests(self):
        self.ready()
        self.press()
        self.jobs[0][3].error = ContextError(fatal=True)
        self.button.tick()
        self.now += 20000
        self.ready()
        self.press()
        self.assertEqual(len(self.jobs), 1)
        self.assertIsNotNone(self.button.snapshot()['fault'])

    def test_clock_reversal_exception_or_nonfinite_value_latches_fault(self):
        for value in (900, math.nan, math.inf, True, None, 10**1000):
            with self.subTest(clock_type=type(value).__name__):
                button = ContextButton(lambda: fixture_frame(1000), self.factory, clock=lambda: self.now)
                self.now = 1000
                button.tick()
                self.now = value
                button.tick()
                self.assertIsNotNone(button.snapshot()['fault'])
                self.now = 2000
                button.set_state(ready=True, consent=True, hazard=False)
                self.assertFalse(button.snapshot()['enabled'])
                button.close()
        def broken(): raise RuntimeError('clock failed')
        button = ContextButton(self.source, self.factory, clock=broken)
        button.tick()
        self.assertIsNotNone(button.snapshot()['fault'])
        button.close()

    def test_independent_timer_cancels_without_further_input_or_capture(self):
        self.ready()
        self.press()
        handle = self.jobs[0][3]
        self.button.start()
        self.now = self.jobs[0][2].metadata['capture_monotonic_ms'] + 8000
        self.assertTrue(handle.cancelled.wait(1))
        self.assertIsNone(self.button.take_result())

    def test_invalid_input_cancels_and_close_prevents_future_dispatch(self):
        self.ready()
        self.press()
        handle = self.jobs[0][3]
        self.button.sample(None)
        self.assertTrue(handle.cancelled.is_set())
        self.button.close()
        self.now += 20000
        self.ready()
        self.press()
        self.assertEqual(len(self.jobs), 1)

    def test_poll_time_or_clock_reversal_cannot_deliver_stale_result(self):
        for reversal in (False, True):
            with self.subTest(reversal=reversal):
                # A separate controller allows recovery only in the nonfault case.
                self.now = 1000
                button = ContextButton(lambda: fixture_frame(1000), self.factory, clock=lambda: self.now)
                self.addCleanup(button.close)
                button.set_state(ready=True, consent=True, hazard=False)
                button.sample(False)
                self.now = 1030
                button.tick()
                button.sample(True)
                self.now = 1060
                button.tick()
                _, request_id, frame, handle = self.jobs[-1]
                def delayed_poll():
                    self.now = 900 if reversal else 9000
                    return reply(request_id, frame)
                handle.poll = delayed_poll
                self.assertIsNone(button.take_result())
                self.assertTrue(handle.cancelled.is_set())

    def test_time_spent_getting_frame_does_not_make_an_old_capture_fresh(self):
        self.ready()
        def delayed_source():
            frame = fixture_frame(self.now - 100)
            self.now += 2000
            return frame
        self.source = delayed_source
        self.press()
        self.assertEqual(self.jobs, [])

    def test_factory_clock_failure_cancels_its_new_handle(self):
        self.ready()
        def failing_clock_factory(request_id, frame):
            handle = Handle()
            self.jobs.append((self.now, request_id, frame, handle))
            self.now -= 200
            return handle
        self.factory = failing_clock_factory
        self.press()
        self.assertTrue(self.jobs[0][3].cancelled.is_set())
        self.assertIsNotNone(self.button.snapshot()['fault'])

    def test_failed_cancellation_prevents_another_outstanding_request(self):
        self.ready()
        self.press()
        def failed_cancel():
            raise RuntimeError('private adapter detail')
        self.jobs[0][3].cancel = failed_cancel
        self.button.cancel()
        self.now += 20000
        self.ready()
        self.press()
        self.assertEqual(len(self.jobs), 1)
        self.assertIsNotNone(self.button.snapshot()['fault'])
        self.assertNotIn('private adapter', str(self.button.snapshot()))


if __name__ == '__main__': unittest.main()
