"""CS-031: bounded scheduling and isolated blocking inference.

The trusted factory is called once in a spawned child process. No model, raw
image, factory exception or result is logged. Results are internal observations,
not a freshness verdict or movement command.
"""
import copy
import json
import math
import multiprocessing
import threading
import time
from collections import OrderedDict

MAX_RESULT_BYTES = 8192


def _model_process(connection, factory):
    # All model loading, prediction, schema validation and serialization stay
    # out of the ASGI process. Factory is trusted application configuration.
    from .app import AcceptedFrame, protocol
    try:
        model = factory()
        version = model.version
        if not isinstance(version, str) or not 1 <= len(version) <= 128:
            raise ValueError('Invalid model version')
        connection.send_bytes(b'loaded')
        while True:
            metadata, jpeg = connection.recv()
            started = time.monotonic()
            # Keep provenance private: a frozen dataclass does not freeze its
            # nested dicts. Preprocessing may mutate its own independent input.
            original = copy.deepcopy(metadata)
            prediction = model.predict(AcceptedFrame(copy.deepcopy(metadata), jpeg))
            if not isinstance(prediction, dict) or set(prediction) != {'detections', 'signal'}:
                raise ValueError('Prediction must contain detections and signal only')
            observation = {k: v for k, v in original.items() if k != 'jpeg_bytes'}
            observation.update(type='vision_observation', model_version=version,
                               processing_ms=(time.monotonic() - started) * 1000,
                               **prediction)
            raw = json.dumps(observation, allow_nan=False, separators=(',', ':')).encode()
            if len(raw) > MAX_RESULT_BYTES:
                raise ValueError('Result exceeds bound')
            protocol.parse_wire(raw)
            connection.send_bytes(raw)
    except (Exception, KeyboardInterrupt):
        try:
            connection.send_bytes(b'failed')
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


class InferenceWorker:
    """One process, one in-flight job, one pending/latest result per source.

    submit/take_result accept only already authenticated and validated grants.
    No public source registration or freshness policy is provided here. A model
    failure/deadline fails closed without reload; explicitly restart the service.
    """
    def __init__(self, factory, *, max_sources=16, job_timeout=1.5, load_timeout=30):
        if type(max_sources) is not int or not 1 <= max_sources <= 16:
            raise ValueError('Source capacity must be 1..16')
        for value in (job_timeout, load_timeout):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 120:
                raise ValueError('Use a finite positive deadline at most 120 seconds')
        self.factory = factory
        self.max_sources = max_sources
        self.job_timeout = job_timeout
        self.load_timeout = load_timeout
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._thread = None
        self._model_available = False
        self._failed = False
        self._started = False
        self._active = None
        self._sources = {}
        self._pending = OrderedDict()
        self._results = {}
        self._generation = 0
        self._metrics = dict.fromkeys(('submitted', 'superseded_pending', 'superseded_result',
                                      'source_capacity', 'unavailable', 'expired', 'completed',
                                      'failed', 'timeouts', 'shutdown_dropped', 'revoked', 'model_loads'), 0)

    @staticmethod
    def _key(grant):
        return (grant.session_id, grant.source_id, grant.boot_id, grant.mode)

    def _prune(self, now):
        for key, (expiry, _) in list(self._sources.items()):
            if expiry <= now:
                self._pending.pop(key, None)
                self._results.pop(key, None)
                del self._sources[key]
                self._metrics['expired'] += 1

    def start(self):
        # Idempotent start: never create a second loader or restart a failed one.
        with self._condition:
            if self._started:
                return
            self._started = True
            self._thread = threading.Thread(target=self._run, name='canesight-inference', daemon=True)
            self._thread.start()

    def health(self):
        with self._condition:
            now = time.monotonic()
            self._prune(now)
            running = self._thread is not None and self._thread.is_alive()
            timely = self._active is None or now - self._active[2] < self.job_timeout
            return {'model_available': self._model_available and not self._failed and not self._stop.is_set(),
                    'worker_healthy': running and self._model_available and timely and not self._failed and not self._stop.is_set()}

    def metrics(self):
        with self._condition:
            self._prune(time.monotonic())
            return dict(self._metrics, sources=len(self._sources), pending=len(self._pending),
                        results=len(self._results), active=int(self._active is not None))

    def submit(self, grant, metadata, jpeg):
        # This is a trusted adapter after JPEG and protocol checks, never raw HTTP.
        if (grant.role != 'pi' or not isinstance(jpeg, bytes) or len(jpeg) > 1_000_000
                or metadata.get('jpeg_bytes') != len(jpeg)
                or any(metadata.get(k) != getattr(grant, k) for k in
                       ('session_id', 'source_id', 'boot_id', 'mode'))):
            raise ValueError('Validated Pi frame and matching grant required')
        with self._condition:
            now = time.monotonic()
            self._prune(now)
            if grant.expires_at <= now:
                self._metrics['expired'] += 1
                return False
            if not self.health()['worker_healthy']:
                self._metrics['unavailable'] += 1
                return False
            key = self._key(grant)
            if key not in self._sources and len(self._sources) >= self.max_sources:
                self._metrics['source_capacity'] += 1
                return False
            self._generation += 1
            generation = self._generation
            self._sources[key] = (grant.expires_at, generation)
            if key in self._pending:
                self._metrics['superseded_pending'] += 1
            if self._results.pop(key, None) is not None:
                self._metrics['superseded_result'] += 1
            # Replacing a value preserves FIFO order across distinct sources.
            self._pending[key] = (generation, copy.deepcopy(metadata), jpeg, now)
            self._metrics['submitted'] += 1
            self._condition.notify()
            return True

    def take_result(self, grant):
        with self._condition:
            self._prune(time.monotonic())
            if grant.role != 'pi' or grant.expires_at <= time.monotonic() or not self.health()['worker_healthy']:
                return None
            result = self._results.pop(self._key(grant), None)
            return json.loads(result) if result is not None else None

    def discard_source(self, grant):
        """Trusted session lifecycle hook for revocation/epoch reset (CS-029)."""
        with self._condition:
            key = self._key(grant)
            if self._sources.pop(key, None) is not None:
                self._pending.pop(key, None)
                self._results.pop(key, None)
                self._metrics['revoked'] += 1
            # In-flight work can finish, but its removed generation cannot publish.

    def stop(self):
        self._stop.set()
        with self._condition:
            self._metrics['shutdown_dropped'] += len(self._pending) + len(self._results)
            self._pending.clear()
            self._results.clear()
            self._sources.clear()
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=3)
        return self._thread is None or not self._thread.is_alive()

    def _receive(self, connection, process, deadline):
        while not self._stop.is_set():
            if time.monotonic() >= deadline:
                with self._condition:
                    self._metrics['timeouts'] += 1
                raise TimeoutError('Inference deadline')
            if connection.poll(0.01):
                return connection.recv_bytes(MAX_RESULT_BYTES)
            if not process.is_alive():
                raise RuntimeError('Inference process exited')
        raise RuntimeError('Worker stopping')

    def _run(self):
        connection, child = multiprocessing.get_context('spawn').Pipe()
        process = multiprocessing.get_context('spawn').Process(
            target=_model_process, args=(child, self.factory), name='canesight-model', daemon=True)
        try:
            process.start()
            child.close()
            if self._receive(connection, process, time.monotonic() + self.load_timeout) != b'loaded':
                raise RuntimeError('Model load failed')
            with self._condition:
                self._model_available = True
                self._metrics['model_loads'] += 1
            while not self._stop.is_set():
                with self._condition:
                    self._prune(time.monotonic())
                    if not self._pending:
                        self._condition.wait(timeout=0.05)
                        continue
                    key, (generation, metadata, jpeg, received) = self._pending.popitem(last=False)
                    if time.monotonic() - received >= self.job_timeout:
                        self._metrics['expired'] += 1
                        continue
                    self._active = (key, generation, received)
                # Bounded frame send can block only this supervisor thread.
                connection.send((metadata, jpeg))
                raw = self._receive(connection, process, received + self.job_timeout)
                if raw == b'failed':
                    raise RuntimeError('Model prediction failed')
                with self._condition:
                    self._prune(time.monotonic())
                    source = self._sources.get(key)
                    if source is not None and source[1] == generation and not self._stop.is_set():
                        self._results[key] = raw
                        self._metrics['completed'] += 1
                    else:
                        self._metrics['superseded_result'] += 1
                    self._active = None
        except Exception:
            with self._condition:
                if not self._stop.is_set():
                    self._failed = True
                    self._metrics['failed'] += 1
        finally:
            # Termination handles a hung loader/predictor; no orphan inference.
            connection.close()
            child.close()
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=0.5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=0.5)
            with self._condition:
                self._model_available = False
                self._active = None
                self._metrics['shutdown_dropped'] += len(self._pending) + len(self._results)
                self._pending.clear()
                self._results.clear()
                self._sources.clear()
