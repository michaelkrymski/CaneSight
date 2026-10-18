"""Completed gestures reuse original request/capture/cancellation gates."""
if __package__:
    from . import test_consumer as fixtures
else:
    import test_consumer as fixtures
from backend.context.speech_channels import OptionalSpeechChannels
import unittest


class GestureTests(unittest.TestCase):
    setUp = fixtures.ConsumerTests.setUp
    deliver = fixtures.ConsumerTests.deliver
    def test_completed_gesture_has_one_slot_and_original_expiry(self):
        self.assertTrue(self.consumer.request())
        self.assertFalse(self.consumer.request())
        self.assertEqual(len(self.handles), 1)
        self.deliver()
        self.assertIsNotNone(self.sink.current)
        self.consumer.cancel()
        self.assertFalse(self.consumer.request())
        self.now += 10000
        self.frame = fixtures.generated_frame(self.now)
        self.assertTrue(self.consumer.request())
        self.now += 8000
        self.deliver()
        self.assertIsNone(self.sink.current)

    def test_gesture_cannot_bypass_priority_consent_or_clock(self):
        self.hazard = True
        self.assertFalse(self.consumer.request())
        self.hazard = False; self.consent = False
        self.assertFalse(self.consumer.request())
        self.consent = True; self.now = 2000
        self.assertTrue(self.consumer.request())
        self.now = 1000
        self.assertFalse(self.consumer.request())
        self.assertTrue(self.handles[0].cancelled)


class HealthySink(fixtures.Sink):
    def healthy(self): return True
    def close(self): self.stop()


class ChannelTests(unittest.TestCase):
    def test_idle_stop_never_kills_other_owner_and_replacement_preempts(self):
        sink = HealthySink(); channels = OptionalSpeechChannels(sink)
        channels.menu.speak('fixed menu')
        channels.context.stop()
        self.assertEqual(sink.current, 'fixed menu')
        channels.context.speak('description')
        channels.menu.stop()
        self.assertEqual(sink.current, 'description')
        channels.stop()
        self.assertIsNone(sink.current)
        channels.close()
        self.assertFalse(channels.menu.healthy())
        with self.assertRaises(RuntimeError): channels.menu.speak('late')

    def test_stop_failure_latches_both_channels_without_replay(self):
        sink = HealthySink(); channels = OptionalSpeechChannels(sink)
        channels.menu.speak('fixed menu')
        def fail(): raise RuntimeError('device')
        sink.stop = fail
        with self.assertRaises(RuntimeError): channels.stop()
        self.assertFalse(channels.context.healthy())
        with self.assertRaises(RuntimeError): channels.context.speak('late')
