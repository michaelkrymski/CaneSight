"""Exercise an explicitly replay-only target with a generated image; no disk images."""
import io
import json
import os
import argparse
from pathlib import Path

import httpx
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be 1..65535')
    token = os.environ.get('CANESIGHT_REPLAY_TOKEN')
    if not token:
        raise SystemExit('Set CANESIGHT_REPLAY_TOKEN in this shell first; never paste it into Git/chat.')
    output = io.BytesIO()
    Image.new('RGB', (32, 24), color=(60, 100, 120)).save(output, format='JPEG')
    jpeg = output.getvalue()
    fixture = Path(__file__).resolve().parents[1] / 'shared/protocol/v1/examples/frame.json'
    metadata = json.loads(fixture.read_text(encoding='utf-8'))
    metadata.update(image={'width': 32, 'height': 24}, jpeg_bytes=len(jpeg))
    # This fixed fixture deliberately fails with 409 if submitted again in the
    # same server epoch. Restart the explicitly replay-only server to rehearse.
    with httpx.Client(base_url=f'http://127.0.0.1:{args.port}', timeout=10, trust_env=False) as client:
        health = client.get('/healthz')
        ready = client.get('/readyz')
        response = client.post('/v1/frames', headers={'Authorization': 'Bearer ' + token},
                               files={'metadata': (None, json.dumps(metadata), 'application/json'),
                                      'image': ('generated.jpg', jpeg, 'image/jpeg')})
        print('Mode: replay; generated synthetic image; no inference or hardware.')
        print('Liveness:', health.status_code, 'Readiness:', ready.status_code)
        print('Upload:', response.status_code, response.json())
        if health.status_code != 200 or ready.status_code != 503 or response.status_code != 202:
            raise SystemExit('Unexpected replay smoke result')


if __name__ == '__main__':
    main()
