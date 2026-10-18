"""Persistent enrollment preserves ephemeral sensor state and role separation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.bonds import BondRegistry, install_bonds, provision
from backend.bond_client import BondClient
from backend.sessions import SessionManager

OPERATOR = 'fixture-operator-not-a-real-credential-00001'


class BondTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'private'
        provision(self.path, 'https://testserver', 'cane-1', 'phone-1', 'pi-1')
        self.now = 1000
        self.manager = SessionManager(OPERATOR, clock=lambda: self.now)
        self.registry = BondRegistry(self.path / 'registry.json', self.manager)
        self.config = {r: json.loads((self.path / f'{r}-bond.json').read_text()) for r in ('phone', 'pi')}

    def poll(self, role, boot=None):
        return self.registry.connect('cane-1', role, boot or role + '-boot',
                                     'Bearer ' + self.config[role]['token'])

    def pair(self):
        self.assertEqual(self.poll('phone')[1], 202)
        pi, status = self.poll('pi')
        self.assertEqual(status, 200)
        phone, status = self.poll('phone')
        self.assertEqual(status, 200)
        self.assertEqual(phone['session_id'], pi['session_id'])
        return phone, pi

    def test_provision_is_private_no_overwrite_and_registry_has_only_hashes(self):
        raw = (self.path / 'registry.json').read_text()
        for c in self.config.values():
            self.assertNotIn(c['token'], raw)
            self.assertIn(hashlib.sha256(c['token'].encode()).hexdigest(), raw)
        with self.assertRaises(FileExistsError):
            provision(self.path, 'https://testserver', 'cane-1', 'phone-1', 'pi-1')

    def test_first_pair_and_repeated_polls_do_not_rotate(self):
        phone, pi = self.pair()
        self.assertNotEqual(phone['device']['token'], pi['device']['token'])
        self.assertNotIn('token', phone['peer'])
        self.assertNotIn(self.config['pi']['token'], json.dumps(phone))
        for _ in range(5):
            self.now += 5
            self.assertEqual(self.poll('pi')[0]['session_id'], pi['session_id'])
        self.assertEqual(len(self.manager.sessions), 1)

    def test_expiry_automatically_reissues_without_manual_pairing(self):
        phone, pi = self.pair()
        self.now += 601
        self.assertEqual(self.poll('phone')[1], 202)
        new, status = self.poll('pi')
        self.assertEqual(status, 200)
        self.assertNotEqual(new['session_id'], pi['session_id'])
        with self.assertRaises(HTTPException):
            self.manager.authenticate('Bearer ' + pi['device']['token'], 'pi')

    def test_active_pair_continues_beyond_ten_minutes_without_socket_rotation(self):
        phone, pi = self.pair()
        session = self.manager.sessions[pi['session_id']]
        original_grant = session.ingress.grants[0]
        for _ in range(150):
            self.now += 5
            for role in ('phone', 'pi'):
                current, status = self.poll(role)
                self.assertEqual(status, 200)
                self.assertEqual(current['session_id'], pi['session_id'])
                self.assertEqual(current['device']['token'], (phone if role == 'phone' else pi)['device']['token'])
        self.assertIs(session.ingress.grants[0], original_grant)
        self.assertGreater(original_grant.expires_at, self.now)
        # One still-polling device cannot keep an absent peer's session alive.
        for _ in range(20):
            self.now += 5
            latest, status = self.poll('pi')
        self.assertEqual(status, 202)
        self.assertNotIn(pi['session_id'], self.manager.sessions)

    def test_key_rotation_and_frame_capacity_create_clean_epochs(self):
        _, pi = self.pair()
        session = self.manager.sessions[pi['session_id']]
        session.ingress.seen_ids['fixture'] = set(range(4000))
        new, status = self.poll('pi')
        self.assertEqual(status, 200)
        self.assertNotEqual(new['session_id'], pi['session_id'])
        registry = json.loads((self.path / 'registry.json').read_text())
        changed_token = 'fixture-rotated-role-credential-long-enough-123'
        registry['bonds'][0]['pi']['token_sha256'] = hashlib.sha256(changed_token.encode()).hexdigest()
        (self.path / 'registry.json').write_text(json.dumps(registry))
        self.config['pi']['token'] = changed_token
        rotated, status = self.poll('pi')
        self.assertEqual(status, 200)
        self.assertNotEqual(rotated['session_id'], new['session_id'])

    def test_reboot_revokes_both_credentials_and_forgets_data(self):
        phone, pi = self.pair()
        session = self.manager.sessions[phone['session_id']]
        session.ingress.latest['test'] = 'old-image'
        conn = self.manager.attach(session, 'phone')
        new, status = self.poll('pi', 'new-pi-boot')
        self.assertEqual(status, 200)
        self.assertNotEqual(new['session_id'], pi['session_id'])
        self.assertEqual(conn.close_code, 1000)
        self.assertFalse(session.ingress.latest)
        for role, reply in [('phone', phone), ('pi', pi)]:
            with self.assertRaises(HTTPException):
                self.manager.authenticate('Bearer ' + reply['device']['token'], role)

    def test_backend_restart_keeps_bond_but_requires_both_current_clients(self):
        _, pi = self.pair()
        self.manager = SessionManager(OPERATOR, clock=lambda: self.now)
        self.registry = BondRegistry(self.path / 'registry.json', self.manager)
        self.assertEqual(self.poll('pi')[1], 202)
        new, status = self.poll('phone')
        self.assertEqual(status, 200)
        self.assertNotEqual(new['session_id'], pi['session_id'])

    def test_role_impersonation_and_unknown_bond_rejected(self):
        for bond, role, token in [('cane-1', 'pi', self.config['phone']['token']),
                                   ('missing', 'phone', self.config['phone']['token'])]:
            with self.assertRaises(HTTPException) as raised:
                self.registry.connect(bond, role, 'boot', 'Bearer ' + token)
            self.assertEqual(raised.exception.status_code, 401)
        self.assertFalse(self.manager.sessions)

    def test_removing_bond_revokes_sockets_and_cannot_reenroll(self):
        phone, _ = self.pair()
        session = self.manager.sessions[phone['session_id']]
        conn = self.manager.attach(session, 'phone')
        (self.path / 'registry.json').write_text(json.dumps({'schema_version': 1, 'bonds': []}))
        with self.assertRaises(HTTPException):
            self.poll('phone')
        self.assertEqual(conn.close_code, 1000)
        self.assertFalse(self.manager.sessions)

    def test_http_tls_shape_and_oversize_rejections(self):
        app = create_app(session_manager=self.manager)
        install_bonds(app, self.manager, self.path / 'registry.json')
        with TestClient(app, base_url='https://testserver') as client:
            headers = {'Authorization': 'Bearer ' + self.config['phone']['token']}
            body = dict(bond_id='cane-1', role='phone', boot_id='boot')
            self.assertEqual(client.post('/v1/bonds/connect', json=body).status_code, 401)
            for bad in ({}, dict(body, role='pi', boot_id=[]), dict(body, extra=1)):
                self.assertEqual(client.post('/v1/bonds/connect',json=bad,headers=headers).status_code,422)
            self.assertEqual(client.post('/v1/bonds/connect',content=b'x'*1025,headers=headers).status_code,413)
            response=client.post('/v1/bonds/connect',json=body,headers=headers)
            self.assertEqual(response.status_code,202)
            self.assertEqual(response.headers['cache-control'],'no-store')
        with TestClient(app) as plain:
            self.assertEqual(plain.post('/v1/bonds/connect',json=body,headers=headers).status_code,403)

    def test_native_config_role_validation_and_response_session_shape(self):
        client = BondClient(self.path / 'pi-bond.json', 'pi')
        with self.assertRaises(ValueError):
            BondClient(self.path / 'phone-bond.json', 'pi')
        _, reply = self.pair()
        session = client.session(reply)
        self.assertEqual(set(session), {'base_url','session_id','source_id','boot_id','mode','token'})
        self.assertEqual(session['source_id'], 'pi-1')

    def test_app_factory_opt_in_is_explicit(self):
        with patch.dict('os.environ', {'CANESIGHT_BOND_REGISTRY': str(self.path / 'registry.json')}):
            self.assertIsInstance(create_app(session_manager=self.manager).state.bonds, BondRegistry)
            with self.assertRaises(ValueError):
                create_app()

    def test_cold_session_factory_import_with_registry_environment(self):
        # Deployment sets the variable before Python imports backend.app. A warm
        # TestClient import alone misses the legacy module-level app construction.
        env = os.environ.copy()
        env.update(CANESIGHT_BOND_REGISTRY=str(self.path / 'registry.json'),
                   CANESIGHT_OPERATOR_TOKEN=OPERATOR)
        env.pop('CANESIGHT_VISION_WEIGHTS', None)
        code = ('from backend.server import create_session_app; '
                'app=create_session_app(); '
                'assert app.state.bonds.manager is app.state.sessions; '
                'assert len(app.state.bonds.records()) == 1')
        result = subprocess.run([sys.executable, '-c', code], env=env,
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, 'Cold configured factory failed')


if __name__ == '__main__':
    unittest.main()
