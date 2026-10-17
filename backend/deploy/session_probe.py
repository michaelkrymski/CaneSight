"""Verified HTTPS/WSS deployment acceptance using synthetic replay data only.

Run from the repository root with backend/requirements-test.txt installed.
Operator credentials come from a private file, never CLI values or URL queries.
"""
import argparse
import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
import secrets
import ssl
import stat

import httpx
from PIL import Image
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from backend.deploy.smoke import ProbeError, target


def operator_token(path):
    path = Path(path)
    if path.stat().st_size > 16384:
        raise ProbeError('Private configuration exceeds bound')
    if os.name != 'nt' and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ProbeError('Private configuration must have mode 0600')
    tokens = [line.partition('=')[2] for line in path.read_text().splitlines()
              if line.startswith('CANESIGHT_OPERATOR_TOKEN=')]
    if (len(tokens) != 1 or not 32 <= len(tokens[0]) <= 128 or not tokens[0].isascii()
            or any(char.isspace() for char in tokens[0])):
        raise ProbeError('Invalid private operator configuration')
    return tokens[0]


def require(condition):
    if not condition:
        raise ProbeError('Deployment acceptance failed; details suppressed')


async def run(base, token, *, context=None, expect_ready=False):
    target(base)
    context = context or ssl.create_default_context()
    require(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED)
    base = base.rstrip('/')
    wss = 'wss://' + base.removeprefix('https://')
    operator = {'Authorization': 'Bearer ' + token}
    options = {'ssl': context, 'proxy': None, 'open_timeout': 5, 'close_timeout': 2}
    prefix = 'probe-' + secrets.token_hex(4)
    body = {'mode': 'replay', 'phone': {'source_id': prefix + '-phone', 'boot_id': prefix + '-phone-boot'},
            'pi': {'source_id': prefix + '-pi', 'boot_id': prefix + '-pi-boot'}, 'ttl_seconds': 60}
    sessions = []
    async with httpx.AsyncClient(base_url=base, verify=context, trust_env=False, timeout=5) as client:
        try:
            require((await client.get('/healthz')).status_code == 200)
            require((await client.post('/v1/sessions', json=body)).status_code == 401)
            require((await client.post('/v1/sessions', json=body,
                headers={'Authorization': 'Bearer ' + secrets.token_urlsafe(40)})).status_code == 401)
            response = await client.post('/v1/sessions', json=body, headers=operator)
            directives = {value.strip().lower() for value in response.headers.get('cache-control', '').split(',')}
            require(response.status_code == 201 and 'no-store' in directives)
            pair = response.json()
            sessions.append(pair['session_id'])
            def auth(role):
                return {'Authorization': 'Bearer ' + pair[role]['token']}
            ready = await client.get('/readyz')
            require(ready.status_code == (200 if expect_ready else 503))
            checks = ready.json()['checks']
            for credential in (None, secrets.token_urlsafe(40)):
                headers = {} if credential is None else {'Authorization': 'Bearer ' + credential}
                try:
                    async with connect(wss + '/v1/events', additional_headers=headers, **options):
                        raise ProbeError('Unauthorized WSS accepted')
                except InvalidStatus as denied:
                    require(denied.response.status_code in (401, 403))
            message = {'schema_version': 1, 'type': 'depth_observation', 'session_id': pair['session_id'],
                'source_id': pair['phone']['source_id'], 'boot_id': pair['phone']['boot_id'],
                'seq': 1, 'capture_monotonic_ms': 0, 'capture_utc': None, 'mode': 'replay',
                'tracking': 'normal', 'sectors': {key: {'distance_m': None, 'valid_fraction': 0}
                                                for key in ('left', 'center', 'right')}}
            async with connect(wss + '/v1/events', additional_headers=auth('pi'), **options) as pi:
                async with connect(wss + '/v1/telemetry', additional_headers=auth('phone'), **options) as phone:
                    await phone.send(json.dumps(message))
                    require(json.loads(await asyncio.wait_for(pi.recv(), 3)) == message)
                    image = io.BytesIO()
                    Image.new('RGB', (32, 24), color=(70, 80, 90)).save(image, format='JPEG')
                    jpeg = image.getvalue()
                    metadata = {'schema_version': 1, 'type': 'frame_metadata', 'session_id': pair['session_id'],
                        'source_id': pair['pi']['source_id'], 'boot_id': pair['pi']['boot_id'], 'seq': 1,
                        'capture_monotonic_ms': 0, 'capture_utc': None, 'mode': 'replay',
                        'frame_id': prefix + '-frame', 'image': {'width': 32, 'height': 24}, 'jpeg_bytes': len(jpeg)}
                    files = {'metadata': (None, json.dumps(metadata), 'application/json'),
                             'image': ('synthetic.jpg', jpeg, 'image/jpeg')}
                    require((await client.post('/v1/frames', files=files, headers=auth('phone'))).status_code == 403)
                    upload = await client.post('/v1/frames', files=files, headers=auth('pi'))
                    require(upload.status_code == 202 and upload.json()['frame_id'] == metadata['frame_id'])
                    require((await client.post('/v1/frames', files=files, headers=auth('pi'))).status_code == 409)
                # Phone transport loss must invalidate the surviving Pi connection.
                try:
                    await asyncio.wait_for(pi.recv(), 3)
                    raise ProbeError('Peer interruption was not observed')
                except ConnectionClosed:
                    require(pi.close_code == 1012)
            # Give the invalidated peer handler time to dispose its registration.
            await asyncio.sleep(.15)
            async with connect(wss + '/v1/telemetry', additional_headers=auth('phone'), **options) as phone:
                await phone.send(json.dumps(message))
                try:
                    await asyncio.wait_for(phone.recv(), 3)
                    raise ProbeError('Reconnect reset sequence protection')
                except ConnectionClosed:
                    require(phone.close_code == 1008)
            expiry_body = dict(body, ttl_seconds=1)
            response = await client.post('/v1/sessions', json=expiry_body, headers=operator)
            require(response.status_code == 201)
            expiring = response.json()
            sessions.append(expiring['session_id'])
            await asyncio.sleep(1.2)
            require((await client.post('/v1/frames',
                headers={'Authorization': 'Bearer ' + expiring['pi']['token']})).status_code == 401)
            return {'verified_https_wss': True, 'matching_frame_ack': True,
                    'duplicate_rejected': True, 'expired_credential_rejected': True,
                    'disconnect_invalidated_peer': True, 'reconnect_replay_rejected': True,
                    'ready': ready.status_code == 200, 'readiness_checks': checks, 'mode': 'synthetic-replay'}
        finally:
            for session_id in sessions:
                with contextlib.suppress(Exception):
                    await client.delete('/v1/sessions/' + session_id, headers=operator)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--operator-file', type=Path, required=True)
    parser.add_argument('--expect-ready', action='store_true')
    args = parser.parse_args()
    try:
        report = asyncio.run(run(args.base, operator_token(args.operator_file), expect_ready=args.expect_ready))
    except Exception:
        print('Deployment acceptance failed; check TLS, secret configuration and session service locally. Details suppressed.')
        return 1
    print(json.dumps(report, sort_keys=True))
    print('Synthetic replay ingestion/transport only; no model, capture-age or hardware acceptance.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
