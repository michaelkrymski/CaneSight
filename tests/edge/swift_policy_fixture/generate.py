"""Explicit local Docker/Swift build; no Pi, camera, real grant or network sink."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
IMAGE = 'swift:6.0.3@sha256:f19aea3f9a889df5884e1186e60be74869613477d99656b598c115a4b91af8a1'


def main():
    source_names = ('Package.swift', 'Sources/CS025PolicyFixture/main.swift', 'review-inputs.json', 'generate.py')
    own_bytes = {name: (HERE / name).read_bytes() for name in source_names}
    own_hashes = {name: hashlib.sha256(data).hexdigest() for name, data in own_bytes.items()}
    pins = json.loads((HERE / 'review-inputs.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='canesight-swift-policy-') as folder:
        workspace = Path(folder)
        for row in pins['files']:
            data = subprocess.check_output(['git', 'show', pins['commit'] + ':' + row['path']], cwd=ROOT)
            if hashlib.sha256(data).hexdigest() != row['sha256']:
                raise RuntimeError('Pinned telemetry source mismatch; no fallback')
            target = workspace / 'CaneSightTelemetry' / Path(row['path']).relative_to('ios/CaneSightTelemetry')
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        for name in ('Package.swift', 'Sources/CS025PolicyFixture/main.swift'):
            target = workspace / 'PolicyFixture' / name
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(own_bytes[name])
        result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--mount',
            f'type=bind,source={workspace},target=/src,readonly', IMAGE, 'sh', '-c',
            'cp -R /src /tmp/work && swift run --package-path /tmp/work/PolicyFixture --jobs 1 '
            '-Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors CS025PolicyFixture'],
            capture_output=True, timeout=120)
        if result.returncode:
            raise RuntimeError('Synthetic Swift fixture build/run failed; inspect local toolchain')
        data = json.loads(result.stdout)
        if data['origin'] != 'synthetic' or set(data['scenarios']) != {'left', 'center', 'right'}:
            raise RuntimeError('Unexpected synthetic fixture output')
        if any((HERE / name).read_bytes() != original for name, original in own_bytes.items()):
            raise RuntimeError('Fixture sources changed during generation')
        data['provenance'] = {'review_pr': 64, 'telemetry_commit': pins['commit'], 'compiler_image': IMAGE,
            'fixture_source_sha256': own_hashes}
        (HERE / 'synthetic-wire.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        print('Generated 3 synthetic side scenarios with original Swift wire bytes; no device used.')


if __name__ == '__main__':
    main()
