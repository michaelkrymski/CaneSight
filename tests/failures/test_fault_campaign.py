"""CS-044 multi-stage failure campaigns; synthetic inputs and simulated outputs."""
import copy
import json
import unittest
from jsonschema import ValidationError
from backend.app import protocol
from backend.freshness import CaptureAgeGate
from edge.haptics import HapticScheduler
from edge.policy import LocalPolicy
from edge.watchdog import PolicyWatchdog

class FaultCampaignTests(unittest.TestCase):
    def setUp(self):
        self.now=1000
        self.clock=lambda:self.now
        self.gate=CaptureAgeGate('campaign','replay','pi','pi-boot',clock_ms=self.clock,relative_drift_ppm=0)
        self.gate.enroll('phone','phone-boot',{'depth_observation','heartbeat'})
        self.boot='phone-boot';self.seq=0
        self.calibrate();self.heartbeat()
        self.scheduler=HapticScheduler(clock=self.clock)
        self.watchdog=PolicyWatchdog(self.scheduler.trip,clock=self.clock)
        self.scheduler.set_guard(self.watchdog.deadline)
        self.policy=LocalPolicy(self.gate,'phone',self.scheduler,clock=self.clock,watchdog=self.watchdog)
        self.policy.arm(True)
        self.addCleanup(self.scheduler.close)
        self.addCleanup(self.watchdog.close)
        self.addCleanup(self.policy.close)
        self.advance(300)

    def calibrate(self):
        probe=self.gate.start_probe('phone')
        self.gate.finish_probe(dict(probe,type='clock_reply',t2_ms=self.now,t3_ms=self.now))

    def packet(self,kind,**fields):
        self.seq+=1
        return dict(schema_version=1,type=kind,session_id='campaign',mode='replay',source_id='phone',boot_id=self.boot,seq=self.seq,capture_monotonic_ms=self.now,capture_utc=None,**fields)

    def heartbeat(self):self.gate.receive(self.packet('heartbeat',state='ready'))

    def depth(self):
        packet=self.packet('depth_observation',tracking='normal',sectors={name:dict(distance_m=.6 if name=='left' else 2,valid_fraction=1) for name in ('left','center','right')})
        packet['capture_monotonic_ms']-=20
        return packet

    def ingest(self,packet):
        value=self.gate.receive(protocol.parse_wire(json.dumps(packet).encode()))
        self.policy.tick()
        return value

    def advance(self,ms):
        until=self.now+ms
        while self.now<until:
            self.now=min(until,self.now+10)
            self.scheduler.tick();self.policy.tick();self.watchdog.tick()

    def active(self):return any(self.scheduler.snapshot()['outputs'].values())

    def recover(self):
        self.ingest(self.depth());self.advance(100)
        packet=self.depth();self.ingest(packet)
        self.assertTrue(self.scheduler.snapshot()['outputs']['left'])
        return packet

    def test_n01_disconnect_then_new_epoch_cannot_reuse_old_evidence(self):
        old=self.recover()
        self.gate.interrupt();self.policy.tick()
        self.assertFalse(self.active())
        self.assertEqual(self.policy.hazards['left'],'unknown')
        self.gate.enroll('phone','new-phone-boot',{'depth_observation','heartbeat'})
        self.boot='new-phone-boot'
        with self.assertRaises(ValueError):self.ingest(dict(old,seq=999))
        self.assertFalse(self.active())
        self.calibrate();self.heartbeat();self.advance(300)
        self.ingest(self.depth());self.assertFalse(self.active())
        self.advance(100);self.ingest(self.depth());self.assertTrue(self.active())
        self.assertEqual(self.scheduler.accepted,2)

    def test_n01_silent_source_expires_depth_then_health_without_network_callbacks(self):
        self.recover();accepted=self.scheduler.accepted
        self.advance(600)
        self.assertTrue(self.gate.healthy('phone'))
        self.assertFalse(self.active())
        self.assertEqual(self.policy.hazards['left'],'unknown')
        self.advance(2000)
        self.assertFalse(self.gate.healthy('phone'))
        self.assertFalse(self.active())
        self.assertEqual(self.scheduler.accepted,accepted)

    def test_n02_delayed_capture_barrage_cannot_become_fresh_at_receipt(self):
        old=self.recover();accepted=self.scheduler.accepted
        self.advance(600)
        for _ in range(20):
            self.heartbeat()
            self.seq+=1
            with self.assertRaises(ValueError):self.ingest(dict(old,seq=self.seq))
            self.policy.tick();self.advance(20)
        self.assertTrue(self.gate.healthy('phone'))
        self.assertFalse(self.active())
        self.assertEqual(self.policy.hazards['left'],'unknown')
        self.assertEqual(self.scheduler.accepted,accepted)

    def test_n03_combined_replay_mode_identity_future_and_reorder_after_expiry(self):
        old=self.recover();accepted=self.scheduler.accepted
        self.advance(600)
        for change in [{},{'seq':0},{'mode':'live'},{'session_id':'other'},
                       {'source_id':'other'},{'boot_id':'other'},
                       {'seq':999,'capture_monotonic_ms':self.now+1}]:
            packet=copy.deepcopy(old);packet.update(change)
            with self.assertRaises(ValueError):self.ingest(packet)
            self.policy.tick()
            self.assertFalse(self.active())
        self.assertEqual(self.scheduler.accepted,accepted)
        self.assertEqual(self.gate.sequence.active['phone'][0],'phone-boot')

    def test_n05_malformed_wire_cannot_sustain_expired_policy(self):
        old=self.recover();accepted=self.scheduler.accepted
        invalid=[b'{}',b'not-json',b'\xff',b'x'*8193,b'{"x":1,"x":2}',
                 json.dumps(dict(old,safe_to_cross=True)).encode(),
                 json.dumps(dict(old,capture_monotonic_ms=float('nan'))).encode()]
        self.advance(600)
        for raw in invalid:
            with self.assertRaises((ValueError,ValidationError)):self.gate.receive(protocol.parse_wire(raw))
            self.policy.tick();self.assertFalse(self.active())
        self.assertEqual(self.scheduler.accepted,accepted)
        self.assertEqual(self.policy.snapshot()['guidance'],'unavailable')
