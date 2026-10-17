"""Select only the reviewed loopback backend or laptop SSH tunnel."""
import argparse
import http.client
from pathlib import Path
import subprocess
import time


def switch(directory, target):
    directory = Path(directory).resolve()
    if target not in ('production', 'laptop'):
        raise ValueError('Invalid reviewed target')
    path = directory / '.env'
    original = path.read_text()
    command = ['sudo', 'docker', 'compose', '--env-file', str(path), '-f', str(directory / 'compose.yaml')]
    if target == 'production':
        subprocess.run(command + ['up', '-d', 'backend'], capture_output=True, check=True, timeout=30)
    port = 18083 if target == 'production' else 18081
    deadline = time.monotonic() + 15
    while True:
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
        try:
            connection.request('GET', '/healthz')
            if connection.getresponse().status == 200:
                break
        except OSError:
            pass
        finally:
            connection.close()
        if time.monotonic() >= deadline:
            raise RuntimeError('Target liveness unavailable; proxy target unchanged')
        time.sleep(.1)
    address = '127.0.0.1:18083' if target == 'production' else '127.0.0.1:18081'
    lines = [line for line in original.splitlines() if not line.startswith('CANESIGHT_UPSTREAM=')]
    path.write_text('\n'.join(lines + ['CANESIGHT_UPSTREAM=' + address]) + '\n')
    try:
        subprocess.run(command + ['config', '--quiet'], capture_output=True, check=True, timeout=15)
        subprocess.run(command + ['up', '-d', '--no-deps', 'proxy'], capture_output=True, check=True, timeout=30)
    except Exception:
        path.write_text(original)
        subprocess.run(command + ['up', '-d', '--no-deps', 'proxy'], capture_output=True, timeout=30)
        raise RuntimeError('Proxy switch failed; original settings restored; verify service locally') from None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--target', choices=('production', 'laptop'), required=True)
    args = parser.parse_args()
    try:
        switch(args.directory, args.target)
    except Exception:
        print('Upstream switch failed; inspect service locally. Details suppressed.')
        raise SystemExit(1)
    print('Reviewed upstream selected; verify HTTPS/WSS before use.')
