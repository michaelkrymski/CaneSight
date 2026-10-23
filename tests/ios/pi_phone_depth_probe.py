"""Manual real-depth transport diagnostics. Never imports camera/GPIO or grants eligibility."""
import argparse
import asyncio
import json
from pathlib import Path
import ssl
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_phone_transport_probe import ID, load_grant, protocol, NoRedirectConnect
from websockets.exceptions import ConnectionClosed


class DepthState:
    def __init__(self, session, phone_source, phone_boot, *, maximum_depth=600):
        if not 1 <= maximum_depth <= 900:
            raise ValueError("Depth counter bound required")
        self.maximum_depth = maximum_depth
        self.session, self.phone_source, self.phone_boot = session, phone_source, phone_boot
        self.last_seq = {}
        self.last_capture = -1
        self.connections = []
        self.pending = None
        self.rtts = []
        self.clock_widths = []
        self.ready = False

    def opened(self):
        if len(self.connections) >= 4:
            raise ValueError('Connection bound exceeded')
        self.connections.append(dict(depth=0, heartbeats=0, first_capture=None, last_capture=None,
                                     first_receipt=None, last_receipt=None, depth_before_ready=0))
        self.pending = None
        self.ready = False

    def probe(self, grant, now):
        if not self.ready or self.pending is not None:
            return None
        value = dict(schema_version=1, type='clock_probe', session_id=self.session, mode='live',
                     nonce=uuid.uuid4().hex, receiver_id=grant['source_id'],
                     receiver_boot_id=grant['boot_id'], source_id=self.phone_source,
                     source_boot_id=self.phone_boot, t1_ms=now)
        self.pending = value
        return json.dumps(value)

    def receive(self, raw, now):
        value = protocol.parse_wire(raw.encode() if isinstance(raw, str) else raw)
        if value['type'] == 'clock_reply':
            expected = self.pending
            self.pending = None  # One-use matching probe; no live drift budget is assumed.
            if (expected is None or any(value[k] != v for k, v in expected.items() if k != 'type')
                    or not 0 <= now - expected['t1_ms'] <= 1000
                    or value['t3_ms'] < value['t2_ms']):
                raise ValueError('Invalid clock reply')
            rtt = now - expected['t1_ms']
            width = rtt - (value['t3_ms'] - value['t2_ms'])
            if width < 0 or len(self.rtts) >= 90:
                raise ValueError('Inconsistent or excessive clock exchange')
            self.rtts.append(rtt); self.clock_widths.append(width)
            return
        kind = value['type']
        if (kind not in ('heartbeat', 'depth_observation') or value['session_id'] != self.session
                or value['source_id'] != self.phone_source or value['boot_id'] != self.phone_boot
                or value['mode'] != 'live' or value['seq'] <= self.last_seq.get(kind, -1)):
            raise ValueError('Unexpected identity, kind or sequence')
        self.last_seq[kind] = value['seq']
        row = self.connections[-1]
        if kind == 'heartbeat':
            self.ready = value['state'] == 'ready'
            row['heartbeats'] += 1
            if row['heartbeats'] > 100:
                raise ValueError('Heartbeat bound exceeded')
            return
        capture = value['capture_monotonic_ms']
        if capture <= self.last_capture or row['depth'] >= self.maximum_depth:
            raise ValueError('Non-increasing capture or depth bound exceeded')
        self.last_capture = capture
        if not self.ready:
            row['depth_before_ready'] += 1
        row['depth'] += 1
        if row['first_capture'] is None:
            row['first_capture'], row['first_receipt'] = capture, now
        row['last_capture'], row['last_receipt'] = capture, now

    def summary(self):
        rates = []
        for row in self.connections:
            count = row['depth']
            def rate(first, last):
                return round((count - 1) * 1000 / (last - first), 3) if count > 1 and last > first else None
            rates.append(dict(depth_packets=count, heartbeats=row['heartbeats'],
                depth_before_ready_heartbeat=row['depth_before_ready'],
                source_capture_rate_hz=rate(row['first_capture'], row['last_capture']),
                receiver_arrival_rate_hz=rate(row['first_receipt'], row['last_receipt'])))
        def stats(values):
            values = sorted(values)
            return dict(count=len(values), median_ms=round(values[len(values)//2], 3),
                        max_ms=round(values[-1], 3)) if values else dict(count=0)
        return dict(real_depth_transport_only=True, connections=len(self.connections), per_connection=rates,
            strict_sequence_order=True, strictly_increasing_captures=True,
            clock_round_trip=stats(self.rtts), clock_exchange_width_diagnostic=stats(self.clock_widths),
            capture_age_eligibility='unknown', drift_budget_justified=False,
            pi_camera_used=False, gpio_used=False, physical_guidance_verified=False)


async def observe(grant, phone_source, phone_boot, *, connector=NoRedirectConnect):
    state = DepthState(grant['session_id'], phone_source, phone_boot)
    anchor = time.monotonic()
    def now():
        return (time.monotonic() - anchor) * 1000
    while now() < 90_000 and len(state.connections) < 4:
        try:
            async with connector('wss://64.177.50.116/v1/events', ssl=ssl.create_default_context(),
                    additional_headers={'Authorization': 'Bearer ' + grant['token']}, proxy=None,
                    compression=None, max_size=8192, max_queue=1, open_timeout=5, close_timeout=1) as socket:
                state.opened()
                print('Pi depth observer connected; waiting for phone. No guidance eligibility.', flush=True)
                next_probe = now() + 1100
                while now() < 90_000:
                    try:
                        raw = await asyncio.wait_for(socket.recv(), .2)
                        state.receive(raw, now())
                    except asyncio.TimeoutError:
                        pass
                    instant = now()
                    if state.pending is not None and instant - state.pending['t1_ms'] >= 1000:
                        raise TimeoutError('Clock reply timeout')
                    if instant >= next_probe:
                        message = state.probe(grant, instant)
                        if message is not None:
                            await socket.send(message)
                        next_probe = instant + 1100
                raise TimeoutError('Depth observation deadline expired')
        except ConnectionClosed as error:
            code = error.rcvd.code if error.rcvd else None
            if code not in (1000, 1001, 1012):
                raise ValueError('Unexpected socket closure') from None
            if len(state.connections) == 2 and all(r['depth'] >= 30 for r in state.connections):
                if len(state.rtts) < 2:
                    raise ValueError('Need observed clock replies')
                print(json.dumps(state.summary()), flush=True)
                return
            await asyncio.sleep(.3)
    raise TimeoutError('Need two completed depth connections')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-file', type=Path, required=True)
    parser.add_argument('--phone-source-id', required=True)
    parser.add_argument('--phone-boot-id', required=True)
    args = parser.parse_args()
    if any(ID.fullmatch(v) is None for v in (args.phone_source_id, args.phone_boot_id)):
        parser.error('Use trusted phone bindings')
    source, boot = 'pi-depth-' + uuid.uuid4().hex, uuid.uuid4().hex
    print(f'Source: {source}; boot: {boot}', flush=True)
    print('Waiting up to 300s for matching private Pi-only file. No camera/GPIO.', flush=True)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            grant = load_grant(args.session_file, source, boot)
            break
        except (OSError, ValueError, TypeError):
            time.sleep(.5)
    else:
        raise TimeoutError('No matching private grant')
    asyncio.run(observe(grant, args.phone_source_id, args.phone_boot_id))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Depth probe stopped; observations unavailable.')
    except Exception as error:
        print('Depth probe failed safely: ' + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
