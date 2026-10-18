"""Native operator consent/deletion helper; credentials and receipts stay private."""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

import httpx

from backend.deploy.session_probe import operator_token
from .event_store import ROOT, stream_id


def control(base, operator_file, action, receipt_file, *, session_id=None, consent_acknowledged=False):
    parsed = urlsplit(base)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Exact HTTPS origin required')
    path = Path(receipt_file).resolve()
    if path.is_relative_to(ROOT) or Path(operator_file).resolve().is_relative_to(ROOT):
        raise ValueError('Keep operator configuration and stream receipts outside the checkout')
    if action == 'enable':
        if not consent_acknowledged or not isinstance(session_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', session_id):
            raise ValueError('Acknowledge participant consent for one enrolled session')
        payload = dict(session_id=session_id, action='enable')
        route = 'consent'
    elif action in ('delete', 'status'):
        if not path.is_file() or path.stat().st_size > 512:
            raise ValueError('Private event stream receipt required')
        receipt = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(receipt, dict) or set(receipt) != {'stream_id'}:
            raise ValueError('Invalid stream receipt')
        payload = dict(stream_id=stream_id(receipt['stream_id']))
        route = 'delete' if action == 'delete' else 'deletion-status'
    else:
        raise ValueError('Invalid event logging action')

    def request():
        with httpx.Client(verify=True, trust_env=False, follow_redirects=False, timeout=5) as client:
            response = client.post(base.rstrip('/') + '/v1/event-logging/' + route,
                headers={'Authorization': 'Bearer ' + operator_token(operator_file)}, json=payload)
        if response.status_code not in (200, 202, 503) or 'no-store' not in response.headers.get('cache-control', ''):
            raise ValueError('Event operation denied')
        return response.json(), response.status_code

    if action == 'enable':
        # Reserve a new private receipt before changing remote consent. A lost
        # response can be retried idempotently with a new receipt filename.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            body, status = request()
            if status != 200 or body.get('enabled') is not True:
                raise ValueError('Consent not enabled')
            json.dump({'stream_id': stream_id(body['stream_id'])}, output)
            output.write('\n')
        return 'consent_enabled_storage_unverified'
    body, status = request()
    state = body.get('deletion_status')
    if state not in ('queued', 'deleted', 'failed', 'unknown', 'retry_required'):
        raise ValueError('Invalid deletion receipt')
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('enable', 'delete', 'status'))
    parser.add_argument('--base', required=True)
    parser.add_argument('--operator-file', type=Path, required=True)
    parser.add_argument('--receipt-file', type=Path, required=True)
    parser.add_argument('--session-id')
    parser.add_argument('--consent-acknowledged', action='store_true')
    args = parser.parse_args()
    try:
        state = control(args.base, args.operator_file, args.action, args.receipt_file,
                        session_id=args.session_id, consent_acknowledged=args.consent_acknowledged)
    except Exception:
        print('Event control failed; private details suppressed. No deletion confirmed.')
        return 1
    print('Event logging status: ' + state)
    return 1 if state in ('failed', 'retry_required', 'unknown') else 0


if __name__ == '__main__':
    raise SystemExit(main())
