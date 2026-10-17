"""Issue a session-scoped viewer file privately; never print credentials."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from backend.deploy.session_probe import operator_token
from backend.sessions import bearer


def issue(base, operator_file, session_id, output):
    parsed = urlsplit(base)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('HTTPS origin required')
    output = Path(output)
    if output.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError('Viewer credentials must stay outside the checkout')
    if output.exists():
        raise ValueError('Use a new private output file')
    with httpx.Client(verify=True, trust_env=False, follow_redirects=False, timeout=5) as client:
        response = client.post(base.rstrip('/') + '/v1/dashboard-viewers',
            headers={'Authorization': 'Bearer ' + operator_token(operator_file)},
            json={'session_id': session_id})
        if response.status_code != 201 or 'no-store' not in response.headers.get('cache-control', ''):
            raise ValueError('Viewer issuance denied')
        data = response.json()
    if set(data) != {'viewer_token', 'expires_in_seconds'}:
        raise ValueError('Invalid viewer response')
    bearer('Bearer ' + data['viewer_token'])
    if type(data['expires_in_seconds']) is not int or not 1 <= data['expires_in_seconds'] <= 600:
        raise ValueError('Invalid viewer lifetime')
    # Parent must be private; Windows callers must verify its user-only ACL.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(dict(base_url=base.rstrip('/'), **data), stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--operator-file', type=Path, required=True)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        issue(args.base,args.operator_file,args.session_id,args.out)
    except Exception:
        print('Viewer issuance failed; private details suppressed.')
        return 1
    print('Viewer-only credential written privately. Never enter device/operator credentials in the dashboard.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
