"""Opt-in Pi eSpeak NG sink, optionally with monitored/pinned Bluetooth output.

No pairing/global route changes, shell, raw provider prose or audio files. Process termination
cannot prove a Bluetooth speaker has flushed buffered audio; verify on device.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import uuid

from .narration import UNAVAILABLE, render_description
from .menu_audio import ALL_PHRASES


def permitted_text(text):
    if type(text) is str and text in ALL_PHRASES:
        return True
    if type(text) is not str or len(text) > 160 or len(text.split()) > 20:
        return False
    if text == UNAVAILABLE:
        return True
    prefix = 'AI description, uncertain: Possible '
    if not text.startswith(prefix) or not text.endswith('.'):
        return False
    labels = text[len(prefix):-1].split(' and ')
    return text == render_description({'objects': labels, 'uncertain': True})


class EspeakSink:
    """Owned speech/playback processes, no queue/retry and bounded kill/reap.

    Install espeak-ng and select/test the Bluetooth output as the same Pi user
    before opting in. A successful process is not evidence of speaker delivery.
    """
    def __init__(self, executable='/usr/bin/espeak-ng', *, bluetooth_sink=None,
                 bluez_device=None, paplay='/usr/bin/paplay', monitor_factory=None):
        path = Path(executable)
        if os.name != 'posix' or not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError('Configure an installed absolute eSpeak NG executable')
        self._executable = str(path)
        self._lock = threading.RLock()
        self._process = self._playback = None
        self._fault = self._closed = False
        self._route = None
        self._sink_name = None
        self._stream_name = None
        if bluetooth_sink is None and bluez_device is None:
            bluetooth_sink = os.environ.get('CANESIGHT_BLUETOOTH_SINK')
            bluez_device = os.environ.get('CANESIGHT_BLUEZ_DEVICE')
        if bluetooth_sink is not None or bluez_device is not None:
            if monitor_factory is None and sys.platform != 'linux':
                raise ValueError('Automatic Bluetooth route monitoring requires Linux')
            from .bluetooth_route import RouteProbe, BluetoothRouteMonitor
            probe = RouteProbe(bluetooth_sink, bluez_device, stream=self._active_stream)
            player = Path(paplay)
            if not player.is_absolute() or not player.is_file() or not os.access(player, os.X_OK):
                raise ValueError('Configure an installed absolute paplay executable')
            self._paplay, self._sink_name = str(player), probe.sink
            factory = BluetoothRouteMonitor if monitor_factory is None else monitor_factory
            self._route = factory(probe, self._route_lost)
            try:
                self._route.start()
            except Exception:
                self._route.close()
                raise ValueError('Bluetooth route unavailable; inspect setup privately') from None

    def _active_stream(self):
        # Called by the probe without the sink lock, avoiding callback lock cycles.
        player = self._playback
        return self._stream_name if player is not None and player.poll() is None else None

    def _route_lost(self):
        with self._lock:
            self._fault = True
            self.stop()

    def healthy(self):
        with self._lock:
            if self._route is not None and not self._route.ready():
                self._fault = True
                self.stop()
            for field in ('_process', '_playback'):
                process = getattr(self, field)
                if process is not None:
                    code = process.poll()
                    if code is not None:
                        setattr(self, field, None)
                        self._fault = self._fault or code != 0
            if self._fault:
                self.stop()
            return not (self._fault or self._closed)

    def speak(self, text):
        with self._lock:
            if not permitted_text(text) or not self.healthy():
                raise ValueError('Speech unavailable')
            self.stop()
            try:
                args = [self._executable, '--stdin']
                if self._route is not None:
                    args.append('--stdout')
                self._process = subprocess.Popen(args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE if self._route is not None else subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, start_new_session=True)
                if self._route is not None:
                    self._stream_name = 'CaneSight-'+uuid.uuid4().hex
                    self._playback = subprocess.Popen([self._paplay, '--device='+self._sink_name,
                        '--stream-name='+self._stream_name, '--client-name=CaneSight'],
                        stdin=self._process.stdout, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, start_new_session=True)
                    self._process.stdout.close()
                # At most 160 characters: below the pipe's atomic-write bound.
                # Text is data on stdin, never an argument or a shell command.
                self._process.stdin.write(text.encode('utf-8'))
                self._process.stdin.close()
            except Exception:
                self._fault = True
                self.stop()
                raise RuntimeError('Speech unavailable') from None

    def stop(self):
        with self._lock:
            failed = False
            # Playback is killed before generation; never target another process.
            for field in ('_playback', '_process'):
                process = getattr(self, field)
                if process is None:
                    continue
                try:
                    if process.poll() is None:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    process.wait(timeout=.2)
                    for pipe in (process.stdin, process.stdout):
                        if pipe is not None and not pipe.closed: pipe.close()
                    setattr(self, field, None)
                except Exception:
                    self._fault = failed = True
            if failed:
                raise RuntimeError('Speech stop unavailable; replace adapter') from None

    def close(self):
        try:
            with self._lock:
                self._closed = True
                self.stop()
        finally:
            if self._route is not None:
                self._route.close()
