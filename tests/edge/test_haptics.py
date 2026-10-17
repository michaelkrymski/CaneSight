"""Deterministic scheduler limits and worker lifecycle, simulated outputs only."""
import random
import threading
import time
import unittest

from edge.haptics import CHANNELS, HapticScheduler, Limits, SchedulerFault, SimulatedOutput


class FakeClock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def advance(self, ms): self.now += ms


class TraceOutput(SimulatedOutput):
    def __init__(self, clock):
        super().__init__()
        self.clock = clock
        self.trace = []  # Test-only exhaustive trace; production trace is bounded.
        self.fail_on = set()
    def write(self, channel, enabled):
        self.trace.append((self.clock(), channel, enabled))
        if (channel, enabled) in self.fail_on:
            raise OSError('Synthetic output failure')
        super().write(channel, enabled)


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.output = TraceOutput(self.clock)
        self.scheduler = HapticScheduler(self.output, clock=self.clock)
        self.addCleanup(self.scheduler.close)

    def arm(self):
        self.assertTrue(self.scheduler.set_ready(True))
        self.clock.advance(200)

    def pulse(self, channels='left', duration=150, lease=1000):
        return self.scheduler.pulse(channels, duration, valid_until_ms=self.clock.now+lease)

    def test_startup_is_off_unarmed_and_initial_off_time_enforced(self):
        self.assertEqual(self.output.trace, [(0,'left',False),(0,'right',False)])
        self.assertFalse(self.pulse())
        self.scheduler.set_ready(True)
        self.assertFalse(self.pulse())
        self.clock.advance(199)
        self.assertFalse(self.pulse())
        self.clock.advance(1)
        self.assertTrue(self.pulse())

    def test_two_independent_channels_stop_at_their_original_deadlines(self):
        self.arm()
        self.assertTrue(self.pulse('left',100))
        self.assertTrue(self.pulse('right',200))
        self.clock.advance(99)
        self.assertEqual(self.scheduler.tick()['outputs'], {'left':True,'right':True})
        self.clock.advance(1)
        self.assertEqual(self.scheduler.tick()['outputs'], {'left':False,'right':True})
        self.clock.advance(100)
        self.assertEqual(self.scheduler.tick()['outputs'], {'left':False,'right':False})

    def test_busy_requests_and_readiness_updates_cannot_extend_or_queue(self):
        self.arm();self.assertTrue(self.pulse(duration=150))
        deadline=self.scheduler.channels['left'].deadline_ms
        for _ in range(20):
            self.clock.advance(5)
            self.scheduler.set_ready(True)
            self.assertFalse(self.pulse(duration=500))
        self.assertEqual(self.scheduler.channels['left'].deadline_ms,deadline)
        self.clock.now=deadline
        self.assertFalse(self.scheduler.tick()['outputs']['left'])
        self.clock.advance(1000)
        self.assertFalse(self.scheduler.tick()['outputs']['left'])

    def test_expired_input_and_original_eligibility_deadline(self):
        self.arm()
        self.assertFalse(self.pulse(lease=0))
        self.assertTrue(self.pulse(duration=500,lease=70))
        self.clock.advance(70)
        self.assertFalse(self.scheduler.tick()['outputs']['left'])
        self.assertEqual(self.scheduler.channels['left'].history[-1],(200,270))

    def test_exact_max_pulse_and_minimum_off_boundary(self):
        self.arm();self.assertTrue(self.pulse(duration=500))
        self.clock.advance(500);self.scheduler.tick()
        self.assertIsNone(self.scheduler.fault)
        self.clock.advance(199);self.assertFalse(self.pulse())
        self.clock.advance(1);self.assertTrue(self.pulse())

    def test_multichannel_admission_is_atomic_when_one_channel_busy(self):
        self.arm();self.pulse('left')
        self.assertFalse(self.pulse(('left','right')))
        self.assertFalse(self.output.states['right'])

    def test_per_channel_rolling_duty_cap_reserves_whole_requested_pulse(self):
        self.arm()
        for _ in range(4):
            self.assertTrue(self.pulse(duration=500))
            self.clock.advance(500);self.scheduler.tick();self.clock.advance(200)
        self.assertFalse(self.pulse(duration=1))
        self.assertEqual(self.scheduler.last_rejection,'duty_cap')
        self.assertTrue(self.pulse('right',500))
        self.clock.advance(500);self.scheduler.tick()
        self.clock.now=10_450  # First [200,700] overlaps this window by 250ms.
        self.assertTrue(self.pulse(duration=250))

    def test_atomic_pair_rejection_for_duty_cap(self):
        self.arm()
        for _ in range(4):
            self.pulse('right',500);self.clock.advance(500);self.scheduler.tick();self.clock.advance(200)
        self.assertFalse(self.pulse(('left','right'),100))
        self.assertEqual(self.output.states,{'left':False,'right':False})

    def test_disarm_and_rearm_preserve_used_duty_and_off_time(self):
        self.arm();self.pulse(duration=500);self.clock.advance(100)
        self.scheduler.set_ready(False)
        self.assertFalse(self.output.states['left'])
        self.scheduler.set_ready(True)
        self.assertFalse(self.pulse())
        self.clock.advance(200);self.assertTrue(self.pulse())
        self.assertEqual(self.scheduler.channels['left'].history[0],(200,300))

    def test_cancel_one_channel_leaves_peer_running_and_retains_charge(self):
        self.arm();self.pulse(CHANNELS,200);self.clock.advance(50)
        self.assertTrue(self.scheduler.cancel('left'))
        self.assertEqual(self.output.states,{'left':False,'right':True})
        self.assertEqual(self.scheduler.channels['left'].history[-1],(200,250))
        self.clock.advance(150);self.scheduler.tick()
        self.assertFalse(self.output.states['right'])

    def test_late_tick_charges_actual_time_and_overrun_fault_is_sticky(self):
        self.arm();self.pulse(CHANNELS,500);self.clock.advance(800)
        snapshot=self.scheduler.tick()
        self.assertEqual(snapshot['outputs'],dict.fromkeys(CHANNELS,False))
        self.assertIsNotNone(snapshot['fault'])
        self.assertFalse(snapshot['ready'])
        self.assertEqual(self.scheduler.channels['left'].history[-1],(200,1000))
        self.assertFalse(self.scheduler.set_ready(True))
        self.clock.advance(20_000);self.assertFalse(self.pulse())

    def test_delayed_short_pulse_counts_elapsed_time_not_planned_duration(self):
        self.arm();self.pulse(duration=100);self.clock.advance(120);self.scheduler.tick()
        self.assertEqual(self.scheduler.channels['left'].history[-1],(200,320))
        self.assertIsNone(self.scheduler.fault)

    def test_late_cancellation_cannot_hide_overrun_or_leave_peer_enabled(self):
        self.arm();self.pulse(CHANNELS,500);self.clock.advance(800)
        self.scheduler.cancel('left')
        self.assertIsNotNone(self.scheduler.fault)
        self.assertEqual(self.output.states,dict.fromkeys(CHANNELS,False))
        self.assertFalse(self.scheduler.set_ready(True))

    def test_invalid_clock_or_reversal_always_requests_both_off(self):
        for bad in (None,True,-1,float('nan'),float('inf'),100):
            with self.subTest(bad=bad):
                clock=FakeClock();output=TraceOutput(clock)
                scheduler=HapticScheduler(output,clock=clock)
                scheduler.set_ready(True);clock.now=200
                scheduler.pulse(CHANNELS,valid_until_ms=500)
                clock.now=bad
                value=scheduler.tick()
                self.assertIsNotNone(value['fault'])
                self.assertEqual(output.states,dict.fromkeys(CHANNELS,False))
                clock.now=1000
                self.assertFalse(scheduler.set_ready(True))
                scheduler.close()

    def test_clock_exception_turns_off_and_faults(self):
        self.arm();self.pulse(CHANNELS)
        def broken(): raise OSError('Synthetic clock fault')
        self.scheduler.clock=broken
        self.assertIsNotNone(self.scheduler.tick()['fault'])
        self.assertEqual(self.output.states,dict.fromkeys(CHANNELS,False))

    def test_startup_clock_failure_still_requests_both_off(self):
        clock=FakeClock();clock.now=float('nan');output=TraceOutput(clock)
        with self.assertRaises(SchedulerFault): HapticScheduler(output,clock=clock)
        self.assertEqual(output.states,dict.fromkeys(CHANNELS,False))

    def test_startup_output_fault_attempts_other_channel_and_refuses_start(self):
        output=TraceOutput(self.clock);output.fail_on.add(('left',False))
        with self.assertRaises(SchedulerFault): HapticScheduler(output,clock=self.clock)
        self.assertIn((0,'right',False),output.trace)

    def test_partial_pair_write_failure_immediately_disarms_both(self):
        self.arm();self.output.fail_on.add(('right',True))
        self.assertFalse(self.pulse(CHANNELS))
        self.assertEqual(self.output.states,dict.fromkeys(CHANNELS,False))
        self.assertIsNotNone(self.scheduler.fault)
        self.assertFalse(self.scheduler.set_ready(True))

    def test_off_failure_is_unknown_not_falsely_confirmed_low(self):
        self.arm();self.pulse(CHANNELS)
        self.output.fail_on.add(('left',False))
        self.clock.advance(150)
        value=self.scheduler.tick()
        self.assertIsNone(value['outputs']['left'])
        self.assertFalse(value['outputs']['right'])
        self.assertIsNotNone(value['fault'])
        self.assertFalse(self.scheduler.close())

    def test_close_idempotent_and_pulses_cannot_restart_closed_scheduler(self):
        self.arm();self.pulse(CHANNELS)
        self.assertTrue(self.scheduler.close())
        self.assertTrue(self.scheduler.close())
        self.assertFalse(self.pulse())
        self.assertFalse(self.scheduler.set_ready(True))
        self.assertTrue(self.scheduler.snapshot()['closed'])
        with self.assertRaises(SchedulerFault): self.scheduler.start()

    def test_invalid_commands_cannot_request_unbounded_pulses(self):
        self.arm()
        for duration in (True,0,-1,501,float('nan'),float('inf'),'150',10**1000):
            with self.subTest(duration=duration),self.assertRaises(ValueError): self.pulse(duration=duration)
        for channels in ((),[],('left','left'),('left','right','left'),'both',['unknown'],{'left'}):
            with self.subTest(channels=channels),self.assertRaises(ValueError): self.pulse(channels)
        for ready in (1,None,'ready'):
            with self.assertRaises(ValueError): self.scheduler.set_ready(ready)
        self.assertEqual(self.output.states,dict.fromkeys(CHANNELS,False))

    def test_config_can_only_tighten_simulation_envelope(self):
        for change in ({'max_pulse_ms':501},{'min_off_ms':199},{'max_on_ms':2001},
                       {'tick_ms':11},{'tick_ms':0},{'max_on_ms':True}):
            with self.subTest(change=change),self.assertRaises(ValueError): Limits(**change)
        self.assertEqual(Limits(max_pulse_ms=200,min_off_ms=300,max_on_ms=1000).max_pulse_ms,200)

    def test_five_minutes_of_adversarial_requests_has_no_overlap_or_duty_bypass(self):
        self.arm();rng=random.Random(23)
        for _ in range(30_000):
            self.clock.advance(10)
            self.scheduler.tick()
            if rng.random()<.03: self.scheduler.set_ready(False)
            else: self.scheduler.set_ready(True)
            self.pulse(rng.choice(('left','right',CHANNELS)),rng.choice((100,150,200)),lease=rng.choice((0,50,300)))
            for state in self.scheduler.channels.values(): self.assertLessEqual(len(state.history),52)
        self.scheduler.close()
        for channel in CHANNELS:
            started=None;intervals=[];last_off=0
            for when,name,enabled in self.output.trace:
                if name!=channel: continue
                if enabled:
                    self.assertIsNone(started)
                    self.assertGreaterEqual(when-last_off,200)
                    started=when
                elif started is not None:
                    self.assertLessEqual(when-started,500)
                    intervals.append((started,when));started=None;last_off=when
            self.assertIsNone(started)
            for _,end in intervals:
                used=sum(max(0,min(b,end)-max(a,end-10_000)) for a,b in intervals if a<end and b>end-10_000)
                self.assertLessEqual(used,2000)
        self.assertLessEqual(len(self.output.events),256)


class WorkerTests(unittest.TestCase):
    def test_independent_worker_expires_while_caller_is_blocked(self):
        ended=threading.Event()
        class Output(SimulatedOutput):
            was_on=False
            def write(self,channel,enabled):
                super().write(channel,enabled)
                if channel=='left':
                    if enabled: self.was_on=True
                    elif self.was_on: ended.set()
        output=Output()
        clock=lambda:time.monotonic()*1000
        with HapticScheduler(output,clock=clock) as scheduler:
            scheduler.set_ready(True)
            time.sleep(.21)
            self.assertTrue(scheduler.pulse('left',100,valid_until_ms=clock()+300))
            # No tick/snapshot calls here: the worker must drive low itself.
            self.assertTrue(ended.wait(1))
            self.assertFalse(output.states['left'])
        self.assertFalse(scheduler._thread.is_alive())
        self.assertEqual(output.states,dict.fromkeys(CHANNELS,False))

    def test_context_exception_cleans_outputs_and_worker(self):
        clock=lambda:time.monotonic()*1000
        output=SimulatedOutput()
        with self.assertRaisesRegex(RuntimeError,'Synthetic caller failure'):
            with HapticScheduler(output,clock=clock) as scheduler:
                scheduler.set_ready(True);time.sleep(.21)
                self.assertTrue(scheduler.pulse(CHANNELS,400,valid_until_ms=clock()+500))
                raise RuntimeError('Synthetic caller failure')
        self.assertFalse(scheduler._thread.is_alive())
        self.assertEqual(output.states,dict.fromkeys(CHANNELS,False))


if __name__=='__main__': unittest.main()
