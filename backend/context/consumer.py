"""Local Pi context button/client/narration composition, never a server speaker.

Input and trusted priority adapters must return promptly. A concrete nonblocking
speech sink is still required; importing this module never activates audio.
"""
import threading

from edge.buttons import ContextButton
from edge.context_client import ContextError
from edge.haptics import clock_ms

from .narration import NarrationController


class ContextNarration:
    """One local worker owns request/input/audio transitions on one Pi clock.

    priority() returns (ready, hazard) from independent trusted policy.
    consent() returns explicit current scene-sharing consent, not model output.
    frame_supplier() supplies the originating uploader's original Frame.
    This is an adapter API, not installed in uploader/phone or a GPIO driver.
    """
    def __init__(self, frame_supplier, client, sink, *, priority, consent, clock=clock_ms):
        if not callable(getattr(client, 'start', None)):
            raise ValueError('A local context client is required')
        self._clock = clock
        self._priority, self._consent = priority, consent
        self._client = client
        self._sink = sink
        self._lock = threading.RLock()
        self._closed = False
        self._ticket = self._request_id = None
        self._delivered = False
        self._pressed = False
        self._stop = threading.Event()
        self._thread = None
        self._narration = NarrationController(sink, clock=lambda: clock()/1000)
        self._button = ContextButton(frame_supplier, self._request, clock=clock)

    def _cancel_audio(self):
        self._narration.cancel()
        self._ticket = self._request_id = None
        self._delivered = False

    def _state(self):
        try:
            ready, hazard = self._priority()
            consent = self._consent()
            health = getattr(self._sink, 'healthy', None)
            if callable(health) and health() is not True:
                ready = False
        except Exception:
            ready, hazard, consent = False, True, False
        enabled = not self._closed and ready is True and hazard is False and consent is True
        # Audio stops before possibly waiting for network-child termination.
        self._narration.set_priority(hazard=hazard, unavailable=not enabled)
        if not enabled:
            self._cancel_audio()
        self._button.set_state(ready=enabled, consent=consent, hazard=hazard)
        return enabled

    def _request(self, request_id, frame):
        self._cancel_audio()
        if not self._state():
            raise ContextError()
        self._ticket = self._narration.begin_capture(
            capture_monotonic_s=frame.metadata['capture_monotonic_ms']/1000, consent=True)
        if self._ticket is None:
            raise ContextError()
        self._request_id = request_id
        try:
            return self._client.start(request_id, frame)
        except Exception:
            self._cancel_audio()
            raise

    def sample(self, pressed):
        with self._lock:
            if self._closed:
                return False
            self._state()
            # A new press interrupts already playing optional narration. It
            # cannot queue another request or bypass the button cooldown.
            if (pressed is True and not self._pressed and self._delivered) or type(pressed) is not bool:
                self._cancel_audio()
                self._button.cancel()
            self._pressed = pressed is True
            result = self._button.sample(pressed)
            self._tick()
            return result

    def request(self):
        """Submit a completed local gesture to the sole existing request slot."""
        with self._lock:
            if self._closed or not self._state():
                return False
            admitted = self._button.request()
            self._tick()
            return admitted

    def _tick(self):
        self._state()
        self._narration.tick()
        value = self._button.take_result()
        if value is not None and self._ticket is not None and not self._delivered:
            if self._state() and value['request_id'] == self._request_id:
                self._delivered = self._narration.deliver(self._ticket, value['description'])
        if not self._delivered and not self._button.snapshot()['requesting']:
            self._cancel_audio()

    def tick(self):
        with self._lock:
            if not self._closed:
                self._tick()

    def cancel(self):
        with self._lock:
            self._cancel_audio()
            self._button.cancel()

    def start(self):
        with self._lock:
            if self._closed or self._thread is not None:
                raise ValueError('Start context narration once')
            def run():
                try:
                    while not self._stop.wait(.01):
                        self.tick()
                except Exception:
                    self.close()
            self._thread = threading.Thread(target=run, daemon=True)
            self._thread.start()
        return self

    def snapshot(self):
        """Sanitized software diagnostics only; never evidence of audible output."""
        with self._lock:
            return {'closed': self._closed, 'result_delivered': self._delivered,
                    'audio_delivery_verified': False, 'button': self._button.snapshot()}

    def close(self):
        with self._lock:
            self._closed = True
            self._stop.set()
            self._cancel_audio()
            self._narration.close()
            self._button.close()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)
