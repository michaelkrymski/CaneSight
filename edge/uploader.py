"""CS-022: bounded Pi camera upload. No inference or movement decisions."""
import argparse
from collections import deque
from dataclasses import dataclass, field
import io
import json
import math
import os
from pathlib import Path
import re
import ssl
import stat
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PIL import Image

MAX_AGE_MS = 1500
ID = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')


def clock_ms():
    """All Pi capture, local expiry and future clock replies use BOOTTIME."""
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME) / 1_000_000


def capture_time(metadata, now):
    """Conservative first-exposure bound; never substitute encoding time."""
    sensor = metadata.get('SensorTimestamp')
    exposure = metadata.get('ExposureTime')
    if (type(sensor) is not int or sensor <= 0
            or type(exposure) not in (int, float)
            or not math.isfinite(exposure) or exposure <= 0):
        raise ValueError('Missing capture timing')
    # Some Pi drivers report CSI start of frame. Subtract a full exposure even
    # for drivers reporting first exposure: an older bound cannot renew age.
    captured = sensor / 1_000_000 - exposure / 1000
    if not 0 <= captured <= now or not sensor / 1_000_000 <= now:
        raise ValueError('Capture clock mismatch')
    return captured


@dataclass(frozen=True)
class Mapping:
    """416-square pixels -> configured 640x480 stream, not phone/sensor rays."""
    sensor_crop: tuple | None = None

    def stream_box(self, box):
        if len(box) != 4 or any(not math.isfinite(x) for x in box):
            raise ValueError('Invalid box')
        x1, y1, x2, y2 = box
        x1, x2 = max(0, x1), min(416, x2)
        y1, y2 = max(52, y1), min(364, y2)
        if x1 >= x2 or y1 >= y2:
            return None
        return (x1 / .65, (y1 - 52) / .65, x2 / .65, (y2 - 52) / .65)


@dataclass(frozen=True)
class Frame:
    metadata: dict
    mapping: Mapping
    jpeg: bytes = field(repr=False)


def make_frame(image, camera_metadata, *, session_id, source_id, boot_id, seq, now):
    if image.size != (640, 480):
        raise ValueError('Expected configured 640x480 stream')
    if any(not ID.fullmatch(x) for x in (session_id, source_id, boot_id)):
        raise ValueError('Invalid enrolled identity')
    if type(seq) is not int or not 0 <= seq <= 2**53 - 1:
        raise ValueError('Invalid sequence')
    captured = capture_time(camera_metadata, now)
    square = Image.new('RGB', (416, 416), 'black')
    square.paste(image.convert('RGB').resize((416, 312), Image.Resampling.LANCZOS), (0, 52))
    output = io.BytesIO()
    square.save(output, format='JPEG', quality=75)
    jpeg = output.getvalue()
    if not 0 < len(jpeg) <= 1_000_000:
        raise ValueError('JPEG size out of bounds')
    crop = camera_metadata.get('ScalerCrop')
    crop = tuple(crop) if crop is not None else None
    if crop is not None and (len(crop) != 4 or any(type(x) is not int for x in crop)
                             or min(crop[:2]) < 0 or min(crop[2:]) <= 0):
        raise ValueError('Invalid sensor crop')
    return Frame({
        'schema_version': 1, 'type': 'frame_metadata',
        'session_id': session_id, 'source_id': source_id, 'boot_id': boot_id,
        'seq': seq, 'capture_monotonic_ms': captured, 'capture_utc': None,
        'mode': 'live', 'frame_id': uuid.uuid4().hex,
        'image': {'width': 416, 'height': 416}, 'jpeg_bytes': len(jpeg),
    }, Mapping(crop), jpeg)


class Latest:
    """One pending JPEG plus at most one held by the single sender."""
    def __init__(self):
        self.condition = threading.Condition()
        self.pending = None
        self.closed = False
        self.replaced = 0

    def put(self, frame):
        with self.condition:
            if self.closed:
                return
            self.replaced += self.pending is not None
            self.pending = frame
            self.condition.notify()

    def take(self):
        with self.condition:
            self.condition.wait_for(lambda: self.closed or self.pending is not None)
            frame, self.pending = self.pending, None
            return frame

    def close(self):
        with self.condition:
            self.closed = True
            self.pending = None
            self.condition.notify_all()


class StopSession(Exception):
    """Authentication/order errors require operator action, not blind retries."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Transport:
    def __init__(self, base_url, token, *, ca_file=None):
        parsed = urllib.parse.urlsplit(base_url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                or parsed.password or parsed.path not in ('', '/')
                or parsed.query or parsed.fragment):
            raise ValueError('Use the HTTPS backend origin without credentials/path')
        if (not isinstance(token, str) or len(token) < 32 or not token.isascii()
                or any(c.isspace() for c in token)):
            raise ValueError('Invalid credential')
        self.url = base_url.rstrip('/') + '/v1/frames'
        self._token = token
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)))

    def send(self, frame):
        boundary = uuid.uuid4().hex
        metadata = json.dumps(frame.metadata, separators=(',', ':'), allow_nan=False).encode()
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()
                + metadata + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="frame.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()
                + frame.jpeg + f'\r\n--{boundary}--\r\n'.encode())
        request = urllib.request.Request(self.url, data=body, method='POST', headers={
            'Authorization': 'Bearer ' + self._token,
            'Content-Type': 'multipart/form-data; boundary=' + boundary,
        })
        try:
            with self.opener.open(request, timeout=2) as response:
                payload = response.read(4097)
                expected = {'schema_version': 1, 'frame_id': frame.metadata['frame_id'], 'status': 'accepted'}
                ack = json.loads(payload) if len(payload) <= 4096 else None
                if (response.status != 202 or not isinstance(ack, dict) or ack != expected
                        or type(ack.get('schema_version')) is not int):
                    raise StopSession('Invalid acknowledgement; operator investigation required')
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code in (401, 403, 409) or 300 <= code < 400:
                raise StopSession(f'Upload stopped: HTTP {code}') from None
            # Do not retain response body, URL or credentials in diagnostics.
            raise OSError('Upload rejected') from None
        except (ValueError, UnicodeError):
            raise StopSession('Invalid acknowledgement') from None


class Sender:
    def __init__(self, latest, transport, *, clock=clock_ms, receiver=None):
        self.latest, self.transport, self.clock = latest, transport, clock
        self.ledger = deque(maxlen=2)  # metadata/mapping only; never JPEGs
        self.lock = threading.Lock()
        self.accepted = self.dropped = self.failed = 0
        self.error = None
        self.receiver = receiver
        if receiver is not None:
            receiver.bind_sender(self)

    def run(self):
        try:
            while (frame := self.latest.take()) is not None:
                age = self.clock() - frame.metadata['capture_monotonic_ms']
                if not 0 <= age <= MAX_AGE_MS:
                    self.dropped += 1
                    continue
                with self.lock:
                    self.ledger.append((dict(frame.metadata), frame.mapping))
                    if self.receiver is not None and not self.receiver.record_frame(frame):
                        self.dropped += 1
                        continue
                try:
                    self.transport.send(frame)
                    self.accepted += 1  # ACK is storage acceptance, not freshness/readiness.
                except OSError:
                    self.failed += 1  # Drop forever; next take receives latest capture.
        except StopSession as exc:
            self.error = str(exc)
            self.latest.close()
        except Exception:
            self.error = 'Sender failed; restart with a newly enrolled boot'
            self.latest.close()


def load_session(path, source_id, boot_id):
    path = Path(path)
    if path.stat().st_size > 4096:
        raise ValueError('Oversized session file')
    if hasattr(os, 'getuid') and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Session file must be private: chmod 600')
    session = json.loads(path.read_text(encoding='utf-8'))
    if (session.get('source_id') != source_id or session.get('boot_id') != boot_id
            or session.get('mode') != 'live' or not ID.fullmatch(session.get('session_id', ''))):
        raise ValueError('Session must match this live process identity')
    return session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-only', action='store_true')
    parser.add_argument('--frames', type=int, default=10, help='0 runs until Ctrl+C')
    parser.add_argument('--source-id', default='pi-camera')
    parser.add_argument('--session-file', type=Path)
    parser.add_argument('--ca-file')
    parser.add_argument('--receive-vision', action='store_true',
                        help='Receive native WSS vision in this same process; no motor outputs')
    parser.add_argument('--simulate-policy', action='store_true',
                        help='Arm local policy with simulated outputs only; requires receiver')
    parser.add_argument('--phone-binding-file', type=Path,
                        help='Trusted phone source/boot/drift file; never a phone/operator token')
    parser.add_argument('--policy-trace',type=Path,help='New private metadata JSONL outside checkout; simulated policy only')
    parser.add_argument('--context-stdin', action='store_true',
                        help='Manual terminal context button; no GPIO/audio; requires verified primary-source policy')
    parser.add_argument('--context-consent', action='store_true',
                        help='Explicit consent to send requested scene frames to the context provider')
    args = parser.parse_args()
    if args.frames < 0 or not ID.fullmatch(args.source_id):
        parser.error('Use nonnegative frames and a protocol source ID')
    if not args.capture_only and not args.session_file:
        parser.error('Supply --session-file or --capture-only')
    if args.receive_vision and args.capture_only:
        parser.error('--receive-vision requires a live enrolled upload session')
    if (args.simulate_policy or args.phone_binding_file) and not args.receive_vision:
        parser.error('Policy/phone binding requires --receive-vision')
    if args.policy_trace and not args.simulate_policy:
        parser.error('--policy-trace requires --simulate-policy')
    if args.context_stdin and not (args.context_consent and args.simulate_policy and args.phone_binding_file):
        parser.error('--context-stdin requires --context-consent, --simulate-policy and --phone-binding-file')
    if args.context_consent and not args.context_stdin:
        parser.error('--context-consent requires --context-stdin')
    boot_id = uuid.uuid4().hex
    print(f'Source: {args.source_id}; boot: {boot_id}', flush=True)
    session_id = 'capture-only'
    latest, sender, worker, receiver = Latest(), None, None, None
    policy, scheduler, watchdog, trace = None, None, None, None
    context_input = None
    if not args.capture_only:
        print('Enroll this identity; waiting up to 300s for matching private session file.', flush=True)
        deadline = time.monotonic() + 300
        session = None
        while time.monotonic() < deadline:
            try:
                session = load_session(args.session_file, args.source_id, boot_id)
                break
            except (OSError, ValueError, TypeError):
                time.sleep(.5)
        if session is None:
            raise SystemExit('No matching session file; no frames sent')
        session_id = session['session_id']
        transport = Transport(session['base_url'], session['token'], ca_file=args.ca_file)
        if args.receive_vision:
            from .receiver import VisionReceiver
            if args.phone_binding_file:
                from .policy import PhoneBinding
                binding = PhoneBinding.load(args.phone_binding_file)
                receiver = VisionReceiver(session,ca_file=args.ca_file,phone_binding=binding)
            else:
                receiver = VisionReceiver(session, ca_file=args.ca_file)
        sender = Sender(latest, transport, receiver=receiver)
        if receiver:
            receiver.start()  # Authenticated WSS must exist before any capture/upload.
        worker = threading.Thread(target=sender.run, daemon=True)
        worker.start()
    camera = None
    try:
        if args.simulate_policy:
            from .haptics import HapticScheduler, SimulatedOutput
            from .policy import LocalPolicy
            from .watchdog import PolicyWatchdog
            scheduler = HapticScheduler(SimulatedOutput(),clock=clock_ms).start()
            watchdog = PolicyWatchdog(scheduler.trip,clock=clock_ms)
            scheduler.set_guard(watchdog.deadline)
            watchdog.start()
            if args.policy_trace:
                from .trace import DecisionTrace
                trace = DecisionTrace(args.policy_trace)
            policy = LocalPolicy(receiver.gate,
                receiver.phone_binding.source_id if receiver.phone_binding else None,
                scheduler,clock=clock_ms,watchdog=watchdog,trace=trace)
            policy.arm(True)
            policy.start()
        if args.context_stdin:
            import sys
            from .context_runtime import ManualContext, policy_priority
            context_input = ManualContext(session,
                lambda: policy_priority(policy, receiver, sender, watchdog),
                consent=args.context_consent, ca_file=args.ca_file, clock=clock_ms)
            context_input.start(sys.stdin)
            print('Manual context input: release / press / cancel / off. No GPIO or audio. '
                  'Unknown primary-source state suppresses requests.', flush=True)
        from picamera2 import Picamera2  # Hardware dependency intentionally lazy.
        camera = Picamera2()
        camera.configure(camera.create_video_configuration(
            main={'size': (640, 480), 'format': 'RGB888'}, buffer_count=2, queue=False))
        camera.start()
        if context_input:
            context_input.set_camera_ready(True)
        if receiver:
            receiver.set_camera_ready(True)
        time.sleep(2)
        seq = 0
        while args.frames == 0 or seq < args.frames:
            started = time.monotonic()
            if watchdog and watchdog.fault:
                raise StopSession('Local watchdog unavailable; restart and reenroll')
            if sender and sender.error:
                raise StopSession(sender.error)
            if receiver and receiver.error:
                raise StopSession(receiver.error)
            request = camera.capture_request()
            try:
                metadata = request.get_metadata()
                image = request.make_image('main').copy()
            finally:
                request.release()
            seq += 1
            try:
                frame = make_frame(image, metadata, session_id=session_id,
                                   source_id=args.source_id, boot_id=boot_id, seq=seq, now=clock_ms())
                age = clock_ms() - frame.metadata['capture_monotonic_ms']
                if not 0 <= age <= MAX_AGE_MS:
                    raise ValueError('Capture already stale')
                print(f'Frame {seq}: 416x416, {len(frame.jpeg)} bytes, age bound {age:.0f}ms', flush=True)
                if sender:
                    latest.put(frame)
                if context_input:
                    context_input.offer(frame)
            except ValueError as exc:
                print(f'Frame {seq} dropped: {exc}', flush=True)
            time.sleep(max(0, 1 - (time.monotonic() - started)))
    finally:
        if context_input:
            context_input.close()
            print('Context ' + json.dumps(context_input.snapshot(), sort_keys=True))
        if policy:
            policy.close()
        if trace:
            print('Policy trace ' + json.dumps(trace.close(),sort_keys=True))
        if watchdog:
            watchdog.close()
        if scheduler:
            scheduler.close()
        try:
            if receiver:
                receiver.set_camera_ready(False)
        finally:
            try:
                if camera:
                    camera.close()
            finally:
                latest.close()
                if worker:
                    worker.join(timeout=3)
                if receiver:
                    receiver.stop()
                    print(f'Vision accepted={receiver.accepted}; rejected={receiver.rejected}; expired={receiver.expired}; unavailable on exit')
        if policy:
            print('Policy ' + json.dumps(policy.snapshot(),sort_keys=True))
            print('Simulated outputs off=' + str(all(value is False for value in scheduler.snapshot()['outputs'].values())) + '; gpio_used=false')
        if receiver and receiver.phone_binding:
            print(f'Depth accepted={receiver.phone_accepted}; rejected={receiver.phone_rejected}; phone binding configured; physical readiness unverified')
        if sender:
            print(f'Accepted={sender.accepted}; stale={sender.dropped}; failed={sender.failed}; replaced={latest.replaced}')
            if sender.error:
                raise SystemExit(sender.error)
        if receiver and receiver.error:
            raise SystemExit(receiver.error)


if __name__ == '__main__':
    import signal
    def terminate(_signum, _frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, terminate)
    try:
        main()
    except KeyboardInterrupt:
        pass
