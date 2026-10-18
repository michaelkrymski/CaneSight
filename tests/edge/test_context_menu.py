"""Virtual clock gesture acceptance; scenarios are explicitly synthetic capabilities."""
import unittest
from edge.context_menu import CrossingMenu, SCENARIOS


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.level = False
        self.core = CrossingMenu(supported=SCENARIOS)
        self.flags = dict(consent=True, ready=True, audio_ready=True, epoch=('session', 'pi', 'boot', 'replay'))
        self.step(); self.step(30)

    def step(self, advance=0, **flags):
        self.now += advance
        return self.core.sample(self.level, now_ms=self.now, **{**self.flags, **flags})

    def edge(self, level):
        self.level = level; self.step(); return self.step(30)

    def open(self):
        self.edge(True)
        events = self.step(3000)
        self.assertEqual([e.kind for e in events], ['entry'])
        self.edge(False)

    def select(self):
        self.edge(True); return self.edge(False)

    def activate(self):
        self.open(); self.select(); self.edge(True)
        self.assertEqual(self.step(1000)[0].kind, 'confirmation')
        self.assertEqual(self.edge(False)[0].kind, 'activate')

    def test_entry_threshold_short_context_on_release_and_no_double_dispatch(self):
        self.edge(True)
        self.assertEqual(self.step(2999), ())
        self.assertEqual(self.step(1)[0].kind, 'entry')
        self.assertEqual(self.step(5000), ())
        self.assertEqual(self.edge(False), ())
        self.assertEqual(self.core.state, 'menu')
        self.core.cancel(); self.edge(False); self.edge(True)
        self.assertEqual(self.edge(False)[0].kind, 'context')

    def test_startup_held_and_recovery_held_do_not_dispatch(self):
        self.core = CrossingMenu(supported=SCENARIOS); self.level = True
        self.step(); self.step(30); self.assertEqual(self.step(4000), ())
        self.edge(False); self.edge(True); self.assertEqual(self.step(3000)[0].kind, 'entry')
        self.step(audio_ready=False); self.step(100, audio_ready=True)
        self.assertEqual(self.step(4000), ())

    def test_no_default_cycle_all_three_and_wrap(self):
        self.open(); self.assertIsNone(self.core.selected)
        self.assertEqual([self.select()[0].scenario for _ in range(4)], [*SCENARIOS, SCENARIOS[0]])

    def test_confirm_threshold_and_release_barrier(self):
        self.open(); self.select(); self.edge(True)
        self.assertEqual(self.step(999), ())
        self.assertEqual(self.step(1)[0].kind, 'confirmation')
        self.assertEqual(self.step(2000), ())
        self.assertEqual(self.edge(False)[0].kind, 'activate')
        self.assertEqual(self.edge(True)[0].kind, 'cancel')
        self.assertEqual(self.step(4000), ())

    def test_hold_without_selection_prompts_and_does_not_cycle_on_release(self):
        self.open(); self.edge(True)
        self.assertEqual(self.step(1000)[0].kind, 'choose')
        self.assertEqual(self.edge(False), ())
        self.assertIsNone(self.core.selected)

    def test_menu_inactivity_and_absolute_cap_even_with_interactions(self):
        self.open(); self.assertEqual(self.step(14999), ())
        self.assertEqual(self.step(1)[0].reason, 'timeout')
        self.edge(False); self.open()
        opened = self.core._opened
        while self.now-opened+9000 < 30000:
            self.select(); self.step(9000)
        events = self.step(max(0, opened+30000-self.now))
        self.assertEqual(events[0].reason, 'timeout')

    def test_source_consent_audio_epoch_loss_cancel_without_resume(self):
        for flags, reason in [(dict(ready=False),'source'), (dict(consent=False),'consent'),
                              (dict(audio_ready=False),'audio'),
                              (dict(epoch=('session','pi','newboot','replay')),'epoch')]:
            self.setUp(); self.activate()
            self.assertEqual(self.step(**flags)[0].reason, reason)
            self.step(30); self.level = True; self.step(); self.step(30)
            self.assertEqual(self.step(4000), ())

    def test_clock_fault_latches_and_close_discards_state(self):
        for value in (-1, float('nan'), float('inf'), True, 10**1000):
            self.setUp(); self.activate()
            self.assertEqual(self.core.sample(False, now_ms=value, **self.flags)[0].reason, 'clock')
            self.assertEqual(self.core.state, 'failed')
            self.core.cancel()
            self.assertEqual(self.step(100), ())
        self.setUp(); self.activate(); self.core.close(); self.core.cancel()
        self.assertEqual(self.step(), ())

    def test_unsupported_real_adapters_never_activate(self):
        self.core = CrossingMenu(); self.edge(False); self.open(); self.select(); self.edge(True)
        self.assertEqual(self.step(1000)[0].reason, 'unsupported')
        self.assertNotEqual(self.core.state, 'active')

    def test_missing_audio_cannot_open_menu_but_idle_short_release_remains_context(self):
        self.flags['audio_ready'] = False
        self.edge(True); self.assertEqual(self.edge(False)[0].kind, 'context')
        self.edge(True); self.assertEqual(self.step(3000)[0].reason, 'audio')

    def test_bounce_does_not_dispatch_and_events_are_not_queued(self):
        self.level = True; self.step(); self.level = False; self.step(10); self.step(30)
        self.assertEqual(self.step(), ())
        self.open(); generation = self.core.generation
        self.core.cancel(); self.assertGreater(self.core.generation, generation)
        self.assertEqual(self.step(), ())

    def test_release_at_hold_threshold_cannot_dispatch_short_context(self):
        self.edge(True)
        self.level = False
        events = self.step(3000)
        self.assertEqual([e.kind for e in events], ['entry'])
        self.assertEqual(self.step(30), ())
        self.assertEqual(self.core.state, 'menu')

    def test_absolute_menu_cap_does_not_expire_healthy_active_mode(self):
        self.activate()
        self.assertEqual(self.step(40000), ())
        self.assertEqual(self.core.state, 'active')
        self.assertEqual(self.edge(True)[0].kind, 'cancel')
