"""Manual physical-Pi receiver for CS-016 transport testing. No camera/GPIO.

Receives starting heartbeats only. Schema/identity/sequence observations are not
capture-age eligibility or source readiness. No clock mapping is fabricated.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app import protocol
from edge.receiver import NoRedirectConnect
from websockets.exceptions import ConnectionClosed

ID = re.compile(r'[A-Za-z0-9_-]{1,64}')
ORIGIN = 'https://64.177.50.116'


def unique(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate credential field')
        result[key] = value
    return result


def load_grant(path, source, boot):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size > 4096
            or stat.S_IMODE(info.st_mode) & 0o077
            or (hasattr(os, 'getuid') and info.st_uid != os.getuid())):
        raise ValueError('Use a user-owned mode-600 regular credential file')
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)
    if not isinstance(value, dict) or set(value) != {'base_url', 'session_id', 'source_id', 'boot_id', 'mode', 'token'}:
        raise ValueError('Use only the six-field Pi credential')
    if (value['base_url'] != ORIGIN or value['source_id'] != source or value['boot_id'] != boot
            or value['mode'] != 'live' or not isinstance(value['session_id'], str)
            or ID.fullmatch(value['session_id']) is None):
        raise ValueError('Credential must match this process and authorized origin')
    token = value['token']
    if not isinstance(token, str) or not 32 <= len(token) <= 128 or not all(33 <= ord(c) <= 126 for c in token):
        raise ValueError('Invalid role credential')
    return value


class ProbeState:
    def __init__(self, session, phone_source, phone_boot):
        self.session, self.phone_source, self.phone_boot = session, phone_source, phone_boot
        self.last_sequence = -1
        self.heartbeats = 0

    def receive(self, raw):
        value = protocol.parse_wire(raw.encode() if isinstance(raw, str) else raw)
        if (value['type'] != 'heartbeat' or value['session_id'] != self.session
                or value['source_id'] != self.phone_source or value['boot_id'] != self.phone_boot
                or value['mode'] != 'live' or value['state'] != 'starting'
                or value['seq'] <= self.last_sequence):
            raise ValueError('Unexpected identity, state, message or sequence')
        self.last_sequence = value['seq']
        self.heartbeats += 1


async def observe(grant, phone_source, phone_boot, *, connector=NoRedirectConnect):
    state = ProbeState(grant['session_id'], phone_source, phone_boot)
    deadline = time.monotonic() + 60
    connections = 0
    while state.heartbeats < 5 and time.monotonic() < deadline and connections < 4:
        try:
            async with connector('wss://64.177.50.116/v1/events',
                    ssl=ssl.create_default_context(), additional_headers={'Authorization': 'Bearer '+grant['token']},
                    proxy=None, compression=None, max_size=8192, max_queue=1,
                    open_timeout=5, close_timeout=1) as socket:
                connections += 1
                print('Pi WSS connected; waiting for phone starting heartbeats.', flush=True)
                while state.heartbeats < 5:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    state.receive(await asyncio.wait_for(socket.recv(), remaining))
                    print(f'Phone starting heartbeats observed={state.heartbeats}; depth eligibility unknown.', flush=True)
                await asyncio.sleep(.5)
        except ConnectionClosed as error:
            code = error.rcvd.code if error.rcvd else None
            if code not in (1000, 1001, 1012) or state.heartbeats >= 5:
                if state.heartbeats >= 5:
                    break
                raise ValueError('Unexpected socket closure') from None
            # Same source process and grant; retain sequence high-water mark.
            await asyncio.sleep(.5)
    if state.heartbeats < 5:
        raise TimeoutError('Phone heartbeat observation deadline expired')
    print(json.dumps({'transport_only': True, 'starting_heartbeats_observed': state.heartbeats,
        'connections': connections, 'strict_sequence_order': True, 'capture_age_eligibility': 'unknown',
        'camera_used': False, 'gpio_used': False, 'physical_guidance_verified': False}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-file', type=Path, required=True)
    parser.add_argument('--phone-source-id', required=True)
    parser.add_argument('--phone-boot-id', required=True)
    args = parser.parse_args()
    if any(ID.fullmatch(value) is None for value in (args.phone_source_id, args.phone_boot_id)):
        parser.error('Use trusted operator phone identity bindings')
    source, boot = 'pi-probe-'+uuid.uuid4().hex, uuid.uuid4().hex
    print(f'Source: {source}; boot: {boot}', flush=True)
    print('Enroll this process; waiting up to 300s for its private Pi-only credential file.', flush=True)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            grant = load_grant(args.session_file, source, boot)
            break
        except (OSError, ValueError, TypeError):
            time.sleep(.5)
    else:
        raise ValueError('No matching private Pi credential; no connection attempted')
    asyncio.run(observe(grant, args.phone_source_id, args.phone_boot_id))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Probe stopped; observations unavailable.')
    except Exception as error:
        # Never print exception text, frames, tokens, URLs or private file data.
        print('Probe failed safely: '+type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
