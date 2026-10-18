"""CS-027 opt-in same-process uploader terminal or GPIO21 input.

Input-only GPIO and audio each require opt-in. Primary-source unknown/hazard state preempts
context. Each worker owns its locks; never hold the frame lock across button,
policy, network, input or output calls.
"""
import copy
import json
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

    Terminal input is default; GPIO21 requires an explicit input adapter at start.
    start/read/emit injection exists for generated offline fixtures.
    """
    def __init__(self, session, priority, *, consent, ca_file=None, clock=clock_ms,
                 client=None, emit=print, audio=False, speech_sink=None, narration_factory=None,
                 menu=False, audio_ready=None):
        if consent is not True:
            raise ValueError('Explicit scene-sharing consent required')
        if type(audio) is not bool or (not audio and (speech_sink is not None or narration_factory is not None)):
            raise ValueError('Audio adapters require explicit audio opt-in')
        if type(menu) is not bool or (menu and not audio):
            raise ValueError('Crossing menu requires explicit audio opt-in')
        if audio_ready is not None and (not menu or not callable(audio_ready)):
            raise ValueError('Route readiness callback requires menu mode')
        self._menu_lock = threading.RLock()
        self._menu = self._menu_audio = None
        self._route_lost = False
        self._menu_last_level = False
        self._route_ready = audio_ready if audio_ready is not None else lambda: False
        self._binding = {key: session[key] for key in ('session_id', 'source_id', 'boot_id', 'mode')}
        self._client = client if client is not None else ContextClient(session, ca_file=ca_file)
        self._priority = priority
        self._clock = clock
        self._emit = emit
        self._lock = threading.Lock()
        self._frame = None
        self._camera = False
        self._gpio = False
        self._last_input_at = None
        self._consent = True
        self._level = False  # Explicit synthetic release for terminal mode only.
        self._closed = self._input_closed = False
        self._fault = None
        self._shown = 0
        self._stop = threading.Event()
        self._thread = self._input_thread = None
        self._audio = audio
        self._narration = self._speech = None
        self.button = None
        if audio:
            try:
                if narration_factory is None:
                    from backend.context.consumer import ContextNarration
                    narration_factory = ContextNarration
                if speech_sink is None:
                    from backend.context.pi_speech import EspeakSink
                    speech_sink = EspeakSink()
                self._speech = speech_sink
                if menu:
                    from .context_menu import CrossingMenu
                    from backend.context.menu_audio import FixedMenuAudio
                    from backend.context.speech_channels import OptionalSpeechChannels
                    self._menu = CrossingMenu()  # Evaluated scenario capabilities are not installed.
                    self._speech = OptionalSpeechChannels(speech_sink)
                    self._menu_audio = FixedMenuAudio(self._speech.menu, clock=lambda: clock()/1000)
                    speech_sink = self._speech.context
                    if not callable(getattr(narration_factory, 'request', None)):
                        raise ValueError('Completed-gesture narration API is required')
                self._narration = narration_factory(self.latest, self._client, speech_sink,
                    priority=self._audio_priority, consent=self._audio_consent, clock=clock)
            except Exception:
                if self._speech is not None:
                    try:
                        self._speech.close()
                    except Exception:
                        pass
                raise RuntimeError('Context audio unavailable; check narration installation and Pi speech setup') from None
        else:
            self.button = ContextButton(self.latest, self._client.start, clock=clock)

    def _audio_priority(self):
        ready, _, hazard, _ = self._state()
        if self._menu is not None:
            ready = ready and self._menu.state == 'idle' and self._audio_route_ready()
        return ready, hazard

    def _audio_route_ready(self):
        try:
            return not self._route_lost and self._route_ready() is True
        except Exception:
            return False

    def _audio_consent(self):
        with self._lock:
            return self._consent and not (self._closed or self._input_closed)

    def _stop_request(self):
        if self._narration is not None:
            self._narration.cancel()  # Stops speech before network cancellation.
        else:
            self.button.cancel()

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
            if self._narration is not None:
                self._stop_request()
            else:
                self.button.set_state(ready=False, consent=False, hazard=True)

    def _state(self):
        with self._lock:
            frame, camera, consent, level = self._frame, self._camera, self._consent, self._level
            closed = self._closed or self._input_closed or self._fault is not None
            gpio, input_at = self._gpio, self._last_input_at
        try:
            now = number(self._clock())
        except Exception:
            if self._menu is not None:
                with self._lock:
                    self._fault = 'Context clock unavailable'
            return False, False, True, False
        try:
            age = now - frame.metadata['capture_monotonic_ms'] if frame is not None else None
            ready, hazard = self._priority()
            input_fresh = not gpio or (input_at is not None and 0 <= now-input_at <= 100)
            ready = bool(not closed and camera and age is not None and 0 <= age <= 1500
                         and input_fresh and ready is True)
            return ready, consent, hazard, level
        except Exception:
            return False, False, True, False

    def _menu_events(self, events):
        for event in events:
            if event.kind == 'context':
                self._narration.request()
                continue
            self._stop_request()  # Cancel old provider/audio before any menu replacement.
            kind = 'unavailable' if event.kind == 'cancel' and event.reason == 'source' else event.kind
            ok = self._menu_audio.speak(kind, generation=event.generation,
                epoch=event.epoch, scenario=event.scenario)
            if not ok and event.kind in ('entry', 'selection', 'choose', 'confirmation'):
                self._menu.cancel('audio')
                self._menu_audio.update(audio_ready=False, priority_clear=False,
                                        epoch=tuple(self._binding.values()))

    def _menu_tick(self):
        with self._menu_lock:
            ready, consent, hazard, level = self._state()
            epoch = tuple(self._binding.values())
            if level is True and not self._menu_last_level:
                self._stop_request()  # An input edge may cancel early; never requests early.
            self._menu_last_level = level
            usable = self._menu_audio.update(audio_ready=self._audio_route_ready(),
                priority_clear=consent is True and hazard is False, epoch=epoch)
            if not usable:
                self._stop_request()
            try:
                now = None if self._fault == 'Context clock unavailable' else self._clock()
            except Exception:
                now = None
            self._menu_events(self._menu.sample(level, now_ms=now,
                consent=consent, ready=ready and hazard is False, audio_ready=usable, epoch=epoch))
            if self._menu.state == 'failed':
                self._stop_request(); self._menu_audio.close()
            self._narration.tick()

    def tick(self):
        if self._menu is not None:
            self._menu_tick()
            return
        ready, consent, hazard, level = self._state()
        if self._narration is not None:
            self._narration.sample(level)
            return  # The narration bridge owns the sole request/button slot.
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
            mode = 'GPIO21 input' if self._gpio else 'manual input'
            message = ('Context (' + mode + '; AI; uncertain): possible ' + ', '.join(labels) + '.'
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
        if command == 'status':
            from .context_report import bounded_status
            self._emit('Context status ' + json.dumps(bounded_status(self.snapshot()), sort_keys=True))
            return True
        if command == 'audio-off' and self._menu is not None:
            self._route_lost = True  # Recovery requires a new controller/explicit confirmation.
            self._menu_tick()
            return True
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
        self._stop_request()
        if self._menu is not None:
            with self._menu_lock:
                ready, consent, hazard, _ = self._state()
                self._menu_audio.update(audio_ready=self._audio_route_ready(),
                    priority_clear=consent is True and hazard is False,
                    epoch=tuple(self._binding.values()))
                self._menu_events(self._menu.cancel())

    def withdraw(self):
        with self._lock:
            self._consent = False
            self._input_closed = True
            self._level = False
            self._frame = None
        if self.button is not None:
            self.button.set_state(ready=False, consent=False, hazard=True)
        self._stop_request()
        if self._menu is not None:
            with self._menu_lock:
                self._menu.cancel('consent'); self._menu_audio.close()

    def start(self, stream=None, *, gpio_input=None):
        with self._lock:
            if self._thread is not None or self._closed:
                raise ValueError('Start context input once')
        if (stream is None) == (gpio_input is None):
            raise ValueError('Select exactly one terminal or GPIO input source')
        if gpio_input is not None:
            try:
                level = gpio_input.read()
                at = number(self._clock())
                if type(level) is not bool:
                    raise ValueError()
                with self._lock:
                    self._gpio = True
                    self._level, self._last_input_at = level, at
            except Exception:
                self.withdraw()
                raise RuntimeError('GPIO21 input unavailable') from None
        if self._narration is not None:
            self._narration.start()
        else:
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
        def read_gpio():
            try:
                while not self._stop.wait(.01):
                    level = gpio_input.read()
                    at = number(self._clock())
                    if type(level) is not bool:
                        raise ValueError()
                    with self._lock:
                        if self._closed or self._input_closed:
                            return
                        self._level, self._last_input_at = level, at
            except Exception:
                with self._lock:
                    self._fault = 'Context input unavailable'
            finally:
                self.withdraw()
        self._thread = threading.Thread(target=monitor, daemon=True)
        self._input_thread = threading.Thread(target=read_gpio if gpio_input is not None else read, daemon=True)
        self._thread.start()
        self._input_thread.start()
        return self

    def snapshot(self):
        with self._lock:
            result = {'input_mode': 'gpio21' if self._gpio else 'manual-terminal', 'gpio_used': self._gpio,
                      'audio_enabled': self._audio, 'audio_used': None if self._audio else False,
                      'audio_delivery_verified': False,
                      'consent': self._consent, 'input_closed': self._input_closed,
                      'closed': self._closed, 'fault': self._fault, 'shown': self._shown}
        if self._menu is not None:
            with self._menu_lock:
                result['menu'] = self._menu.snapshot()
        result['button'] = self.button.snapshot() if self.button is not None else None
        if self._narration is not None:
            snapshot = getattr(self._narration, 'snapshot', None)
            if callable(snapshot):
                state = snapshot()
                if type(state) is dict and type(state.get('button')) is dict:
                    result['button'] = state['button']
        return result

    def close(self):
        with self._lock:
            self._closed = True
            self._frame = None
            self._consent = False
            self._stop.set()
        if self._menu is not None:
            with self._menu_lock:
                self._menu.close(); self._menu_audio.close()
        if self._narration is not None:
            try:
                self._narration.close()
            except Exception:
                with self._lock:
                    self._fault = 'Audio stop unavailable; inspect device'
            finally:
                try:
                    self._speech.close()
                except Exception:
                    with self._lock:
                        self._fault = 'Audio stop unavailable; inspect device'
        else:
            self.button.close()
        for thread in (self._thread, self._input_thread):
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=.1)
        # Caller owns stdin. A blocked daemon reader may finish only at EOF/input;
        # it cannot dispatch after close. Do not close someone else's stream.
