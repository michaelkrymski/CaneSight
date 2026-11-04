"""Install a Pi runtime/service WITHOUT starting it or running tests by default."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise SystemExit('Run as the normal Pi user, not sudo; privileged install commands will ask separately')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', action='store_true', help='Explicitly start AFTER checking the config and exclusive Pi ownership')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    user = getpass.getuser()
    config = Path.home() / '.config/canesight'
    config.mkdir(parents=True, exist_ok=True, mode=0o700)
    environment = config / 'lidar-venv'
    if not (environment / 'bin/python').exists():
        subprocess.run([sys.executable, '-m', 'venv', '--system-site-packages', str(environment)], check=True)
    python = environment / 'bin/python'
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(root/'backend/requirements.txt')], check=True)
    from .lidar_service import DEFAULT
    target = config / 'lidar-agent.json'
    if not target.exists():
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(DEFAULT, out, indent=2)
            out.write('\n')
    def unit(value):
        # Quote a systemd argument, not shell text. Reject expansion specifiers.
        value = str(value)
        if any(c in value for c in ('\n', '\r', '%')):
            raise ValueError('Unsupported systemd path')
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    service = '\n'.join([
        '[Unit]', 'Description=CaneSight bonded calibrated LiDAR receiver', 'After=network.target',
        'StartLimitIntervalSec=120', 'StartLimitBurst=3', '', '[Service]', 'Type=simple',
        'User='+user, 'WorkingDirectory='+unit(root),
        'ExecStart='+unit(python)+' -m edge.lidar_service --config '+unit(target),
        'Restart=on-failure', 'RestartSec=5', 'TimeoutStopSec=15', 'KillSignal=SIGTERM',
        'UMask=0077', '', '[Install]', 'WantedBy=multi-user.target', ''])
    with tempfile.TemporaryDirectory(prefix='canesight-service-') as folder:
        source = Path(folder) / 'canesight-lidar.service'
        source.write_text(service, encoding='utf-8')
        subprocess.run(['sudo', 'install', '-m', '644', str(source), '/etc/systemd/system/canesight-lidar.service'], check=True)
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    print('Service installed. Existing config/bond preserved. No tests or camera/GPIO checks run.')
    print('Config: ' + str(target))
    print('Default is simulation with no configured drift. Existing Pi-only bond must be at '+str(config/'pi-bond.json'))
    if args.start:
        subprocess.run(['sudo', 'systemctl', 'enable', '--now', 'canesight-lidar.service'], check=True)
    else:
        print('Not started/enabled. Inspect the config, stop conflicting Pi peers, then enable when ready.')


if __name__ == '__main__':
    main()
