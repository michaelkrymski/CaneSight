"""CS-044 software-only campaign against exact, unmodified review inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / 'qa/failures/crossing-review-inputs.json'
CASES = ROOT / 'tests/failures/crossing_cases.py'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pins():
    manifest = json.loads(PINS.read_text(encoding='utf-8'))
    for row in manifest['files']:
        if (not re.fullmatch('[0-9a-f]{40}', row['commit'])
                or not re.fullmatch('[0-9a-f]{64}', row['sha256'])
                or not re.fullmatch(r'(edge|backend)/[A-Za-z0-9_/]+\.py', row['path'])
                or '..' in row['path']):
            raise ValueError('Invalid review source pin')
    if (not manifest['case_ids'] or len(set(manifest['case_ids'])) != len(manifest['case_ids'])
            or any(not re.fullmatch(r'[A-Za-z0-9_.]+', name) for name in manifest['case_ids'])):
        raise ValueError('Invalid closed campaign')
    return manifest


def prepare(destination):
    """No network/fetch. Missing pinned Git objects fail rather than use HEAD."""
    manifest = pins()
    for row in manifest['files']:
        result = subprocess.run(['git', 'show', row['commit'] + ':' + row['path']],
                                cwd=ROOT, capture_output=True, timeout=10)
        if result.returncode or hashlib.sha256(result.stdout).hexdigest() != row['sha256']:
            raise ValueError('Pinned source unavailable or mismatched')
        target = Path(destination) / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.stdout)
    return manifest


def verify(destination):
    manifest = pins()
    for row in manifest['files']:
        path = Path(destination) / row['path']
        if not path.is_file() or digest(path) != row['sha256']:
            raise ValueError('Prepared source mismatch')
    # Unexpected Python modules could otherwise shadow the reviewed imports.
    expected = {row['path'] for row in manifest['files']}
    actual = {p.relative_to(destination).as_posix() for p in Path(destination).rglob('*.py')}
    if actual != expected:
        raise ValueError('Unexpected prepared source')
    return manifest


def assess(cases, expected_ids):
    expected = len(expected_ids)
    if (type(cases) is not list or len(cases) != expected or expected < 1
            or any(type(row) is not dict or set(row) != {'id', 'status'} for row in cases)):
        return False
    return ({row['id'] for row in cases} == set(expected_ids)
            and all(row['status'] == 'pass' for row in cases))


def run(prepared=None):
    manifest = pins()
    report = {'task': 'CS-044', 'scope': 'pinned synthetic menu/audio composition',
        'python': platform.python_version(), 'platform': sys.platform,
        'review_inputs': manifest, 'cases': [], 'all_software_passed': False,
        'physical_acceptance': False,
        'source_sha256': {'qa/crossing_failure_suite.py': digest(__file__),
                          'qa/failures/crossing-review-inputs.json': digest(PINS),
                          'tests/failures/crossing_cases.py': digest(CASES)},
        'remaining_gates': ['Production menu/request/result bridge absent from review inputs.',
            'No real scenario result/track correlation integration tested.',
            'Readiness/route/source loss is injected; no actual Bluetooth monitor.',
            'No camera, Pi, network, GPIO, motor or physical speech timing test.',
            'Accepted 500ms depth/1500ms vision age gates remain independent.']}
    with tempfile.TemporaryDirectory(prefix='canesight-crossing-') as temporary:
        source = Path(prepared) if prepared is not None else Path(temporary) / 'source'
        try:
            if prepared is None:
                prepare(source)
            verify(source)
            env = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1')
            child = subprocess.run([sys.executable, str(CASES)], cwd=source,
                env=env, capture_output=True, timeout=30)
            result = json.loads(child.stdout)
            verify(source)
            unchanged = all(digest(ROOT / name) == value for name, value in report['source_sha256'].items())
            # Never serialize tracebacks, test assertion strings or raw output.
            cases = result['cases']
            valid = (result['expected_cases'] == len(manifest['case_ids'])
                     and assess(cases, manifest['case_ids']))
            if any(not re.fullmatch(r'[A-Za-z0-9_.]+', row['id'])
                   or row['id'] not in manifest['case_ids']
                   or row['status'] not in ('pass', 'fail', 'error', 'skip') for row in cases):
                raise ValueError('Invalid child report')
            report.update(cases=cases, expected_cases=result['expected_cases'],
                source_unchanged=unchanged,
                all_software_passed=child.returncode == 0 and valid and unchanged)
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            report['runner_error'] = 'Pinned campaign unavailable; inspect local setup or test failures.'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path, help='Export exact pins into a NEW local directory, then exit')
    parser.add_argument('--prepared', type=Path, help='Use an existing byte-verified export, without Git')
    parser.add_argument('--output', type=Path, help='Write allowlisted synthetic results')
    args = parser.parse_args()
    if args.prepare:
        if args.prepared or args.output:
            parser.error('--prepare is a separate operation')
        try:
            args.prepare.mkdir(parents=True, exist_ok=False)
            prepare(args.prepare)
        except (OSError, ValueError, subprocess.SubprocessError):
            parser.exit(2, 'Cannot prepare exact review sources; no fallback or fetch used.\n')
        return
    report = run(args.prepared)
    encoded = json.dumps(report, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded, end='')
    raise SystemExit(0 if report['all_software_passed'] else 1)


if __name__ == '__main__':
    main()
