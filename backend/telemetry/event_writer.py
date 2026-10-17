"""Bounded, lossy event writer. A stalled database never runs in the API process."""
from collections import OrderedDict
from functools import partial
import multiprocessing
import queue
import time
import uuid

from .event_store import Event, PostgresStore, stream_id


def worker(commands, results, stop, factory):
    try:
        store = factory()
    except Exception:
        return
    purge_at = 0
    while not stop.is_set():
        now = time.monotonic()
        if now >= purge_at:
            try:
                store.purge()
            except Exception:
                pass
            purge_at = now + 30
        try:
            kind, value = commands.get(timeout=.25)
        except queue.Empty:
            continue
        try:
            if kind == 'event':
                store.insert(value)
            elif kind == 'delete':
                identifier, attempt = value
                store.delete(identifier)
            else:
                continue
            status = 'deleted'
        except Exception:
            status = 'failed'  # Never return exception/SQL/config text across the boundary.
        if kind == 'delete':
            try:
                results.put_nowait((identifier, attempt, status))
            except queue.Full:
                pass  # Unknown receipt requires explicit retry, never a false success.


class EventWriter:
    def __init__(self, config_file=None, *, factory=None, capacity=32):
        if type(capacity) is not int or not 1 <= capacity <= 128:
            raise ValueError('Invalid event queue capacity')
        self.context = multiprocessing.get_context('spawn')
        self.commands = self.context.Queue(maxsize=capacity)
        self.results = self.context.Queue(maxsize=32)
        self.stop = self.context.Event()
        self.factory = factory or partial(PostgresStore, config_file)
        self.process = None
        self.closed = False
        self.dropped = 0
        self.receipts = OrderedDict()
        self.attempts = OrderedDict()

    def start(self):
        if self.closed or self.process is not None:
            raise ValueError('Event writer may be started once')
        self.process = self.context.Process(target=worker,
            args=(self.commands, self.results, self.stop, self.factory), daemon=True)
        self.process.start()

    def _put(self, kind, value):
        if self.closed or self.process is None or not self.process.is_alive():
            return False
        try:
            self.commands.put_nowait((kind, value))
            return True
        except (queue.Full, ValueError, OSError):
            return False

    def submit(self, event):
        try:
            if type(event) is not Event:
                raise ValueError('Minimal events only')
            event.values()
        except (ValueError, TypeError, OverflowError):
            self.dropped += 1
            return False
        accepted = self._put('event', event)
        self.dropped += not accepted
        return accepted

    def delete(self, identifier):
        stream_id(identifier)
        # A receipt can only be trusted for this attempt after the previous
        # receipts have been drained. Queue acceptance is not deletion evidence.
        self.deletion_status(identifier)
        attempt = str(uuid.uuid4())
        if not self._put('delete', (identifier, attempt)):
            return False
        self.attempts[identifier] = attempt
        self.attempts.move_to_end(identifier)
        while len(self.attempts) > 32:
            self.attempts.popitem(last=False)
        self._receipt(identifier, 'queued')
        return True

    def _receipt(self, identifier, status):
        self.receipts[identifier] = status
        self.receipts.move_to_end(identifier)
        while len(self.receipts) > 32:
            self.receipts.popitem(last=False)

    def deletion_status(self, identifier):
        stream_id(identifier)
        for _ in range(32):
            try:
                key, attempt, status = self.results.get_nowait()
                if self.attempts.get(key) == attempt:
                    self._receipt(key, status)
            except queue.Empty:
                break
            except (OSError, ValueError):
                return 'unknown'
        return self.receipts.get(identifier, 'unknown')

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stop.set()
        if self.process is not None:
            self.process.join(.25)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(1)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(1)
        for channel in (self.commands, self.results):
            channel.cancel_join_thread()
            channel.close()
