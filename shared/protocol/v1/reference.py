"""Contract reference checks; transport auth, clocks and motor policy are adapters' responsibility."""
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = json.loads(Path(__file__).with_name('messages.schema.json').read_text(encoding='utf-8'))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
LIMITS_MS = {'depth_observation': 500, 'vision_observation': 1500, 'heartbeat': 2500}


def finite_nonnegative(*values):
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('Expected finite nonnegative clock/age values')


def validate_message(message):
    # JSON Schema alone does not forbid Python NaN/Infinity. Strict JSON does.
    json.dumps(message, allow_nan=False)
    VALIDATOR.validate(message)
    utc = message.get('capture_utc')
    if utc is not None:
        # format-checker date-time support can be optional in jsonschema;
        # enforce actual UTC dates here without relying on extra packages.
        if 'T' not in utc or not utc.endswith('Z'):
            raise ValueError('Expected UTC Z date-time')
        datetime.fromisoformat(utc[:-1] + '+00:00')
    kind = message['type']
    if kind == 'depth_observation':
        for sector in message['sectors'].values():
            if sector['distance_m'] is not None and (sector['valid_fraction'] == 0 or message['tracking'] != 'normal'):
                raise ValueError('Invalid tracking/no valid samples requires null distance')
    if kind == 'vision_observation':
        for detection in message['detections']:
            x1, y1, x2, y2 = detection['bbox_xyxy']
            if x1 >= x2 or y1 >= y2:
                raise ValueError('Bounding box must have positive area')
        signal = message['signal']
        if signal['symbol'] == 'unknown':
            if signal['confidence'] is not None or signal['countdown_s'] is not None:
                raise ValueError('Unknown signal requires null confidence/countdown')
        elif signal['candidate_count'] != 1 or signal['confidence'] is None:
            raise ValueError('Known symbol requires one candidate and confidence')
    return message


def parse_wire(raw):
    if not isinstance(raw, bytes) or len(raw) > 8192:
        raise ValueError('JSON message must be UTF-8 bytes, at most 8192 bytes')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError('Non-JSON numeric constant')
    return validate_message(json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=reject_constant))


class SequenceGate:
    """Ordering only, not a freshness/permission verdict. Enrollment is trusted control-plane input."""
    def __init__(self, session_id, mode):
        self.session_id, self.mode = session_id, mode
        self.active = {}
        self.last = {}
        self.retired = set()

    def enroll(self, source_id, boot_id, allowed_types):
        # The authenticated session service authorizes a new epoch explicitly.
        # Never call this just because an incoming observation has a new boot_id.
        if (source_id, boot_id) in self.retired:
            raise ValueError('Retired epoch cannot be reactivated')
        old = self.active.get(source_id)
        allowed = frozenset(allowed_types)
        if old == (boot_id, allowed):
            return  # Reconnect must not reset sequence high-water marks.
        if old and old[0] == boot_id:
            raise ValueError('Role/type change requires explicit session reconfiguration')
        if (len(self.active) >= 16 and source_id not in self.active) or (old and len(self.retired) >= 128):
            raise ValueError('Session identity bound reached; create a new session')
        if old:
            self.retired.add((source_id, old[0]))
        self.active[source_id] = (boot_id, allowed)
        self.last = {key:value for key,value in self.last.items() if key[0] != source_id}
        # Caller must atomically purge this source's observations, pending
        # frames and clock maps before enabling the newly enrolled epoch.

    def admit(self, message):
        validate_message(message)
        if message['session_id'] != self.session_id or message['mode'] != self.mode:
            raise ValueError('Wrong session or replay/live mode')
        binding = self.active.get(message['source_id'])
        if not binding or message['boot_id'] != binding[0] or message['type'] not in binding[1]:
            raise ValueError('Unknown source, epoch or message role')
        key = (message['source_id'], message['boot_id'], message['type'])
        if message['seq'] <= self.last.get(key, -1):
            raise ValueError('Duplicate or decreasing sequence')
        self.last[key] = message['seq']


@dataclass(frozen=True)
class ClockBound:
    source_id: str
    source_boot_id: str
    receiver_boot_id: str
    measured_local_ms: float
    lower_offset_ms: float  # source clock minus receiver clock
    upper_offset_ms: float
    relative_drift_ppm: float
    valid_for_ms: float = 10000

    @classmethod
    def from_exchange(cls, source_id, source_boot_id, receiver_boot_id, t1, t2, t3, t4, relative_drift_ppm):
        finite_nonnegative(t1,t2,t3,t4,relative_drift_ppm)
        # t1/t4: receiver send/receive; t2/t3: source receive/send. No
        # assumption of symmetric delay: true offset lies in this interval.
        if not 0 <= t4-t1 <= 1000 or t3 < t2 or t3 - t4 > t2 - t1:
            raise ValueError('Inconsistent clock exchange')
        drift = (t4-t1) * relative_drift_ppm / 1_000_000
        return cls(source_id,source_boot_id,receiver_boot_id,t4,t3-t4-drift,t2-t1+drift,relative_drift_ppm)

    def age_interval(self, message, now_local_ms, receiver_boot_id):
        finite_nonnegative(now_local_ms,self.measured_local_ms,self.relative_drift_ppm,self.valid_for_ms)
        if not 0 < self.valid_for_ms <= 10000:
            raise ValueError('Clock-map lifetime must be at most 10000 ms')
        if not all(math.isfinite(v) for v in (self.lower_offset_ms,self.upper_offset_ms)) or self.lower_offset_ms > self.upper_offset_ms:
            raise ValueError('Invalid clock bound')
        elapsed = now_local_ms - self.measured_local_ms
        if (message['source_id'],message['boot_id'],receiver_boot_id) != (self.source_id,self.source_boot_id,self.receiver_boot_id) or not 0 <= elapsed <= self.valid_for_ms:
            raise ValueError('Clock bound missing, expired or wrong epoch')
        finite_nonnegative(message['capture_monotonic_ms'])
        drift = elapsed * self.relative_drift_ppm / 1_000_000
        if message['capture_monotonic_ms'] - self.upper_offset_ms - drift < self.measured_local_ms:
            raise ValueError('Capture predates this clock calibration; wait for a new frame')
        age = now_local_ms - message['capture_monotonic_ms']
        return age + self.lower_offset_ms - drift, age + self.upper_offset_ms + drift


def verify_clock_reply(pending_probe, reply, t4, relative_drift_ppm):
    """Caller authenticates the sender and atomically consumes its one-time pending probe."""
    validate_message(pending_probe)
    validate_message(reply)
    if pending_probe['type'] != 'clock_probe' or reply['type'] != 'clock_reply':
        raise ValueError('Wrong clock control message type')
    if any(reply[key] != value for key,value in pending_probe.items() if key != 'type'):
        raise ValueError('Clock nonce/session/source/receiver/t1 mismatch')
    return ClockBound.from_exchange(reply['source_id'],reply['source_boot_id'],reply['receiver_boot_id'],
                                    pending_probe['t1_ms'],reply['t2_ms'],reply['t3_ms'],t4,relative_drift_ppm)


def within_budget(kind, age_interval):
    """Fail closed; null/unbounded age is not fresh. Never use as crossing permission."""
    if kind not in LIMITS_MS or age_interval is None:
        return False
    lower, upper = age_interval
    uncertainty_budget = 250 if kind == 'vision_observation' else 100
    return (all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (lower,upper))
            and 0 <= lower <= upper <= LIMITS_MS[kind] and (upper-lower)/2 <= uncertainty_budget)


def local_vision_age(message, pending, now_local_ms, session_id, mode):
    """pending is the originating Pi's trusted capture ledger, never peer-supplied metadata."""
    validate_message(message)
    if message['type'] != 'vision_observation' or message['session_id'] != session_id or message['mode'] != mode:
        raise ValueError('Wrong vision session/type/mode')
    keys = ('source_id','boot_id','seq','frame_id','capture_monotonic_ms','image','mode','session_id')
    if any(message[key] != pending[key] for key in keys):
        raise ValueError('Vision result does not match a pending original frame')
    finite_nonnegative(now_local_ms,pending['capture_monotonic_ms'])
    age = now_local_ms - pending['capture_monotonic_ms']
    return age, age
