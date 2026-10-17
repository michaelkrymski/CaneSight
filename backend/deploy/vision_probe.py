"""Verified HTTPS/WSS generated-JPEG inference transport; never device evidence."""
import argparse
import asyncio
import contextlib
import io
import json
import math
from pathlib import Path
import secrets
import ssl
import statistics
import time

import httpx
from PIL import Image
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from backend.app import protocol
from backend.vision.baseline import manifest
from .session_probe import operator_token, require
from .smoke import target


async def run(base, token, *, context=None, samples=20):
    target(base)
    if type(samples) is not int or not 1 <= samples <= 100:
        raise ValueError('Use 1..100 samples')
    context = context or ssl.create_default_context()
    require(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED)
    base = base.rstrip('/')
    wss = 'wss://' + base.removeprefix('https://')
    options = {'ssl': context, 'proxy': None, 'open_timeout': 5, 'close_timeout': 2}
    operator = {'Authorization': 'Bearer ' + token}
    prefix = 'generated-' + secrets.token_hex(4)
    body = {'mode': 'replay', 'ttl_seconds': 180,
        'phone': {'source_id': prefix + '-phone', 'boot_id': prefix + '-phone-boot'},
        'pi': {'source_id': prefix + '-pi', 'boot_id': prefix + '-pi-boot'}}
    buffer = io.BytesIO()
    with Image.new('RGB', (416, 416), 'black') as image:
        image.save(buffer, format='JPEG', quality=75)
    jpeg = buffer.getvalue()
    sessions, durations = [], []
    async with httpx.AsyncClient(base_url=base, verify=context, trust_env=False, timeout=5) as client:
        async def enroll(specification):
            response = await client.post('/v1/sessions', json=specification, headers=operator)
            require(response.status_code == 201)
            pair = response.json()
            sessions.append(pair['session_id'])
            return pair
        try:
            startup_deadline = time.monotonic() + 10
            while True:
                try:
                    require((await client.get('/healthz')).status_code == 200)
                    break
                except httpx.ConnectError:
                    require(time.monotonic() < startup_deadline)
                    await asyncio.sleep(.1)
            pair, other = await enroll(body), await enroll(body)
            auth = {'Authorization': 'Bearer ' + pair['pi']['token']}
            deadline = time.monotonic() + 35
            while (await client.get('/readyz')).status_code != 200:
                require(time.monotonic() < deadline)
                await asyncio.sleep(.1)
            for url, headers in ((wss + '/v1/events', {}),
                    (wss + '/v1/events', {'Authorization': 'Bearer ' + pair['phone']['token']}),
                    (wss + '/v1/events', dict(auth, Origin='https://untrusted.example')),
                    (wss + '/v1/events?unsupported=1', auth)):
                try:
                    async with connect(url, additional_headers=headers, **options):
                        require(False)
                except InvalidStatus as denied:
                    require(denied.response.status_code == 403)
            async with contextlib.AsyncExitStack() as stack:
                pi = await stack.enter_async_context(connect(wss + '/v1/events', additional_headers=auth, **options))
                phone = await stack.enter_async_context(connect(wss + '/v1/telemetry',
                    additional_headers={'Authorization': 'Bearer ' + pair['phone']['token']}, **options))
                isolated = await stack.enter_async_context(connect(wss + '/v1/events',
                    additional_headers={'Authorization': 'Bearer ' + other['pi']['token']}, **options))
                for seq in range(samples):
                    started = time.monotonic()
                    metadata = {'schema_version': 1, 'type': 'frame_metadata', 'session_id': pair['session_id'],
                        'source_id': pair['pi']['source_id'], 'boot_id': pair['pi']['boot_id'],
                        'mode': 'replay', 'seq': seq, 'capture_monotonic_ms': started * 1000,
                        'capture_utc': None, 'frame_id': prefix + '-frame-' + str(seq),
                        'image': {'width': 416, 'height': 416}, 'jpeg_bytes': len(jpeg)}
                    files = {'metadata': (None, json.dumps(metadata), 'application/json'),
                             'image': ('generated.jpg', jpeg, 'image/jpeg')}
                    response = await client.post('/v1/frames', files=files, headers=auth)
                    require(response.status_code == 202 and response.json()['frame_id'] == metadata['frame_id'])
                    raw = await asyncio.wait_for(pi.recv(), 3)
                    observation = protocol.parse_wire(raw.encode() if isinstance(raw, str) else raw)
                    require(observation['type'] == 'vision_observation')
                    require(all(observation.get(k) == v for k, v in metadata.items() if k not in ('type', 'jpeg_bytes')))
                    require(observation['model_version'] == manifest()['model'] + '-sha256-' + manifest()['artifact']['sha256'])
                    require(observation['signal'] == {'candidate_count': 0, 'symbol': 'unknown',
                            'confidence': None, 'countdown_s': None})
                    durations.append((time.monotonic() - started) * 1000)
                    if seq + 1 < samples:
                        await asyncio.sleep(max(0, 1.05 - (time.monotonic() - started)))
                for socket in (phone, isolated):
                    try:
                        await asyncio.wait_for(socket.recv(), .2)
                        require(False)
                    except asyncio.TimeoutError:
                        pass
                response = await client.delete('/v1/sessions/' + pair['session_id'], headers=operator)
                require(response.status_code == 204)
                try:
                    await asyncio.wait_for(pi.recv(), 2)
                    require(False)
                except ConnectionClosed:
                    require(pi.close_code == 1000)
            expiring = await enroll(dict(body, ttl_seconds=1))
            async with connect(wss + '/v1/events', additional_headers={
                    'Authorization': 'Bearer ' + expiring['pi']['token']}, **options) as socket:
                try:
                    await asyncio.wait_for(socket.recv(), 2)
                    require(False)
                except ConnectionClosed:
                    require(socket.close_code == 4401)
            return {'generated_replay_only': True, 'verified_https_wss': True,
                'samples': samples, 'original_lineage_preserved': True,
                'phone_and_other_session_isolated': True, 'origin_query_and_role_denied': True,
                'revocation_and_expiry_closed': True, 'pedestrian_signal_unknown': True,
                'generated_upload_to_result_ms': {'median': round(statistics.median(durations), 3),
                    'p95_nearest_rank': round(sorted(durations)[math.ceil(samples * .95) - 1], 3),
                    'max': round(max(durations), 3)},
                'limits': 'Generated pixels only; excludes physical capture and Pi receipt; no detection accuracy or motor readiness.'}
        finally:
            for session_id in sessions:
                with contextlib.suppress(Exception):
                    await client.delete('/v1/sessions/' + session_id, headers=operator)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--operator-file', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--ca-file', type=Path, help='Explicit trusted test CA; hostname verification remains enabled')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        context = ssl.create_default_context(cafile=args.ca_file)
        report = asyncio.run(run(args.base, operator_token(args.operator_file), context=context, samples=args.samples))
        if args.report:
            with args.report.open('x', encoding='utf-8') as output:
                json.dump(report, output, indent=2)
                output.write('\n')
    except Exception:
        print('Vision transport verification failed; private details suppressed.')
        return 1
    print(json.dumps(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
