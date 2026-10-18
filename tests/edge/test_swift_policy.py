"""Actual Swift-generated replay bytes -> accepted relay -> gate/policy simulation."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from backend.app import protocol
from backend.freshness import CaptureAgeGate
from backend.sessions import SessionManager, SessionRequest
from edge.haptics import HapticScheduler, SimulatedOutput
from edge.policy import LocalPolicy

FIXTURE = Path(__file__).resolve().parent / 'swift_policy_fixture'


class SwiftPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((FIXTURE / 'synthetic-wire.json').read_text(encoding='utf-8'))

    def setUp(self):
        self.now = 1000.0
        self.clock = lambda: self.now
        self.manager = SessionManager('synthetic-operator-only-never-deploy-000001', clock=lambda: self.now / 1000)
        request = SessionRequest.model_validate(dict(mode='replay', ttl_seconds=600,
            phone=dict(source_id='phone-1', boot_id='phone-boot-1'),
            pi=dict(source_id='pi-1', boot_id='pi-boot-1')))
        with patch('backend.sessions.secrets.token_hex', return_value='demo-session'):
            self.manager.create(request)
        self.session = self.manager.sessions['demo-session']
        self.grants = {grant.role: grant for grant in self.session.ingress.grants}
        self.phone = self.manager.attach(self.session, 'phone')
        self.pi = self.manager.attach(self.session, 'pi')
        self.gate = CaptureAgeGate('demo-session', 'replay', 'pi-1', 'pi-boot-1',
                                  relative_drift_ppm=0, clock_ms=self.clock)
        self.gate.enroll('phone-1', 'phone-boot-1', {'depth_observation', 'heartbeat'})
        self.output = SimulatedOutput()
        self.scheduler = HapticScheduler(self.output, clock=self.clock)
        self.policy = LocalPolicy(self.gate, 'phone-1', self.scheduler, clock=self.clock)
        self.policy.arm(True)
        self.addCleanup(self.scheduler.close)
        self.addCleanup(self.policy.close)
        with patch('backend.freshness.secrets.token_hex', return_value='swift-policy-probe'):
            probe = self.gate.start_probe('phone-1')
        self.assertEqual(probe, protocol.parse_wire(base64.b64decode(self.fixture['probe_base64'])))
        self.manager.relay(self.session, self.grants['pi'], self.pi, probe)
        self.assertEqual(self.phone.queue.get_nowait(), probe)

    def packet(self, side, index):
        row = self.fixture['scenarios'][side][index]
        return row, protocol.parse_wire(base64.b64decode(row['wire_base64'], validate=True))

    def advance(self, now):
        while self.now < now:
            self.now = min(now, self.now + 10)
            self.scheduler.tick()

    def deliver(self, side, index, *, delay=0):
        row, packet = self.packet(side, index)
        self.advance(row['phone_time_ms'] - 200 + delay)
        self.manager.relay(self.session, self.grants['phone'], self.phone, packet)
        relayed = self.pi.queue.get_nowait()
        self.assertEqual(relayed, packet) # No timestamp or distance replacement.
        if packet['type'] == 'clock_reply': self.gate.finish_probe(relayed)
        else: self.gate.receive(relayed)
        self.policy.tick()
        return packet

    def outputs(self): return self.scheduler.snapshot()['outputs']

    def test_fixture_bytes_have_exact_source_provenance_and_no_credentials(self):
        self.assertEqual(self.fixture['origin'], 'synthetic')
        for name, expected in self.fixture['provenance']['fixture_source_sha256'].items():
            self.assertEqual(hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest(), expected)
        pins = json.loads((FIXTURE / 'review-inputs.json').read_text(encoding='utf-8'))
        self.assertEqual(self.fixture['provenance']['telemetry_commit'], pins['commit'])
        for side in ('left', 'center', 'right'):
            packets = [self.packet(side, i)[1] for i in range(6)]
            self.assertEqual([p['type'] for p in packets],
                             ['clock_reply', 'heartbeat', 'depth_observation', 'depth_observation', 'depth_observation', 'heartbeat'])
            self.assertEqual([p['capture_monotonic_ms'] for p in packets[2:5]], [1700, 1800, 1900])
            for packet in packets:
                self.assertNotIn('token', packet)
                self.assertEqual(packet['mode'], 'replay')

    def test_two_swift_left_frames_drive_only_simulated_left(self):
        self.deliver('left', 0); self.deliver('left', 1); self.deliver('left', 2)
        self.assertEqual(self.scheduler.accepted, 0)
        packet = self.deliver('left', 3)
        self.assertEqual(self.outputs(), {'left': True, 'right': False})
        observation = self.gate.current('phone-1', 'depth_observation')
        self.assertEqual(observation.message['capture_monotonic_ms'], packet['capture_monotonic_ms'])
        self.assertEqual(observation.deadline_ms, 2100) # 1800 - offset 200 + age budget 500.

    def test_two_swift_center_frames_drive_both_simulated_channels(self):
        for index in range(4): self.deliver('center', index)
        self.assertEqual(self.outputs(), {'left': True, 'right': True})

    def test_two_swift_right_frames_drive_only_simulated_right(self):
        for index in range(4): self.deliver('right', index)
        self.assertEqual(self.outputs(), {'left': False, 'right': True})

    def test_swift_limited_tracking_cancels_and_heartbeat_cannot_restore(self):
        for index in range(3): self.deliver('left', index)
        self.deliver('left', 3, delay=30)
        self.assertTrue(self.outputs()['left'])
        unknown = self.deliver('left', 4)
        self.assertEqual(unknown['tracking'], 'limited')
        self.assertTrue(all(s['distance_m'] is None for s in unknown['sectors'].values()))
        self.assertFalse(any(self.outputs().values()))
        self.assertEqual(set(self.policy.hazards.values()), {'unknown'})
        accepted = self.scheduler.accepted
        self.deliver('left', 5)
        self.assertEqual(self.scheduler.accepted, accepted)
        self.assertFalse(any(self.outputs().values()))

    def test_delayed_original_swift_capture_cannot_become_fresh_at_receipt(self):
        self.deliver('left', 0); self.deliver('left', 1); self.deliver('left', 2)
        with self.assertRaises(ValueError): self.deliver('left', 3, delay=501)
        self.policy.tick()
        self.assertEqual(self.scheduler.accepted, 0)
        self.assertFalse(any(self.outputs().values()))

    def test_duplicate_and_foreign_boot_swift_packets_rejected_without_new_pulse(self):
        for index in range(4): self.deliver('left', index)
        accepted = self.scheduler.accepted
        _, packet = self.packet('left', 3)
        with self.assertRaises(ValueError): self.manager.relay(self.session, self.grants['phone'], self.phone, packet)
        foreign = copy.deepcopy(self.packet('left', 4)[1]); foreign['boot_id'] = 'retired-boot'
        with self.assertRaises(ValueError): self.manager.relay(self.session, self.grants['phone'], self.phone, foreign)
        self.advance(2200); self.policy.tick()
        self.assertEqual(self.scheduler.accepted, accepted)
        self.assertFalse(any(self.outputs().values()))


if __name__ == '__main__':
    unittest.main()
