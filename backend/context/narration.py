"""CS-040: render a closed vocabulary and gate optional speech locally.

Provider prose is never spoken. This component has no movement, signal, motor,
or shared-protocol interface. Integrators supply local capture-age bounds and
call tick independently of provider/network progress.
"""
from dataclasses import dataclass
import math
import secrets
import threading
import time
from typing import Callable, Protocol


OBJECTS = frozenset({
    'person', 'chair', 'table', 'door', 'stairs', 'tree', 'vehicle', 'sign',
    'building', 'bicycle', 'bench', 'bag', 'dog', 'pole', 'wall', 'plant',
})
UNAVAILABLE = 'Description unavailable.'


def render_description(value: object) -> str:
    """Accept only the private context shape, never arbitrary model wording."""
    if type(value) is not dict or set(value) != {'objects', 'uncertain'}:
        return UNAVAILABLE
    labels = value['objects']
    if value['uncertain'] is not True or type(labels) is not list or not 1 <= len(labels) <= 3:
        return UNAVAILABLE
    if any(type(label) is not str or label not in OBJECTS for label in labels):
        return UNAVAILABLE
    labels = list(dict.fromkeys(labels))
    names = ' and '.join(labels)
    return 'AI description, uncertain: Possible ' + names + '.'


class SpeechSink(Protocol):
    """Nonblocking local adapter; stop must interrupt current audio immediately.

    These methods must not call back into the controller. The controller
    serializes them to prevent a delayed speak after a completed cancel.
    """
    def speak(self, text: str) -> None: ...
    def stop(self) -> None: ...


@dataclass(frozen=True)
class Ticket:
    request_id: str
    expires_at: float


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


class NarrationController:
    """One request/audio slot, fail-closed priorities and a capture-based expiry.

    Defaults to unavailable. set_priority must be driven by the independent
    trusted health/hazard policy, never a Gemini result. Even a recovered source
    cannot resurrect a cancelled/expired request. No images or keys retained.
    """
    def __init__(self, sink: SpeechSink, *, clock: Callable[[], float] = time.monotonic):
        self._sink = sink
        self._clock = clock
        self._lock = threading.Lock()
        self._ticket = None
        self._delivered = False
        self._blocked = True
        self._closed = False

    def _cancel(self):
        self._ticket = None
        self._delivered = False
        try:
            self._sink.stop()
        except Exception:
            # A broken adapter requires replacement; do not accept more audio.
            self._closed = True

    def set_priority(self, *, hazard: bool, unavailable: bool) -> None:
        with self._lock:
            self._blocked = hazard is not False or unavailable is not False
            if self._blocked:
                self._cancel()

    def begin(self, *, capture_age_upper_s: float, consent: bool) -> Ticket | None:
        with self._lock:
            self._cancel()
            now = self._clock()
            if (self._closed or self._blocked or consent is not True
                    or not _finite(now) or not _finite(capture_age_upper_s)
                    or not 0 <= capture_age_upper_s < 8):
                return None
            self._ticket = Ticket(secrets.token_urlsafe(24), now + 8 - capture_age_upper_s)
            return self._ticket

    def deliver(self, ticket: Ticket, value: object) -> bool:
        with self._lock:
            now = self._clock()
            if (self._ticket is None or ticket != self._ticket or self._delivered
                    or self._closed or self._blocked):
                return False
            if not _finite(now) or now >= ticket.expires_at:
                self._cancel()
                return False
            # Consume before invoking the sink, including on adapter failure.
            self._delivered = True
            try:
                self._sink.speak(render_description(value))
            except Exception:
                self._cancel()
                return False
            return True

    def tick(self) -> None:
        with self._lock:
            now = self._clock()
            if self._ticket and (not _finite(now) or now >= self._ticket.expires_at):
                self._cancel()

    def cancel(self) -> None:
        with self._lock:
            self._cancel()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._cancel()
