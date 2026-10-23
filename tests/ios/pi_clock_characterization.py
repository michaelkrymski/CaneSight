"""Manual real-Pi clock characterization and conditional age diagnostics. No outputs."""
import argparse
import asyncio
import json
from pathlib import Path
import ssl
import sys
import time
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_phone_depth_probe import DepthState
from pi_phone_transport_probe import ID, load_grant, protocol, NoRedirectConnect
from clock_characterization import Exchange, Characterization
from backend.freshness import CaptureAgeGate, Unavailable
from websockets.exceptions import ConnectionClosed


class State(DepthState):
    def __init__(self, grant, phone, boot):
        super().__init__(grant['session_id'], phone, boot, maximum_depth=900)
        self.grant = grant
        self.model = Characterization()
        self.bound = None
        self.age_intervals = []
        self.rejected_age = 0
        self.receiver_now = 0
        self.bench_gate = None
        self.bench_nonce = None
        self.bench_ages = []
        self.close_cleared = False

    def probe(self, grant, now):
        self.receiver_now = now
        if self.bench_gate is None:
            return super().probe(grant, now)
        if not self.ready or self.pending is not None:
            return None
        request = self.bench_gate.start_probe(self.phone_source)
        self.pending = request
        self.bench_nonce = request['nonce']
        return json.dumps(request)

    def receive(self, raw, now):
        self.receiver_now = now
        value = protocol.parse_wire(raw.encode() if isinstance(raw, str) else raw)
        pending = self.pending
        super().receive(raw, now)
        if value['type'] == 'clock_reply':
            row = Exchange(pending['t1_ms'], value['t2_ms'], value['t3_ms'], now)
            self.model.add(row)
            ppm = self.model.candidate_ppm
            self.bound = None
            if ppm is not None:
                # CONDITIONAL bench calculation only. No production gate is configured.
                self.bound = protocol.verify_clock_reply(pending, value, now, ppm)
            if self.model.failed and self.bench_gate is not None:
                self.bench_gate.interrupt()
            elif self.bench_gate is None and self.model.summary()['holdout_consistent']:
                # Isolated measurement receiver, only AFTER twenty separate holdouts.
                # This explicitly assumes an affine rate for this controlled run.
                self.bench_gate = CaptureAgeGate(self.session, 'live', self.grant['source_id'],
                    self.grant['boot_id'], relative_drift_ppm=ppm, clock_ms=lambda: self.receiver_now)
                self.bench_gate.enroll(self.phone_source, self.phone_boot, {'heartbeat', 'depth_observation'})
            elif self.bench_gate is not None and self.bench_nonce == value['nonce']:
                try: self.bench_gate.finish_probe(value)
                except Unavailable: pass
                self.bench_nonce = None
        elif value['type'] == 'depth_observation':
            if self.model.failed:
                self.bound = None
            try:
                if self.bound is None or not self.ready:
                    raise ValueError('No conditional age map')
                interval = self.bound.age_interval(value, now, self.grant['boot_id'])
                if not protocol.within_budget('depth_observation', interval):
                    raise ValueError('Conditional age outside budget')
                if len(self.age_intervals) >= 900:
                    raise ValueError('Age sample bound')
                self.age_intervals.append(interval)
            except ValueError:
                self.rejected_age += 1
        if self.bench_gate is not None and not self.model.failed and value['type'] != 'clock_reply':
            try:
                observation = self.bench_gate.receive(value)
                if observation is not None and observation.message['type'] == 'depth_observation':
                    interval = observation.bound.age_interval(value, now, self.grant['boot_id'])
                    if len(self.bench_ages) < 900: self.bench_ages.append(interval)
            except (Unavailable, ValueError): pass

    def tick(self, now):
        self.receiver_now = now
        if self.bench_gate is not None: self.bench_gate.expire()

    def interrupted(self, now):
        self.receiver_now = now
        if self.bench_gate is not None:
            self.bench_gate.interrupt()
            self.close_cleared = self.bench_gate.current(self.phone_source, 'depth_observation') is None

    def summary(self):
        result = super().summary()
        result['clock_characterization'] = self.model.summary()
        result['isolated_measurement_receiver'] = dict(
            qualified_model_configured=self.bench_gate is not None, eligible_depth_count=len(self.bench_ages),
            min_lower_ms=round(min(x[0] for x in self.bench_ages), 3) if self.bench_ages else None,
            max_upper_ms=round(max(x[1] for x in self.bench_ages), 3) if self.bench_ages else None,
            transport_close_cleared_observations=self.close_cleared,
            scope='same controlled run, conditional on validated affine clock model; no guidance outputs')
        result['conditional_age_diagnostics'] = dict(
            packets_within_500ms_and_100ms_halfwidth=len(self.age_intervals), rejected_or_unmapped=self.rejected_age,
            min_lower_ms=round(min(x[0] for x in self.age_intervals), 3) if self.age_intervals else None,
            max_upper_ms=round(max(x[1] for x in self.age_intervals), 3) if self.age_intervals else None,
            NOT_a_production_eligibility_verdict=True)
        return result


async def observe(grant, phone, boot):
    state = State(grant, phone, boot)
    anchor = time.monotonic()
    def now(): return (time.monotonic()-anchor)*1000
    async with NoRedirectConnect('wss://64.177.50.116/v1/events', ssl=ssl.create_default_context(),
            additional_headers={'Authorization': 'Bearer '+grant['token']}, proxy=None,
            compression=None, max_size=8192, max_queue=1, open_timeout=5, close_timeout=1) as socket:
        state.opened()
        print('Pi clock observer connected; start phone characterization test now.', flush=True)
        next_probe = now()+1100
        try:
            while now() < 150_000:
                try: state.receive(await asyncio.wait_for(socket.recv(), .2), now())
                except asyncio.TimeoutError: pass
                instant = now()
                state.tick(instant)
                if state.pending is not None and instant-state.pending['t1_ms'] >= 1000:
                    raise TimeoutError('Clock reply deadline')
                if instant >= next_probe:
                    message = state.probe(grant, instant)
                    if message is not None: await socket.send(message)
                    next_probe = instant+1100
        except ConnectionClosed as error:
            if error.rcvd is None or error.rcvd.code not in (1000, 1001, 1012): raise ValueError('Unexpected close') from None
    state.interrupted(now())
    result = state.summary()
    print(json.dumps(result), flush=True)
    if not result['clock_characterization']['holdout_consistent'] or sum(r['depth'] for r in state.connections) < 400:
        raise ValueError('Characterization did not pass measured-model checks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-file', type=Path, required=True)
    parser.add_argument('--phone-source-id', required=True)
    parser.add_argument('--phone-boot-id', required=True)
    args = parser.parse_args()
    if any(ID.fullmatch(x) is None for x in (args.phone_source_id, args.phone_boot_id)):
        parser.error('Trusted phone bindings required')
    source, boot = 'pi-clock-'+uuid.uuid4().hex, uuid.uuid4().hex
    print(f'Source: {source}; boot: {boot}', flush=True)
    print('Waiting up to 300s for matching private Pi-only file.', flush=True)
    deadline = time.monotonic()+300
    while time.monotonic() < deadline:
        try:
            grant = load_grant(args.session_file, source, boot)
            break
        except (OSError, ValueError, TypeError): time.sleep(.5)
    else: raise TimeoutError('No matching private role file')
    asyncio.run(observe(grant, args.phone_source_id, args.phone_boot_id))


if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: print('Clock probe stopped; unavailable.')
    except Exception as error:
        print('Clock probe failed safely: '+type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
