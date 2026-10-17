"""CS-032 bounded admission/transport limits, independent of authentication.

One process per demo. These limits never authorize sources, renew capture age,
declare readiness or block waiting for rate capacity. CS-029 still authenticates
and validates typed messages; CS-031 still owns bounded inference work.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import threading
import time


class RateTable:
    """Hard-capped token buckets. New identities fail closed at capacity.

    Idle entries expire; active entries are never evicted to admit new identities.
    Caller keys must be bounded trusted identities, not credentials or JSON data.
    """
    def __init__(self, rate, burst, *, capacity=128, idle_seconds=60, clock=time.monotonic):
        if (not isinstance(rate, (int, float)) or isinstance(rate, bool)
                or not math.isfinite(rate) or rate <= 0
                or type(burst) is not int or not 1 <= burst <= 10000
                or type(capacity) is not int or not 1 <= capacity <= 4096
                or not isinstance(idle_seconds, (int, float))
                or isinstance(idle_seconds, bool)
                or not math.isfinite(idle_seconds) or idle_seconds < burst / rate):
            raise ValueError('Invalid bounded rate configuration')
        self.rate, self.burst, self.capacity = rate, burst, capacity
        self.idle_seconds, self.clock = idle_seconds, clock
        self._buckets = {}
        self._lock = threading.Lock()

    def allow(self, key):
        with self._lock:
            now = self.clock()
            if not isinstance(now, (int, float)) or not math.isfinite(now):
                return False
            for expired in [k for k, (_, seen) in self._buckets.items()
                            if now - seen >= self.idle_seconds]:
                del self._buckets[expired]
            previous = self._buckets.get(key)
            if previous is None:
                if len(self._buckets) >= self.capacity:
                    return False
                tokens, seen = float(self.burst), now
            else:
                tokens, seen = previous
            # A clock regression cannot mint tokens or move the refill origin back.
            now = max(now, seen)
            tokens = min(self.burst, tokens + (now - seen) * self.rate)
            allowed = tokens >= 1
            self._buckets[key] = (tokens - 1 if allowed else tokens, now)
            return allowed

    def size(self):
        with self._lock:
            return len(self._buckets)


def strict_object(raw):
    """Bounded generic JSON envelope check; typed protocol validation stays upstream."""
    if not isinstance(raw, bytes) or len(raw) > 8192:
        raise ValueError('Message byte limit')
    # Bound nesting before materializing JSON containers.
    depth, quoted, escaped = 0, False, False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (123, 91):
            depth += 1
            if depth > 12:
                raise ValueError('Message nesting limit')
        elif char in (125, 93):
            depth -= 1

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result

    def floating(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('Nonfinite JSON number')
        return number

    def constant(_value):
        raise ValueError('Invalid JSON constant')

    result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                        parse_float=floating, parse_constant=constant)
    if not isinstance(result, dict):
        raise ValueError('JSON object required')
    return result


@dataclass(frozen=True)
class Limits:
    # Demo starting envelopes, not measured throughput guarantees.
    frame_rate: float = 1.0
    frame_burst: int = 8
    peer_rate: float = 32.0
    peer_burst: int = 64
    global_rate: float = 128.0
    global_burst: int = 128
    websocket_capacity: int = 64


class TrafficLimits:
    def __init__(self, policy=None, *, clock=time.monotonic):
        self.policy = policy or Limits()
        p = self.policy
        if type(p.websocket_capacity) is not int or not 1 <= p.websocket_capacity <= 1024:
            raise ValueError('Invalid WebSocket capacity')
        self.frames = RateTable(p.frame_rate, p.frame_burst, capacity=128, clock=clock)
        self.telemetry = RateTable(10, 10, capacity=128, clock=clock)
        self.peers = RateTable(p.peer_rate, p.peer_burst, capacity=128, clock=clock)
        self.total = RateTable(p.global_rate, p.global_burst, capacity=1, clock=clock)
        self.clock = clock
        self._active = 0
        self._lock = threading.Lock()
        self._counts = dict.fromkeys(('http_rejected', 'frame_rejected', 'ws_capacity_rejected',
                                     'ws_rate_rejected', 'ws_size_rejected', 'ws_json_rejected'), 0)

    def count(self, reason):
        with self._lock:
            self._counts[reason] += 1

    def snapshot(self):
        with self._lock:
            return dict(self._counts, active_websockets=self._active)

    def frame_allowed(self, grant):
        # This is called only after the accepted ingress has authenticated the grant.
        allowed = self.frames.allow((grant.session_id, grant.source_id, grant.boot_id))
        if not allowed:
            self.count('frame_rejected')
        return allowed

    def traffic_allowed(self, scope):
        # Do not trust caller-supplied X-Forwarded-For or retain bearer credentials.
        peer = str((scope.get('client') or ('unknown', 0))[0])[:128]
        key = hashlib.sha256(peer.encode('utf-8')).digest()
        return self.total.allow('global') and self.peers.allow(key)

    def telemetry_allowed(self, grant):
        """CS-029 calls this after authenticating a phone, across reconnects."""
        allowed = self.telemetry.allow((grant.session_id, grant.source_id, grant.boot_id))
        if not allowed:
            self.count('ws_rate_rejected')
        return allowed

    def acquire_socket(self):
        with self._lock:
            if self._active >= self.policy.websocket_capacity:
                self._counts['ws_capacity_rejected'] += 1
                return False
            self._active += 1
            return True

    def release_socket(self):
        with self._lock:
            self._active -= 1


class TrafficGuard:
    """Pure ASGI guard; preserves messages and delegates authentication to CS-029."""
    def __init__(self, app, limits):
        self.app, self.limits = app, limits

    async def __call__(self, scope, receive, send):
        kind = scope['type']
        if kind not in ('http', 'websocket') or not scope.get('path', '').startswith('/v1/'):
            await self.app(scope, receive, send)
            return
        if not self.limits.traffic_allowed(scope):
            if kind == 'http':
                self.limits.count('http_rejected')
                await send({'type': 'http.response.start', 'status': 429,
                            'headers': [(b'content-type', b'application/json'), (b'retry-after', b'1')]})
                await send({'type': 'http.response.body', 'body': b'{"detail":"Request rate exceeded"}'})
            else:
                self.limits.count('ws_rate_rejected')
                await send({'type': 'websocket.close', 'code': 1013})
            return
        if kind == 'http':
            await self.app(scope, receive, send)
            return
        if not self.limits.acquire_socket():
            await send({'type': 'websocket.close', 'code': 1013})
            return
        depth = RateTable(10, 10, capacity=1, clock=self.limits.clock)
        closed = False

        async def guarded_send(message):
            if not closed:
                await send(message)

        async def guarded_receive():
            nonlocal closed
            if closed:
                return {'type': 'websocket.disconnect', 'code': 1008}
            message = await receive()
            if message['type'] != 'websocket.receive':
                return message
            code, reason = None, None
            if not self.limits.traffic_allowed(scope):
                code, reason = 1008, 'ws_rate_rejected'
            else:
                try:
                    text = message.get('text')
                    # Avoid allocating another unbounded copy of an oversized text frame.
                    raw = (b'x' * 8193 if text is not None and len(text) > 8192 else
                           text.encode('utf-8') if text is not None else message.get('bytes', b''))
                    if len(raw) > 8192:
                        code, reason = 1009, 'ws_size_rejected'
                    else:
                        envelope = strict_object(raw)
                        if envelope.get('type') == 'depth_observation' and not depth.allow('depth'):
                            code, reason = 1008, 'ws_rate_rejected'
                except (ValueError, TypeError, UnicodeError, RecursionError):
                    # Preserve accepted CS-029 application rejection semantics.
                    code, reason = 1008, 'ws_json_rejected'
            if code is not None:
                closed = True
                self.limits.count(reason)
                await send({'type': 'websocket.close', 'code': code})
                return {'type': 'websocket.disconnect', 'code': code}
            return message

        try:
            await self.app(scope, guarded_receive, guarded_send)
        finally:
            self.limits.release_socket()
