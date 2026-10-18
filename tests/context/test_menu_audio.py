"""Closed phrase/availability/preemption tests with a silent sink."""
import unittest
from backend.context.menu_audio import ALL_PHRASES, FixedMenuAudio, LABELS, phrase
from backend.context.pi_speech import permitted_text


class Sink:
    def __init__(self): self.current = None; self.spoken = []; self.ok = True
    def stop(self): self.current = None
    def speak(self, text): self.current = text; self.spoken.append(text)
    def healthy(self): return self.ok


class MenuAudioTests(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.epoch = ('session','pi','boot','replay')
        self.sink = Sink()
        self.audio = FixedMenuAudio(self.sink, clock=lambda: self.now)
        self.audio.update(audio_ready=True, priority_clear=True, epoch=self.epoch)

    def say(self, kind, generation=1, scenario=None):
        return self.audio.speak(kind, generation=generation, epoch=self.epoch, scenario=scenario)

    def test_closed_fixed_words_and_all_three_labels_only(self):
        for text in ALL_PHRASES: self.assertTrue(permitted_text(text))
        self.assertTrue(self.say('entry'))
        for scenario in LABELS:
            self.assertTrue(self.say('selection', scenario=scenario))
            self.assertEqual(self.sink.current, LABELS[scenario])
        self.assertIsNone(phrase('selection', 'safe to cross'))
        self.assertFalse(permitted_text('All cars stopped. Go.'))
        self.assertFalse(self.say('raw provider prose'))
        self.assertIsNone(self.sink.current)

    def test_no_silent_activation_or_old_replay_after_output_loss(self):
        self.assertFalse(self.say('confirmation', scenario='pedestrian_signal'))
        self.assertTrue(self.say('entry'))
        self.audio.update(audio_ready=False, priority_clear=True, epoch=self.epoch)
        self.assertIsNone(self.sink.current)
        self.audio.update(audio_ready=True, priority_clear=True, epoch=self.epoch)
        self.assertFalse(self.say('selection', scenario='pedestrian_signal'))
        self.assertFalse(self.say('entry'))
        self.assertTrue(self.say('entry', generation=2))

    def test_priority_and_epoch_preempt_and_old_completion_cannot_speak(self):
        self.say('entry')
        self.audio.update(audio_ready=True, priority_clear=False, epoch=self.epoch)
        self.assertIsNone(self.sink.current)
        self.assertFalse(self.say('cancel'))
        self.epoch = ('session','pi','newboot','replay')
        self.audio.update(audio_ready=True, priority_clear=True, epoch=self.epoch)
        self.assertFalse(self.say('entry'))
        self.assertTrue(self.say('entry', generation=2))

    def test_expiry_clock_fault_and_engine_loss_are_fail_closed(self):
        self.say('entry'); self.now += 15; self.audio.tick()
        self.assertIsNone(self.sink.current)
        self.assertFalse(self.say('selection', scenario='pedestrian_signal'))
        self.now = 90; self.audio.tick()
        self.now = 200
        self.audio.update(audio_ready=True, priority_clear=True, epoch=self.epoch)
        self.assertFalse(self.say('entry', generation=2))
        self.setUp(); self.say('entry'); self.sink.ok = False
        self.assertFalse(self.audio.update(audio_ready=True, priority_clear=True, epoch=self.epoch))
        self.assertIsNone(self.sink.current)

    def test_cancel_is_fixed_preemptive_and_cannot_repeat(self):
        self.say('entry'); self.assertTrue(self.say('cancel'))
        self.assertEqual(self.sink.current, 'Crossing assistance stopped.')
        self.assertFalse(self.say('selection', scenario='pedestrian_signal'))
        self.audio.close(); self.assertIsNone(self.sink.current)
        self.assertFalse(self.say('entry', generation=2))

    def test_clock_failure_during_update_tick_reports_not_ready_immediately(self):
        reads = [100]
        def clock():
            if reads: return reads.pop()
            raise RuntimeError('clock unavailable')
        audio = FixedMenuAudio(self.sink, clock=clock)
        self.assertFalse(audio.update(audio_ready=True, priority_clear=True, epoch=self.epoch))
        self.assertFalse(audio.speak('entry', generation=1, epoch=self.epoch))
        self.assertIsNone(self.sink.current)
