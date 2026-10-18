"""CS-025 bounded private metadata trace; never images, GPS or credentials."""
import json
import os
from pathlib import Path
import queue
import threading

FIELDS = frozenset(('session_id','source_id','boot_id','seq','mode',
    'capture_monotonic_ms','received_ms','capture_deadline_ms','software_command_observed_ms',
    'capture_age_interval_ms','hazards','channels','accepted','reason'))


class DecisionTrace:
    """Nonblocking producer, single disk writer, <=64 queued /1024 total records.

    Output must be new/outside checkout in a private parent. Incomplete/dropped
    traces are explicitly reported; logging never renews evidence or blocks policy.
    """
    def __init__(self, path, *, provenance='enrolled-session', output_mode='simulation'):
        path=Path(path)
        if provenance not in ('enrolled-session','synthetic-fixture'):
            raise ValueError('Explicit trace provenance required')
        if output_mode not in ('simulation', 'gpio'):
            raise ValueError('Explicit supported trace output mode required')
        if path.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
            raise ValueError('Private trace must stay outside checkout')
        self.stream=os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8')
        self.provenance=provenance
        self.output_mode=output_mode
        self.pending=queue.Queue(maxsize=64)
        self.lock=threading.Lock()
        self.stop=threading.Event()
        self.submitted=self.written=self.dropped=0
        self.error=False
        self.thread=threading.Thread(target=self._run,daemon=True)
        self.thread.start()

    def record(self, event):
        if set(event) != FIELDS:
            raise ValueError('Closed trace fields required')
        raw=json.dumps(dict(event,schema_version=1,input_kind=self.provenance,output_mode=self.output_mode),allow_nan=False,separators=(',',':'))+'\n'
        if len(raw.encode('utf-8'))>2048:
            raise ValueError('Trace record exceeds bound')
        with self.lock:
            if self.stop.is_set() or self.error or self.submitted>=1024:
                self.dropped+=1
                return False
            try:self.pending.put_nowait(raw)
            except queue.Full:
                self.dropped+=1
                return False
            self.submitted+=1
            return True

    def _run(self):
        try:
            while not self.stop.is_set() or not self.pending.empty():
                try:raw=self.pending.get(timeout=.05)
                except queue.Empty:continue
                self.stream.write(raw)
                self.stream.flush()
                with self.lock:self.written+=1
        except Exception:
            with self.lock:self.error=True
        finally:
            try:self.stream.close()
            except Exception:
                with self.lock:self.error=True

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
        return self.summary()

    def summary(self):
        with self.lock:
            closed=not self.thread.is_alive()
            return dict(submitted=self.submitted,written=self.written,dropped=self.dropped,
                error=self.error,closed=closed,complete=bool(closed and not self.error
                    and not self.dropped and self.written==self.submitted and self.written>0),
                output_mode=self.output_mode,input_kind=self.provenance)
