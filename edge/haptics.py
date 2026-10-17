"""CS-023 capped local pulse scheduler. Ships simulated outputs only.

No network command, perception decision, GPIO adapter or crossing permission.
Software deadlines cannot force a frozen process or a failed driver low.
"""
import argparse
from collections import deque
from dataclasses import dataclass, field
import json
import math
import threading
import time

CHANNELS = ('left', 'right')
WINDOW_MS = 10_000


def clock_ms():
    # Pi policy uses BOOTTIME so suspend cannot silently renew eligibility.
    if hasattr(time, 'CLOCK_BOOTTIME'):
        return time.clock_gettime_ns(time.CLOCK_BOOTTIME) / 1_000_000
    return time.monotonic() * 1000  # Laptop simulation fallback only.


def number(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('Expected a finite nonnegative number')
    return value


@dataclass(frozen=True)
class Limits:
    max_pulse_ms: float = 500
    min_off_ms: float = 200
    max_on_ms: float = 2000  # Simulation starting point: <=20% in any 10s window.
    tick_ms: float = 10

    def __post_init__(self):
        for value in (self.max_pulse_ms, self.min_off_ms, self.max_on_ms, self.tick_ms):
            number(value)
        if not (0 < self.max_pulse_ms <= 500 and self.min_off_ms >= 200
                and 0 < self.max_on_ms <= 2000 and 1 <= self.tick_ms <= 10):
            raise ValueError('Limits may tighten, never exceed the simulation envelope')


class SimulatedOutput:
    """Bounded trace of requested states; never imports a GPIO library."""
    def __init__(self):
        self.lock = threading.Lock()
        self.states = dict.fromkeys(CHANNELS, False)
        self.events = deque(maxlen=256)

    def write(self, channel, enabled):
        if channel not in CHANNELS or type(enabled) is not bool:
            raise ValueError('Unknown channel/state')
        with self.lock:
            self.states[channel] = enabled
            self.events.append((channel, enabled))


@dataclass
class Channel:
    on: bool | None = False  # None means the output write failed; state unknown.
    started_ms: float | None = None
    deadline_ms: float | None = None
    off_since_ms: float = 0
    history: deque = field(default_factory=deque)


class SchedulerFault(RuntimeError):
    pass


class HapticScheduler:
    """No pulse queue: a busy/ineligible request is rejected, never deferred.

    The trusted local policy supplies readiness and an ORIGINAL eligibility
    deadline on the same clock. It must cancel/disarm when evidence is lost;
    this layer cannot establish source freshness from a motor request alone.
    Call tick manually in deterministic tests or start the independent worker.
    Output.write must return promptly; no hardware adapter is provided here.
    """
    def __init__(self, output=None, *, clock=clock_ms, limits=Limits()):
        if not isinstance(limits, Limits):
            raise ValueError('Use validated immutable limits')
        self.output = output if output is not None else SimulatedOutput()
        self.clock = clock
        self.limits = limits
        self.lock = threading.RLock()
        self.channels = {name: Channel() for name in CHANNELS}
        self.ready = False
        self.closed = False
        self.fault = None
        self.last_now = None
        self.accepted = self.rejected = 0
        self.last_rejection = None
        self.guard = None
        self._stop = threading.Event()
        self._thread = None
        # Request BOTH outputs low, even when one write fails. No clock needed.
        if not self._force_off(None):
            self.fault = 'Output initialization failed'
            raise SchedulerFault(self.fault)
        now = self._now()
        if now is None:
            raise SchedulerFault(self.fault)
        for state in self.channels.values():
            state.off_since_ms = now

    def _off(self, name, now):
        state = self.channels[name]
        if state.started_ms is not None and now is not None:
            # Charge actual observed elapsed time, including a late scheduler tick.
            state.history.append((state.started_ms, max(state.started_ms, now)))
            state.off_since_ms = now
            if now - state.started_ms > self.limits.max_pulse_ms:
                self.fault = self.fault or 'Pulse overrun; new scheduler required'
                self.ready = False
                self._stop.set()
        state.started_ms = state.deadline_ms = None
        if now is not None and self._used(state, now) > self.limits.max_on_ms:
            self.fault = self.fault or 'Rolling duty overrun; new scheduler required'
            self.ready = False
            self._stop.set()
        try:
            self.output.write(name, False)
            state.on = False
            return True
        except Exception:
            state.on = None
            return False

    def _force_off(self, now):
        success = True
        for name in CHANNELS:
            success = self._off(name, now) and success
        return success

    def _fail(self, reason, now=None):
        self.ready = False
        self.fault = self.fault or reason
        self._stop.set()
        self._force_off(now)

    def _now(self):
        try:
            now = number(self.clock())
            if self.last_now is not None and now < self.last_now:
                raise ValueError('Clock reversed')
        except Exception:
            self._fail('Clock unavailable; new scheduler required', self.last_now)
            return None
        self.last_now = now
        return now

    def _used(self, state, now):
        floor = now - WINDOW_MS
        while state.history and state.history[0][1] <= floor:
            state.history.popleft()
        used = sum(end - max(start, floor) for start, end in state.history)
        if state.started_ms is not None:
            used += now - max(state.started_ms, floor)
        return used

    def _guard_deadline(self):
        if self.guard is None:
            return None
        try:
            deadline = self.guard()
            number(deadline)
            return deadline
        except Exception:
            return None

    def set_guard(self, guard):
        """Attach one trusted same-clock watchdog before arming; no network API."""
        with self.lock:
            if self.guard is not None or self.ready or self.accepted or self.closed or not callable(guard):
                raise ValueError('Attach one local guard before any pulse')
            self.guard = guard

    def trip(self, reason='Local watchdog unavailable'):
        with self.lock:
            self._fail('Local watchdog unavailable; new epoch required', self._now())

    def _tick(self, now):
        if self.guard is not None:
            deadline = self._guard_deadline()
            if deadline is None or now >= deadline:
                self._fail('Policy lease unavailable; new epoch required', now)
                return
        for name, state in self.channels.items():
            self._used(state, now)
            if state.deadline_ms is not None and now >= state.deadline_ms:
                overrun = now - state.started_ms > self.limits.max_pulse_ms
                if not self._off(name, now):
                    self._fail('Output unavailable; new scheduler required', now)
                    return
                if overrun:
                    self._fail('Pulse overrun; new scheduler required', now)
                    return
                if self.fault:
                    self._fail(self.fault, now)
                    return

    @staticmethod
    def _names(channels):
        names = (channels,) if isinstance(channels, str) else channels
        if not isinstance(names, (tuple, list, frozenset)) or not 1 <= len(names) <= 2:
            raise ValueError('Choose one or two distinct local channels')
        if any(name not in CHANNELS for name in names) or len(set(names)) != len(names):
            raise ValueError('Unknown or duplicate local channels')
        return tuple(name for name in CHANNELS if name in names)

    def set_ready(self, ready):
        if type(ready) is not bool:
            raise ValueError('Explicit local readiness required')
        with self.lock:
            now = self._now()
            if now is None or self.fault or self.closed:
                return False
            self._tick(now)
            if self.fault:
                return False
            self.ready = ready
            if not ready and not self._force_off(now):
                self._fail('Output unavailable; new scheduler required', now)
            return self.fault is None

    def pulse(self, channels, duration_ms=150, *, valid_until_ms):
        names = self._names(channels)
        number(duration_ms)
        number(valid_until_ms)
        if not 0 < duration_ms <= self.limits.max_pulse_ms:
            raise ValueError('Pulse duration exceeds cap')
        with self.lock:
            now = self._now()
            if now is not None:
                self._tick(now)
            reason = None
            deadline = min(now + duration_ms, valid_until_ms) if now is not None else 0
            if self.guard is not None:
                lease = self._guard_deadline()
                if lease is None:
                    self._fail('Policy lease unavailable; new epoch required', now)
                    deadline = 0
                else:
                    deadline = min(deadline,lease)
            if self.closed or self.fault or not self.ready:
                reason = 'unavailable'
            elif deadline <= now:
                reason = 'expired'
            else:
                for name in names:
                    state = self.channels[name]
                    if state.on is not False:
                        reason = 'busy'
                    elif now - state.off_since_ms < self.limits.min_off_ms:
                        reason = 'minimum_off_time'
                    elif self._used(state, now) + deadline - now > self.limits.max_on_ms:
                        reason = 'duty_cap'
                    if reason:
                        break
            if reason:
                self.rejected += 1
                self.last_rejection = reason
                return False
            # Atomic admission: start neither channel unless both pass all caps.
            for name in names:
                state = self.channels[name]
                state.started_ms, state.deadline_ms = now, deadline
                try:
                    self.output.write(name, True)
                    state.on = True
                except Exception:
                    self._fail('Output unavailable; new scheduler required', now)
                    self.rejected += 1
                    self.last_rejection = 'unavailable'
                    return False
            self.accepted += 1
            self.last_rejection = None
            return True

    def cancel(self, channels=CHANNELS):
        names = self._names(channels)
        with self.lock:
            now = self._now()
            if now is None:
                return False
            success = True
            for name in names:
                success = self._off(name, now) and success
            if not success:
                self._fail('Output unavailable; new scheduler required', now)
            elif self.fault:
                self._force_off(now)
            return success

    def tick(self):
        with self.lock:
            now = self._now()
            if now is not None:
                self._tick(now)
            return self._snapshot()

    def _snapshot(self):
        return {'mode': 'simulation', 'ready': self.ready, 'closed': self.closed,
                'fault': self.fault, 'outputs': {name: state.on for name, state in self.channels.items()},
                'accepted': self.accepted, 'rejected': self.rejected,
                'last_rejection': self.last_rejection}

    def snapshot(self):
        # Read also enforces expiry; callers must not cache this as eligibility.
        return self.tick()

    def start(self):
        with self.lock:
            if self.closed or self.fault or self._thread is not None:
                raise SchedulerFault('Start a healthy scheduler once')
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def _run(self):
        try:
            while not self._stop.wait(self.limits.tick_ms / 1000):
                self.tick()
        except Exception:
            with self.lock:
                self._fail('Scheduler unavailable; new scheduler required', self.last_now)

    def close(self):
        self._stop.set()
        with self.lock:
            self.ready = False
            self.closed = True
            now = self._now()
            success = self._force_off(now)
            if not success:
                self.fault = self.fault or 'Output cleanup failed; state unknown'
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)
        return success

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulate', action='store_true', required=True)
    parser.parse_args()
    output = SimulatedOutput()
    with HapticScheduler(output) as scheduler:
        scheduler.set_ready(True)
        time.sleep(.21)  # Initial off-time is mandatory, too.
        for name in CHANNELS:
            scheduler.pulse(name, valid_until_ms=clock_ms() + 150)
            time.sleep(.2)
    print(json.dumps(dict(scheduler.snapshot(), gpio_used=False,
                          limits='Simulation only; no electrical or physical timing validation.')))


if __name__ == '__main__':
    main()
