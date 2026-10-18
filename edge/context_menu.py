"""CS-027 deterministic local gestures; no sensors, audio, network or motor output.

Implements the merged CROSSING_ASSISTANCE brief. Callers supply independently
verified consent/source/audio state; supported scenarios default to NONE.
"""
from dataclasses import dataclass
import math

SCENARIOS = ('pedestrian_signal', 'flashing_beacon', 'unsignalized_street')


@dataclass(frozen=True)
class MenuEvent:
    kind: str
    generation: int
    epoch: tuple
    scenario: str | None = None
    reason: str | None = None


class CrossingMenu:
    def __init__(self, *, supported=()):
        if not set(supported) <= set(SCENARIOS):
            raise ValueError('Unknown scenario capability')
        self.supported = frozenset(supported)
        self.state, self.selected = 'idle', None
        self.generation = 0
        self._epoch = None
        self._last_now = None
        self._opened = self._interaction = None
        self._reset_input()

    def _reset_input(self):
        self._raw = self._stable = None
        self._changed = self._down = None
        self._released = self._consumed = False

    def _event(self, kind, *, reason=None):
        return MenuEvent(kind, self.generation, self._epoch or (),
                         SCENARIOS[self.selected] if self.selected is not None else None, reason)

    def cancel(self, reason='manual'):
        event = self._event('cancel', reason=reason)
        self.generation += 1
        if self.state not in ('closed', 'failed'):
            self.state = 'idle'
        self.selected = None
        self._opened = self._interaction = None
        self._reset_input()
        return (event,)

    def close(self):
        events = self.cancel('shutdown')
        self.state = 'closed'
        return events

    def sample(self, pressed, *, now_ms, consent, ready, audio_ready, epoch):
        if self.state in ('closed', 'failed'):
            return ()
        try:
            valid_time = type(now_ms) in (int, float) and math.isfinite(now_ms) and now_ms >= 0
        except (OverflowError, ValueError):
            valid_time = False
        if not valid_time or (self._last_now is not None and now_ms < self._last_now):
            events = self.cancel('clock'); self.state = 'failed'; return events
        self._last_now = now_ms
        if (type(pressed) is not bool or type(epoch) is not tuple or len(epoch) != 4
                or any(type(x) is not str or not 1 <= len(x) <= 64 for x in epoch)):
            events = self.cancel('invalid'); self.state = 'failed'; return events
        events = []
        if self._epoch is not None and epoch != self._epoch:
            events.extend(self.cancel('epoch'))
        self._epoch = epoch
        if consent is not True or ready is not True:
            if self.state != 'unavailable':
                events.extend(self.cancel('consent' if consent is not True else 'source'))
                self.state = 'unavailable'
            return tuple(events)
        if self.state not in ('idle', 'unavailable') and audio_ready is not True:
            events.extend(self.cancel('audio')); self.state = 'unavailable'; return tuple(events)
        if self.state == 'unavailable':
            self.state = 'idle'; self._reset_input()
        if self._opened is not None and (now_ms-self._opened >= 30000 or now_ms-self._interaction >= 15000):
            events.extend(self.cancel('timeout')); return tuple(events)
        if self._stable is True and self._down is not None and not self._consumed:
            held = now_ms-self._down
            if self.state == 'idle' and held >= 3000:
                self._consumed = True
                self.generation += 1
                if audio_ready is not True:
                    events.append(self._event('unavailable', reason='audio'))
                    self.state = 'unavailable'; self.selected = None; self._reset_input()
                else:
                    self.state = 'menu_entry'; self._opened = self._interaction = now_ms
                    events.append(self._event('entry'))
            elif self.state == 'menu' and held >= 1000:
                self._consumed = True
                if self.selected is None:
                    events.append(self._event('choose'))
                elif SCENARIOS[self.selected] not in self.supported:
                    events.append(self._event('unavailable', reason='unsupported'))
                    self.cancel('unsupported')
                else:
                    self.state = 'confirm_release'; events.append(self._event('confirmation'))
        if self._changed is None and events:
            return tuple(events)
        if pressed != self._raw:
            self._raw, self._changed = pressed, now_ms
        if now_ms-self._changed >= 30 and self._stable != self._raw:
            self._stable = self._raw
            if self._opened is not None:
                self._interaction = now_ms
            if pressed:
                if self.state == 'active':
                    events.extend(self.cancel()); return tuple(events)
                if self._released:
                    self._released = False; self._down = now_ms; self._consumed = False
            else:
                if self.state == 'menu_entry':
                    self.state = 'menu'
                elif self.state == 'confirm_release':
                    self.state = 'active'; self._opened = self._interaction = None
                    events.append(self._event('activate'))
                elif self._down is not None and not self._consumed:
                    if self.state == 'idle':
                        self.generation += 1; events.append(self._event('context'))
                    elif self.state == 'menu':
                        self.selected = 0 if self.selected is None else (self.selected+1) % len(SCENARIOS)
                        events.append(self._event('selection'))
                self._released = True; self._down = None; self._consumed = False
        return tuple(events)

    def snapshot(self):
        return dict(state=self.state, selected=SCENARIOS[self.selected] if self.selected is not None else None,
                    generation=self.generation, live_observations_implemented=False)
