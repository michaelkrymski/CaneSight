"""Exclusive Pi-role clock bench using an EXISTING saved bond. No camera/GPIO.

Stop the Pi's other bond poller/receiver before running. It remains a diagnostic
receiver: no production drift configuration or physical guidance is enabled.
"""
import argparse
import asyncio
import json
from pathlib import Path
import ssl
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.bond_client import BondClient
from pi_clock_characterization import State
from pi_phone_transport_probe import NoRedirectConnect
from websockets.exceptions import ConnectionClosed


class SessionChanged(ValueError):
    pass


def same_pair(before, after):
    return (after is not None and before['session_id'] == after['session_id']
            and before['peer'] == after['peer'] and before['device']['boot_id'] == after['device']['boot_id'])


async def renew(client, boot, pair):
    while True:
        await asyncio.sleep(8)
        fresh = await asyncio.to_thread(client.poll, boot)
        if not same_pair(pair, fresh):
            raise SessionChanged('Pair changed; discard this run')


async def one_run(client, boot, pair, now, seconds, *, connector=NoRedirectConnect):
    grant = client.session(pair)
    state = State(grant, pair['peer']['source_id'], pair['peer']['boot_id'])
    start = now()
    async with connector(client.base_url.replace('https://', 'wss://', 1) + '/v1/events',
            ssl=ssl.create_default_context(), additional_headers={'Authorization': 'Bearer ' + grant['token']},
            proxy=None, compression=None, max_size=8192, max_queue=1, open_timeout=5, close_timeout=1) as socket:
        state.opened()
        keeper = asyncio.create_task(renew(client, boot, pair))
        print('Pi clock receiver connected. Keep the phone foregrounded and streaming. No camera/GPIO.', flush=True)
        next_probe = now() + 1100
        try:
            while now() - start < seconds * 1000:
                if keeper.done():
                    await keeper
                try:
                    state.receive(await asyncio.wait_for(socket.recv(), .2), now())
                except asyncio.TimeoutError:
                    pass
                instant = now()
                state.tick(instant)
                if state.pending is not None and instant - state.pending['t1_ms'] >= 1000:
                    raise TimeoutError('Matched clock reply deadline')
                if instant >= next_probe:
                    message = state.probe(grant, instant)
                    if message is not None:
                        await socket.send(message)
                    next_probe = instant + 1100
        finally:
            keeper.cancel()
            await asyncio.gather(keeper, return_exceptions=True)
            state.interrupted(now())
    result = state.summary()
    result.update(existing_bond_reused=True, sample_seconds=round((now() - start) / 1000, 3),
                  measurement_peer_only=True, gpio_used=False, camera_used=False,
                  motor_state_verified=False, production_drift_configured=False)
    print(json.dumps(result), flush=True)
    if not result['clock_characterization']['holdout_consistent'] or sum(r['depth'] for r in state.connections) < 40:
        raise ValueError('Not enough consistent exchange/depth evidence; no bound configured')
    return result


async def observe(client, seconds):
    # Process epoch only, not a newly provisioned credential. Remains fixed
    # across reconnects; state/affine model never cross a session/peer boundary.
    boot = 'pi-clock-' + uuid.uuid4().hex
    anchor = time.monotonic()
    now = lambda: (time.monotonic() - anchor) * 1000
    deadline = time.monotonic() + 300
    reconnects = 0
    print('Polling existing Pi bond. Stop other Pi bond pollers. Phone may need Connect after this peer epoch changes.', flush=True)
    while time.monotonic() < deadline:
        pair = await asyncio.to_thread(client.poll, boot)
        if pair is None:
            print('Pi authenticated; waiting for matching phone.', flush=True)
            await asyncio.sleep(2)
            continue
        try:
            return await one_run(client, boot, pair, now, seconds)
        except (SessionChanged, ConnectionClosed):
            reconnects += 1
            if reconnects > 3:
                raise ValueError('Repeated pair changes; stop the other Pi poller and reconnect phone') from None
            print('Transport/peer changed; discarded partial model and waiting for a fresh pair.', flush=True)
            await asyncio.sleep(1)
    raise TimeoutError('No stable matching pair within 300 seconds')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bond-file', type=Path, required=True, help='Existing Pi-only saved file; never paste its contents')
    parser.add_argument('--exclusive-pi-peer', action='store_true', required=True,
                        help='Other Pi bond pollers/receivers have been stopped for this isolated test')
    parser.add_argument('--seconds', type=int, default=75, choices=range(60, 86), metavar='60..85')
    args = parser.parse_args()
    client = BondClient(args.bond_file, 'pi')
    if client.base_url != 'https://64.177.50.116':
        raise ValueError('Unexpected backend origin')
    asyncio.run(observe(client, args.seconds))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Clock bench stopped; no eligibility claimed.')
    except Exception as error:
        # Never print request/response objects, tokens or exception details.
        print('Clock bench failed safely: ' + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
