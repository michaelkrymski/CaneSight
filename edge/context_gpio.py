"""Opt-in input-only adapter for issue #68's active-high BCM GPIO21 button."""


class GPIO21Input:
    """No internal pull, GPIO callbacks, debounce layer, or motor/output pins.

    The installed circuit must drive a stable 3.3 V/0 V level. ContextButton owns
    the release-to-arm/30 ms debounce/cooldown policy; this adapter only reads.
    """
    def __init__(self, *, device_factory=None):
        self._device = None
        try:
            if device_factory is None:
                from gpiozero import DigitalInputDevice
                device_factory = DigitalInputDevice
            self._device = device_factory(21, pull_up=None, active_state=True, bounce_time=None)
        except Exception:
            raise RuntimeError('GPIO21 input unavailable; inspect installation and wiring') from None

    def read(self):
        try:
            if self._device is None:
                raise ValueError()
            value = self._device.value
            if type(value) not in (bool, int, float) or value not in (0, 1):
                raise ValueError()
            return bool(value)
        except Exception:
            raise RuntimeError('GPIO21 input unavailable') from None

    def close(self):
        device, self._device = self._device, None
        if device is not None:
            try:
                device.close()
            except Exception:
                raise RuntimeError('GPIO21 cleanup unavailable; inspect device') from None


def main(argv=None):
    """Raw input observation only; no context request, camera, audio or motors."""
    import argparse
    import math
    from pathlib import Path
    import time
    from .context_report import ContextRunReport, UnsupportedReportPlatform
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--observe', action='store_true', help='Explicitly open only BCM21 as an input')
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--output', type=Path, required=True, help='New JSON in a private directory outside Git')
    args = parser.parse_args(argv)
    if not args.observe or not math.isfinite(args.seconds) or not 1 <= args.seconds <= 120:
        parser.error('Use --observe and 1..120 seconds')
    report, device = ContextRunReport(), None
    report.data.update(mode='gpio21-input-observation', gpio_used=None,
        context_requests_used=False, camera_used=False, backend_used=False,
        gpio_input_verified=False, raw_rising_edges=0, raw_falling_edges=0, samples=0)
    status = 1
    try:
        report.open(args.output, audio=False, gpio=True)
        device = GPIO21Input()
        previous = None
        deadline = time.monotonic()+args.seconds
        print('BCM21 INPUT ONLY: release, press, hold, release. No requests, speaker or motor GPIO.')
        while time.monotonic() < deadline:
            value = device.read()
            report.data['gpio_used'] = True
            report.data['samples'] += 1
            if previous is None:
                report.data['initially_high'] = value
            elif value != previous:
                key = 'raw_rising_edges' if value else 'raw_falling_edges'
                report.data[key] += 1
            if value != previous:
                print('HIGH (pressed)' if value else 'LOW (released)', flush=True)
            previous = value
            time.sleep(.01)
        report.data.update(complete=True, outcome='finished')
        status = 0
    except KeyboardInterrupt:
        report.data['outcome'] = 'interrupted'
        status = 130
    except UnsupportedReportPlatform as error:
        print(str(error), flush=True)
    except Exception:
        report.data['outcome'] = 'unavailable'
        print('GPIO21 observation unavailable; inspect installation, permissions and wiring')
    finally:
        if device is not None:
            try:
                device.close()
            except Exception:
                report.data.update(complete=False, outcome='cleanup-unavailable')
                status = 1
        report.finish()
    return status


if __name__ == '__main__':
    raise SystemExit(main())
