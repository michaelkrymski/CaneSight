"""CS-017 synthetic receiver evidence, no phone/Pi hardware or network required."""
import json
from pathlib import Path
import unittest

from backend.freshness import CaptureAgeGate, Unavailable

EXAMPLES = Path(__file__).resolve().parents[2] / 'shared/protocol/v1/examples'


class LifecycleReceiverTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.gate = CaptureAgeGate('demo-session', 'replay', 'pi-camera-1', 'pi-boot-1',
                                  relative_drift_ppm=0, clock_ms=lambda: self.now)
        self.gate.enroll('phone-1', 'phone-boot-1', {'depth_observation', 'heartbeat'})
        self.heartbeat_sequence = 0
        self.calibrate()
        self.now += 50
        self.heartbeat()
        self.now += 50

    def calibrate(self):
        probe = self.gate.start_probe('phone-1')
        reply = dict(probe, type='clock_reply', t2_ms=self.now + 210, t3_ms=self.now + 210)
        self.now += 20
        self.gate.finish_probe(reply)

    def message(self, kind, seq):
        value = json.loads((EXAMPLES / f'{kind}.json').read_text(encoding='utf-8'))
        value.update(seq=seq, capture_monotonic_ms=self.now + 200 - 30)
        return value

    def heartbeat(self):
        self.heartbeat_sequence += 1
        self.gate.receive(dict(self.message('heartbeat', self.heartbeat_sequence), state='ready'))

    def test_silent_phone_suspension_expires_without_interruption_packet(self):
        observation = self.gate.receive(self.message('depth', 1))
        self.assertIsNotNone(observation)
        self.now = observation.deadline_ms + .01
        self.assertIn(('phone-1', 'depth_observation'), self.gate.expire())
        self.assertIsNone(self.gate.current('phone-1', 'depth_observation'))

    def test_heartbeats_after_resume_cannot_restore_or_retimestamp_depth(self):
        observation = self.gate.receive(self.message('depth', 1))
        original = observation.message['capture_monotonic_ms']
        self.now += 100
        self.heartbeat()
        current = self.gate.current('phone-1', 'depth_observation')
        self.assertEqual(current.message['capture_monotonic_ms'], original)
        self.assertEqual(current.deadline_ms, observation.deadline_ms)
        self.now = observation.deadline_ms + 1
        self.heartbeat()
        self.assertTrue(self.gate.healthy('phone-1'))
        self.assertIsNone(self.gate.current('phone-1', 'depth_observation'))

    def test_reconnect_needs_new_mapping_and_new_capture_and_keeps_sequence(self):
        old = self.message('depth', 10)
        self.gate.receive(old)
        self.gate.interrupt()
        self.assertIsNone(self.gate.current('phone-1', 'depth_observation'))
        self.assertEqual(self.gate.bounds, {})
        with self.assertRaises(Unavailable):
            self.gate.receive(self.message('depth', 11))
        self.now += 1100
        self.calibrate()
        self.now += 50
        self.heartbeat()
        with self.assertRaises(ValueError):
            self.gate.receive(old)
        with self.assertRaises(Unavailable):
            self.gate.receive(dict(old, seq=12))
        self.now += 50
        self.assertIsNotNone(self.gate.receive(self.message('depth', 13)))


if __name__ == '__main__':
    unittest.main()
