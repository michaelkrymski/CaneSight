"""CS-030 stateful capture-age, clock correlation and lineage failure suite."""
import copy
import json
import ssl
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.freshness import CaptureAgeGate, Unavailable
from backend.events_client import PairedEventsClient

ROOT = Path(__file__).resolve().parents[2] / 'shared/protocol/v1/examples'


def fixture(name):
    return json.loads((ROOT / f'{name}.json').read_text())


class CaptureAgeTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.gate = self.make_gate()
        self.seq = 0

    def make_gate(self, drift=0):
        gate = CaptureAgeGate('demo-session', 'replay', 'pi-camera-1', 'pi-boot-1',
                             relative_drift_ppm=drift, clock_ms=lambda: self.now)
        gate.enroll('phone-1', 'phone-boot-1', {'depth_observation', 'heartbeat'})
        gate.enroll('pi-camera-1', 'pi-boot-1', {'frame_metadata', 'vision_observation'})
        return gate

    def calibrate(self, gate=None, delay=20):
        gate = self.gate if gate is None else gate
        probe = gate.start_probe('phone-1')
        reply = dict(probe, type='clock_reply', t2_ms=self.now+210, t3_ms=self.now+210)
        self.now += delay
        gate.finish_probe(reply)
        return probe, reply

    def heartbeat(self, gate=None, age=30, state='ready'):
        gate = self.gate if gate is None else gate
        self.seq += 1
        message = dict(fixture('heartbeat'), seq=self.seq, state=state,
                       capture_monotonic_ms=self.now+200-age)
        gate.receive(message)
        return message

    def ready_phone(self):
        self.calibrate()
        self.now += 50
        self.heartbeat()
        self.now += 50

    def depth(self, age=30, seq=104):
        return dict(fixture('depth'), seq=seq, capture_monotonic_ms=self.now+200-age)

    def frame(self, seq=9, frame_id=None):
        return dict(fixture('frame'), seq=seq, frame_id=frame_id or f'frame-{seq}',
                    capture_monotonic_ms=self.now)

    def vision(self, frame):
        result = fixture('vision')
        for key in ('session_id','mode','source_id','boot_id','seq','frame_id','capture_monotonic_ms','capture_utc','image'):
            result[key] = copy.deepcopy(frame[key])
        return result

    def test_missing_clock_and_unverified_drift_remain_unavailable(self):
        with self.assertRaises(Unavailable):
            self.gate.receive(self.depth())
        unknown = self.make_gate(drift=None)
        with self.assertRaises(Unavailable):
            self.calibrate(unknown)
        self.assertFalse(unknown.healthy('phone-1'))
        self.assertIsNone(unknown.current('phone-1', 'depth_observation'))

    def test_clock_nonce_is_consumed_once_and_identity_is_bound(self):
        probe, reply = self.calibrate()
        with self.assertRaises(Unavailable):
            self.gate.finish_probe(reply)
        self.now += 1000
        pending = self.gate.start_probe('phone-1')
        wrong = dict(pending, type='clock_reply', t2_ms=self.now+200,
                     t3_ms=self.now+200, receiver_boot_id='old-pi')
        with self.assertRaises(Unavailable):
            self.gate.finish_probe(wrong)
        self.assertEqual(self.gate.bounds, {})
        self.assertNotEqual(probe['nonce'], pending['nonce'])

    def test_late_asymmetric_and_uncertain_clock_exchange(self):
        self.calibrate()  # 190..210 ms offset; no equal-delay assumption.
        bound = self.gate.bounds['phone-1']
        self.assertEqual((bound.lower_offset_ms,bound.upper_offset_ms), (190,210))
        self.now += 1000
        probe = self.gate.start_probe('phone-1')
        self.now += 1001
        with self.assertRaises(Unavailable):
            self.gate.finish_probe(dict(probe, type='clock_reply', t2_ms=probe['t1_ms']+200,
                                        t3_ms=probe['t1_ms']+200))
        self.now += 1000
        with self.assertRaises(Unavailable):
            self.calibrate(delay=300)  # Half width 150 ms >100 ms.

    def test_probe_rate_and_one_pending_bound(self):
        self.gate.start_probe('phone-1')
        with self.assertRaises(Unavailable):
            self.gate.start_probe('phone-1')
        self.now += 1000
        with self.assertRaises(Unavailable):
            self.gate.start_probe('phone-1')
        self.now += .01
        self.gate.start_probe('phone-1')
        self.assertEqual(len(self.gate.probes), 1)

    def test_depth_expires_independently_and_heartbeat_cannot_renew(self):
        self.ready_phone()
        observation = self.gate.receive(self.depth())
        deadline = observation.deadline_ms
        self.now += 100
        self.heartbeat()
        self.assertEqual(self.gate.current('phone-1','depth_observation').deadline_ms, deadline)
        self.now = deadline
        self.assertIsNotNone(self.gate.current('phone-1','depth_observation'))
        self.now += .01
        self.assertEqual(self.gate.expire(), [('phone-1','depth_observation')])
        self.assertTrue(self.gate.healthy('phone-1'))
        self.assertIsNone(self.gate.current('phone-1','depth_observation'))

    def test_old_future_precalibration_and_wrong_session_packets(self):
        self.ready_phone()
        for index, age in enumerate((501, -50, 1000)):
            with self.assertRaises(Unavailable):
                self.gate.receive(self.depth(age, seq=104+index))
        for key,value in (('session_id','other'),('boot_id','old-boot'),('mode','live'),('source_id','other')):
            with self.assertRaises(ValueError):
                self.gate.receive(dict(self.depth(seq=200), **{key:value}))

    def test_replay_and_reordered_observations_never_restore_expired_state(self):
        self.ready_phone()
        message = self.depth()
        observation = self.gate.receive(message)
        self.now = observation.deadline_ms + 1
        for seq in (104,103):
            with self.assertRaises(ValueError):
                self.gate.receive(dict(message, seq=seq))
        self.assertIsNone(self.gate.current('phone-1','depth_observation'))

    def test_limited_tracking_missing_samples_and_zero_are_unknown(self):
        self.ready_phone()
        message = self.depth()
        self.gate.receive(message)
        unknown = self.depth(seq=105)
        unknown['tracking'] = 'unavailable'
        for sector in unknown['sectors'].values():
            sector['distance_m'] = None
        self.assertIsNone(self.gate.receive(unknown))
        self.assertIsNone(self.gate.current('phone-1','depth_observation'))
        zero = self.depth(seq=106)
        zero['sectors']['left']['distance_m'] = 0
        self.assertIsNone(self.gate.receive(zero))

    def test_health_expiry_degradation_and_recovery_require_new_capture(self):
        self.ready_phone()
        self.gate.receive(self.depth())
        self.heartbeat(state='degraded')
        self.assertFalse(self.gate.healthy('phone-1'))
        self.assertIsNone(self.gate.current('phone-1','depth_observation'))
        self.now += 100
        old = self.depth(seq=105)
        self.heartbeat()
        with self.assertRaises(Unavailable):
            self.gate.receive(old)  # Captured before ready recovery.
        self.now += 50
        self.gate.receive(self.depth(seq=106))
        self.now += 2501
        self.assertFalse(self.gate.healthy('phone-1'))
        self.assertIsNone(self.gate.current('phone-1','depth_observation'))

    def test_resync_never_extends_an_existing_observation_deadline(self):
        self.ready_phone()
        self.now += 1000
        self.heartbeat()
        self.now += 50
        observation = self.gate.receive(self.depth())
        self.calibrate()
        self.assertEqual(self.gate.current('phone-1','depth_observation').deadline_ms,
                         observation.deadline_ms)

    def test_drift_widening_and_expired_mapping_remove_eligibility(self):
        self.gate = self.make_gate(drift=200)
        self.ready_phone()
        observation = self.gate.receive(self.depth())
        self.now = observation.deadline_ms  # Additional drift can expire earlier.
        self.assertIsNone(self.gate.current('phone-1','depth_observation'))
        self.now = 11021
        with self.assertRaises(Unavailable):
            self.heartbeat()

    def test_clock_reset_is_sticky_until_new_receiver_epoch(self):
        self.ready_phone()
        self.gate.receive(self.depth())
        self.now = 1
        with self.assertRaises(Unavailable):
            self.gate.current('phone-1','depth_observation')
        self.now = 2000
        with self.assertRaises(Unavailable):
            self.gate.start_probe('phone-1')
        self.assertEqual(self.gate.observations, {})

    def test_reconnect_preserves_sequences_and_retires_old_probe_and_frames(self):
        self.ready_phone()
        self.gate.receive(self.depth())
        self.gate.interrupt()
        self.assertEqual(self.gate.bounds, {})
        self.assertIsNone(self.gate.current('phone-1','depth_observation'))
        self.now += 1001
        self.calibrate()
        self.now += 50
        self.heartbeat()
        self.now += 50
        with self.assertRaises(ValueError):
            self.gate.receive(self.depth(seq=104))
        self.assertIsNotNone(self.gate.receive(self.depth(seq=105)))

    def test_authorized_source_boot_change_purges_maps_and_retires_epoch(self):
        self.ready_phone()
        self.gate.receive(self.depth())
        self.gate.enroll('phone-1','new-boot',{'depth_observation','heartbeat'})
        self.assertEqual(self.gate.bounds, {})
        self.assertFalse(self.gate.healthy('phone-1'))
        with self.assertRaises(ValueError):
            self.gate.receive(self.depth(seq=0))
        with self.assertRaises(ValueError):
            self.gate.enroll('phone-1','phone-boot-1',{'depth_observation'})
        with self.assertRaises(ValueError):
            self.gate.enroll('pi-camera-1','new-pi-boot',{'vision_observation'})

    def test_vision_lineage_includes_entire_capture_round_trip_and_expires(self):
        self.gate.set_local_ready(True)
        frame = self.frame()
        self.gate.record_frame(frame)
        self.now += 1200
        observation = self.gate.receive(self.vision(frame))
        self.assertEqual(observation.deadline_ms, frame['capture_monotonic_ms']+1500)
        self.now = observation.deadline_ms
        self.assertIsNotNone(self.gate.current('pi-camera-1','vision_observation'))
        self.now += .01
        self.assertIsNone(self.gate.current('pi-camera-1','vision_observation'))
        self.assertTrue(self.gate.healthy('pi-camera-1'))

    def test_retimed_capture_utc_and_dimensions_cannot_match_origin_ledger(self):
        self.gate.set_local_ready(True)
        frame = self.frame()
        self.gate.record_frame(frame)
        self.now += 100
        for key,value in (('capture_monotonic_ms',self.now+1), ('capture_utc','2026-10-17T00:00:00Z'),
                          ('image',{'width':10,'height':10})):
            # Separate gate for each tampered result, since replay marks persist.
            gate = self.make_gate()
            gate.set_local_ready(True)
            new_frame = self.frame()
            gate.record_frame(new_frame)
            with self.assertRaises(Unavailable):
                gate.receive(dict(self.vision(new_frame), **{key:value}))

    def test_frame_ledger_bounds_consumption_and_old_results_cannot_revive(self):
        self.gate.set_local_ready(True)
        frames = [self.frame(seq=i) for i in (9,10,11)]
        for frame in frames:
            self.gate.record_frame(frame)
        self.assertEqual(len(self.gate.frames), 2)
        with self.assertRaises(Unavailable):
            self.gate.receive(self.vision(frames[0]))
        self.now += 100
        self.gate.receive(self.vision(frames[1]))
        with self.assertRaises(ValueError):
            self.gate.receive(self.vision(frames[1]))
        with self.assertRaises(Unavailable):
            self.gate.record_frame(dict(frames[1],seq=12))
        self.now += 1501
        with self.assertRaises(Unavailable):
            self.gate.receive(self.vision(frames[2]))

    def test_frame_future_local_fault_and_recovery_cannot_reuse_old_capture(self):
        with self.assertRaises(Unavailable):
            self.gate.record_frame(self.frame())
        self.gate.set_local_ready(True)
        future = dict(self.frame(),capture_monotonic_ms=self.now+1)
        with self.assertRaises(Unavailable):
            self.gate.record_frame(future)
        original = self.frame()
        self.gate.record_frame(original)
        self.gate.set_local_ready(False)
        self.now += 1
        self.gate.set_local_ready(True)
        with self.assertRaises(Unavailable):
            self.gate.record_frame(original)
        self.assertEqual(self.gate.frames, {})

    def test_returned_snapshot_is_not_mutable_internal_state(self):
        self.ready_phone()
        observation = self.gate.receive(self.depth())
        observation.message['sectors']['left']['distance_m'] = 999
        current = self.gate.current('phone-1','depth_observation')
        self.assertNotEqual(current.message['sectors']['left']['distance_m'], 999)

    def test_huge_integer_clock_is_unavailable_without_overflow_crash(self):
        self.ready_phone()
        with self.assertRaises(Unavailable):
            self.gate.receive(dict(self.depth(), capture_monotonic_ms=10**500))
        self.gate.set_local_ready(True)
        with self.assertRaises(Unavailable):
            self.gate.record_frame(dict(self.frame(), capture_monotonic_ms=10**500))

    def test_event_consumer_requires_verified_wss_and_explicit_contract_version(self):
        pair = {'schema_version':1, 'session_id':'demo-session','mode':'replay',
                'phone':{'source_id':'phone-1','boot_id':'phone-boot-1'},
                'pi':{'source_id':'pi-camera-1','boot_id':'pi-boot-1','token':'fixture-only-token-not-a-real-credential-00001'}}
        for origin in ('ws://example.com','wss://user:password@example.com',
                       'wss://example.com?token=forbidden','wss://example.com/other'):
            with self.assertRaises(ValueError):
                PairedEventsClient(origin, pair)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with self.assertRaises(ValueError):
            PairedEventsClient('wss://example.com', pair, ssl_context=context)
        with self.assertRaises(ValueError):
            CaptureAgeGate.for_pair(dict(pair,schema_version=2))


if __name__ == '__main__':
    unittest.main()
