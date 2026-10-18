"""Compile the exact host bridge with real CS-016 actor in local Linux Docker."""
import hashlib
import argparse
import datetime
import io
import json
import re
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
IMAGE = 'swift:6.0.3@sha256:f19aea3f9a889df5884e1186e60be74869613477d99656b598c115a4b91af8a1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--telemetry-ref', help='Test an exact CS-016 review commit without changing host pins')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'ios/CaneSightApp/ReviewDependencies.json').read_text())
    dependency = next((p for p in manifest['packages'] if p['name'] == 'CaneSightTelemetry'), None)
    if args.telemetry_ref:
        revision = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options',
            args.telemetry_ref + '^{commit}'], cwd=ROOT, text=True).strip()
        dependency = dict(commit=revision, path='ios/CaneSightTelemetry')
    elif dependency is None:
        # CS-016's accepted host will resolve the sibling package directly rather
        # than duplicating it in ReviewDependencies. Archive that exact HEAD.
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dependency = dict(commit=revision, path='ios/CaneSightTelemetry')
    with tempfile.TemporaryDirectory(prefix='canesight-cs017-') as folder:
        base = Path(folder)
        shutil.copytree(ROOT / 'ios/Lifecycle', base / 'Lifecycle', ignore=shutil.ignore_patterns('.build', '.swiftpm'))
        raw = subprocess.check_output(['git', 'archive', dependency['commit'], '--', dependency['path']], cwd=ROOT)
        dependency_hashes = {}
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            for member in archive:
                if member.isdir(): continue
                name = Path(member.name).relative_to(dependency['path'])
                if not member.isfile() or '..' in name.parts: raise ValueError('Invalid source archive')
                data = archive.extractfile(member).read()
                target = base / 'CaneSightTelemetry' / name
                target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
                dependency_hashes[member.name] = hashlib.sha256(data).hexdigest()
        if not dependency_hashes or not (base / 'CaneSightTelemetry/Package.swift').is_file():
            raise ValueError('Selected CS-016 revision has no telemetry package')
        harness = base / 'Harness'
        sources = harness / 'Sources/CaneSightHostLifecycle'; sources.mkdir(parents=True)
        tests = harness / 'Tests/HostLifecycleTests'; tests.mkdir(parents=True)
        bridge = ROOT / 'ios/CaneSightApp/Sources/LifecycleTelemetry.swift'
        cases = ROOT / 'tests/ios/LifecycleTransportTests.swift'
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (bridge, cases, Path(__file__))}
        shutil.copyfile(bridge, sources / bridge.name)
        shutil.copyfile(cases, tests / cases.name)
        (harness / 'Package.swift').write_text('''// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "CS017TransportHarness", dependencies: [
    .package(path: "../Lifecycle"), .package(path: "../CaneSightTelemetry")
], targets: [
    .target(name: "CaneSightHostLifecycle", dependencies: [
        .product(name: "CaneSightLifecycle", package: "Lifecycle"),
        .product(name: "CaneSightTelemetry", package: "CaneSightTelemetry")]),
    .testTarget(name: "HostLifecycleTests", dependencies: ["CaneSightHostLifecycle"])
])
''', encoding='utf-8')
        result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--mount',
            f'type=bind,source={base},target=/src,readonly', IMAGE, 'sh', '-c',
            'cp -R /src /tmp/work && swift test --package-path /tmp/work/Harness --jobs 1 '
            '-Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors'],
            capture_output=True, text=True, timeout=120)
        print(result.stdout)
        print(result.stderr)
        if any(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != value for p, value in before.items()):
            raise RuntimeError('Tested host bridge sources changed during run')
        if args.output:
            summaries = re.findall(r'Executed (\d+) tests?, with (\d+) failures?', result.stdout + result.stderr)
            report = {
                'task': 'CS-017', 'recorded_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'container_image': IMAGE, 'network': 'none', 'exit_code': result.returncode,
                'test_count': int(summaries[-1][0]) if summaries else None,
                'failure_count': int(summaries[-1][1]) if summaries else None,
                'strict_concurrency': 'complete', 'warnings_as_errors': True,
                'source_sha256': before,
                'telemetry_dependency_commit': dependency['commit'],
                'telemetry_dependency_sha256': dependency_hashes,
                'lifecycle_source_sha256': {
                    p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((ROOT / 'ios/Lifecycle').rglob('*.swift'))
                    if '.build' not in p.parts and '.swiftpm' not in p.parts},
                'limits': ['Linux host coordinator tests with actual CS-016 actor and fake sockets/clocks.',
                           'CameraController and native Apple SDK integration are not compiled by this harness.',
                           'No verified device clock mapping, native network, physical phone/Pi or motor test.']
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
