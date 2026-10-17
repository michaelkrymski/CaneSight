"""Synthetic final-consumer depth -> capped simulated outputs; never GPIO."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from backend.freshness import CaptureAgeGate
from edge.haptics import HapticScheduler, SimulatedOutput
from edge.policy import LocalPolicy, PhoneBinding
from edge.receiver import VisionReceiver
from edge.uploader import Sender, Latest

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.now=1000
        self.clock=lambda:self.now
        self.gate=CaptureAgeGate('session','replay','pi','pi-boot',clock_ms=self.clock,relative_drift_ppm=0)
        self.gate.enroll('phone','phone-boot',{'depth_observation','heartbeat'})
        self.gate.enroll('pi','pi-boot',{'frame_metadata','vision_observation'})
        probe=self.gate.start_probe('phone')
        self.gate.finish_probe(dict(probe,type='clock_reply',t2_ms=self.now,t3_ms=self.now))
        self.seq=0
        self.heartbeat()
        self.output=SimulatedOutput()
        self.scheduler=HapticScheduler(self.output,clock=self.clock)
        self.policy=LocalPolicy(self.gate,'phone',self.scheduler,clock=self.clock)
        self.policy.arm(True)
        self.advance(500)
        self.addCleanup(self.scheduler.close)
        self.addCleanup(self.policy.close)

    def advance(self,ms):
        end=self.now+ms
        while self.now<end:
            self.now=min(end,self.now+10)
            self.scheduler.tick()

    def base(self,kind):
        self.seq+=1
        return dict(schema_version=1,type=kind,session_id='session',mode='replay',source_id='phone',boot_id='phone-boot',seq=self.seq,capture_monotonic_ms=self.now,capture_utc=None)

    def heartbeat(self,state='ready'):
        self.gate.receive(dict(self.base('heartbeat'),state=state))

    def depth(self,left=.8,center=None,right=None,coverage=1,tracking='normal',age=0):
        message=dict(self.base('depth_observation'),tracking=tracking,sectors={name:dict(distance_m=value,valid_fraction=coverage) for name,value in [('left',left),('center',center),('right',right)]})
        message['capture_monotonic_ms']-=age
        self.gate.receive(message)
        return self.policy.tick()

    def recover(self,**kwargs):
        self.depth(**kwargs);self.advance(100)
        return self.depth(**kwargs)

    def outputs(self): return self.scheduler.snapshot()['outputs']

    def test_health_alone_is_not_hazard_or_motor_readiness(self):
        for _ in range(5):
            self.advance(100);self.heartbeat();self.policy.tick()
        self.assertEqual(self.policy.snapshot()['health']['depth'],'no-fresh-depth')
        self.assertEqual(set(self.policy.hazards.values()),{'unknown'})
        self.assertEqual(self.scheduler.accepted,0)
        self.assertFalse(any(self.outputs().values()))

    def test_two_frames_side_mapping_and_no_tick_or_heartbeat_retrigger(self):
        self.depth()
        self.assertEqual(self.scheduler.accepted,0)
        self.advance(100);self.depth()
        self.assertEqual(self.outputs(),{'left':True,'right':False})
        self.advance(100);self.policy.tick()
        for _ in range(3):self.heartbeat();self.policy.tick()
        self.assertEqual(self.scheduler.accepted,1)
        self.assertFalse(any(self.outputs().values()))

    def test_center_priority_and_right_side(self):
        self.recover(left=.6,center=.9,right=.5)
        self.assertEqual(self.outputs(),{'left':True,'right':True})
        self.advance(300);self.depth(left=2,center=2,right=.6)
        self.assertEqual(self.outputs(),{'left':False,'right':True})

    def test_unknown_coverage_and_tracking_remove_pulses(self):
        self.recover()
        self.advance(20);self.depth(left=None,right=2)
        self.assertFalse(any(self.outputs().values()))
        self.assertEqual(self.policy.hazards['left'],'unknown')
        self.advance(300);self.recover(coverage=.49)
        self.assertEqual(self.policy.hazards['left'],'unknown')
        self.advance(100);self.depth(left=None,tracking='limited')
        self.assertFalse(any(self.outputs().values()))

    def test_original_capture_deadline_clips_pulse_and_heartbeat_never_renews(self):
        self.depth();self.advance(100)
        self.depth(age=450)
        deadline=self.gate.current('phone','depth_observation').deadline_ms
        self.assertEqual(self.scheduler.channels['left'].deadline_ms,deadline)
        self.now=deadline;self.heartbeat();self.policy.tick()
        self.assertFalse(any(self.outputs().values()))
        self.advance(1);self.policy.tick()
        self.assertEqual(self.policy.health['depth'],'no-fresh-depth')
        self.assertEqual(self.policy.hazards['left'],'unknown')

    def test_hysteresis_does_not_call_far_observations_clear(self):
        self.recover()
        self.advance(100);self.depth(left=1.3)
        self.assertEqual(self.policy.hazards['left'],'nearby')
        self.advance(100);self.depth(left=1.5)
        self.assertEqual(self.policy.hazards['left'],'not-nearby-observed')
        self.assertFalse(any(self.outputs().values()))
        self.assertEqual(self.policy.snapshot()['guidance'],'unavailable')

    def test_expiry_gap_and_disarm_require_new_recovery(self):
        self.recover()
        self.advance(600);self.policy.tick()
        self.depth();self.assertEqual(self.policy.counts['left'],1)
        self.policy.arm(False)
        self.assertFalse(any(self.outputs().values()))
        self.policy.arm(True)
        self.policy.tick();self.assertEqual(self.policy.counts['left'],1)
        self.policy.tick();self.assertEqual(self.policy.counts['left'],1)

    def test_disconnect_resets_evidence_sequence_and_requires_calibration(self):
        self.recover()
        self.gate.interrupt();self.policy.tick()
        self.assertFalse(any(self.outputs().values()))
        self.assertEqual(self.policy.hazards['left'],'unknown')
        with self.assertRaises(ValueError):self.heartbeat()
        self.assertFalse(any(self.outputs().values()))

    def test_wrong_session_duplicate_future_and_stale_do_not_pulse(self):
        self.depth()
        for changes in [{'session_id':'other'},{'boot_id':'other'},{'mode':'live'},
                        {'capture_monotonic_ms':self.now+10},{'capture_monotonic_ms':self.now-501}]:
            message=dict(self.base('depth_observation'),tracking='normal',sectors={name:dict(distance_m=.5,valid_fraction=1) for name in self.policy.counts})
            message.update(changes)
            with self.assertRaises(ValueError):self.gate.receive(message)
            self.policy.tick()
        self.assertEqual(self.scheduler.accepted,0)

    def test_clock_fault_latches_and_cleanup_off(self):
        self.recover();self.now=0
        self.policy.tick()
        self.assertIsNotNone(self.policy.fault)
        self.assertFalse(any(self.outputs().values()))
        self.policy.arm(True);self.assertFalse(self.policy.armed)
        self.policy.close();self.scheduler.close()
        self.assertFalse(any(self.output.states.values()))

    def test_scheduler_fault_latches_even_without_depth(self):
        self.scheduler._fail('Synthetic output failure',self.now)
        state=self.policy.tick()
        self.assertIsNotNone(state['fault'])
        self.assertFalse(state['armed'])
        self.assertFalse(any(self.outputs().values()))

    def test_no_default_arming_and_clock_epoch_mismatch_rejected(self):
        self.policy.arm(False);self.recover()
        self.assertEqual(self.scheduler.accepted,0)
        with self.assertRaises(ValueError):LocalPolicy(self.gate,'phone',self.scheduler,clock=lambda:self.now)
        with self.assertRaises(ValueError):LocalPolicy(self.gate,'untrusted',self.scheduler,clock=self.clock)

    def test_independent_worker_cancels_while_caller_blocked(self):
        # Real monotonic simulation, not physical timing or a frozen-process guarantee.
        self.now=time.monotonic()*1000
        clock=lambda:time.monotonic()*1000
        gate=CaptureAgeGate('session','replay','pi','boot',clock_ms=clock,relative_drift_ppm=0)
        gate.enroll('phone','phone-boot',{'depth_observation','heartbeat'})
        scheduler=HapticScheduler(clock=clock).start()
        policy=LocalPolicy(gate,'phone',scheduler,clock=clock).start()
        try:
            time.sleep(.22)
            probe=gate.start_probe('phone');gate.finish_probe(dict(probe,type='clock_reply',t2_ms=probe['t1_ms'],t3_ms=probe['t1_ms']))
            self.gate=gate;self.policy=policy;self.clock=clock
            time.sleep(.02);self.now=clock()-10;self.heartbeat();policy.arm(True)
            time.sleep(.02);self.now=clock()-10;self.depth();time.sleep(.03);self.now=clock()-10;self.depth()
            self.assertTrue(scheduler.snapshot()['outputs']['left'])
            time.sleep(.7)
            self.assertFalse(any(scheduler.snapshot()['outputs'].values()))
            self.assertEqual(policy.hazards['left'],'unknown')
        finally:policy.close();scheduler.close()

class PhoneBindingTests(unittest.TestCase):
    def test_closed_binding_no_tokens_duplicates_or_unbounded_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'binding.json'
            p.write_text(json.dumps(dict(source_id='phone',boot_id='boot',relative_drift_ppm=None)))
            self.assertIsNone(PhoneBinding.load(p).relative_drift_ppm)
            for value in ['{"source_id":"phone","boot_id":"boot","relative_drift_ppm":0,"token":"forbidden"}',
                          '{"source_id":"phone","source_id":"other","boot_id":"boot","relative_drift_ppm":0}']:
                p.write_text(value)
                with self.assertRaises(ValueError):PhoneBinding.load(p)
        for value in [-1,float('nan'),True]:
            with self.assertRaises(ValueError):PhoneBinding('phone','boot',value)


class ReceiverPhoneTests(unittest.TestCase):
    def setUp(self):
        self.now=1000
        self.session=dict(base_url='https://127.0.0.1',session_id='session',source_id='pi',boot_id='pi-boot',mode='live',token='synthetic-'+'t'*40)
        self.binding=PhoneBinding('phone','phone-boot',0)
        self.receiver=VisionReceiver(self.session,clock=lambda:self.now,phone_binding=self.binding)
        Sender(Latest(),None,receiver=self.receiver)
        self.receiver.connected=True

    def send(self,message):return self.receiver.receive(json.dumps(message))

    def calibrate(self):
        probe=self.receiver.gate.start_probe('phone')
        self.send(dict(probe,type='clock_reply',t2_ms=self.now,t3_ms=self.now))

    def heartbeat(self):
        return dict(schema_version=1,type='heartbeat',session_id='session',mode='live',source_id='phone',boot_id='phone-boot',seq=1,capture_monotonic_ms=self.now,capture_utc=None,state='ready')

    def test_phone_is_explicit_calibrated_and_never_wire_enrolled(self):
        self.send(self.heartbeat())
        self.assertFalse(self.receiver.gate.healthy('phone'))
        self.calibrate();self.now+=100;self.send(dict(self.heartbeat(),seq=2))
        self.assertTrue(self.receiver.gate.healthy('phone'))
        self.now+=100
        message=dict(self.heartbeat(),seq=3,type='depth_observation',tracking='normal',sectors={n:dict(distance_m=.6,valid_fraction=1) for n in ('left','center','right')})
        del message['state']
        self.assertIsNotNone(self.send(message))
        self.assertEqual(self.receiver.phone_accepted,1)
        self.assertEqual(self.receiver.accepted,0)
        self.assertIsNone(self.send(message))
        self.assertEqual(self.receiver.phone_rejected,2) # missing mapping + duplicate
        self.receiver.invalidate()
        self.assertIsNone(self.receiver.gate.current('phone','depth_observation'))
        self.assertIsNone(self.send(dict(message,seq=4)))

    def test_unverified_drift_or_wrong_binding_never_admits_depth(self):
        self.receiver=VisionReceiver(self.session,clock=lambda:self.now,phone_binding=PhoneBinding('phone','phone-boot',None))
        Sender(Latest(),None,receiver=self.receiver);self.receiver.connected=True
        self.calibrate();self.now+=100;self.send(self.heartbeat())
        self.assertFalse(self.receiver.gate.healthy('phone'))
        self.assertEqual(self.receiver.gate.bounds,{})
        with self.assertRaises(ValueError):VisionReceiver(self.session,phone_binding=PhoneBinding('pi','other',0))
