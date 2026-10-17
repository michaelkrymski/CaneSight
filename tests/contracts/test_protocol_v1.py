import importlib.util
import json
from pathlib import Path
import sys
import unittest
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / 'shared/protocol/v1'
spec = importlib.util.spec_from_file_location('canesight_protocol_v1', V1 / 'reference.py')
protocol = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)


def fixture(name):
    return json.loads((V1 / 'examples' / (name+'.json')).read_text(encoding='utf-8'))


class SchemaTests(unittest.TestCase):
    def test_schema_and_replay_examples_are_valid(self):
        protocol.Draft202012Validator.check_schema(protocol.SCHEMA)
        for name in ('depth','frame','vision','heartbeat','clock-probe','clock-reply'):
            message = fixture(name)
            self.assertEqual(protocol.parse_wire(json.dumps(message).encode()), message)
            self.assertEqual(message['mode'], 'replay')

    def test_utc_is_nullable_diagnostic_but_must_be_real_utc_if_present(self):
        for utc in ('2026-10-17T14:00:00Z',None):
            protocol.validate_message(dict(fixture('depth'),capture_utc=utc))
        for utc in ('nonsenseZ','2026-02-31T14:00:00Z','2026-10-17T14:00:00+01:00'):
            with self.subTest(utc=utc), self.assertRaises((ValueError,ValidationError)):
                protocol.validate_message(dict(fixture('depth'),capture_utc=utc))

    def test_rejects_wrong_version_unknown_keys_and_permission_fields(self):
        for key, value in [('schema_version',2),('safe_to_cross',True),('motor_left',1),('go',True)]:
            message = fixture('depth')
            message[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                protocol.validate_message(message)

    def test_rejects_nonfinite_negative_bool_and_unsafe_integer(self):
        for key, value in [('seq',True),('seq',9007199254740992),('capture_monotonic_ms',float('nan')),('capture_monotonic_ms',float('inf')),('capture_monotonic_ms',-1)]:
            message = fixture('depth')
            message[key] = value
            with self.subTest(value=value), self.assertRaises((ValueError,ValidationError)):
                protocol.validate_message(message)

    def test_strict_wire_rejects_duplicate_keys_oversize_and_non_json_constants(self):
        for raw in (b'{"seq":1,"seq":2}', b' '*8193, b'{"value":NaN}', b'{"value":1e999}', b'\xff'):
            with self.subTest(raw=raw[:30]), self.assertRaises((ValueError,ValidationError)):
                protocol.parse_wire(raw)

    def test_unknown_distance_and_tracking(self):
        message = fixture('depth')
        message['tracking'] = 'limited'
        with self.assertRaises(ValueError):
            protocol.validate_message(message)
        for sector in message['sectors'].values():
            sector['distance_m'] = None
        protocol.validate_message(message)
        message['tracking'] = 'normal'
        message['sectors']['left'] = {'distance_m':1, 'valid_fraction':0}
        with self.assertRaises(ValueError):
            protocol.validate_message(message)

    def test_image_limits_and_array_bounds(self):
        message = fixture('frame')
        for key, value in [('jpeg_bytes',1000001),('image',{'width':1921,'height':480})]:
            bad = dict(message, **{key:value})
            with self.assertRaises(ValidationError):
                protocol.validate_message(bad)
        vision = fixture('vision')
        detection = dict(label='person',confidence=.8,bbox_xyxy=[.1,.2,.3,.4])
        vision['detections'] = [detection]*33
        with self.assertRaises(ValidationError):
            protocol.validate_message(vision)
        vision['detections'] = [dict(detection,bbox_xyxy=[.3,.2,.1,.4])]
        with self.assertRaises(ValueError):
            protocol.validate_message(vision)

    def test_ambiguous_signal_is_unknown_and_countdown_is_nullable(self):
        vision = fixture('vision')
        vision['signal'] = dict(candidate_count=2,symbol='walk',confidence=.9,countdown_s=12)
        with self.assertRaises(ValueError):
            protocol.validate_message(vision)
        vision['signal'] = dict(candidate_count=2,symbol='unknown',confidence=None,countdown_s=None)
        protocol.validate_message(vision)
        vision['signal']['countdown_s'] = 12
        with self.assertRaises(ValueError):
            protocol.validate_message(vision)


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.gate = protocol.SequenceGate('demo-session','replay')
        self.gate.enroll('phone-1','phone-boot-1',{'depth_observation','heartbeat'})

    def test_duplicate_and_reordered_packets(self):
        message = fixture('depth')
        self.gate.admit(message)
        for sequence in (104,103):
            with self.assertRaises(ValueError):
                self.gate.admit(dict(message,seq=sequence))
        self.gate.admit(dict(message,seq=105))

    def test_unknown_source_session_mode_epoch_and_role(self):
        for key,value in [('source_id','other'),('session_id','other'),('mode','live'),('boot_id','new-boot')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.gate.admit(dict(fixture('depth'),**{key:value}))
        self.gate.enroll('phone-1','phone-boot-1',{'depth_observation','heartbeat'})
        with self.assertRaises(ValueError):
            self.gate.admit(fixture('vision'))

    def test_reconnect_cannot_reset_and_retired_epoch_cannot_return(self):
        message = fixture('depth')
        self.gate.admit(message)
        self.gate.enroll('phone-1','phone-boot-1',{'depth_observation','heartbeat'})
        with self.assertRaises(ValueError):
            self.gate.admit(message)
        self.gate.enroll('phone-1','phone-boot-2',{'depth_observation','heartbeat'})
        self.gate.admit(dict(message,boot_id='phone-boot-2',seq=0))
        with self.assertRaises(ValueError):
            self.gate.admit(dict(message,seq=106))
        with self.assertRaises(ValueError):
            self.gate.enroll('phone-1','phone-boot-1',{'depth_observation'})

    def test_stream_sequences_are_independent(self):
        self.gate.admit(fixture('depth'))
        self.gate.admit(fixture('heartbeat'))  # seq 8 vs depth seq 104


class FreshnessTests(unittest.TestCase):
    def test_clock_control_correlates_nonce_identity_timestamp_and_deadline(self):
        probe,reply = fixture('clock-probe'),fixture('clock-reply')
        bound = protocol.verify_clock_reply(probe,reply,1030,0)
        self.assertEqual(bound.lower_offset_ms,185)
        for key,value in [('nonce','different'),('session_id','other'),('receiver_boot_id','old-boot'),('source_boot_id','old-phone'),('mode','live'),('t1_ms',1001)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                protocol.verify_clock_reply(probe,dict(reply,**{key:value}),1030,0)
        with self.assertRaises(ValueError):
            protocol.verify_clock_reply(probe,reply,2001,0)

    def test_exact_budgets_and_unbounded_or_future_age(self):
        for kind,limit in protocol.LIMITS_MS.items():
            self.assertTrue(protocol.within_budget(kind,(limit,limit)))
            for age in ((limit+.01,limit+.01),None,(-1,1),(10,5),(0,float('inf'))):
                with self.subTest(kind=kind,age=age):
                    self.assertFalse(protocol.within_budget(kind,age))

    def test_clock_exchange_offset_asymmetry_and_uncertainty(self):
        clock = protocol.ClockBound.from_exchange('phone-1','phone-boot-1','pi-boot-1',1000,1210,1215,1030,0)
        message = dict(fixture('depth'),capture_monotonic_ms=1250)
        age = clock.age_interval(message,1150,'pi-boot-1')
        self.assertEqual(age,(85,110))
        self.assertTrue(protocol.within_budget('depth_observation',age))
        self.assertFalse(protocol.within_budget('depth_observation',(0,300)))
        with self.assertRaises(ValueError):
            protocol.ClockBound.from_exchange('a','b','c',100,200,500,110,0)

    def test_expired_mapping_wrong_epoch_and_precalibration_capture(self):
        clock = protocol.ClockBound.from_exchange('phone-1','phone-boot-1','pi-boot-1',1000,1210,1215,1030,200)
        message = dict(fixture('depth'),capture_monotonic_ms=1250)
        for now,boot,msg in [(11031,'pi-boot-1',message),(1150,'new-pi',message),(1150,'pi-boot-1',dict(message,boot_id='new-phone')),(1150,'pi-boot-1',dict(message,capture_monotonic_ms=1200))]:
            with self.assertRaises(ValueError):
                clock.age_interval(msg,now,boot)
        lower,upper = clock.age_interval(message,1150,'pi-boot-1')
        self.assertLess(lower,85)
        self.assertGreater(upper,110)

    def test_vision_lineage_includes_entire_round_trip_and_heartbeat_cannot_renew(self):
        vision = fixture('vision')
        pending = fixture('frame')
        original = protocol.local_vision_age(vision,pending,42500,'demo-session','replay')
        self.assertTrue(protocol.within_budget('vision_observation',original))
        # Receiving heartbeat/current server time never changes capture ledger.
        heartbeat = fixture('heartbeat')
        protocol.validate_message(heartbeat)
        later = protocol.local_vision_age(vision,pending,42501,'demo-session','replay')
        self.assertFalse(protocol.within_budget('vision_observation',later))

    def test_retimed_wrong_or_replayed_frame_result_is_rejected(self):
        vision = fixture('vision')
        for key,value in [('frame_id','another'),('capture_monotonic_ms',42000),('boot_id','old-boot'),('seq',10),('image',{'width':100,'height':100}),('session_id','other'),('mode','live')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                protocol.local_vision_age(dict(vision,**{key:value}),fixture('frame'),42500,'demo-session','replay')


if __name__ == '__main__':
    unittest.main()
