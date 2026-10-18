"""CS-037 local, explicitly selected synthetic replay adapters.

No model loading, automatic scene selection, network schema, audio or motors.
Annotations are authored test inputs, not detections or real-world accuracy.
"""
from collections import deque
from dataclasses import dataclass
import math
import re

from .signal_parser import ReplaySignalParser, TTL_MS

SCENARIOS = ('pedestrian_signal', 'pedestrian_yellow_beacon', 'unsignalized_street')
MAX_TRACKS = 16
MAX_SAMPLE_GAP_MS = 200
MAX_TIME = 2**53 - 1


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value) is not None


def _time(value):
    return type(value) is int and 0 <= value <= MAX_TIME


def _box(value):
    return (isinstance(value, tuple) and len(value) == 4
            and all(type(v) in (int, float) and 0 <= v <= 1 and math.isfinite(v) for v in value)
            and 0 <= value[0] < value[2] <= 1 and 0 <= value[1] < value[3] <= 1)


@dataclass(frozen=True)
class ReplayFrame:
    source_id: str
    session_id: str
    boot_id: str
    sequence: int
    captured_ms: int
    mode: str = 'replay'
    provenance: str = 'authored_synthetic_replay'
    lighting: str = 'day'
    camera_motion: str = 'stable'
    visibility: str = 'clear'


@dataclass(frozen=True)
class Selection:
    generation: int
    scenario: str
    source_id: str
    session_id: str
    boot_id: str


@dataclass(frozen=True)
class BeaconSample:
    target_id: str
    box_xyxy: tuple
    illuminated: bool
    kind: str = 'pedestrian_yellow_beacon'


@dataclass(frozen=True)
class VehicleSample:
    track_id: str
    box_xyxy: tuple
    visible: bool = True


@dataclass(frozen=True)
class VehicleMotion:
    track_id: str
    state: str = 'unknown'
    displacement_xy: tuple | None = None


@dataclass(frozen=True)
class ScenarioResult:
    scenario: str | None = None
    generation: int = 0
    mode: str = 'replay'
    live_supported: bool = False
    reason: str = 'selection_required'
    captured_ms: int | None = None
    symbol: str = 'unknown'
    countdown_s: int | None = None
    beacon_state: str = 'unknown'
    vehicles: tuple = ()


class _BeaconReplay:
    """Bounded annotated alternation, not a flashing detector or frequency meter."""
    def __init__(self):
        self.target = None
        self.samples = deque(maxlen=16)

    def observe(self, sample, captured_ms):
        if (not isinstance(sample, BeaconSample) or not _identifier(sample.target_id)
                or not _box(sample.box_xyxy) or type(sample.illuminated) is not bool
                or sample.kind != 'pedestrian_yellow_beacon'):
            self.__init__()
            return 'unknown'
        target = (sample.target_id, sample.box_xyxy)
        if target != self.target or (self.samples and
                captured_ms - self.samples[-1][0] > MAX_SAMPLE_GAP_MS):
            self.__init__()
            self.target = target
        self.samples.append((captured_ms, sample.illuminated))
        while self.samples and captured_ms - self.samples[0][0] > 2000:
            self.samples.popleft()
        # Require two complete on/off cycles and dense intervening samples.
        # The cadence is an engineering replay rule, not field validation.
        transitions = [b[0] for a, b in zip(self.samples, list(self.samples)[1:]) if a[1] != b[1]]
        intervals = [b-a for a, b in zip(transitions, transitions[1:])]
        if len(transitions) >= 4 and all(200 <= gap <= 600 for gap in intervals):
            return 'alternating_replay_evidence'
        return 'unknown'


class _VehicleReplay:
    """At most 16 previous annotated boxes; no physical speed/stop/yield state."""
    def __init__(self):
        self.previous = {}
        self.captured_ms = None

    def observe(self, samples, captured_ms):
        if (not isinstance(samples, tuple) or len(samples) > MAX_TRACKS
                or any(not isinstance(s, VehicleSample) or not _identifier(s.track_id)
                       or not _box(s.box_xyxy) or type(s.visible) is not bool for s in samples)
                or len({s.track_id for s in samples}) != len(samples)):
            self.__init__()
            return None
        if self.captured_ms is not None and captured_ms - self.captured_ms > MAX_SAMPLE_GAP_MS:
            self.previous = {}
        current, results = {}, []
        for sample in samples:
            old = self.previous.get(sample.track_id)
            state, delta = 'unknown', None
            if sample.visible:
                current[sample.track_id] = sample.box_xyxy
                if old is not None:
                    box = sample.box_xyxy
                    dx = (box[0]+box[2]-old[0]-old[2])/2
                    dy = (box[1]+box[3]-old[1]-old[3])/2
                    # Unchanged boxes cannot establish a stopped vehicle. Large
                    # jumps are ambiguous association, not speed or approach.
                    distance = math.hypot(dx, dy)
                    if .01 <= distance <= .20:
                        state, delta = 'image_displacement_observed', (dx, dy)
                    elif distance > .20:
                        current.pop(sample.track_id)
            results.append(VehicleMotion(sample.track_id, state, delta))
        self.previous, self.captured_ms = current, captured_ms
        return tuple(results)


class ScenarioReplay:
    """One explicit scenario/epoch at a time, with stale-callback fencing.

    All times use a single authored replay timeline. current() must be polled
    independently; it is not device capture-age verification. Source loss or
    invalid frame cancels the selection; recovery requires select() again.
    A bad/backward poll clock latches the instance closed, including select().
    """
    def __init__(self):
        self.generation = 0
        self.selection = None
        self.clock = -1
        self.clock_failed = False
        self.identity = None
        self.high_water = None
        self.result = ScenarioResult()
        self._reset_adapters()

    def _reset_adapters(self):
        self.signal = None  # Lazy; even replay fixtures are not opened on import.
        self.beacon = _BeaconReplay()
        self.vehicle = _VehicleReplay()

    def cancel(self, reason='cancelled'):
        self.generation += 1
        self.selection = None
        self._reset_adapters()
        self.result = ScenarioResult(generation=self.generation, reason=reason)
        return self.result

    def select(self, scenario, *, source_id, session_id, boot_id):
        self.cancel()
        if self.clock_failed:
            raise ValueError('Replay clock failed; create a new controller')
        if scenario not in SCENARIOS or not all(map(_identifier, (source_id, session_id, boot_id))):
            raise ValueError('Explicit supported scenario and source/session/boot required')
        identity = (source_id, session_id, boot_id)
        if self.identity is not None and identity != self.identity:
            raise ValueError('New source epoch requires a new replay controller')
        self.identity = identity
        self.selection = Selection(self.generation, scenario, source_id, session_id, boot_id)
        self.result = ScenarioResult(scenario=scenario, generation=self.generation, reason='needs_replay_evidence')
        return self.selection

    def current(self, replay_ms):
        if not _time(replay_ms) or replay_ms < self.clock:
            self.clock_failed = True
        if self.clock_failed:
            return self.cancel('replay_clock_invalid')
        self.clock = replay_ms
        if self.result.captured_ms is not None and replay_ms - self.result.captured_ms > TTL_MS:
            return self.cancel('expired')
        return self.result

    def observe(self, selection, frame, *, replay_ms, image=None, target_id=None,
                manual_rois=None, beacon=None, vehicles=()):
        # A completion from an old scenario may neither populate nor erase the
        # current scenario. Tokens are local objects, never wire credentials.
        if self.selection is None or selection is not self.selection:
            return ScenarioResult(generation=self.generation,
                reason='selection_required' if self.selection is None else 'superseded_selection')
        self.current(replay_ms)
        if self.selection is None:
            return self.result
        identity = (selection.source_id, selection.session_id, selection.boot_id)
        if (not isinstance(frame, ReplayFrame) or frame.mode != 'replay'
                or frame.provenance != 'authored_synthetic_replay'):
            return self.cancel('synthetic_replay_only')
        if (frame.source_id, frame.session_id, frame.boot_id) != identity:
            return self.cancel('source_epoch_changed')
        if (not _time(frame.sequence) or not _time(frame.captured_ms)
                or frame.captured_ms > replay_ms or replay_ms-frame.captured_ms > TTL_MS):
            return self.cancel('invalid_or_expired_frame')
        if self.high_water is not None:
            old_identity, sequence, captured_ms = self.high_water
            if old_identity == identity and (frame.sequence <= sequence or frame.captured_ms <= captured_ms):
                return self.cancel('replayed_or_reordered_frame')
        self.high_water = (identity, frame.sequence, frame.captured_ms)
        if frame.lighting != 'day':
            return self.cancel('unsupported_lighting')
        if frame.camera_motion != 'stable' or frame.visibility != 'clear':
            return self.cancel('camera_motion_or_visibility_unknown')
        scenario = selection.scenario
        symbol, countdown, beacon_state, tracks = 'unknown', None, 'unknown', ()
        reason = 'needs_temporal_evidence'
        if scenario == 'pedestrian_signal':
            # Other scenario payloads cannot contaminate this adapter.
            if beacon is not None or vehicles != ():
                return self.cancel('scenario_payload_mismatch')
            if self.signal is None:
                self.signal = ReplaySignalParser()
            result = self.signal.observe(image, mode='replay', sequence=frame.sequence,
                replay_ms=frame.captured_ms, target_id=target_id, manual_rois=manual_rois)
            symbol, countdown, reason = result.symbol, result.countdown_s, result.reason
        else:
            if image is not None or target_id is not None or manual_rois is not None:
                return self.cancel('scenario_payload_mismatch')
            if scenario == 'unsignalized_street' and beacon is not None:
                return self.cancel('scenario_payload_mismatch')
            tracks = self.vehicle.observe(vehicles, frame.captured_ms)
            if tracks is None:
                return self.cancel('invalid_vehicle_annotations')
            if scenario == 'pedestrian_yellow_beacon':
                beacon_state = self.beacon.observe(beacon, frame.captured_ms)
            if beacon_state != 'unknown' or any(t.state != 'unknown' for t in tracks):
                reason = 'annotated_replay_observation'
        self.result = ScenarioResult(scenario, selection.generation,
            reason=reason, captured_ms=frame.captured_ms, symbol=symbol,
            countdown_s=countdown, beacon_state=beacon_state, vehicles=tracks)
        return self.result


def live_capabilities():
    """No evaluated custom models or temporal adapters are registered."""
    return {scenario: False for scenario in SCENARIOS}
