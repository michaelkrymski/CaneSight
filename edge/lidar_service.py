"""Translate a small private JSON configuration to LiDAR agent arguments."""
import argparse
import json
import os
from pathlib import Path
import sys


DEFAULT = dict(schema_version=1, gpio=False, relative_drift_ppm=None,
               with_camera=False, context_button=False, context_consent=False, context_audio=False,
               left_bcm=18, right_bcm=19, near_metres=1.2, release_metres=1.5,
               minimum_valid_fraction=.5, pulse_ms=100)


def arguments(path):
    if path.stat().st_size > 8192:
        raise ValueError('Oversized service configuration')
    config = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(config, dict) or set(config) - set(DEFAULT) - {'bond_file', 'status_file', 'ca_file'}:
        raise ValueError('Unknown service configuration field')
    data = {**DEFAULT, **config}
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('Unsupported service configuration version')
    root = path.parent
    def location(key, default):
        value = data.get(key, default)
        if not isinstance(value, str) or not value:
            raise ValueError('Invalid path in service configuration')
        result = Path(value).expanduser()
        return result if result.is_absolute() else root / result
    result = ['--bond-file', str(location('bond_file', 'pi-bond.json')),
              '--status-file', str(location('status_file', 'lidar-status.json'))]
    for key in ('gpio', 'with_camera', 'context_button', 'context_consent', 'context_audio'):
        if type(data[key]) is not bool:
            raise ValueError('Use JSON true/false for switches')
        if data[key]:
            result.append('--' + key.replace('_', '-'))
    for key in ('left_bcm', 'right_bcm', 'near_metres', 'release_metres', 'minimum_valid_fraction', 'pulse_ms'):
        if type(data[key]) not in (int, float):
            raise ValueError('Use JSON numbers for numeric options')
        result.extend(['--' + key.replace('_', '-'), str(data[key])])
    if data['relative_drift_ppm'] is not None:
        if type(data['relative_drift_ppm']) not in (int, float):
            raise ValueError('Use a JSON number for drift')
        result.extend(['--relative-drift-ppm', str(data['relative_drift_ppm'])])
    if data.get('ca_file') is not None:
        result.extend(['--ca-file', str(location('ca_file', ''))])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    argv = [sys.executable, '-m', 'edge.lidar_agent', *arguments(args.config.expanduser().resolve())]
    # Replace the service process: SIGTERM goes directly to the agent, not an
    # orphaned subprocess. No shell or generated credential-bearing command.
    os.execv(sys.executable, argv)


if __name__ == '__main__':
    main()
