"""CS-024 local depth policy. Simulated outputs only; no crossing decision."""
from dataclasses import dataclass
import json
import re
import threading

from backend.freshness import CaptureAgeGate
from .haptics import HapticScheduler, SimulatedOutput, clock_ms, number


@dataclass(frozen=True)
class PhoneBinding:
    """Trusted operator binding, NOT discovered from incoming packets.

    A numeric drift budget is an operator assertion backed by measurement.
    None leaves remote ages unknown; use zero only in synthetic same-clock tests.
    No phone/operator token belongs in this file or on the Pi.
    """
    source_id: str
    boot_id: str
    relative_drift_ppm: float | None = None

    def __post_init__(self):
        for value in (self.source_id, self.boot_id):
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
                raise ValueError('Invalid trusted phone identity')
        if self.relative_drift_ppm is not None:
            number(self.relative_drift_ppm)

    @classmethod
    def load(cls, path):
        if path.stat().st_size > 1024:
            raise ValueError('Oversized phone binding')
        def unique(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise ValueError('Duplicate phone binding field')
                value[key] = item
            return value
        data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)
        if not isinstance(data, dict) or set(data) != {'source_id','boot_id','relative_drift_ppm'}:
            raise ValueError('Use the closed trusted phone binding; no tokens')
        return cls(**data)


class LocalPolicy:
    """Poll a trusted final-consumer gate on the SAME clock as the scheduler.

    One new sequence can request one pulse, never replay on a heartbeat/tick.
    Two consecutive covered frames recover each sector; gaps/unknown reset it.
    Entry <=1.2m, exit >=1.5m, coverage >=0.5 are simulation tuning only.
    Side pulses mean an obstacle on that side, never a direction to move.
    Center takes precedence and requests both channels atomically.
    """
    def __init__(self, gate, phone_id, scheduler, *, clock=clock_ms):
        if not isinstance(gate, CaptureAgeGate) or not isinstance(scheduler, HapticScheduler):
            raise ValueError('Use the accepted gate and capped scheduler')
        if not isinstance(scheduler.output, SimulatedOutput):
            raise ValueError('This checkpoint supports simulated outputs only')
        # Clock identity prevents mixing two monotonic epochs or units.
        if gate.clock_ms is not clock or scheduler.clock is not clock:
            raise ValueError('Gate, policy and scheduler must share one clock callable')
        if phone_id is not None and (phone_id == gate.receiver_id or phone_id not in gate.sequence.active):
            raise ValueError('Explicitly enroll a distinct phone before policy construction')
        self.gate, self.phone_id, self.scheduler, self.clock = gate, phone_id, scheduler, clock
        self.lock = threading.RLock()
        self.armed = False
        self.closed = False
        self.fault = None
        self.last_now = None
        self.last_seq = None
        self.last_boot = None
        self.last_deadline = None
        self.counts = dict.fromkeys(('left','center','right'),0)
        self.hazards = dict.fromkeys(self.counts,'unknown')
        self.health = {'depth':'unconfigured' if phone_id is None else 'unavailable','vision':'unavailable'}
        self.active = ()
        self.requests = 0
        self._stop = threading.Event()
        self._thread = None

    def _reset(self):
        self.counts = dict.fromkeys(self.counts,0)
        self.hazards = dict.fromkeys(self.hazards,'unknown')
        self.last_seq = self.last_boot = self.last_deadline = None
        self.active = ()
        self.scheduler.set_ready(False)

    def arm(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Explicit simulation arming required')
        with self.lock:
            self.armed = enabled and not self.closed and self.fault is None
            self._reset()

    def tick(self):
        with self.lock:
            try:
                now = number(self.clock())
                if self.last_now is not None and now < self.last_now:
                    raise ValueError('Policy clock reversed')
                self.last_now = now
                motor = self.scheduler.tick()
                if motor['fault'] or motor['closed']:
                    raise ValueError('Scheduler unavailable')
                self.gate.expire()
                vision = self.gate.current(self.gate.receiver_id,'vision_observation')
                self.health['vision'] = 'fresh' if vision else 'unavailable'
                observation = self.gate.current(self.phone_id,'depth_observation') if self.phone_id else None
                healthy = self.gate.healthy(self.phone_id) if self.phone_id else False
                self.health['depth'] = 'fresh' if observation else 'no-fresh-depth' if healthy else 'unavailable' if self.phone_id else 'unconfigured'
                if self.closed or self.fault or not self.armed or observation is None:
                    self._reset()
                    return self.snapshot()
                message = observation.message
                if self.last_deadline is not None and now > self.last_deadline:
                    self._reset()  # A new frame after a missed expiry must recover.
                if self.last_boot is not None and message['boot_id'] != self.last_boot:
                    self._reset()
                if observation.deadline_ms <= now:
                    self._reset()
                    return self.snapshot()
                fresh_sequence = message['seq'] != self.last_seq
                if fresh_sequence:
                    self.last_seq, self.last_boot = message['seq'], message['boot_id']
                    self.last_deadline = observation.deadline_ms
                    for sector, value in message['sectors'].items():
                        distance = value['distance_m']
                        if distance is None or distance <= 0 or value['valid_fraction'] < .5:
                            self.counts[sector] = 0
                            self.hazards[sector] = 'unknown'
                            continue
                        self.counts[sector] = min(2,self.counts[sector]+1)
                        if self.counts[sector] < 2:
                            self.hazards[sector] = 'unknown'
                        elif distance <= 1.2:
                            self.hazards[sector] = 'nearby'
                        elif distance >= 1.5:
                            self.hazards[sector] = 'not-nearby-observed'
                        # Mid-band preserves prior classification; unknown stays unknown.
                wanted = ('left','right') if self.hazards['center']=='nearby' else tuple(
                    name for name in ('left','right') if self.hazards[name]=='nearby')
                # Every tick removes pulses whose supporting evidence has changed.
                if self.active and self.active != wanted:
                    running = self.scheduler.tick()['outputs']
                    remaining = tuple(name for name in self.active if running[name] is not False)
                    if remaining:
                        self.scheduler.cancel(remaining)
                    self.active = ()
                if not wanted:
                    self.scheduler.set_ready(False)
                else:
                    self.scheduler.set_ready(True)
                    if fresh_sequence and self.scheduler.pulse(wanted,100,valid_until_ms=observation.deadline_ms):
                        self.active = wanted
                        self.requests += 1
                state = self.scheduler.tick()
                if state['fault']:
                    raise ValueError('Scheduler fault')
            except Exception:
                self.fault = 'Policy unavailable; restart and reenroll'
                self.armed = False
                self.health = dict.fromkeys(self.health,'unavailable')
                self._reset()
                self._stop.set()
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            return dict(mode=self.gate.mode, output_mode='simulation', armed=self.armed,
                health=dict(self.health), hazards=dict(self.hazards), fault=self.fault,
                requests=self.requests, guidance='unavailable',
                status='Obstacle evidence only; unknown is not clear. No crossing permission.')

    def start(self):
        with self.lock:
            if self.closed or self._thread is not None:
                raise ValueError('Start one policy worker')
            self._thread = threading.Thread(target=self._run,daemon=True)
            self._thread.start()
        return self

    def _run(self):
        while not self._stop.wait(.02):
            self.tick()  # Never performs camera, network, image or GPIO I/O.

    def close(self):
        self._stop.set()
        with self.lock:
            self.closed = True
            self.health = dict.fromkeys(self.health,'unavailable')
            self.armed = False
            self._reset()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)
