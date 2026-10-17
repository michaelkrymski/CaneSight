"""Opt-in Pi eSpeak NG sink using the OS-selected output (e.g. Bluetooth).

No pairing/routing, shell, raw provider prose or audio files. Process termination
cannot prove a Bluetooth speaker has flushed buffered audio; verify on device.
"""
import os
from pathlib import Path
import signal
import subprocess
import threading

from .narration import UNAVAILABLE, render_description


def permitted_text(text):
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
    """One disposable speech process, no queue/retry and bounded kill/reap.

    Install espeak-ng and select/test the Bluetooth output as the same Pi user
    before opting in. A successful process is not evidence of speaker delivery.
    """
    def __init__(self, executable='/usr/bin/espeak-ng'):
        path = Path(executable)
        if os.name != 'posix' or not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError('Configure an installed absolute eSpeak NG executable')
        self._executable = str(path)
        self._lock = threading.RLock()
        self._process = None
        self._fault = self._closed = False

    def healthy(self):
        with self._lock:
            if self._process is not None:
                code = self._process.poll()
                if code is not None:
                    self._process = None
                    self._fault = self._fault or code != 0
            return not (self._fault or self._closed)

    def speak(self, text):
        with self._lock:
            if not permitted_text(text) or not self.healthy():
                raise ValueError('Speech unavailable')
            self.stop()
            try:
                self._process = subprocess.Popen([self._executable, '--stdin'],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True)
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
            process = self._process
            if process is None:
                return
            try:
                if process.poll() is None:
                    # Only this adapter's new process group; never system-wide
                    # pkill, audio-server restart or another cue's playback.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=.2)
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                self._process = None
            except Exception:
                self._fault = True
                raise RuntimeError('Speech stop unavailable; replace adapter') from None

    def close(self):
        with self._lock:
            self._closed = True
            self.stop()
