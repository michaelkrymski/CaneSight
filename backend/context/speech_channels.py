"""Two bounded optional-speech owners over one local sink; no audio queue.

A controller's idle/expiry stop cannot kill the other controller's current
speech. Global preemption remains explicit through stop(); recovery never plays.
"""
import threading


class OptionalSpeechChannels:
    def __init__(self, sink):
        self._sink = sink
        self._lock = threading.RLock()
        self._owner = None
        self._closed = self._fault = False
        self.context = _Channel(self)
        self.menu = _Channel(self)

    def _stop(self):
        self._owner = None
        try:
            self._sink.stop()
        except Exception:
            self._fault = True
            raise

    def stop(self):
        with self._lock:
            self._stop()

    def close(self):
        with self._lock:
            self._closed = True
            try:
                self._stop()
            finally:
                self._sink.close()


class _Channel:
    def __init__(self, parent):
        self._parent = parent
        self._closed = False

    def healthy(self):
        with self._parent._lock:
            p = self._parent
            if self._closed or p._closed or p._fault:
                return False
            try:
                return p._sink.healthy() is True
            except Exception:
                p._fault = True
                return False

    def speak(self, text):
        with self._parent._lock:
            p = self._parent
            if not self.healthy():
                raise RuntimeError('Optional speech unavailable')
            try:
                p._stop()
                p._owner = self
                p._sink.speak(text)
            except Exception:
                p._fault = True
                try:
                    p._stop()
                except Exception:
                    pass
                raise

    def stop(self):
        with self._parent._lock:
            if self._parent._owner is self:
                self._parent._stop()

    def close(self):
        with self._parent._lock:
            self._closed = True
            self.stop()
