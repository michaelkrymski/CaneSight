"""Materialize exact, local Git review inputs without changing teammate source."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def prepare():
    manifest = json.loads((HERE / 'ReviewDependencies.json').read_text())
    destination = HERE / 'ReviewDependencies'
    expected = {}
    archives = []
    for package in manifest['packages']:
        archive = subprocess.run(
            ['git', 'archive', package['commit'], '--', package['path']],
            cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            files = []
            for member in tar.getmembers():
                if member.isdir():
                    continue
                relative = PurePosixPath(member.name).relative_to(package['path'])
                if not member.isfile() or '..' in relative.parts:
                    raise ValueError('Unexpected archive entry')
                data = tar.extractfile(member).read()
                name = package['name'] + '/' + str(relative)
                expected[name] = hashlib.sha256(data).hexdigest()
                files.append((name, data))
            archives.extend(files)
    if destination.exists():
        actual = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in destination.rglob('*') if p.is_file()
                  and '.build' not in p.relative_to(destination).parts
                  and '.swiftpm' not in p.relative_to(destination).parts}
        if actual != expected:
            raise SystemExit('ReviewDependencies differs from pinned source; preserve/move it before preparing again.')
        print('Existing review inputs match all pinned source hashes.')
        return
    staging = Path(tempfile.mkdtemp(prefix='.review-staging-', dir=HERE))
    try:
        for name, data in archives:
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print('Prepared', len(archives), 'files from', len(manifest['packages']), 'pinned inputs; no network or credentials used.')


if __name__ == '__main__':
    prepare()
