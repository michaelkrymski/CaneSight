"""Rehearse laptop backend over a loopback-only reverse SSH tunnel.

Requires the Vultr SSH/proxy host to remain available. No host-outage fallback
or real device inference is claimed. All probe images/sessions are synthetic.
"""
import argparse
import asyncio
import http.client
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import time

from backend.deploy.session_probe import run


def exercise(base, ssh_host, identity, remote_directory, simulate_outage=False):
    root = Path(__file__).resolve().parents[2]
    token = secrets.token_urlsafe(40)
    env = dict(os.environ, CANESIGHT_OPERATOR_TOKEN=token)
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    backend = subprocess.Popen([sys.executable, '-m', 'backend.server', '--host', '127.0.0.1',
                                '--port', '18082'], cwd=root, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'ExitOnForwardFailure=yes',
           '-i', str(identity)]
    remote = Path(remote_directory).as_posix()
    controller = shlex.quote(remote + '/switch_upstream.py')
    remote_switch = lambda target: subprocess.run(ssh + [ssh_host, 'python3 ' + controller + ' --target ' + target],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=45)
    tunnel = None
    switched = False
    try:
        deadline = time.monotonic() + 20
        while True:
            connection = http.client.HTTPConnection('127.0.0.1', 18082, timeout=1)
            try:
                connection.request('GET', '/healthz')
                if connection.getresponse().status == 200:
                    break
            except OSError:
                pass
            finally:
                connection.close()
            if backend.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('Laptop backend failed to start')
            time.sleep(.1)
        tunnel = subprocess.Popen(ssh + ['-N', '-R', '127.0.0.1:18081:127.0.0.1:18082', ssh_host],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
        time.sleep(.7)
        if tunnel.poll() is not None:
            raise RuntimeError('SSH reverse forwarding unavailable')
        switched = True
        remote_switch('laptop')
        if simulate_outage:
            command = ('sudo docker compose --env-file ' + shlex.quote(remote + '/.env')
                       + ' -f ' + shlex.quote(remote + '/compose.yaml') + ' stop backend')
            subprocess.run(ssh + [ssh_host, command], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True, timeout=30)
        report = asyncio.run(run(base, token))
        report.update(laptop_backend_verified=True, backend_outage_simulated=simulate_outage,
                      requires_proxy_host=True)
        return report
    finally:
        try:
            if switched:
                remote_switch('production')
        finally:
            for process in (tunnel, backend):
                if process is not None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--ssh-host', required=True)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--remote-directory', required=True, help='Remote backend/deploy directory')
    parser.add_argument('--simulate-backend-outage', action='store_true')
    args = parser.parse_args()
    try:
        result = exercise(args.base, args.ssh_host, args.identity, args.remote_directory,
                          args.simulate_backend_outage)
    except Exception:
        print('Laptop fallback rehearsal failed; verify production restoration locally. Details suppressed.')
        raise SystemExit(1)
    print(json.dumps(result, sort_keys=True))
    print('Production upstream restored; laptop child server and tunnel stopped.')
