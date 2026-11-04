"""Saved-bond phone depth -> obstacle-side haptics, optional Pi camera upload.

No tests/hardware run is performed by importing this module. Output simulation
is the default. Real GPIO requires --gpio and an explicit clock-drift budget.
"""
import argparse
import asyncio
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import threading
import time
import uuid

from backend.bond_client import BondClient
from backend.app import protocol
from .haptics import HapticScheduler, SimulatedOutput, Limits, clock_ms
from .policy import LocalPolicy, PhoneBinding, DepthPolicySettings
from .receiver import VisionReceiver
from .uploader import Latest, Sender, Transport, make_frame
from .watchdog import PolicyWatchdog


class RecoverConnection(RuntimeError):
    pass


class LiveDepthReceiver(VisionReceiver):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw_depth_count = self.clock_reply_count = 0
        self.last_depth_received_ms = None
        self.last_received_sectors = None
        self.last_clock_rtt_ms = None

    def receive(self, raw):
        # Diagnostics are not a second eligibility gate. Only the inherited
        # capture-age gate can provide observations to LocalPolicy.
        try:
            message = protocol.parse_wire(raw.encode() if isinstance(raw, str) else raw)
            with self.lock:
                peer = self.phone_binding
                matching = (message.get('session_id') == self.gate.session_id and peer is not None
                            and message.get('source_id') == peer.source_id)
                if matching and message['type'] == 'depth_observation' and message.get('boot_id') == peer.boot_id:
                    self.raw_depth_count += 1
                    self.last_depth_received_ms = clock_ms()
                    self.last_received_sectors = message['sectors']
                if matching and message['type'] == 'clock_reply' and message.get('source_boot_id') == peer.boot_id:
                    pending = self.gate.probes.get(peer.source_id)
                    if pending and pending['nonce'] == message['nonce']:
                        self.clock_reply_count += 1
                        self.last_clock_rtt_ms = clock_ms() - pending['t1_ms']
        except (ValueError, KeyError, TypeError):
            pass
        return super().receive(raw)

    def depth_status(self):
        with self.lock:
            observation = self.gate.current(self.phone_binding.source_id, 'depth_observation')
            age = None
            if observation is not None and observation.bound is not None:
                age = list(observation.bound.age_interval(observation.message, clock_ms(), self.gate.receiver_boot_id))
            if not self.connected:
                reason = 'disconnected'
            elif self.gate.drift is None:
                reason = 'clock_drift_budget_not_configured'
            elif self.phone_binding.source_id not in self.gate.bounds:
                reason = 'waiting_for_bounded_clock_exchange'
            elif not self.gate.healthy(self.phone_binding.source_id):
                reason = 'phone_not_ready_or_calibration_required'
            elif observation is None:
                reason = 'waiting_for_fresh_eligible_depth'
            else:
                reason = 'fresh_depth'
            return dict(connected=self.connected, reason=reason,
                        received_depth=self.raw_depth_count, accepted_depth=self.phone_accepted,
                        rejected_phone_packets=self.phone_rejected,
                        clock_replies=self.clock_reply_count, last_clock_rtt_ms=self.last_clock_rtt_ms,
                        age_interval_ms=age,
                        sectors=observation.message['sectors'] if observation else None,
                        last_raw_sectors=self.last_received_sectors,
                        last_raw_receipt_age_ms=(clock_ms()-self.last_depth_received_ms)
                        if self.last_depth_received_ms is not None else None)


class CameraUpload:
    """Optional vision source on the SAME bond/socket. Depth needs no camera."""
    def __init__(self, session, receiver, sender, latest, context=None):
        self.session, self.receiver, self.sender, self.latest = session, receiver, sender, latest
        self.stop_event = threading.Event()
        self.error = None
        self.camera = None
        self.count = 0
        self.context = context
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.sender_thread = threading.Thread(target=sender.run, daemon=True)

    def start(self):
        self.sender_thread.start()
        self.thread.start()

    def run(self):
        try:
            from picamera2 import Picamera2
            self.camera = Picamera2()
            self.camera.configure(self.camera.create_video_configuration(
                main={'size': (640, 480), 'format': 'RGB888'}, buffer_count=2, queue=False))
            self.camera.start()
            self.receiver.set_camera_ready(True)
            if self.context is not None:
                self.context.set_camera_ready(True)
            self.stop_event.wait(2)
            while not self.stop_event.is_set():
                started = time.monotonic()
                request = self.camera.capture_request()
                try:
                    image = request.make_image('main').copy()
                    metadata = request.get_metadata()
                finally:
                    request.release()
                self.count += 1
                try:
                    frame = make_frame(image, metadata, session_id=self.session['session_id'],
                        source_id=self.session['source_id'], boot_id=self.session['boot_id'],
                        seq=self.count, now=clock_ms())
                    self.latest.put(frame)
                except ValueError:
                    pass
                self.stop_event.wait(max(0, 1 - (time.monotonic()-started)))
        except Exception:
            self.error = 'camera_capture_unavailable'
        finally:
            with suppress(Exception):
                self.receiver.set_camera_ready(False)
            if self.context is not None:
                with suppress(Exception):
                    self.context.set_camera_ready(False)
            if self.camera is not None:
                with suppress(Exception):
                    self.camera.close()

    def close(self):
        self.stop_event.set()
        self.latest.close()
        self.thread.join(timeout=2)
        self.sender_thread.join(timeout=2)
        # Do not leave an old camera capture thread across a fresh process epoch.
        if self.thread.is_alive() or self.sender_thread.is_alive():
            raise RuntimeError('Capture worker did not stop; restart this process before reusing camera')


class StatusWriter:
    def __init__(self, path):
        self.path = path

    def write(self, data):
        row = dict(utc=datetime.now(timezone.utc).isoformat(), **data)
        print(json.dumps(row, allow_nan=False), flush=True)
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(row, out, allow_nan=False)
            out.write('\n')
        os.replace(temporary, self.path)


def same_pair(first, other):
    return (other is not None and other['session_id'] == first['session_id']
            and other['peer'] == first['peer'] and other['device']['boot_id'] == first['device']['boot_id'])


async def connected_run(args, client, pair, boot, stop, status, settings):
    binding = PhoneBinding(**pair['peer'], relative_drift_ppm=args.relative_drift_ppm)
    session = client.session(pair)
    receiver = LiveDepthReceiver(session, phone_binding=binding, ca_file=args.ca_file, clock=clock_ms)
    latest = Latest()
    sender = Sender(latest, Transport(session['base_url'], session['token'], ca_file=args.ca_file),
                    receiver=receiver, clock=clock_ms)
    output = scheduler = watchdog = policy = camera = context = context_gpio = None
    try:
        # Sender supplies the receiver's shared originating-frame ledger even in
        # depth-only mode; no upload worker runs unless the camera is requested.
        try:
            await asyncio.to_thread(receiver.start)
        except ValueError:
            raise RecoverConnection('native_socket_not_available') from None
        if args.gpio:
            from .haptic_gpio import GPIOOutput
            output = GPIOOutput(left_bcm=args.left_bcm, right_bcm=args.right_bcm, active_high=True)
        else:
            output = SimulatedOutput()
        scheduler = HapticScheduler(output, clock=clock_ms,
            limits=Limits(max_pulse_ms=150, min_off_ms=850, max_on_ms=1000, tick_ms=10))
        watchdog = PolicyWatchdog(scheduler.trip, clock=clock_ms)
        scheduler.set_guard(watchdog.deadline)
        scheduler.start()
        watchdog.start()
        policy = LocalPolicy(receiver.gate, binding.source_id, scheduler, clock=clock_ms,
                             watchdog=watchdog, enable_gpio=args.gpio, settings=settings)
        policy.arm(True)
        policy.start()
        if args.context_button:
            from .context_runtime import ManualContext, policy_priority
            from .context_gpio import GPIO21Input
            context = ManualContext(session,
                lambda: policy_priority(policy, receiver, sender, watchdog),
                consent=True, ca_file=args.ca_file, clock=clock_ms,
                **({'audio': True} if args.context_audio else {}))
            context_gpio = GPIO21Input()
            context.start(gpio_input=context_gpio)
        if args.with_camera:
            camera = CameraUpload(session, receiver, sender, latest, context=context)
            camera.start()
        next_poll = time.monotonic() + 5
        while not stop.is_set():
            if receiver.error or not receiver.connected:
                raise RecoverConnection('native_socket_lost')
            if watchdog.fault or policy.fault:
                raise RecoverConnection('local_policy_or_watchdog_fault')
            if time.monotonic() >= next_poll:
                current = await asyncio.to_thread(client.poll, boot)
                if not same_pair(pair, current):
                    raise RecoverConnection('pair_changed')
                next_poll = time.monotonic() + 5
            depth = receiver.depth_status()
            status.write(dict(state='connected', output_mode='gpio' if args.gpio else 'simulation',
                motor_gpio_requested=args.gpio, clock_drift_ppm=args.relative_drift_ppm,
                depth=depth, policy=policy.snapshot(), settings=asdict(settings),
                commanded_outputs=scheduler.tick()['outputs'],
                camera_enabled=args.with_camera, camera_error=camera.error if camera else None,
                vision_upload_error=bool(sender.error), physical_operation_verified=False))
            await asyncio.sleep(1)
    finally:
        # Motor eligibility/output is withdrawn before network/camera cleanup.
        failures = []
        for component in (policy, watchdog, scheduler, output, context, context_gpio):
            if component is not None and hasattr(component, 'close'):
                try:
                    if component.close() is False:
                        failures.append(type(component).__name__)
                except Exception:
                    failures.append(type(component).__name__)
        try:
            receiver.invalidate()
        except Exception:
            failures.append('receiver_invalidation')
        latest.close()
        if camera is not None:
            try:
                await asyncio.to_thread(camera.close)
            except Exception:
                failures.append('camera_shutdown')
        try:
            await asyncio.to_thread(receiver.stop)
        except Exception:
            failures.append('receiver_shutdown')
        if failures:
            # No automatic retry after an output/cleanup failure could reopen
            # GPIO or a camera while an old worker still owns the device.
            raise RuntimeError('Cleanup incomplete: ' + ','.join(failures))


async def run(args, status, settings):
    client = BondClient(args.bond_file, 'pi', ca_file=args.ca_file)
    stop = threading.Event()
    previous = {}
    def terminate(*_):
        stop.set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, terminate)
    boot = uuid.uuid4().hex
    try:
        while not stop.is_set():
            try:
                pair = await asyncio.to_thread(client.poll, boot)
                if pair is None:
                    status.write(dict(state='waiting_for_phone', output_mode='gpio' if args.gpio else 'simulation'))
                    await asyncio.sleep(2)
                    continue
                await connected_run(args, client, pair, boot, stop, status, settings)
            except (ConnectionError, OSError, RecoverConnection, TimeoutError):
                if stop.is_set():
                    break
                status.write(dict(state='reconnecting', outputs_off_requested=True))
                boot = uuid.uuid4().hex
                await asyncio.sleep(3)
            # Configuration/value errors are intentionally not retried silently.
    finally:
        stop.set()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        status.write(dict(state='stopped', outputs_off_requested=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bond-file', type=Path, required=True)
    parser.add_argument('--relative-drift-ppm', type=float,
                        help='Explicit supported-operation clock bound; omission is monitor-only eligibility')
    parser.add_argument('--gpio', action='store_true', help='Use real GPIO motors, not simulated outputs')
    parser.add_argument('--left-bcm', type=int, default=18)
    parser.add_argument('--right-bcm', type=int, default=19)
    parser.add_argument('--with-camera', action='store_true', help='Also upload Pi frames on this same session')
    parser.add_argument('--context-button', action='store_true', help='Optional GPIO21 scene-context request/cancel')
    parser.add_argument('--context-consent', action='store_true', help='Explicit consent for requested scene sharing')
    parser.add_argument('--context-audio', action='store_true', help='Use the existing current-user Pi speech route')
    parser.add_argument('--ca-file')
    parser.add_argument('--status-file', type=Path)
    parser.add_argument('--near-metres', type=float, default=1.2)
    parser.add_argument('--release-metres', type=float, default=1.5)
    parser.add_argument('--minimum-valid-fraction', type=float, default=.5)
    parser.add_argument('--pulse-ms', type=float, default=100)
    args = parser.parse_args()
    if args.context_button and not (args.with_camera and args.context_consent):
        parser.error('--context-button requires --with-camera and --context-consent')
    if args.context_audio and not args.context_button:
        parser.error('--context-audio requires --context-button')
    if args.context_consent and not args.context_button:
        parser.error('--context-consent requires --context-button')
    if args.relative_drift_ppm is not None and (not math.isfinite(args.relative_drift_ppm) or args.relative_drift_ppm < 0):
        parser.error('Clock drift must be a finite, nonnegative supported bound')
    if args.gpio and (args.relative_drift_ppm is None or args.relative_drift_ppm <= 0):
        parser.error('--gpio requires an explicit positive measured --relative-drift-ppm; no drift is invented')
    if args.gpio:
        from .haptic_gpio import GPIOOutput
        GPIOOutput.validate_configuration(args.left_bcm, args.right_bcm, True)
    try:
        settings = DepthPolicySettings(near_metres=args.near_metres, release_metres=args.release_metres,
                                      minimum_valid_fraction=args.minimum_valid_fraction, pulse_ms=args.pulse_ms)
    except ValueError as exc:
        parser.error(str(exc))
    # One local Pi owner, shared with the deployment launcher. Lock contents are
    # not credentials. Other legacy programs must still be stopped explicitly.
    lock_path = Path.home() / '.config/canesight/lidar-agent.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another LiDAR agent is running; stop it before starting a second peer')
        asyncio.run(run(args, StatusWriter(args.status_file), settings))


if __name__ == '__main__':
    main()
