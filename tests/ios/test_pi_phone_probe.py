import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

spec = importlib.util.spec_from_file_location('pi_phone_probe', Path(__file__).with_name('pi_phone_transport_probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
ROOT = Path(__file__).resolve().parents[2]


class PiPhoneProbeTests(unittest.TestCase):
    def packet(self, **updates):
        value = json.loads((ROOT/'shared/protocol/v1/examples/heartbeat.json').read_text())
        value.update(session_id='probe-session', source_id='phone', boot_id='phone-boot', mode='live', state='starting')
        value.update(updates)
        return json.dumps(value)

    def test_sequence_high_water_survives_a_socket_replacement(self):
        state = probe.ProbeState('probe-session', 'phone', 'phone-boot')
        state.receive(self.packet(seq=2))
        state.receive(self.packet(seq=4))
        with self.assertRaises(ValueError):
            state.receive(self.packet(seq=2))
        self.assertEqual(state.heartbeats, 2)

    def test_foreign_mode_identity_and_readiness_cannot_count_as_starting_transport(self):
        for update in [dict(mode='replay'), dict(boot_id='other'), dict(source_id='other'),
                       dict(session_id='other'), dict(state='ready')]:
            state = probe.ProbeState('probe-session', 'phone', 'phone-boot')
            with self.assertRaises(ValueError):
                state.receive(self.packet(**update))
            self.assertEqual(state.heartbeats, 0)

    def test_role_file_matches_exact_process_and_contains_only_pi_grant(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'private.json'
            value = dict(base_url=probe.ORIGIN, session_id='probe-session', source_id='pi',
                         boot_id='pi-boot', mode='live', token='x'*40)
            path.write_text(json.dumps(value)); path.chmod(0o600)
            self.assertEqual(probe.load_grant(path, 'pi', 'pi-boot'), value)
            with self.assertRaises(ValueError):
                probe.load_grant(path, 'pi', 'old-boot')
            for changes in [dict(base_url='https://other.invalid'), dict(phone_token='y'*40),
                            dict(operator_token='y'*40)]:
                path.write_text(json.dumps(dict(value, **changes)))
                with self.assertRaises(ValueError):
                    probe.load_grant(path, 'pi', 'pi-boot')

    @unittest.skipUnless(os.name == 'posix', 'POSIX private-file modes')
    def test_public_readable_or_duplicate_credential_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'private.json'
            path.write_text('{}'); path.chmod(0o644)
            with self.assertRaises(ValueError):
                probe.load_grant(path, 'pi', 'pi-boot')

            path.chmod(0o600); path.write_text('{"token":"a","token":"b"}')
            with self.assertRaises(ValueError):
                probe.load_grant(path, 'pi', 'pi-boot')


class PiPhoneReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_observer_loop_retains_sequence_through_peer_disconnect(self):
        packets = PiPhoneProbeTests().packet

        class Socket:
            def __init__(self, sequences):
                self.sequences = list(sequences)

            async def recv(self):
                if not self.sequences:
                    raise ConnectionClosedError(Close(1012, ''), Close(1012, ''), True)
                return packets(seq=self.sequences.pop(0))

        class Context:
            def __init__(self, sequences):
                self.socket = Socket(sequences)

            async def __aenter__(self):
                return self.socket

            async def __aexit__(self, *args):
                return False

        calls = []

        def connect(url, **options):
            calls.append(True)
            return Context([0, 1, 2] if len(calls) == 1 else [3, 4])

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            await probe.observe(dict(session_id='probe-session', token='x'*40),
                                'phone', 'phone-boot', connector=connect)
        result = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(result['starting_heartbeats_observed'], 5)
        self.assertEqual(result['connections'], 2)
        self.assertEqual(result['capture_age_eligibility'], 'unknown')
        self.assertFalse(result['gpio_used'])
