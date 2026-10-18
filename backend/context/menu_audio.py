"""CS-040 closed menu speech; no traffic inference, provider text or speech queue."""
import math
import time

LABELS = {
    'pedestrian_signal': 'Pedestrian walk-and-hand signal',
    'flashing_beacon': 'Flashing yellow pedestrian beacon',
    'unsignalized_street': 'Street without a crossing signal',
}
ENTRY = ('Crossing observations. This does not tell you when to cross. '
         'Select crossing type. Press to cycle; hold to select.')
FIXED = {'entry': ENTRY, 'choose': 'Press to select a crossing type.',
         'cancel': 'Crossing assistance stopped.',
         'unavailable': 'Crossing observations unavailable.'}
ALL_PHRASES = frozenset([*FIXED.values(), *LABELS.values(),
    *('Observation mode selected: '+label+'. This does not tell you when to cross.' for label in LABELS.values())])


def phrase(kind, scenario=None):
    if kind in ('selection', 'confirmation'):
        if scenario not in LABELS:
            return None
        label = LABELS[scenario]
        return label if kind == 'selection' else 'Observation mode selected: '+label+'. This does not tell you when to cross.'
    return FIXED.get(kind) if scenario is None or scenario in LABELS else None


class FixedMenuAudio:
    """Explicit trusted output availability, priority and epoch required.

    Engine process health alone is not Bluetooth route availability. Caller must
    report loss immediately. Recovery permits only a newer explicit entry event.
    One owned sink, no replay queue. tick() independently enforces speech expiry.
    """
    def __init__(self, sink, *, clock=time.monotonic):
        self.sink, self.clock = sink, clock
        self._last = None
        self._epoch = None
        self._seen = -1
        self._valid = self._ready = False
        self._fault = self._closed = False
        self._deadline = None

    def _stop(self):
        self._valid = False; self._deadline = None
        try:
            self.sink.stop()
        except Exception:
            self._fault = True

    def _now(self):
        try:
            now = self.clock()
            if type(now) not in (int, float) or not math.isfinite(now) or now < 0 or (self._last is not None and now < self._last):
                raise ValueError()
            self._last = now
            return now
        except Exception:
            self._fault = True; self._stop(); return None

    def update(self, *, audio_ready, priority_clear, epoch):
        now = self._now()
        valid_epoch = type(epoch) is tuple and len(epoch) == 4 and all(type(x) is str and 1 <= len(x) <= 64 for x in epoch)
        try:
            healthy = self.sink.healthy() is True
        except Exception:
            healthy = False
        if not healthy:
            self._fault = True
        ready = bool(now is not None and valid_epoch and audio_ready is True and priority_clear is True
                     and healthy and not (self._fault or self._closed))
        if not ready or epoch != self._epoch:
            self._stop()
        self._epoch = epoch if valid_epoch else None
        self._ready = ready and not self._fault
        self.tick()
        return self._ready

    def speak(self, kind, *, generation, epoch, scenario=None):
        now = self._now()
        text = phrase(kind, scenario)
        if (now is None or not self._ready or self._fault or self._closed or epoch != self._epoch
                or type(generation) is not int or not 0 <= generation <= 2**53-1 or text is None):
            self._stop(); return False
        if kind == 'entry':
            if generation <= self._seen:
                return False
            self._seen = generation; self._valid = True
        if generation != self._seen or not self._valid:
            return False
        try:
            self.sink.stop()  # Preempt old optional audio before replacement.
            self.sink.speak(text)
            self._deadline = now+15
            if kind in ('cancel', 'unavailable'):
                self._valid = False
            return True
        except Exception:
            self._fault = True; self._stop(); return False

    def tick(self):
        now = self._now()
        if now is not None and self._deadline is not None and now >= self._deadline:
            self._stop()

    def close(self):
        self._closed = True; self._stop()
