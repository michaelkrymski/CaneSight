"""CS-027 opt-in same-process uploader integration with manual terminal input.

No GPIO or audio output. Local primary-source unknown/hazard state preempts
context. Each worker owns its locks; never hold the frame lock across button,
policy, network, input or output calls.
"""
import copy
import threading

from .buttons import ContextButton
from .context_client import ContextClient, validate_frame
from .haptics import number
from .uploader import Frame, clock_ms


def policy_priority(policy, receiver, sender, watchdog):
    """Read trusted policy + original freshness, never infer health from YOLO."""
    acquired = []
    try:
        if (policy is None or not receiver.connected or receiver.error or sender.error
                or watchdog is None):
            return False, True
        # A stalled policy/gate/watchdog worker must not stall cancellation.
        # These accepted components use RLocks, so their readers can reenter.
        for lock in (policy.lock, policy.gate.lock, watchdog.lock):
            if not lock.acquire(blocking=False):
                return False, True
            acquired.append(lock)
        if watchdog.deadline() is None:
            return False, True
        state = policy.snapshot()
        observation = policy.gate.current(policy.phone_id, 'depth_observation')
        if (policy.closed or state['fault'] or not state['armed']
                or state['health']['depth'] != 'fresh' or observation is None
                or observation.message['seq'] != policy.last_seq
                or observation.deadline_ms != policy.last_deadline
                or set(state['hazards']) != {'left', 'center', 'right'}
                or any(v not in ('nearby', 'not-nearby-observed') for v in state['hazards'].values())):
            return False, True
        return True, any(v == 'nearby' for v in state['hazards'].values())
    except Exception:
        return False, True
    finally:
        for lock in reversed(acquired):
            lock.release()


class ManualContext:
    """Bounded latest frame, explicit consent, separate timer and input workers.

    This is a terminal-operated bench adapter, not a physical switch or phone
    narrator. start/read/emit injection exists for generated offline fixtures.
    """
    def __init__(self, session, priority, *, consent, ca_file=None, clock=clock_ms,
                 client=None, emit=print):
        if consent is not True:
            raise ValueError('Explicit scene-sharing consent required')
        self._binding = {key: session[key] for key in ('session_id', 'source_id', 'boot_id', 'mode')}
        self._client = client if client is not None else ContextClient(session, ca_file=ca_file)
        self._priority = priority
        self._clock = clock
        self._emit = emit
        self._lock = threading.Lock()
        self._frame = None
        self._camera = False
        self._consent = True
        self._level = False  # Explicit synthetic release for terminal mode only.
        self._closed = self._input_closed = False
        self._fault = None
        self._shown = 0
        self._stop = threading.Event()
        self._thread = self._input_thread = None
        self.button = ContextButton(self.latest, self._client.start, clock=clock)

    def latest(self):
        with self._lock:
            return self._frame

    def offer(self, frame):
        # `python -m edge.uploader` defines the producer Frame in __main__.
        # Normalize to the importable type for validation/spawn, preserving the
        # original metadata and bytes rather than deriving a new capture time.
        frame = Frame(frame.metadata, frame.mapping, frame.jpeg)
        metadata = validate_frame(frame)
        if any(metadata[key] != value for key, value in self._binding.items()):
            self.withdraw()
            raise ValueError('Context frame must match this process/session epoch')
        with self._lock:
            if self._consent and not self._closed:
                self._frame = Frame(copy.deepcopy(metadata), frame.mapping, frame.jpeg)

    def set_camera_ready(self, ready):
        with self._lock:
            self._camera = ready is True
            if not self._camera:
                self._frame = None
        if ready is not True:
            self.button.set_state(ready=False, consent=False, hazard=True)

    def _state(self):
        with self._lock:
            frame, camera, consent, level = self._frame, self._camera, self._consent, self._level
            closed = self._closed or self._input_closed or self._fault is not None
        try:
            now = number(self._clock())
            age = now - frame.metadata['capture_monotonic_ms'] if frame is not None else None
            ready, hazard = self._priority()
            ready = bool(not closed and camera and age is not None and 0 <= age <= 1500
                         and ready is True)
            return ready, consent, hazard, level
        except Exception:
            return False, False, True, False

    def tick(self):
        ready, consent, hazard, level = self._state()
        self.button.set_state(ready=ready, consent=consent, hazard=hazard)
        self.button.sample(level)
        value = self.button.take_result()
        if value is None:
            return
        # Priority/consent/capture can change while polling or reaping a child.
        ready, consent, hazard, _ = self._state()
        try:
            age = number(self._clock()) - value['frame']['capture_monotonic_ms']
            if not ready or consent is not True or hazard is not False or not 0 <= age < 8000:
                return
            labels = value['description']['objects']
            message = ('Context (manual input; AI; uncertain): possible ' + ', '.join(labels) + '.'
                       if labels else 'Description unavailable.')
            self._emit(message)  # Closed labels only; never provider prose/frame/key.
            with self._lock:
                self._shown += 1
        except Exception:
            self.withdraw()

    def command(self, line):
        """Closed command vocabulary. Never evaluate or echo untrusted input."""
        if type(line) is not str or len(line) > 64:
            self.cancel()
            return False
        command = line.strip()
        with self._lock:
            if self._closed or self._input_closed:
                return False
        if command in ('press', 'release'):
            with self._lock:
                self._level = command == 'press'
            return True
        if command == 'cancel':
            self.cancel()
            return True
        if command == 'off':
            self.withdraw()
            return True
        self.cancel()
        return False

    def cancel(self):
        with self._lock:
            self._level = False
        self.button.cancel()

    def withdraw(self):
        with self._lock:
            self._consent = False
            self._input_closed = True
            self._level = False
            self._frame = None
        self.button.set_state(ready=False, consent=False, hazard=True)
        self.button.cancel()

    def start(self, stream):
        with self._lock:
            if self._thread is not None or self._closed:
                raise ValueError('Start manual context once')
        self.button.start()
        def monitor():
            try:
                while not self._stop.wait(.02):
                    self.tick()
            except Exception:
                with self._lock:
                    self._fault = 'Context unavailable'
                self.withdraw()
        def read():
            draining = False
            try:
                while not self._stop.is_set():
                    line = stream.readline(65)
                    if self._stop.is_set():
                        return
                    if not line:
                        break
                    if type(line) is not str or len(line) > 64 or draining:
                        self.cancel()
                        draining = type(line) is not str or not line.endswith('\n')
                        continue
                    self.command(line)
            except Exception:
                pass  # Never echo input, credential-like paste or exception data.
            finally:
                self.withdraw()
        self._thread = threading.Thread(target=monitor, daemon=True)
        self._input_thread = threading.Thread(target=read, daemon=True)
        self._thread.start()
        self._input_thread.start()
        return self

    def snapshot(self):
        with self._lock:
            result = {'input_mode': 'manual-terminal', 'gpio_used': False, 'audio_used': False,
                      'consent': self._consent, 'input_closed': self._input_closed,
                      'closed': self._closed, 'fault': self._fault, 'shown': self._shown}
        result['button'] = self.button.snapshot()
        return result

    def close(self):
        with self._lock:
            self._closed = True
            self._frame = None
            self._consent = False
            self._stop.set()
        self.button.close()
        for thread in (self._thread, self._input_thread):
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=.1)
        # Caller owns stdin. A blocked daemon reader may finish only at EOF/input;
        # it cannot dispatch after close. Do not close someone else's stream.
