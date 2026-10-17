"""Opt-in integration against the actual packaged app, not a fixture HTTP app."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('private_smoke', ROOT / 'backend/deploy/private_smoke.py')
private = importlib.util.module_from_spec(spec)
spec.loader.exec_module(private)


class PrivateProbeTests(unittest.TestCase):
    def test_refuses_public_or_credential_bearing_targets(self):
        for origin in ('http://example.org', 'https://localhost', 'http://user@localhost',
                       'http://localhost/path', 'http://localhost?token=fixture'):
            with self.assertRaises(ValueError):
                private.probe(origin)


@unittest.skipUnless(os.environ.get('CS_BACKEND_TEST_IMAGE'), 'Opt-in built backend container integration')
class BackendContainerTests(unittest.TestCase):
    def test_missing_operator_secret_refuses_paired_factory_startup(self):
        image = os.environ['CS_BACKEND_TEST_IMAGE']
        result = subprocess.run(['docker', 'run', '--rm', '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', image,
            'python', '-m', 'backend.server', '--host', '0.0.0.0'],
            capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'ModuleNotFoundError', result.stderr)

    def test_explicit_replay_image_accepts_fixture_and_rejects_duplicate(self):
        import io
        import httpx
        from PIL import Image
        image = os.environ['CS_BACKEND_TEST_IMAGE']
        self.assertTrue(image.startswith('sha256:') or '@sha256:' in image)
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            port = reserve.getsockname()[1]
        name = 'canesight-cs033-replay-test-' + uuid.uuid4().hex[:10]
        token = secrets.token_urlsafe(32)
        environment = dict(os.environ, CANESIGHT_REPLAY_TOKEN=token)
        command = ['docker', 'run', '--rm', '-d', '--name', name, '--read-only',
                   '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                   '-p', f'127.0.0.1:{port}:8000', '-e', 'CANESIGHT_REPLAY_TOKEN', image,
                   'python', '-m', 'uvicorn', 'backend.replay:create_replay_app', '--factory',
                   '--host', '0.0.0.0', '--port', '8000', '--workers', '1', '--no-access-log']
        result = subprocess.run(command, env=environment, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, 'Replay fixture container failed; details suppressed.')
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    private.probe(f'http://127.0.0.1:{port}')
                    break
                except (OSError, ValueError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.1)
            output = io.BytesIO()
            Image.new('RGB', (32, 24), color=(60, 100, 120)).save(output, format='JPEG')
            jpeg = output.getvalue()
            metadata = json.loads((ROOT / 'shared/protocol/v1/examples/frame.json').read_text())
            metadata.update(image={'width': 32, 'height': 24}, jpeg_bytes=len(jpeg))
            self.assertEqual(metadata['mode'], 'replay')
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=5) as client:
                for expected in (202, 409):
                    response = client.post('/v1/frames', headers={'Authorization': 'Bearer ' + token},
                                           files={'metadata': (None, json.dumps(metadata), 'application/json'),
                                                  'image': ('synthetic.jpg', jpeg, 'image/jpeg')})
                    self.assertEqual(response.status_code, expected)
                    if expected == 202:
                        self.assertEqual(response.json()['frame_id'], metadata['frame_id'])
                self.assertEqual(client.get('/readyz').status_code, 503)
        finally:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, check=True, timeout=20)

    def test_default_auth_readiness_and_restart(self):
        image = os.environ['CS_BACKEND_TEST_IMAGE']
        self.assertTrue(image.startswith('sha256:') or '@sha256:' in image)
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            port = reserve.getsockname()[1]
        name = 'canesight-cs033-app-test-' + uuid.uuid4().hex[:10]
        command = ['docker', 'run', '--rm', '-d', '--name', name, '--read-only',
                   '--tmpfs', '/tmp:size=128m,mode=1777', '--cap-drop', 'ALL',
                   '--security-opt', 'no-new-privileges:true', '--pids-limit', '256',
                   '-p', f'127.0.0.1:{port}:8000', '--health-start-period', '1s',
                   '--health-start-interval', '1s', '--health-interval', '1s',
                   '--health-retries', '1', image]
        result = subprocess.run(command, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, 'Backend test container did not start; details suppressed.')
        try:
            for attempt in range(2):
                deadline = time.monotonic() + 30
                while True:
                    try:
                        self.assertEqual(private.probe(f'http://127.0.0.1:{port}'), [200, 503, 401, 401])
                        break
                    except (OSError, ValueError):
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(.1)
                if attempt == 0:
                    subprocess.run(['docker', 'restart', name], check=True, capture_output=True, timeout=30)
            deadline = time.monotonic() + 10
            while True:
                state = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
                if state['State']['Health']['Status'] == 'unhealthy' or time.monotonic() >= deadline:
                    break
                time.sleep(.1)
            self.assertTrue(state['State']['Running'])
            self.assertEqual(state['State']['Health']['Status'], 'unhealthy')
            self.assertEqual(state['Config']['User'], '10001:10001')
        finally:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
