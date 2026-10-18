"""Explicit CS-016 Swift->accepted Python protocol/backend fixture conformance.

Builds its Swift fixture when Swift is installed; generated replay data only.
This separate test root does not change protected CI workflows.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from backend.app import protocol
from backend.sessions import SessionManager, SessionRequest
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT/'ios/CaneSightTelemetry'


class SwiftWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get('CANESIGHT_TELEMETRY_FIXTURES_BIN')
        if not binary:
            if not shutil.which('swift'):
                raise unittest.SkipTest('Swift compiler/fixture binary unavailable; run explicitly after swift build')
            # A clean CI checkout can have Swift without any package artifacts.
            # Build the current product rather than requiring a stale local binary.
            subprocess.run(['swift', 'build', '--package-path', str(PACKAGE),
                            '--product', 'TelemetryFixtures', '--jobs', '2'],
                           text=True, capture_output=True, timeout=180, check=True)
            result = subprocess.run(['swift', 'build', '--package-path', str(PACKAGE), '--show-bin-path'],
                                    text=True, capture_output=True, timeout=30, check=True)
            binary = str(Path(result.stdout.strip())/'TelemetryFixtures')
        if not Path(binary).is_file():
            raise RuntimeError('Build TelemetryFixtures before running Swift conformance tests')
        result = subprocess.run([binary], text=True, capture_output=True, timeout=10, check=True)
        cls.raw = [line.encode() for line in result.stdout.splitlines()]
        cls.packets = [protocol.parse_wire(raw) for raw in cls.raw]

    def manager(self):
        manager = SessionManager('fixture-operator-credential-never-deploy-000001', clock=lambda: 1000)
        request = SessionRequest.model_validate(dict(mode='replay',
            phone=dict(source_id='phone-1', boot_id='phone-boot-1'),
            pi=dict(source_id='pi-1', boot_id='pi-boot-1')))
        with patch('backend.sessions.secrets.token_hex', return_value='demo-session'):
            manager.create(request)
        session = manager.sessions['demo-session']
        grants = {grant.role: grant for grant in session.ingress.grants}
        phone, pi = manager.attach(session, 'phone'), manager.attach(session, 'pi')
        return manager, session, grants, phone, pi

    def test_original_swift_bytes_match_accepted_closed_schema_and_unknown_semantics(self):
        self.assertEqual([p['type'] for p in self.packets],
                         ['heartbeat', 'depth_observation', 'depth_observation', 'clock_reply'])
        for raw in self.raw:
            self.assertLessEqual(len(raw), 8192)
        first, second = self.packets[1:3]
        self.assertEqual(first['capture_monotonic_ms'], 1002)
        self.assertEqual(second['capture_monotonic_ms'], 1102)
        self.assertIsNone(first['sectors']['right']['distance_m'])
        self.assertEqual(second['tracking'], 'limited')
        self.assertTrue(all(s['distance_m'] is None for s in second['sectors'].values()))
        self.assertTrue(all(p['mode'] == 'replay' for p in self.packets))
        self.assertNotIn('token', json.dumps(self.packets))

    def test_accepted_backend_relays_original_swift_depth_and_heartbeat_with_role_binding(self):
        manager, session, grants, phone, pi = self.manager()
        for packet in self.packets[:3]:
            manager.relay(session, grants['phone'], phone, packet)
            self.assertEqual(pi.queue.get_nowait(), packet)
        with self.assertRaises(ValueError):
            manager.relay(session, grants['phone'], phone, self.packets[1])
        self.assertEqual([p['seq'] for p in self.packets[:3]], [0, 0, 1])

    def test_swift_clock_reply_matches_accepted_native_exchange(self):
        manager, session, grants, phone, pi = self.manager()
        reply = self.packets[3]
        probe = {k: v for k, v in reply.items() if k not in ('t2_ms', 't3_ms')}
        probe['type'] = 'clock_probe'
        protocol.validate_message(probe)
        manager.relay(session, grants['pi'], pi, probe)
        self.assertEqual(phone.queue.get_nowait(), probe)
        manager.relay(session, grants['phone'], phone, reply)
        self.assertEqual(pi.queue.get_nowait(), reply)
        self.assertEqual(reply['t1_ms'], 1000)
        self.assertEqual(reply['t2_ms'], 1200)
        self.assertEqual(reply['t3_ms'], 1201)
        with self.assertRaises(ValueError):
            manager.relay(session, grants['phone'], phone, reply)

    def test_foreign_epoch_mode_unknown_fields_and_readiness_injection_are_rejected(self):
        for change in (dict(boot_id='retired-boot'), dict(mode='live'),
                       dict(go=True), dict(state='all-clear')):
            manager, session, grants, phone, _ = self.manager()
            packet = copy.deepcopy(self.packets[0]); packet.update(change)
            with self.assertRaises((ValueError, ValidationError)):
                manager.relay(session, grants['phone'], phone, packet)


if __name__ == '__main__':
    unittest.main()
