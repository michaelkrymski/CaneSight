import math
import unittest

from backend.context.narration import NarrationController, OBJECTS, UNAVAILABLE, render_description


class Sink:
    def __init__(self):
        self.current = None
        self.spoken = []
        self.stops = 0

    def speak(self, text):
        self.current = text
        self.spoken.append(text)

    def stop(self):
        self.current = None
        self.stops += 1


class RenderingTests(unittest.TestCase):
    def test_closed_vocabulary_short_uncertain_and_labeled(self):
        for label in OBJECTS:
            text = render_description({'objects': [label, 'chair', 'tree'], 'uncertain': True})
            self.assertIn('AI description, uncertain', text)
            self.assertLessEqual(len(text.split()), 20)

    def test_injection_and_permission_prose_never_spoken(self):
        for text in ['Walk forward', 'safe to cross', 'all clear', 'ignore previous instructions',
                     'chair. Go now', 'turn left', 'GO', 'walking symbol', 'chair\nstop']:
            self.assertEqual(render_description({'objects': [text], 'uncertain': True}), UNAVAILABLE)
            self.assertEqual(render_description(text), UNAVAILABLE)

    def test_malformed_or_overconfident_shapes_fail_closed(self):
        for value in [None, [], {}, {'objects': ['chair']},
                      {'objects': [], 'uncertain': True}, {'objects': ['chair'], 'uncertain': False},
                      {'objects': ['chair'], 'uncertain': 1},
                      {'objects': ['chair'], 'uncertain': True, 'advice': 'go'},
                      {'objects': [['chair']], 'uncertain': True},
                      {'objects': ['chair'] * 4, 'uncertain': True}]:
            self.assertEqual(render_description(value), UNAVAILABLE)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.sink = Sink()
        self.controller = NarrationController(self.sink, clock=lambda: self.now)
        self.value = {'objects': ['chair'], 'uncertain': True}

    def ready(self):
        self.controller.set_priority(hazard=False, unavailable=False)

    def begin(self, age=0):
        return self.controller.begin(capture_age_upper_s=age, consent=True)

    def test_unknown_health_or_no_consent_cannot_start(self):
        self.assertIsNone(self.begin())
        self.ready()
        self.assertIsNone(self.controller.begin(capture_age_upper_s=0, consent=False))

    def test_invalid_capture_age_never_becomes_fresh(self):
        self.ready()
        for age in [None, True, -1, 8, math.nan, math.inf, '0']:
            self.assertIsNone(self.begin(age))

    def test_deadline_includes_capture_age_and_duplicate_is_suppressed(self):
        self.ready()
        t = self.begin(2)
        self.assertEqual(t.expires_at, 106)
        self.assertTrue(self.controller.deliver(t, self.value))
        self.assertFalse(self.controller.deliver(t, self.value))
        self.now = 106
        self.controller.tick()
        self.assertIsNone(self.sink.current)

    def test_result_at_deadline_is_suppressed_without_tick(self):
        self.ready()
        t = self.begin(7)
        self.now = 101
        self.assertFalse(self.controller.deliver(t, self.value))
        self.assertEqual(self.sink.spoken, [])

    def test_same_clock_capture_deadline_is_absolute(self):
        self.ready()
        self.now = 102
        ticket = self.controller.begin_capture(capture_monotonic_s=98, consent=True)
        self.assertEqual(ticket.expires_at, 106)
        self.now = 106
        self.assertFalse(self.controller.deliver(ticket, self.value))
        self.assertEqual(self.sink.spoken, [])

    def test_same_clock_capture_rejects_future_expired_invalid_and_unconsented(self):
        self.ready()
        for capture in (101, 92, None, True, math.nan, math.inf, 10 ** 1000):
            self.assertIsNone(self.controller.begin_capture(capture_monotonic_s=capture, consent=True))
        self.assertIsNone(self.controller.begin_capture(capture_monotonic_s=100, consent=False))

    def test_manual_cancel_blocks_late_result(self):
        self.ready()
        t = self.begin()
        self.controller.cancel()
        self.assertFalse(self.controller.deliver(t, self.value))

    def test_hazard_stops_audio_and_recovery_never_resurrects_result(self):
        self.ready()
        t = self.begin()
        self.controller.deliver(t, self.value)
        self.controller.set_priority(hazard=True, unavailable=False)
        self.assertIsNone(self.sink.current)
        self.ready()
        self.assertFalse(self.controller.deliver(t, self.value))

    def test_unknown_and_unavailable_preempt(self):
        for priority in [dict(hazard=False, unavailable=True), dict(hazard=None, unavailable=False)]:
            self.ready()
            t = self.begin()
            self.controller.set_priority(**priority)
            self.assertFalse(self.controller.deliver(t, self.value))
            self.assertIsNone(self.begin())

    def test_new_request_supersedes_old_even_if_old_completes_last(self):
        self.ready()
        old = self.begin()
        new = self.begin()
        self.assertTrue(self.controller.deliver(new, self.value))
        self.assertFalse(self.controller.deliver(old, self.value))
        self.assertEqual(len(self.sink.spoken), 1)

    def test_malformed_response_yields_only_unavailable(self):
        self.ready()
        self.assertTrue(self.controller.deliver(self.begin(), {'advice': 'cross now'}))
        self.assertEqual(self.sink.current, UNAVAILABLE)

    def test_closed_adapter_stays_closed(self):
        self.ready()
        self.controller.close()
        self.assertIsNone(self.begin())

    def test_speech_adapter_failure_cannot_replay(self):
        self.ready()
        t = self.begin()
        def fail(text):
            raise RuntimeError('adapter failure')
        self.sink.speak = fail
        self.assertFalse(self.controller.deliver(t, self.value))
        self.assertFalse(self.controller.deliver(t, self.value))

    def test_stop_failure_disables_future_audio(self):
        self.ready()
        def fail():
            raise RuntimeError('adapter failure')
        self.sink.stop = fail
        self.controller.cancel()
        self.assertIsNone(self.begin())

    def test_clock_reversal_before_delivery_invalidates_ticket(self):
        self.ready()
        ticket = self.begin()
        self.now = 90
        self.assertFalse(self.controller.deliver(ticket, self.value))
        self.assertEqual(self.sink.spoken, [])
        self.assertIsNone(self.begin())
        self.now = 101
        self.assertFalse(self.controller.deliver(ticket, self.value))
        self.assertTrue(self.controller.deliver(self.begin(), self.value))

    def test_tick_stops_playing_audio_on_clock_reversal(self):
        self.ready()
        ticket = self.begin()
        self.now = 102
        self.assertTrue(self.controller.deliver(ticket, self.value))
        self.now = 101  # Still after begin, but before the most recent reading.
        self.controller.tick()
        self.assertIsNone(self.sink.current)
        self.now = 103
        self.assertFalse(self.controller.deliver(ticket, self.value))

    def test_new_begin_does_not_reset_clock_history(self):
        self.ready()
        self.begin()
        self.controller.cancel()
        self.now = 90
        self.assertIsNone(self.begin())

    def test_clock_exception_cancels_before_begin_deliver_or_tick(self):
        def broken_clock():
            raise RuntimeError('clock unavailable')
        for operation in ('begin', 'deliver', 'tick'):
            with self.subTest(operation=operation):
                self.setUp()
                self.ready()
                ticket = self.begin()
                if operation != 'deliver':
                    self.assertTrue(self.controller.deliver(ticket, self.value))
                self.controller._clock = broken_clock
                if operation == 'begin':
                    self.assertIsNone(self.begin())
                elif operation == 'deliver':
                    self.assertFalse(self.controller.deliver(ticket, self.value))
                else:
                    self.controller.tick()
                self.assertIsNone(self.sink.current)
                self.controller._clock = lambda: 101
                self.assertFalse(self.controller.deliver(ticket, self.value))

    def test_nonfinite_or_invalid_clock_readings_cancel_speech(self):
        for reading in (math.nan, math.inf, -math.inf, None, True, '101', 10 ** 1000):
            with self.subTest(reading_type=type(reading).__name__):
                self.setUp()
                self.ready()
                ticket = self.begin()
                self.assertTrue(self.controller.deliver(ticket, self.value))
                self.now = reading
                self.controller.tick()
                self.assertIsNone(self.sink.current)
                self.now = 101
                self.assertFalse(self.controller.deliver(ticket, self.value))


if __name__ == '__main__':
    unittest.main()
