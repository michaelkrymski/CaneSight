"""CS-024 native vision receiver. Observation availability, never motor permission."""
import asyncio
import copy
import ssl
import threading
from urllib.parse import urlsplit

from jsonschema import ValidationError
from websockets.asyncio.client import connect

from backend.app import check_json_depth, protocol
from backend.freshness import CaptureAgeGate, Unavailable
from .uploader import clock_ms


class NoRedirectConnect(connect):
    def process_redirect(self, exc):
        # Credentials never accompany a redirected handshake, even same-origin.
        return exc


class VisionReceiver:
    """One socket, two-frame gate, and independent 50ms expiry loop.

    Only the trusted local camera is enrolled. A six-field Pi credential does
    not establish a phone identity, clock mapping or source health.
    The uploader and receiver must share a process, boot, clock and sender ledger.
    No reconnect: interruption requires a new process/session epoch.
    """
    def __init__(self, session, *, clock=clock_ms, ca_file=None, connector=NoRedirectConnect):
        if set(session) != {'base_url', 'session_id', 'source_id', 'boot_id', 'mode', 'token'}:
            raise ValueError('Use the private six-field Pi credential')
        origin = urlsplit(session['base_url'])
        if (origin.scheme != 'https' or not origin.hostname or origin.username or origin.password
                or origin.path not in ('', '/') or origin.query or origin.fragment):
            raise ValueError('Use the HTTPS origin without credentials/path/query')
        token = session['token']
        if (not isinstance(token, str) or not 32 <= len(token) <= 128 or not token.isascii()
                or any(c.isspace() for c in token) or session['mode'] != 'live'):
            raise ValueError('Use a valid live Pi credential')
        self.url = 'wss://' + origin.netloc + '/v1/events'
        self._token = token
        self.context = ssl.create_default_context(cafile=ca_file)
        self.connector = connector
        self.gate = CaptureAgeGate(session['session_id'], session['mode'], session['source_id'],
                                   session['boot_id'], clock_ms=clock)
        self.gate.enroll(session['source_id'], session['boot_id'], {'frame_metadata', 'vision_observation'})
        self.lock = threading.RLock()
        self.sender = None
        self.connected = False
        self.error = None
        self.accepted = self.rejected = self.expired = 0
        self._mapping = None
        self._started = threading.Event()
        self._stop = threading.Event()
        self._thread = None

    def bind_sender(self, sender):
        if self.sender is not None or self._thread is not None:
            raise ValueError('Bind one sender before starting')
        self.sender = sender

    def set_camera_ready(self, ready):
        if not isinstance(ready, bool):
            raise ValueError('Explicit local camera readiness required')
        with self.lock:
            self.gate.set_local_ready(bool(ready and self.connected and not self._stop.is_set()))
            if not ready:
                self._mapping = None

    def record_frame(self, frame):
        """Called by sender, under its ledger lock, before the HTTP request."""
        with self.lock:
            if not self.connected or self._stop.is_set():
                return False
            try:
                self.gate.record_frame(frame.metadata)
                return True
            except (ValueError, ValidationError, OverflowError):
                return False

    def receive(self, raw):
        # Same lock order as Sender: ledger, then receiver, then gate.
        with self.sender.lock, self.lock:
            try:
                if isinstance(raw, str):
                    raw = raw.encode('utf-8')
                check_json_depth(raw)
                message = protocol.parse_wire(raw)
                if message['type'] != 'vision_observation' or not self.connected or self._stop.is_set():
                    raise Unavailable('Not a current local vision observation')
                record = next((item for item in self.sender.ledger
                               if item[0]['frame_id'] == message['frame_id']), None)
                if record is None:
                    raise Unavailable('Frame no longer in originating ledger')
                observation = self.gate.receive(message)
                self._mapping = record[1] if observation else None
                self.accepted += observation is not None
                return observation
            except (ValueError, KeyError, TypeError, ValidationError, OverflowError):
                self.rejected += 1
                return None

    def tick(self):
        with self.lock:
            self.expired += len(self.gate.expire())
            return self.current()

    def current(self):
        """Fresh observation plus original stream mapping, or None.

        Callers still read on every policy tick. A saved snapshot is not a lease.
        Empty detections and unknown signal never imply an obstacle-free route.
        """
        with self.lock:
            observation = self.gate.current(self.gate.receiver_id, 'vision_observation')
            if not self.connected or self._stop.is_set() or observation is None:
                self._mapping = None
                return None
            return observation, copy.deepcopy(self._mapping)

    def invalidate(self):
        with self.lock:
            self.connected = False
            self._mapping = None
            try:
                self.gate.set_local_ready(False)
                self.gate.interrupt()
            except Unavailable:
                pass  # A reversed clock already cleared all evidence.

    async def _run(self):
        try:
            async with self.connector(self.url, ssl=self.context,
                    additional_headers={'Authorization': 'Bearer ' + self._token},
                    proxy=None, compression=None, max_size=8192, max_queue=1,
                    open_timeout=5, close_timeout=1) as socket:
                with self.lock:
                    self.connected = True
                self._started.set()
                async def read():
                    while True:
                        raw = await socket.recv()
                        self.receive(raw)
                reader = asyncio.create_task(read())
                try:
                    while not self._stop.is_set():
                        self.tick()
                        # Receive can block indefinitely; expiry cannot depend on it.
                        done, _ = await asyncio.wait({reader}, timeout=.05)
                        if done:
                            await reader
                            break
                finally:
                    reader.cancel()
                    await asyncio.gather(reader, return_exceptions=True)
        except Exception:
            if not self._stop.is_set():
                self.error = 'Vision transport unavailable; restart and reenroll'
        finally:
            self.invalidate()
            self._started.set()

    def start(self):
        if self.sender is None or self._thread is not None or self._stop.is_set():
            raise ValueError('Bind sender and start receiver once')
        self._thread = threading.Thread(target=lambda: asyncio.run(self._run()), daemon=True)
        self._thread.start()
        if not self._started.wait(6) or not self.connected:
            self.stop()
            raise ValueError('Vision connection unavailable; no capture started')

    def stop(self):
        self._stop.set()
        self.invalidate()
        if self._thread is not None:
            self._thread.join(timeout=2)
