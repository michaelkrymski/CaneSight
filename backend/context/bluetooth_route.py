"""Opt-in Linux route observations, bounded helpers and latched loss.

No pairing, connection, routing changes or audible-delivery claims. Probe work
never runs under the state lock; an independent watchdog expires stalled work.
"""
import json
import math
import os
import re
import selectors
import signal
import subprocess
import threading
import time

MAX_AGE_S = .350
POLL_S = .100
COMMAND_TIMEOUT_S = .100
MAX_OUTPUT = 65536


def target(sink, device):
    match = re.fullmatch(r'bluez_output\.([0-9A-Fa-f]{2}(?:_[0-9A-Fa-f]{2}){5})\.[A-Za-z0-9_.-]{1,32}', sink) if type(sink) is str else None
    path = re.fullmatch(r'/org/bluez/hci[0-9]{1,3}/dev_([0-9A-Fa-f]{2}(?:_[0-9A-Fa-f]{2}){5})', device) if type(device) is str else None
    if not match or not path or match[1].upper() != path[1].upper():
        raise ValueError('Configure matching Bluetooth sink and BlueZ device path')
    return sink, device


def command(args):
    """Read at most 64 KiB from one owned helper; no shell or stderr capture."""
    if os.name != 'posix':
        raise ValueError('Bounded route helpers require POSIX')
    process = None
    try:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=True,
            env={**os.environ, 'LC_ALL': 'C'})
        deadline = time.monotonic()+COMMAND_TIMEOUT_S
        data = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline-time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise ValueError()
                chunk = os.read(process.stdout.fileno(), min(4096, MAX_OUTPUT+1-len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_OUTPUT:
                    raise ValueError()
        if process.wait(timeout=max(.001, deadline-time.monotonic())) != 0:
            raise ValueError()
        return data.decode('utf-8')
    except Exception:
        raise ValueError('Bluetooth route observation unavailable') from None
    finally:
        if process is not None:
            try:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                try:
                    process.wait(timeout=.2)
                finally:
                    process.stdout.close()
            except Exception:
                raise ValueError('Bluetooth route observation unavailable') from None



class RouteProbe:
    def __init__(self, sink, device, *, run=command, stream=lambda: None, clock=time.monotonic):
        self.sink, self.device = target(sink, device)
        self.run, self.stream, self.clock = run, stream, clock
        self._missing = None

    def __call__(self):
        # paplay is explicitly bound to this sink; the global default is not used.
        raw = self.run(['/usr/bin/pactl', '--format=json', 'list', 'sinks'])
        if type(raw) is not str or len(raw.encode('utf-8')) > MAX_OUTPUT:
            return False
        sinks = json.loads(raw)
        if type(sinks) is not list or not 1 <= len(sinks) <= 64:
            return False
        matches = [s for s in sinks if type(s) is dict and s.get('name') == self.sink]
        if len(matches) != 1:
            return False
        sink = matches[0]
        volume = sink.get('volume')
        if (sink.get('state') not in ('RUNNING', 'IDLE', 'SUSPENDED')
                or sink.get('mute') is not False
                or type(sink.get('properties')) is not dict
                or sink['properties'].get('device.api') not in ('bluez', 'bluez5')
                or type(volume) is not dict or not 1 <= len(volume) <= 8
                or any(type(v) is not dict or type(v.get('value')) is not int
                       or not 0 < v['value'] <= 2**31-1 for v in volume.values())):
            return False
        connected = self.run(['/usr/bin/busctl', '--system', 'get-property', 'org.bluez',
            self.device, 'org.bluez.Device1', 'Connected'])
        if type(connected) is not str or connected.strip() != 'b true':
            return False
        active = self.stream()
        if active is None:
            self._missing = None
            return True
        # A server can move a live stream even when the original sink survives.
        raw = self.run(['/usr/bin/pactl', '--format=json', 'list', 'sink-inputs'])
        if type(raw) is not str or len(raw.encode('utf-8')) > MAX_OUTPUT:
            return False
        inputs = json.loads(raw)
        if type(inputs) is not list or len(inputs) > 128:
            return False
        matches = [i for i in inputs if type(i) is dict and type(i.get('properties')) is dict
                   and i['properties'].get('media.name') == active]
        if len(matches) > 1:
            return False
        if matches:
            self._missing = None
            return (type(sink.get('index')) is int and type(matches[0].get('sink')) is int
                    and matches[0]['sink'] == sink['index'])
        # Stream registration/completion can race the observation. Bound missing
        # registration to 200ms; a hung player cannot preserve readiness forever.
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now):
            return False
        if self._missing is None or self._missing[0] != active:
            self._missing = (active, now)
        return 0 <= now-self._missing[1] < .200


class BluetoothRouteMonitor:
    """Loss/errors/clock faults latch; reconnect requires a new monitor/run.

    Cache timestamps anchor to probe START, never completion. Callbacks must
    return promptly and stop only owned optional speech. No event/audio queue.
    """
    def __init__(self, probe, on_loss, *, clock=time.monotonic):
        self.probe, self.on_loss, self.clock = probe, on_loss, clock
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._started = self._closed = self._fault = False
        self._observed = self._last = None
        self._threads = ()

    def _now(self):
        with self._lock:
            value = self.clock()
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError()
            if self._last is not None and value < self._last:
                raise ValueError()
            self._last = value
            return value

    def _fail(self):
        with self._lock:
            notify = not (self._fault or self._closed)
            self._fault = True
            self._observed = None
        if notify:
            try:
                self.on_loss()
            except Exception:
                pass  # Fault is already latched; no raw callback details escape.
        return False

    def refresh(self):
        with self._lock:
            if self._fault or self._closed:
                return False
        try:
            began = self._now()
            valid = self.probe() is True
            ended = self._now()
            if not valid or not 0 <= ended-began < MAX_AGE_S:
                return self._fail()
            with self._lock:
                if self._fault or self._closed:
                    return False
                self._observed = began
            return True
        except Exception:
            return self._fail()

    def ready(self):
        try:
            now = self._now()
            with self._lock:
                if not self._started or self._closed or self._fault:
                    return False
                fresh = self._observed is not None and 0 <= now-self._observed < MAX_AGE_S
            return True if fresh else self._fail()
        except Exception:
            return self._fail()

    def start(self):
        with self._lock:
            if self._started or self._closed or self._fault:
                raise ValueError('Start Bluetooth route monitor once')
            self._started = True
        # Complete initial observation before audio controllers test sink health.
        if not self.refresh():
            raise ValueError('Bluetooth route unavailable; inspect setup privately')
        def poll():
            while not self._stop.wait(POLL_S):
                if not self.refresh(): return
        def watchdog():
            while not self._stop.wait(.010):
                if not self.ready(): return
        self._threads = tuple(threading.Thread(target=fn, daemon=True) for fn in (poll, watchdog))
        for thread in self._threads: thread.start()
        return self

    def close(self):
        with self._lock:
            self._closed = True
            self._observed = None
        self._stop.set()
        for thread in self._threads:
            if thread is not threading.current_thread(): thread.join(timeout=.2)


def main(argv=None):
    """Read-only single observation; never plays, pairs or starts a monitor."""
    import argparse
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--check', action='store_true', required=True)
    parser.parse_args(argv)
    result = dict(mode='bluetooth-route-check', complete=False, route_observed=False,
                  automatic_monitor_running=False, physical_audio_accepted=False)
    try:
        probe = RouteProbe(os.environ.get('CANESIGHT_BLUETOOTH_SINK'),
                           os.environ.get('CANESIGHT_BLUEZ_DEVICE'))
        result['route_observed'] = probe() is True
        result['complete'] = True
    except Exception:
        result['error'] = 'Bluetooth route check unavailable; inspect configuration privately'
    print(json.dumps(result, sort_keys=True))
    return 0 if result['route_observed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
