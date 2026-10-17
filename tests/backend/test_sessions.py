"""Paired-session authorization, relay isolation and lifecycle tests."""
import asyncio
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from starlette.websockets import WebSocketDisconnect

from backend.app import create_app
from backend.sessions import SessionManager, SessionRequest

OPERATOR = 'fixture-operator-credential-only-never-deploy-00001'
ROOT = Path(__file__).resolve().parents[2]


def fixture(name):
    return json.loads((ROOT / 'shared/protocol/v1/examples' / f'{name}.json').read_text())


def specification(mode='replay', ttl=300):
    return {'mode': mode, 'ttl_seconds': ttl,
            'phone': {'source_id': 'phone-1', 'boot_id': 'phone-boot-1'},
            'pi': {'source_id': 'pi-camera-1', 'boot_id': 'pi-boot-1'}}


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.manager = SessionManager(OPERATOR, clock=lambda: self.now)
        self.client = TestClient(create_app(session_manager=self.manager), base_url='https://testserver')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.operator_headers = {'Authorization': 'Bearer ' + OPERATOR}

    def pair(self, body=None):
        response = self.client.post('/v1/sessions', headers=self.operator_headers,
                                    json=specification() if body is None else body)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return response.json()

    def headers(self, pair, role):
        return {'Authorization': 'Bearer ' + pair[role]['token']}

    def depth(self, pair, seq=104):
        return dict(fixture('depth'), session_id=pair['session_id'], mode=pair['mode'], seq=seq)

    def heartbeat(self, pair, role, seq=1):
        grant = pair[role]
        return dict(fixture('heartbeat'), session_id=pair['session_id'], source_id=grant['source_id'],
                    boot_id=grant['boot_id'], mode=pair['mode'], seq=seq)

    def test_operator_only_creation_tls_required_and_no_query_auth(self):
        self.assertEqual(self.client.post('/v1/sessions', json=specification()).status_code, 401)
        self.assertEqual(self.client.post('/v1/sessions', json=specification(),
                                         headers={'Authorization': 'Bearer '+'x'*40}).status_code, 401)
        plain = TestClient(create_app(session_manager=self.manager))
        self.assertEqual(plain.post('/v1/sessions', json=specification(), headers=self.operator_headers).status_code, 403)
        # An untrusted header cannot upgrade the ASGI transport scheme.
        self.assertEqual(plain.post('/v1/sessions', json=specification(),
                         headers={**self.operator_headers, 'X-Forwarded-Proto': 'https'}).status_code, 403)
        pair = self.pair()
        self.assertEqual(self.client.post('/v1/sessions', json=specification(),
                                         headers=self.headers(pair, 'pi')).status_code, 401)

    def test_explicit_mode_closed_shape_ttl_and_bound_identities(self):
        for body in ({}, dict(specification(), mode='auto'), dict(specification(), ttl_seconds=True),
                     dict(specification(), ttl_seconds=601), dict(specification(), ttl_seconds=0),
                     dict(specification(), arbitrary='x'), dict(specification(), phone={'source_id': 'bad!', 'boot_id': 'x'}),
                     dict(specification(), phone=specification()['pi'])):
            self.assertEqual(self.client.post('/v1/sessions', json=body, headers=self.operator_headers).status_code, 422)
        for raw, status in ((b'{"mode":"live","mode":"replay"}', 422), (b' '*2049, 413), (b'['*20+b'0'+b']'*20, 422)):
            self.assertEqual(self.client.post('/v1/sessions', content=raw,
                headers={**self.operator_headers, 'Content-Type': 'application/json'}).status_code, status)

    def test_unique_credentials_and_bounded_sessions(self):
        tokens = set()
        for _ in range(8):
            pair = self.pair()
            tokens.update((pair['phone']['token'], pair['pi']['token']))
        self.assertEqual(len(tokens), 16)
        self.assertEqual(self.client.post('/v1/sessions', json=specification(), headers=self.operator_headers).status_code, 503)
        self.now += 301
        self.pair()
        self.assertEqual(len(self.manager.sessions), 1)

    def test_wss_missing_wrong_role_query_origin_and_plaintext_rejected(self):
        pair = self.pair()
        cases = [('wss://testserver/v1/events', {}, 4401),
                 ('wss://testserver/v1/events', self.headers(pair, 'phone'), 4403),
                 ('wss://testserver/v1/telemetry', self.headers(pair, 'pi'), 4403),
                 ('wss://testserver/v1/events?token=hidden', self.headers(pair, 'pi'), 4403),
                 ('wss://testserver/v1/events', {**self.headers(pair, 'pi'), 'Origin': 'https://example.com'}, 4403),
                 ('ws://testserver/v1/events', self.headers(pair, 'pi'), 4403)]
        for url, headers, code in cases:
            with self.subTest(url=url), self.assertRaises(WebSocketDisconnect) as caught:
                with self.client.websocket_connect(url, headers=headers):
                    pass
            self.assertEqual(caught.exception.code, code)

    def test_depth_and_heartbeat_relay_preserves_original_packet(self):
        pair = self.pair()
        with self.client.websocket_connect('wss://testserver/v1/events', headers=self.headers(pair, 'pi')) as pi:
            with self.client.websocket_connect('wss://testserver/v1/telemetry', headers=self.headers(pair, 'phone')) as phone:
                depth = self.depth(pair)
                phone.send_json(depth)
                self.assertEqual(pi.receive_json(), depth)
                heartbeat = self.heartbeat(pair, 'pi')
                pi.send_json(heartbeat)
                self.assertEqual(phone.receive_json(), heartbeat)

    def test_duplicate_connection_rejected_and_reconnect_keeps_sequence(self):
        pair = self.pair()
        with self.client.websocket_connect('wss://testserver/v1/telemetry', headers=self.headers(pair, 'phone')) as phone:
            with self.assertRaises(WebSocketDisconnect) as caught:
                with self.client.websocket_connect('wss://testserver/v1/telemetry', headers=self.headers(pair, 'phone')):
                    pass
            self.assertEqual(caught.exception.code, 4409)
            # Receive processing completion deterministically via a Pi subscriber.
            with self.client.websocket_connect('wss://testserver/v1/events', headers=self.headers(pair, 'pi')) as pi:
                phone.send_json(self.depth(pair))
                self.assertEqual(pi.receive_json()['seq'], 104)
                phone.send_json(self.depth(pair, 105))
                self.assertEqual(pi.receive_json()['seq'], 105)
        with self.client.websocket_connect('wss://testserver/v1/telemetry', headers=self.headers(pair, 'phone')) as phone:
            phone.send_json(self.depth(pair, 105))
            with self.assertRaises(WebSocketDisconnect) as caught:
                phone.receive_json()
            self.assertEqual(caught.exception.code, 1008)

    def test_wrong_session_source_mode_epoch_and_actuator_packets_close(self):
        for changes in ({'session_id': 'other'}, {'source_id': 'imposter'}, {'mode': 'live'},
                        {'boot_id': 'old-boot'}, {'go': True}, {'type': 'vision_observation'}):
            pair = self.pair()
            with self.client.websocket_connect('wss://testserver/v1/telemetry', headers=self.headers(pair, 'phone')) as phone:
                phone.send_json(dict(self.depth(pair), **changes))
                with self.assertRaises(WebSocketDisconnect) as caught:
                    phone.receive_json()
                self.assertEqual(caught.exception.code, 1008)

    def test_session_isolation_and_slow_consumer_bound(self):
        # Direct manager admission avoids timing-based 'nothing received' tests.
        async def run():
            first, second = self.pair(), self.pair()
            a = self.manager.sessions[first['session_id']]
            b = self.manager.sessions[second['session_id']]
            phone = self.manager.attach(a, 'phone')
            own_pi = self.manager.attach(a, 'pi')
            other_pi = self.manager.attach(b, 'pi')
            _, grant = self.manager.authenticate('Bearer '+first['phone']['token'], 'phone')
            _, pi_grant = self.manager.authenticate('Bearer '+first['pi']['token'], 'pi')
            probe = dict(fixture('clock-probe'), session_id=first['session_id'], receiver_id='pi-camera-1')
            self.manager.relay(a, pi_grant, own_pi, probe)
            for n in range(8):
                self.manager.relay(a, grant, phone, self.depth(first, n))
            self.assertEqual(own_pi.queue.qsize(), 8)
            self.assertTrue(other_pi.queue.empty())
            with self.assertRaises(ValueError):
                self.manager.relay(a, grant, phone, self.depth(first, 8))
            self.assertEqual(own_pi.close_code, 1013)
            self.assertTrue(own_pi.queue.empty())
            self.assertTrue(phone.queue.empty())
            self.assertIsNone(a.probe)
        asyncio.run(run())

    def test_expiry_closes_idle_socket_and_revokes_credentials(self):
        pair = self.pair(specification(ttl=1))
        with self.client.websocket_connect('wss://testserver/v1/events', headers=self.headers(pair, 'pi')) as pi:
            self.now += 2
            with self.assertRaises(WebSocketDisconnect) as caught:
                pi.receive_json()
            self.assertEqual(caught.exception.code, 4401)
        self.assertEqual(self.manager.sessions, {})
        with self.assertRaises(HTTPException):
            self.manager.authenticate('Bearer '+pair['pi']['token'], 'pi')

    def test_revoke_closes_socket_purges_frames_and_blocks_inflight_commit(self):
        pair = self.pair()
        record, grant = self.manager.authenticate('Bearer '+pair['pi']['token'], 'pi')
        metadata = dict(fixture('frame'), session_id=pair['session_id'])
        self.manager.accept_frame(record, grant, metadata, b'synthetic-manager-unit-fixture')
        with self.client.websocket_connect('wss://testserver/v1/events', headers=self.headers(pair, 'pi')) as pi:
            url = '/v1/sessions/'+pair['session_id']
            self.assertEqual(self.client.delete(url, headers=self.headers(pair, 'pi')).status_code, 401)
            self.assertEqual(self.client.delete(url, headers=self.operator_headers).status_code, 204)
            with self.assertRaises(WebSocketDisconnect):
                pi.receive_json()
        self.assertEqual(record.ingress.latest, {})
        self.assertEqual(record.gate.last, {})
        with self.assertRaises(HTTPException):
            self.manager.accept_frame(record, grant, metadata, b'late')

    def test_phone_disconnect_invalidates_peer_and_pending_observations(self):
        pair = self.pair()
        with self.client.websocket_connect('wss://testserver/v1/events', headers=self.headers(pair, 'pi')) as pi:
            with self.client.websocket_connect('wss://testserver/v1/telemetry', headers=self.headers(pair, 'phone')) as phone:
                phone.send_json(self.depth(pair))
                pi.receive_json()
            with self.assertRaises(WebSocketDisconnect) as caught:
                pi.receive_json()
            self.assertEqual(caught.exception.code, 1012)

    def test_reconnect_cleanup_cannot_invalidate_replacement_peer(self):
        async def run():
            pair = self.pair()
            session = self.manager.sessions[pair['session_id']]
            phone = self.manager.attach(session, 'phone')
            pi = self.manager.attach(session, 'pi')
            _, phone_grant = self.manager.authenticate('Bearer '+pair['phone']['token'], 'phone')
            _, pi_grant = self.manager.authenticate('Bearer '+pair['pi']['token'], 'pi')
            self.manager.relay(session, phone_grant, phone, self.depth(pair))
            probe = dict(fixture('clock-probe'), session_id=pair['session_id'], receiver_id='pi-camera-1')
            self.manager.relay(session, pi_grant, pi, probe)
            self.assertIsNotNone(session.probe)

            # Michael's exact ordering: old phone goes away, new phone arrives,
            # then the invalidated old Pi finishes its asynchronous cleanup.
            self.manager.detach(session, phone)
            self.assertEqual(pi.close_code, 1012)
            self.assertTrue(pi.queue.empty())
            self.assertIsNone(session.probe)
            replacement_phone = self.manager.attach(session, 'phone')
            self.assertIsNone(replacement_phone.close_code)
            self.manager.detach(session, pi)
            self.assertIsNone(replacement_phone.close_code)
            self.assertTrue(phone.queue.empty())
            replacement_pi = self.manager.attach(session, 'pi')

            # Reconnection does not reset sequence marks or replay old buffers.
            self.assertTrue(replacement_pi.queue.empty())
            with self.assertRaises(ValueError):
                self.manager.relay(session, phone_grant, replacement_phone, self.depth(pair))
            fresh = self.depth(pair, 105)
            self.manager.relay(session, phone_grant, replacement_phone, fresh)
            self.assertEqual(replacement_pi.queue.get_nowait(), fresh)
            with self.assertRaises(ValueError):
                self.manager.relay(session, phone_grant, phone, self.depth(pair, 106))

            # Cleanup called again for stale objects cannot touch new control
            # state or either replacement role's connection registration.
            self.now += 1
            fresh_probe = dict(probe, nonce='new-pair-probe')
            self.manager.relay(session, pi_grant, replacement_pi, fresh_probe)
            self.manager.detach(session, phone)
            self.manager.detach(session, pi)
            self.assertEqual(session.probe['message'], fresh_probe)
            self.assertIs(session.connections['phone'], replacement_phone)
            self.assertIs(session.connections['pi'], replacement_pi)
            self.manager.detach(session, replacement_phone)
            self.assertEqual(replacement_pi.close_code, 1012)
            self.assertIsNone(session.probe)
        asyncio.run(run())

    def test_oversize_binary_and_invalid_json_rejected(self):
        for raw, code in ((b'x'*8193, 1009), (b'{"seq":1,"seq":2}', 1008),
                          (b'\xff', 1008), (b'{"a":NaN}', 1008), (b'['*20+b'0'+b']'*20, 1008)):
            pair = self.pair()
            with self.client.websocket_connect('wss://testserver/v1/telemetry', headers=self.headers(pair, 'phone')) as phone:
                phone.send_bytes(raw)
                with self.assertRaises(WebSocketDisconnect) as caught:
                    phone.receive_json()
                self.assertEqual(caught.exception.code, code)

    def test_paired_pi_token_can_upload_but_phone_cannot(self):
        pair = self.pair()
        image = io.BytesIO()
        Image.new('RGB', (16, 16)).save(image, format='JPEG')
        metadata = dict(fixture('frame'), session_id=pair['session_id'],
                        image={'width': 16, 'height': 16}, jpeg_bytes=len(image.getvalue()))
        files = {'metadata': (None, json.dumps(metadata)), 'image': ('generated.jpg', image.getvalue(), 'image/jpeg')}
        self.assertEqual(self.client.post('/v1/frames', headers=self.headers(pair, 'phone'), files=files).status_code, 403)
        self.assertEqual(self.client.post('/v1/frames', headers=self.headers(pair, 'pi'), files=files).status_code, 202)
        plain = TestClient(create_app(session_manager=self.manager))
        self.assertEqual(plain.post('/v1/frames', headers=self.headers(pair, 'pi'), files=files).status_code, 403)

    def test_clock_probe_reply_correlated_roles_and_one_time_nonce(self):
        pair = self.pair()
        probe = dict(fixture('clock-probe'), session_id=pair['session_id'], receiver_id='pi-camera-1')
        reply = dict(fixture('clock-reply'), session_id=pair['session_id'], receiver_id='pi-camera-1')
        with self.client.websocket_connect('wss://testserver/v1/events', headers=self.headers(pair, 'pi')) as pi:
            with self.client.websocket_connect('wss://testserver/v1/telemetry', headers=self.headers(pair, 'phone')) as phone:
                pi.send_json(probe)
                self.assertEqual(phone.receive_json(), probe)
                phone.send_json(reply)
                self.assertEqual(pi.receive_json(), reply)
                phone.send_json(reply)
                with self.assertRaises(WebSocketDisconnect) as caught:
                    phone.receive_json()
                self.assertEqual(caught.exception.code, 1008)

    def test_clock_probe_rate_late_wrong_nonce_and_reversed_source_clock(self):
        async def run():
            pair = self.pair()
            session = self.manager.sessions[pair['session_id']]
            pi = self.manager.attach(session, 'pi')
            phone = self.manager.attach(session, 'phone')
            _, pi_grant = self.manager.authenticate('Bearer '+pair['pi']['token'], 'pi')
            _, phone_grant = self.manager.authenticate('Bearer '+pair['phone']['token'], 'phone')
            probe = dict(fixture('clock-probe'), session_id=pair['session_id'], receiver_id='pi-camera-1')
            reply = dict(fixture('clock-reply'), session_id=pair['session_id'], receiver_id='pi-camera-1')
            self.manager.relay(session, pi_grant, pi, probe)
            with self.assertRaises(ValueError):
                self.manager.relay(session, pi_grant, pi, dict(probe, nonce='replacement'))
            for invalid in (dict(reply, nonce='wrong'), dict(reply, t3_ms=reply['t2_ms']-1)):
                with self.assertRaises(ValueError):
                    self.manager.relay(session, phone_grant, phone, invalid)
            self.now += 1
            with self.assertRaises(ValueError):
                self.manager.relay(session, phone_grant, phone, reply)
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
