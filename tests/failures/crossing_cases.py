"""Executed ONLY by the pinned isolated CS-044 runner, not default discovery."""
import io
import json
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout

from edge.context_menu import CrossingMenu, SCENARIOS
from edge.menu_bench import MenuBench
from backend.context.menu_audio import ALL_PHRASES, FixedMenuAudio
from backend.context.narration import NarrationController


class Sink:
    def __init__(self):
        self.current = None
        self.spoken = []
        self.ok = True
    def speak(self, value): self.current = value; self.spoken.append(value)
    def stop(self): self.current = None
    def healthy(self): return self.ok


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.sink = Sink()
        self.bench = MenuBench(self.sink, synthetic_adapters=True, clock=lambda: self.now)
        self.addCleanup(self.bench.close)
        self.bench.tick(); self.tick(30)

    def tick(self, delta=0): self.now += delta; self.bench.tick()
    def edge(self, level):
        self.bench.command('press' if level else 'release'); self.tick(30)
    def enter(self):
        self.edge(True); self.tick(3000); self.edge(False)
        self.assertEqual(self.bench.core.state, 'menu')
    def select(self): self.edge(True); self.edge(False)
    def activate(self):
        self.enter(); self.select(); self.edge(True); self.tick(1000); self.edge(False)
        self.assertEqual(self.bench.core.state, 'active')

    def test_2999_3000_entry_and_999_1000_confirmation_barriers(self):
        self.edge(True); self.tick(2999)
        self.assertEqual(self.bench.counts['entry'], 0)
        self.assertEqual(self.bench.context_gestures, 0)
        self.tick(1)
        self.assertEqual(self.bench.counts['entry'], 1)
        self.assertIn('does not tell you when to cross', self.sink.current)
        self.tick(4000)
        self.assertEqual(self.bench.counts['confirmation'], 0)
        self.edge(False); self.select(); self.edge(True); self.tick(999)
        self.assertEqual(self.bench.counts['confirmation'], 0)
        self.tick(1)
        self.assertEqual(self.bench.counts['confirmation'], 1)
        self.assertEqual(self.bench.counts['activate'], 0)
        self.tick(2000); self.edge(False)
        self.assertEqual(self.bench.counts['activate'], 1)
        self.assertEqual(self.bench.counts['cancel'], 0)

    def test_short_release_context_compatibility_and_bounce(self):
        self.bench.command('press'); self.tick(10)
        self.bench.command('release'); self.tick(30)
        self.assertEqual(self.bench.context_gestures, 0)
        self.edge(True)
        self.assertEqual(self.bench.context_gestures, 0)
        self.edge(False)
        self.assertEqual(self.bench.context_gestures, 1)
        self.tick(4000)
        self.assertEqual(self.bench.context_gestures, 1)
        self.assertFalse(self.bench.snapshot()['context_requests_used'])

    def test_no_default_three_spoken_labels_and_wrap(self):
        self.enter()
        self.assertIsNone(self.bench.core.selected)
        self.edge(True); self.tick(1000); self.edge(False)
        self.assertEqual(self.sink.current, 'Press to select a crossing type.')
        self.assertEqual(self.bench.counts['activate'], 0)
        labels = ('Pedestrian walk-and-hand signal', 'Flashing yellow pedestrian beacon',
                  'Street without a crossing signal', 'Pedestrian walk-and-hand signal')
        for scenario, label in zip((*SCENARIOS, SCENARIOS[0]), labels):
            self.select()
            self.assertEqual(self.bench.core.snapshot()['selected'], scenario)
            self.assertEqual(self.sink.current, label)

    def test_cancel_on_down_edge_and_held_input_cannot_restart(self):
        self.activate(); self.edge(True)
        self.assertEqual(self.bench.counts['cancel'], 1)
        self.assertEqual(self.sink.current, 'Crossing assistance stopped.')
        self.tick(4000)
        self.assertEqual(self.bench.counts['entry'], 1)
        self.assertEqual(self.bench.core.state, 'idle')
        self.edge(False); self.edge(True); self.tick(3000)
        self.assertEqual(self.bench.counts['entry'], 2)

    def test_startup_held_has_no_context_or_menu(self):
        core = CrossingMenu(supported=SCENARIOS)
        flags = dict(consent=True, ready=True, audio_ready=True, epoch=('s','p','b','replay'))
        for now in (0, 30, 3000, 30000):
            self.assertEqual(core.sample(True, now_ms=now, **flags), ())
        self.assertEqual(core.state, 'idle')

    def test_inactivity_and_absolute_menu_cap_discard_selection(self):
        self.enter(); self.select(); self.tick(14999)
        self.assertEqual(self.bench.core.state, 'menu')
        self.tick(1)
        self.assertEqual(self.bench.last_event['reason'], 'timeout')
        self.assertIsNone(self.bench.core.selected)
        self.edge(False); self.enter()
        opened = self.now - 30
        self.tick(9000); self.select(); self.tick(9000); self.select(); self.tick(9000); self.select()
        self.tick(opened + 30000 - self.now)
        self.assertEqual(self.bench.last_event['reason'], 'timeout')
        self.assertEqual(self.bench.core.state, 'idle')

    def test_audio_disconnect_reconnect_never_replays_or_reactivates(self):
        self.activate()
        self.bench.command('audio-off')
        self.assertIsNone(self.sink.current)
        spoken = list(self.sink.spoken)
        self.bench.command('audio-on'); self.tick(20000)
        self.assertEqual(self.sink.spoken, spoken)
        self.assertNotEqual(self.bench.core.state, 'active')
        self.assertFalse(self.bench.snapshot()['automatic_audio_route_detection'])

    def test_no_audio_at_confirmation_never_activates(self):
        self.enter(); self.select(); self.edge(True); self.tick(999)
        self.bench.command('audio-off'); self.tick(1); self.edge(False)
        self.assertEqual(self.bench.counts['activate'], 0)
        self.assertIsNone(self.sink.current)

    def test_source_failure_and_recovery_require_new_entry(self):
        self.activate(); self.bench.command('source-off')
        self.assertEqual(self.sink.current, 'Crossing observations unavailable.')
        self.bench.command('source-on'); self.tick(100)
        self.assertNotEqual(self.bench.core.state, 'active')
        self.assertIsNone(self.bench.core.selected)
        self.assertFalse(self.bench.snapshot()['backend_used'])

    def test_consent_withdrawal_stops_speech_and_blocks_held_input(self):
        self.activate(); self.bench.command('consent-off')
        self.assertIsNone(self.sink.current)
        self.edge(True); self.tick(4000)
        self.assertNotEqual(self.bench.core.state, 'active')
        self.assertEqual(self.bench.counts['entry'], 1)

    def test_priority_preempts_menu_and_does_not_resume(self):
        self.enter(); self.bench.command('hazard-on')
        self.assertIsNone(self.sink.current)
        self.bench.command('hazard-off'); self.tick(100)
        self.assertNotEqual(self.bench.core.state, 'menu')
        self.assertIsNone(self.sink.current)

    def test_each_epoch_component_cancels_without_old_speech(self):
        for field in range(4):
            with self.subTest(field=field):
                self.setUp(); self.activate()
                old = self.bench.flags['epoch']
                new = tuple('replacement' if i == field else part for i, part in enumerate(old))
                self.bench.flags['epoch'] = new
                self.tick(1)
                self.assertEqual(self.bench.last_event['reason'], 'epoch')
                self.assertIsNone(self.sink.current)
                self.assertNotEqual(self.bench.core.state, 'active')

    def test_clock_failure_latches_and_recovery_does_not_restart(self):
        self.activate(); self.now = float('nan'); self.bench.tick()
        self.assertEqual(self.bench.core.state, 'failed')
        self.assertIsNone(self.sink.current)
        self.now = 100000; self.bench.tick(); self.edge(True); self.tick(4000)
        self.assertEqual(self.bench.counts['entry'], 1)

    def test_default_real_capabilities_remain_unavailable(self):
        self.bench.core = CrossingMenu()
        self.bench.tick(); self.tick(30)
        self.enter(); self.select(); self.edge(True); self.tick(1000); self.edge(False)
        self.assertEqual(self.bench.counts['activate'], 0)
        self.assertEqual(self.sink.current, 'Crossing observations unavailable.')

    def test_shutdown_cancels_and_cannot_reopen(self):
        self.activate(); self.bench.command('quit')
        self.assertIsNone(self.sink.current)
        self.edge(True); self.tick(4000)
        self.assertEqual(self.bench.core.state, 'closed')
        self.assertEqual(self.bench.counts['entry'], 1)


class DelayedAudioTests(unittest.TestCase):
    def test_old_generation_or_epoch_event_cannot_replay(self):
        sink = Sink(); epoch = ('s','p','b','replay')
        audio = FixedMenuAudio(sink, clock=lambda: 1)
        self.assertTrue(audio.update(audio_ready=True, priority_clear=True, epoch=epoch))
        self.assertTrue(audio.speak('entry', generation=1, epoch=epoch))
        self.assertTrue(audio.speak('cancel', generation=1, epoch=epoch))
        self.assertTrue(audio.speak('entry', generation=2, epoch=epoch))
        self.assertFalse(audio.speak('confirmation', generation=1, epoch=epoch, scenario=SCENARIOS[0]))
        changed = ('s','p','new','replay')
        audio.update(audio_ready=True, priority_clear=True, epoch=changed)
        self.assertFalse(audio.speak('selection', generation=2, epoch=epoch, scenario=SCENARIOS[0]))
        self.assertIsNone(sink.current)

    def test_stalled_worker_result_cannot_restore_cancelled_narration(self):
        now = [100.0]; sink = Sink(); narration = NarrationController(sink, clock=lambda: now[0])
        narration.set_priority(hazard=False, unavailable=False)
        ticket = narration.begin_capture(capture_monotonic_s=99, consent=True)
        self.assertIsNotNone(ticket)
        waiting, release = threading.Event(), threading.Event()
        delivered = []
        def worker():
            waiting.set()
            if release.wait(2): delivered.append(narration.deliver(ticket, {'objects':['vehicle'], 'uncertain':True}))
        thread = threading.Thread(target=worker, daemon=True); thread.start()
        try:
            self.assertTrue(waiting.wait(1))
            narration.cancel()  # Must complete while worker is still blocked.
            self.assertIsNone(sink.current)
            release.set(); thread.join(1)
            self.assertFalse(thread.is_alive())
            self.assertEqual(delivered, [False])
        finally:
            release.set(); thread.join(1); narration.close()

    def test_context_original_capture_deadline_is_not_rebased_on_delivery(self):
        now = [100.0]; sink = Sink(); narration = NarrationController(sink, clock=lambda: now[0])
        narration.set_priority(hazard=False, unavailable=False)
        ticket = narration.begin_capture(capture_monotonic_s=93, consent=True)
        now[0] = 101
        self.assertFalse(narration.deliver(ticket, {'objects':['chair'], 'uncertain':True}))
        self.assertIsNone(sink.current)
        # Context's 8-second optional-description deadline is separate from
        # accepted depth/vision 500/1500ms observation gates.

    def test_menu_speech_expires_without_new_jobs_and_fixed_words_only(self):
        now = [10.0]; sink = Sink(); epoch = ('s','p','b','replay')
        audio = FixedMenuAudio(sink, clock=lambda: now[0])
        audio.update(audio_ready=True, priority_clear=True, epoch=epoch)
        self.assertTrue(audio.speak('entry', generation=1, epoch=epoch))
        now[0] = 25; audio.tick()
        self.assertIsNone(sink.current)
        self.assertFalse(audio.speak('confirmation', generation=1, epoch=epoch, scenario=SCENARIOS[0]))
        self.assertTrue(set(sink.spoken) <= ALL_PHRASES)


class Result(unittest.TestResult):
    def __init__(self): super().__init__(); self.cases = []
    def startTest(self, test): super().startTest(test); self.status = 'pass'
    def addFailure(self, test, err): super().addFailure(test, err); self.status = 'fail'
    def addError(self, test, err): super().addError(test, err); self.status = 'error'
    def addSkip(self, test, reason): super().addSkip(test, reason); self.status = 'skip'
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None: self.status = 'fail'
    def stopTest(self, test):
        self.cases.append({'id': test.__class__.__name__ + '.' + test._testMethodName, 'status': self.status})
        super().stopTest(test)


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                               for cls in (CompositionTests, DelayedAudioTests))
    expected = suite.countTestCases()
    result = Result()
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        suite.run(result)
    print(json.dumps({'expected_cases': expected, 'cases': result.cases}))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
