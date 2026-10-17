"""One-command loopback-only replay smoke, with ephemeral in-memory credentials."""
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def main():
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    environment = dict(os.environ, CANESIGHT_REPLAY_TOKEN=secrets.token_urlsafe(32))
    root = Path(__file__).resolve().parents[1]
    server = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'backend.replay:create_replay_app',
         '--factory', '--host', '127.0.0.1', '--port', str(port), '--workers', '1', '--no-access-log'],
        cwd=root, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=1, trust_env=False) as client:
            deadline = time.monotonic() + 15
            while True:
                if server.poll() is not None:
                    raise SystemExit('Replay server did not start; check dependencies and local port availability.')
                try:
                    if client.get('/healthz').status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if time.monotonic() >= deadline:
                    raise SystemExit('Replay startup timed out')
                time.sleep(.1)
        subprocess.run([sys.executable, '-m', 'backend.smoke_replay', '--port', str(port)],
                       cwd=root, env=environment, check=True)
        repeated = subprocess.run([sys.executable, '-m', 'backend.smoke_replay', '--port', str(port)],
                                  cwd=root, env=environment, capture_output=True, text=True)
        if repeated.returncode == 0 or "Upload: 409" not in repeated.stdout:
            raise SystemExit('Replay duplicate rejection failed')
        print('Repeated replay upload: 409 (expected).')
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        print('Loopback replay server stopped; no image or token saved.')


if __name__ == '__main__':
    main()
