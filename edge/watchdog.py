"""CS-026 independent policy lease; simulated-output supervision, not hardware."""
import argparse
import json
import threading
import time
import uuid
from .haptics import HapticScheduler, SimulatedOutput, clock_ms, number


class PolicyWatchdog:
    """Completed policy ticks renew a bounded lease; camera/network never feed it.

    The callback runs OUTSIDE the lease lock and must request outputs off without
    taking policy/camera/network locks. A blocked adapter or frozen process still
    needs a physical kill/hardware timeout. One instance/epoch; no fault recovery.
    """
    def __init__(self, on_fault, *, clock=clock_ms, timeout_ms=200):
        number(timeout_ms)
        if not 50 <= timeout_ms <= 250 or not callable(on_fault):
            raise ValueError('Use a local stop callback and 50..250ms lease')
        self.clock, self.on_fault, self.timeout_ms = clock, on_fault, timeout_ms
        self.lock = threading.RLock()
        self.fault = None
        self.closed = False
        self.last_now = None
        self.expires_ms = None
        self._stop = threading.Event()
        self._thread = None
        self.epoch = uuid.uuid4().hex
        now = number(clock())
        self.last_now = now
        self.expires_ms = now + timeout_ms

    def _check(self):
        try:
            now = number(self.clock())
            if now < self.last_now:
                raise ValueError('Clock reversed')
            self.last_now = now
            if now >= self.expires_ms:
                self.fault = self.fault or 'Policy lease expired'
        except Exception:
            self.fault = self.fault or 'Watchdog clock unavailable'
        return not (self.closed or self.fault)

    def deadline(self):
        with self.lock:
            return self.expires_ms if self._check() else None

    def feed(self):
        with self.lock:
            if not self._check():
                return False
            self.expires_ms = self.last_now + self.timeout_ms
            return True

    def tick(self):
        with self.lock:
            healthy = self._check()
            reason = self.fault or 'Watchdog closed'
        if not healthy:
            self._stop.set()
            self.on_fault(reason)
        return healthy

    def start(self):
        with self.lock:
            if self._thread is not None or self.closed or self.fault:
                raise ValueError('Start one healthy watchdog')
            self._thread = threading.Thread(target=self._run,daemon=True)
            self._thread.start()
        return self

    def _run(self):
        while not self._stop.wait(.01):
            if not self.tick():
                return

    def close(self):
        self._stop.set()
        with self.lock:
            self.closed = True
        # Never acquire a policy lock, even when that worker is frozen.
        self.on_fault('Watchdog closed')
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulate', action='store_true', required=True)
    parser.parse_args()
    clock = clock_ms
    output = SimulatedOutput()
    scheduler = HapticScheduler(output,clock=clock).start()
    watchdog = PolicyWatchdog(scheduler.trip,clock=clock,timeout_ms=250)
    scheduler.set_guard(watchdog.deadline)
    watchdog.start()
    initial = scheduler.snapshot()
    try:
        # Model completed policy work during initial cooldown, then a stalled
        # caller. No camera, network, credentials, enrollment or GPIO involved.
        for _ in range(12):
            watchdog.feed();time.sleep(.02)
        scheduler.set_ready(True)
        watchdog.feed()
        scheduler.pulse('left',500,valid_until_ms=clock()+1000)
        time.sleep(.4)
        state = scheduler.snapshot()
        print(json.dumps(dict(boot_id=watchdog.epoch,initial_outputs=initial['outputs'],
            initial_ready=initial['ready'],outputs=state['outputs'],fault=state['fault'],
            gpio_used=False,mode='simulation',credentials_loaded=False)))
    finally:
        watchdog.close();scheduler.close()


if __name__ == '__main__':
    main()
