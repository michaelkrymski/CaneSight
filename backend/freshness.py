"""CS-030 consumer-side capture-age policy for the accepted v1 protocol.

Run on the final consumer's clock. A relay must not use its clock as the Pi's.
Caller supplies authenticated messages and trusted enrollment, never wire-driven
reenrollment. No return value is a movement/crossing permission.
"""
import copy
import math
import re
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from .app import protocol


class Unavailable(ValueError):
    """Data cannot establish bounded, usable evidence."""


@dataclass(frozen=True)
class Observation:
    message: dict
    received_ms: float
    deadline_ms: float
    bound: object = None


class CaptureAgeGate:
    """Bounded, locked state for one authenticated session/receiver epoch.

    Default drift is unknown. A device-verified joint drift budget must be
    explicitly supplied before remote clock calibration can establish freshness.
    current()/expire() recompute age using each observation's ORIGINAL bound;
    resync and heartbeats never renew old observations.
    """
    def __init__(self, session_id, mode, receiver_id, receiver_boot_id, *,
                 relative_drift_ppm=None, clock_ms=lambda: time.monotonic() * 1000):
        for identity in (session_id, receiver_id, receiver_boot_id):
            if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', identity):
                raise ValueError('Invalid session/receiver identity')
        if mode not in ('live', 'replay'):
            raise ValueError('Explicit live/replay mode required')
        if relative_drift_ppm is not None:
            protocol.finite_nonnegative(relative_drift_ppm)
        self.session_id, self.mode = session_id, mode
        self.receiver_id, self.receiver_boot_id = receiver_id, receiver_boot_id
        self.drift = relative_drift_ppm
        self.clock_ms = clock_ms
        self.lock = threading.RLock()
        self.sequence = protocol.SequenceGate(session_id, mode)
        self.bounds = {}
        self.probes = {}
        self.last_probe_ms = {}
        self.observations = {}
        self.health = {}
        self.capture_floor = {}
        self.frames = OrderedDict()
        self.seen_frame_ids = set()
        self.local_ready = False
        self.last_now = None
        self.failed_clock = False

    @classmethod
    def for_pair(cls, pair, **kwargs):
        """Construct a Pi consumer from the authenticated operator response."""
        if type(pair.get('schema_version')) is not int or pair['schema_version'] != 1:
            raise ValueError('Unsupported paired-session response version')
        gate = cls(pair['session_id'], pair['mode'], pair['pi']['source_id'],
                   pair['pi']['boot_id'], **kwargs)
        gate.enroll(pair['phone']['source_id'], pair['phone']['boot_id'],
                    {'depth_observation', 'heartbeat'})
        gate.enroll(pair['pi']['source_id'], pair['pi']['boot_id'],
                    {'frame_metadata', 'vision_observation'})
        return gate

    def _now(self):
        now = self.clock_ms()
        try:
            protocol.finite_nonnegative(now)
            if self.last_now is not None and now < self.last_now:
                raise ValueError('Receiver clock reversed')
        except (ValueError, OverflowError):
            self.failed_clock = True
        if self.failed_clock:
            self.bounds.clear()
            self.probes.clear()
            self.observations.clear()
            self.health.clear()
            self.frames.clear()
            self.local_ready = False
            raise Unavailable('Receiver clock invalid; create a new receiver/session epoch')
        self.last_now = now
        return now

    def _purge_source(self, source_id, now):
        self.bounds.pop(source_id, None)
        self.probes.pop(source_id, None)
        self.health.pop(source_id, None)
        for key in list(self.observations):
            if key[0] == source_id:
                self.observations.pop(key)
        self.capture_floor[source_id] = now
        if source_id == self.receiver_id:
            self.frames.clear()

    def enroll(self, source_id, boot_id, allowed_types):
        """Trusted control-plane operation. Ordinary packets cannot call this."""
        with self.lock:
            now = self._now()
            if source_id == self.receiver_id and boot_id != self.receiver_boot_id:
                raise ValueError('Receiver restart requires a new consumer/session epoch')
            old = self.sequence.active.get(source_id)
            self.sequence.enroll(source_id, boot_id, allowed_types)
            if old != self.sequence.active[source_id]:
                self._purge_source(source_id, now)
                self.last_probe_ms.pop(source_id, None)

    def interrupt(self):
        """Transport loss/suspension clears evidence, NEVER sequence history."""
        with self.lock:
            now = self._now()
            for source in self.sequence.active:
                self._purge_source(source, now)

    def set_local_ready(self, ready):
        """Trusted originating-camera health, not a backend heartbeat verdict."""
        if not isinstance(ready, bool):
            raise ValueError('Explicit local readiness required')
        with self.lock:
            now = self._now()
            if not ready or not self.local_ready:
                self._purge_source(self.receiver_id, now)
            self.local_ready = ready

    def start_probe(self, source_id):
        with self.lock:
            now = self._now()
            binding = self.sequence.active.get(source_id)
            if binding is None or source_id == self.receiver_id:
                raise Unavailable('Unknown/nonremote source')
            if now - self.last_probe_ms.get(source_id, -math.inf) < 1000:
                raise Unavailable('Clock probe rate limit')
            pending = self.probes.get(source_id)
            if pending and now <= pending['t1_ms'] + 1000:
                raise Unavailable('Clock probe already pending')
            probe = dict(schema_version=1, type='clock_probe', session_id=self.session_id,
                         mode=self.mode, nonce=secrets.token_hex(16), receiver_id=self.receiver_id,
                         receiver_boot_id=self.receiver_boot_id, source_id=source_id,
                         source_boot_id=binding[0], t1_ms=now)
            protocol.validate_message(probe)
            self.probes[source_id] = copy.deepcopy(probe)
            self.last_probe_ms[source_id] = now
            return probe

    def finish_probe(self, reply):
        with self.lock:
            now = self._now()
            protocol.validate_message(reply)
            source = reply['source_id']
            pending = self.probes.get(source)
            if pending is None or reply['nonce'] != pending['nonce']:
                raise Unavailable('Unmatched or consumed clock nonce')
            # Consume exactly once, including malformed/late matching replies.
            self.probes.pop(source)
            self.bounds.pop(source, None)
            if self.drift is None:
                self._purge_source(source, now)
                raise Unavailable('Joint device clock drift is not verified/configured')
            try:
                bound = protocol.verify_clock_reply(pending, reply, now, self.drift)
            except (ValueError, OverflowError) as error:
                self._purge_source(source, now)
                raise Unavailable('Invalid or late clock exchange') from error
            # Reject an exchange too uncertain for depth even at calibration.
            if (bound.upper_offset_ms - bound.lower_offset_ms) / 2 > 100:
                self._purge_source(source, now)
                raise Unavailable('Clock uncertainty exceeds depth/health budget')
            self.bounds[source] = bound
            return bound

    def _age(self, observation, now):
        message = observation.message
        if observation.bound is not None:
            return observation.bound.age_interval(message, now, self.receiver_boot_id)
        age = now - message['capture_monotonic_ms']
        return age, age

    def _valid(self, observation, now):
        try:
            return (now <= observation.deadline_ms
                    and protocol.within_budget(observation.message['type'], self._age(observation, now)))
        except (ValueError, OverflowError):
            return False

    def _prune(self, now):
        expired = []
        for source, observation in list(self.health.items()):
            if not self._valid(observation, now):
                self.health.pop(source)
                self.capture_floor[source] = now
                for key in list(self.observations):
                    if key[0] == source:
                        self.observations.pop(key)
                        expired.append(key)
        for key, observation in list(self.observations.items()):
            if not self._valid(observation, now):
                self.observations.pop(key)
                expired.append(key)
        for frame_id, frame in list(self.frames.items()):
            if now - frame['capture_monotonic_ms'] > 1500:
                self.frames.pop(frame_id)
        return expired

    def expire(self):
        """Call on each independent policy tick; no network callback needed."""
        with self.lock:
            return self._prune(self._now())

    def healthy(self, source_id):
        with self.lock:
            now = self._now()
            self._prune(now)
            if source_id == self.receiver_id:
                return self.local_ready
            observation = self.health.get(source_id)
            return observation is not None and observation.message['state'] == 'ready'

    def record_frame(self, metadata):
        """Originating Pi records actual local capture BEFORE requesting work."""
        with self.lock:
            now = self._now()
            self._prune(now)
            protocol.validate_message(metadata)
            try:
                protocol.finite_nonnegative(metadata['capture_monotonic_ms'])
            except (ValueError, OverflowError) as error:
                raise Unavailable('Invalid local capture clock') from error
            if (metadata['type'] != 'frame_metadata' or metadata['source_id'] != self.receiver_id
                    or metadata['boot_id'] != self.receiver_boot_id or not self.local_ready):
                raise Unavailable('Frame must originate from the ready local receiver epoch')
            age = now - metadata['capture_monotonic_ms']
            if (not 0 <= age <= 1500
                    or metadata['capture_monotonic_ms'] < self.capture_floor.get(self.receiver_id, now)):
                raise Unavailable('Frame is future, old or predates readiness/recovery')
            frame_id = metadata['frame_id']
            if frame_id in self.seen_frame_ids or len(self.seen_frame_ids) >= 4096:
                raise Unavailable('Duplicate frame ID or session frame bound reached')
            self.sequence.admit(metadata)
            self.seen_frame_ids.add(frame_id)
            self.frames[frame_id] = copy.deepcopy(metadata)
            while len(self.frames) > 2:
                self.frames.popitem(last=False)

    def receive(self, message):
        """Admit one authenticated observation; errors/None mean unavailable.

        Clock replies use finish_probe(). Ingestion acknowledgments are never
        observations. Invalid/replayed packets cannot reset sequence state.
        """
        with self.lock:
            now = self._now()
            self._prune(now)
            protocol.validate_message(message)
            kind, source = message['type'], message.get('source_id')
            if kind not in ('depth_observation', 'vision_observation', 'heartbeat'):
                raise Unavailable('Not a sensor/health observation')
            try:
                protocol.finite_nonnegative(message['capture_monotonic_ms'])
            except (ValueError, OverflowError) as error:
                raise Unavailable('Invalid source capture clock') from error
            self.sequence.admit(message)
            key = (source, kind)
            self.observations.pop(key, None)
            bound = None
            try:
                if kind == 'vision_observation':
                    pending = self.frames.get(message['frame_id'])
                    if pending is None or source != self.receiver_id or not self.local_ready:
                        raise Unavailable('Unknown, consumed or superseded local frame lineage')
                    if message['capture_utc'] != pending['capture_utc']:
                        raise Unavailable('Original diagnostic capture time changed')
                    age = protocol.local_vision_age(message, pending, now, self.session_id, self.mode)
                    self.frames.pop(message['frame_id'])
                else:
                    bound = self.bounds.get(source)
                    if bound is None:
                        raise Unavailable('No bounded source-consumer clock mapping')
                    age = bound.age_interval(message, now, self.receiver_boot_id)
                if not protocol.within_budget(kind, age):
                    raise Unavailable('Capture age or uncertainty outside budget')
                earliest_capture = now - age[1]
                if kind != 'heartbeat' and earliest_capture < self.capture_floor.get(source, now):
                    raise Unavailable('Capture predates readiness/recovery')
            except (ValueError, OverflowError) as error:
                if kind == 'heartbeat':
                    self.health.pop(source, None)
                    for old_key in list(self.observations):
                        if old_key[0] == source:
                            self.observations.pop(old_key)
                    self.capture_floor[source] = now
                raise Unavailable('Observation freshness unavailable') from error
            observation = Observation(copy.deepcopy(message), now,
                                      now + protocol.LIMITS_MS[kind] - age[1], bound)
            if kind == 'heartbeat':
                was_ready = self.healthy(source)
                self.health[source] = observation
                if message['state'] != 'ready' or not was_ready:
                    self.capture_floor[source] = now
                    for old_key in list(self.observations):
                        if old_key[0] == source:
                            self.observations.pop(old_key)
                return None  # Health is never sensor guidance.
            if not self.healthy(source):
                raise Unavailable('Source health unknown; require fresh ready heartbeat/local health')
            if kind == 'depth_observation' and (message['tracking'] != 'normal'
                    or any(s['distance_m'] is not None and s['distance_m'] <= 0
                           for s in message['sectors'].values())
                    or not any(s['distance_m'] is not None and s['distance_m'] > 0
                               for s in message['sectors'].values())):
                return None
            self.observations[key] = observation
            return copy.deepcopy(observation)

    def current(self, source_id, kind):
        with self.lock:
            now = self._now()
            self._prune(now)
            if not self.healthy(source_id):
                return None
            observation = self.observations.get((source_id, kind))
            return copy.deepcopy(observation) if observation else None
