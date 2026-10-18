"""Build optional application packaging over an exact locally installed image ID.

Dockerfile FROM interprets bare sha256:... as a repository/tag, not a local image
ID. Use a content-named local tag only after verifying its exact image identity.
No container is started, service recreated or private configuration read here.
"""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def inspect(reference):
    result = subprocess.run(['docker','image','inspect',reference,'--format','{{.Id}}'],
                            capture_output=True,text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def build(base_id, *, tag='canesight:application-candidate', log=None):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', base_id):
        raise ValueError('Supply the exact locally installed vision image ID')
    if not re.fullmatch(r'canesight:application-[a-z0-9][a-z0-9-]{0,80}',tag):
        raise ValueError('Use a dedicated canesight:application-* candidate tag')
    if inspect(base_id) != base_id:
        raise RuntimeError('Reviewed base image is not installed locally')
    base_tag = 'canesight-cs033-reviewed-base:' + base_id.removeprefix('sha256:')
    existing = inspect(base_tag)
    if existing is not None and existing != base_id:
        raise RuntimeError('Content-named base tag has an unexpected image; inspect locally')
    if existing is None:
        result = subprocess.run(['docker','tag',base_id,base_tag],capture_output=True)
        if result.returncode:
            raise RuntimeError('Cannot prepare reviewed local base tag')
    if inspect(base_tag) != base_id:
        raise RuntimeError('Local base identity changed before build')
    command = ['docker','build','-f','backend/deploy/Dockerfile.application',
               '--build-arg','BASE_IMAGE='+base_tag,'-t',tag,'.']
    if log is None:
        result = subprocess.run(command,cwd=ROOT)
    else:
        with Path(log).open('x',encoding='utf-8') as stream:
            result = subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode or inspect(base_tag) != base_id:
        raise RuntimeError('Application image build/base verification failed; inspect local build log')
    image = inspect(tag)
    if image is None or not re.fullmatch(r'sha256:[0-9a-f]{64}',image):
        raise RuntimeError('Application image identity unavailable')
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-image',required=True)
    parser.add_argument('--tag',default='canesight:application-candidate')
    parser.add_argument('--log',type=Path,help='New build log; never resolved Compose/private config')
    args = parser.parse_args()
    try:
        image = build(args.base_image,tag=args.tag,log=args.log)
    except (ValueError,RuntimeError,OSError):
        print('Application build unavailable; inspect base ID, Docker permissions and local build log.')
        return 1
    print('Built application image:',image)
    print('No container started or service activated.')
    return 0


if __name__ == '__main__': raise SystemExit(main())
