"""CS-023 explicit active-high GPIO output adapter and bounded bench command.

Imports never open GPIO. The uploader/policy defaults to simulated outputs.
BCM pins must be chosen from the reviewed circuit; no wiring is inferred here.
"""
import argparse
import json
import signal
import threading
import time

from .haptics import CHANNELS, HapticScheduler, Limits, clock_ms, number


class GPIOOutput:
    """Two exclusively claimed active-high driver inputs; no PWM or pulse queue.

    Own this adapter outside the scheduler context so scheduler shutdown requests
    off before adapter cleanup releases the pins. GPIO writes acknowledge software
    requests only; they cannot verify electrical off state or a stopped motor.
    """
    mode = 'gpio'
    gpio_used = True

    @staticmethod
    def validate_configuration(left_bcm, right_bcm, active_high):
        pins = (left_bcm, right_bcm)
        if (any(type(pin) is not int or not 2 <= pin <= 27 or pin == 21 for pin in pins)
                or left_bcm == right_bcm):
            raise ValueError('Choose distinct BCM 2..27 outputs excluding the BCM21 button')
        if active_high is not True:
            raise ValueError('This adapter requires explicitly verified active-high drivers')

    def __init__(self, *, left_bcm, right_bcm, active_high, device_factory=None):
        self.validate_configuration(left_bcm, right_bcm, active_high)
        pins = (left_bcm, right_bcm)
        self._lock = threading.Lock()
        self._devices = {}
        self._closed = self._faulted = False
        self._cleanup_ok = True
        try:
            if device_factory is None:
                from gpiozero import DigitalOutputDevice
                device_factory = DigitalOutputDevice
            for name, pin in zip(CHANNELS, pins):
                self._devices[name] = device_factory(pin, active_high=True, initial_value=False)
        except BaseException as error:
            self.close()
            if not isinstance(error, Exception):
                raise
            raise RuntimeError('Motor GPIO initialization unavailable; inspect pins and installation') from None

    def _off_all(self):
        ok = True
        for device in self._devices.values():
            try:
                device.off()
            except Exception:
                ok = False
        return ok

    def write(self, channel, enabled):
        if channel not in CHANNELS or type(enabled) is not bool:
            raise ValueError('Unknown channel/state')
        with self._lock:
            if self._closed or (self._faulted and enabled):
                raise RuntimeError('Motor GPIO unavailable; open a new adapter after inspection')
            try:
                device = self._devices[channel]
                if enabled:
                    device.on()
                else:
                    device.off()
            except Exception:
                self._faulted = True
                self._off_all()  # Attempt the peer even if the failed channel cannot stop.
                raise RuntimeError('Motor GPIO write unavailable; both off requested') from None

    def close(self):
        with self._lock:
            if self._closed:
                return self._cleanup_ok
            self._closed = True
            self._cleanup_ok = self._off_all()
            for device in self._devices.values():
                try:
                    device.close()
                except Exception:
                    self._cleanup_ok = False
            self._devices.clear()
            return self._cleanup_ok

    def __enter__(self):
        if self._closed:
            raise RuntimeError('Motor GPIO adapter is closed')
        return self

    def __exit__(self, *exc):
        if not self.close() and exc[0] is None:
            raise RuntimeError('Motor GPIO cleanup unavailable; inspect physical off state')


def bench(output, *, channels=(), duration_ms=150, clock=clock_ms, sleep=time.sleep):
    """One explicit bench stimulus, never interpreted as a sensor observation."""
    number(duration_ms)
    if not 0 < duration_ms <= Limits().max_pulse_ms:
        raise ValueError('Bench pulse must be greater than zero and at most 500 ms')
    if channels:
        channels = HapticScheduler._names(channels)
    with HapticScheduler(output, clock=clock) as scheduler:
        if channels:
            # Initial cooldown, pulse caps, original deadline and independent expiry
            # all remain owned by the existing scheduler.
            sleep(scheduler.limits.min_off_ms / 1000 + .01)
            if not scheduler.set_ready(True):
                raise RuntimeError('Bench scheduler unavailable')
            if not scheduler.pulse(channels, duration_ms, valid_until_ms=clock() + duration_ms):
                raise RuntimeError('Bench pulse refused')
            sleep(duration_ms / 1000)
            if scheduler.tick()['fault']:
                raise RuntimeError('Bench scheduler fault; inspect timing and output')
    result = scheduler.snapshot()
    if result['fault'] or any(value is not False for value in result['outputs'].values()):
        raise RuntimeError('Bench shutdown unavailable; inspect physical off state')
    return dict(result, bench_only=True, physical_acceptance=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-gpio', action='store_true')
    parser.add_argument('--left-bcm', type=int, required=True)
    parser.add_argument('--right-bcm', type=int, required=True)
    parser.add_argument('--active-high', action='store_true')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--off-only', action='store_true')
    action.add_argument('--pulse', choices=('left', 'right', 'both'))
    parser.add_argument('--duration-ms', type=float, default=150)
    args = parser.parse_args(argv)
    if not args.enable_gpio or not args.active_high:
        parser.error('Explicit --enable-gpio and verified --active-high are required')
    try:
        number(args.duration_ms)
        if not 0 < args.duration_ms <= Limits().max_pulse_ms:
            raise ValueError()
    except ValueError:
        parser.error('Use a finite pulse duration greater than zero and at most 500 ms')
    channels = CHANNELS if args.pulse == 'both' else (args.pulse,) if args.pulse else ()
    previous_term = signal.getsignal(signal.SIGTERM)
    def terminate(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, terminate)
    try:
        with GPIOOutput(left_bcm=args.left_bcm, right_bcm=args.right_bcm,
                        active_high=args.active_high) as output:
            result = bench(output, channels=channels, duration_ms=args.duration_ms)
        result['adapter_closed'] = True
        print(json.dumps(result))
        return 0
    except KeyboardInterrupt:
        print('Motor bench interrupted; off and cleanup requested. Inspect physical off state.')
        return 130
    except Exception:
        print('Motor bench unavailable; inspect GPIO installation, wiring and physical off state.')
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous_term)


if __name__ == '__main__':
    raise SystemExit(main())
