"""CS-027 context button state machine. No GPIO, speech or motor output.

The optional independent 10ms timer handles debounce and request expiry even if
capture/network/input code is blocked. Input adapters supply bool level changes;
injected frame suppliers, factories and job.poll/cancel must return promptly.
"""
import copy
from dataclasses import dataclass, field
import threading
import uuid

from .context_client import ContextError, validate_frame, validate_reply
from .haptics import clock_ms, number
from .uploader import Frame

DEBOUNCE_MS = 30
COOLDOWN_MS = 10_000
DEADLINE_MS = 8_000
MAX_START_AGE_MS = 1_500


@dataclass
class Pending:
    request_id: str
    deadline_ms: float
    metadata: dict = field(repr=False)
    handle: object = field(repr=False)


class ContextButton:
    """Release-to-arm, one outstanding job, no retry and a capture-based expiry.

    A second debounced press cancels an outstanding request even during cooldown.
    Cooldown starts with every attempted factory call and survives cancellation.
    Unknown/unsafe state suppresses context; the model never supplies this state.
    """
    def __init__(self, frame_supplier, request_factory, *, clock=clock_ms):
        self._frame_supplier = frame_supplier
        self._factory = request_factory
        self._clock = clock
        self._lock = threading.RLock()
        self._pending = None
        self._result = None
        self._result_deadline = None
        self._enabled = False
        self._closed = False
        self._fault = None
        self._last_now = None
        self._next_allowed = 0
        self._reset_input()
        self.requests = self.cancelled = self.failed = 0
        self._stop = threading.Event()
        self._thread = None

    def _reset_input(self):
        self._raw = self._stable = None
        self._changed_at = None
        self._released = False

    def _cancel(self, *, completed=False):
        pending, self._pending = self._pending, None
        self._result = self._result_deadline = None
        if pending is not None:
            self.cancelled += not completed
            try:
                pending.handle.cancel()
            except Exception:
                self._fault = 'Context cancellation unavailable; replace controller'
                self._enabled = False

    def _now(self):
        try:
            now = number(self._clock())
            if self._last_now is not None and now < self._last_now:
                raise ValueError('Clock reversed')
            self._last_now = now
            return now
        except Exception:
            self._cancel()
            self._fault = 'Context clock unavailable; replace controller'
            self._enabled = False
            self._reset_input()
            return None

    def set_state(self, *, ready: bool, consent: bool, hazard: bool):
        """Trusted local state only; call immediately on loss/preemption."""
        with self._lock:
            enabled = ready is True and consent is True and hazard is False
            if not enabled or enabled != self._enabled:
                self._cancel()
                self._reset_input()
            self._enabled = enabled and not self._closed and self._fault is None

    def sample(self, pressed: bool):
        with self._lock:
            now = self._now()
            if now is None or self._closed or self._fault is not None:
                return False
            if type(pressed) is not bool:
                self._cancel()
                self._reset_input()
                return False
            if pressed is not self._raw:
                self._raw, self._changed_at = pressed, now
            return self._tick(now)

    def _tick(self, now):
        if self._pending:
            pending = self._pending
            if now >= pending.deadline_ms or not self._enabled:
                self._cancel()
            else:
                try:
                    reply = pending.handle.poll()
                    if reply is not None:
                        reply = validate_reply(reply, pending.request_id, pending.metadata)
                        self._cancel(completed=True)
                        now = self._now()  # Poll/reaping time cannot renew capture age.
                        if now is None:
                            return False
                        if (self._fault is None and self._enabled and not self._closed
                                and now < pending.deadline_ms):
                            self._result, self._result_deadline = reply, pending.deadline_ms
                except Exception as error:
                    self.failed += 1
                    self._cancel()
                    if isinstance(error, ContextError) and error.fatal:
                        self._fault = 'Context session unavailable; restart and reenroll'
                        self._enabled = False
        if self._result is not None and now >= self._result_deadline:
            self._result = self._result_deadline = None
        if (not self._enabled or self._fault is not None or self._raw is None
                or now - self._changed_at < DEBOUNCE_MS or self._stable is self._raw):
            return False
        self._stable = self._raw
        if not self._stable:
            self._released = True
            return False
        if not self._released:
            return False
        self._released = False
        if self._pending is not None or self._result is not None:
            self._cancel()
            return False
        if now < self._next_allowed:
            return False
        return self._dispatch(now)

    def request(self):
        """Dispatch one completed trusted gesture without synthesizing input/time.

        Caller owns gesture debounce/release barriers. This retains the same
        request slot, cooldown, capture binding/expiry and fail-closed state.
        It never replaces or queues an outstanding request/result.
        """
        with self._lock:
            now = self._now()
            if (now is None or not self._enabled or self._closed or self._fault is not None
                    or self._pending is not None or self._result is not None
                    or now < self._next_allowed):
                return False
            self._reset_input()
            return self._dispatch(now)

    def _dispatch(self, now):
        try:
            frame = self._frame_supplier()
            metadata = validate_frame(frame)
            now = self._now()
            if now is None or not self._enabled or self._closed or self._fault is not None:
                return False
            age = now - metadata['capture_monotonic_ms']
            if not 0 <= age <= MAX_START_AGE_MS:
                return False
            # Do not let mutable producer metadata change the outstanding binding.
            frame = Frame(copy.deepcopy(metadata), frame.mapping, frame.jpeg)
            request_id = uuid.uuid4().hex
            self._next_allowed = now + COOLDOWN_MS
            self.requests += 1
            handle = self._factory(request_id, frame)
            self._pending = Pending(request_id,
                metadata['capture_monotonic_ms'] + DEADLINE_MS, metadata, handle)
            now = self._now()
            if (now is None or not self._enabled or self._closed or self._fault is not None
                    or now >= self._pending.deadline_ms):
                self._cancel()
                return False
            return True
        except Exception as error:
            self.failed += 1
            if isinstance(error, ContextError) and error.fatal:
                self._fault = 'Context session unavailable; restart and reenroll'
                self._enabled = False
            return False

    def tick(self):
        with self._lock:
            now = self._now()
            if now is not None and not self._closed and self._fault is None:
                self._tick(now)

    def take_result(self):
        """Consume one still-fresh structured result, never authorize speech."""
        with self._lock:
            self.tick()
            now = self._now()
            if (now is None or not self._enabled or self._closed or self._fault is not None
                    or self._result is None or now >= self._result_deadline):
                self._result = self._result_deadline = None
                return None
            result, self._result = self._result, None
            self._result_deadline = None
            return copy.deepcopy(result)

    def cancel(self):
        with self._lock:
            self._cancel()
            self._reset_input()

    def snapshot(self):
        with self._lock:
            self.tick()
            return {'requesting': self._pending is not None,
                'result_available': self._result is not None,
                'enabled': self._enabled, 'closed': self._closed, 'fault': self._fault,
                'requests': self.requests, 'cancelled': self.cancelled, 'failed': self.failed}

    def start(self):
        with self._lock:
            if self._thread is not None or self._closed:
                raise ValueError('Start the context timer once')
            def run():
                while not self._stop.wait(.01):
                    self.tick()
            self._thread = threading.Thread(target=run, daemon=True)
            self._thread.start()
        return self

    def close(self):
        with self._lock:
            self._closed = True
            self._enabled = False
            self._cancel()
            self._reset_input()
            self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)
