"""CS-040 synthetic speaker bench: real speech, no phone/camera/network/provider."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import threading
import time

from .narration import NarrationController
from .pi_speech import EspeakSink

DESCRIPTION = {'objects': ['chair', 'table', 'stairs'], 'uncertain': True}


class ObservedSink:
    def __init__(self, sink, clock):
        self.sink, self.clock = sink, clock
        self.stops = []
        self.spoken = 0
        self.lock = threading.Lock()
    def speak(self, text):
        self.sink.speak(text)
        with self.lock:
            self.spoken += 1
    def stop(self):
        started = self.clock()
        self.sink.stop()
        with self.lock:
            self.stops.append((started, self.clock()))
    def snapshot(self):
        with self.lock:
            return self.spoken, list(self.stops)


def run_bench(sink, *, observe, emit=print, clock=time.monotonic,
              pause=lambda seconds: threading.Event().wait(seconds),
              interrupt_after=1.0, repetitions=1, bluetooth_recovery=False):
    """Synthetic priority/capture inputs; observations are human, not inferred.

    The caller owns the sink. The independent timer remains active while the
    operator answers questions. No network, raw images or device IDs are used.
    """
    observed = ObservedSink(sink, clock)
    controller = NarrationController(observed, clock=clock)
    stop = threading.Event()
    faults = []
    def timer():
        try:
            while not stop.wait(.01):
                controller.tick()
        except Exception:
            faults.append('Bench timer unavailable')
            controller.close()
    worker = threading.Thread(target=timer, daemon=True)
    worker.start()
    records = []
    summary = dict(mode='synthetic-speaker-bench', priority_input='synthetic',
        capture_input='synthetic', phone_used=False, backend_used=False,
        gemini_used=False, gpio_used=False, physical_audio_accepted=False,
        bluetooth_disconnect_reconnect_verified=False, complete=False, records=records)
    def begin(age=0):
        controller.set_priority(hazard=False, unavailable=False)
        return controller.begin_capture(capture_monotonic_s=clock()-age, consent=True)
    try:
        emit('SYNTHETIC BENCH: fixed object labels; no phone/backend/camera/Gemini or GPIO.')
        emit('Use the configured Pi speaker output. Answers describe audible behavior, not system readiness.')
        for repetition in range(1, repetitions+1):
            for kind in ('manual_cancel', 'hazard', 'unavailable'):
                emit(f'[{repetition}/{repetitions}] {kind}: speech starts; stop requested after {interrupt_after:g}s.')
                ticket = begin()
                delivered = ticket is not None and controller.deliver(ticket, DESCRIPTION)
                pause(interrupt_after)
                started = clock()
                if kind == 'manual_cancel':
                    controller.cancel()
                else:
                    controller.set_priority(hazard=kind == 'hazard', unavailable=kind == 'unavailable')
                elapsed = max(0, (clock()-started)*1000)
                emit('STOP requested. Measure any audible tail separately; software timing is not speaker latency.')
                controller.set_priority(hazard=False, unavailable=False)
                replay_blocked = not controller.deliver(ticket, DESCRIPTION)
                answer = observe(kind, 'Was the sentence audible, then interrupted without restarting?')
                records.append(dict(repetition=repetition, case=kind,
                    software_pass=bool(delivered and replay_blocked and sink.healthy()),
                    stop_call_ms=round(elapsed, 3), operator_pass=answer))
            emit(f'[{repetition}/{repetitions}] expiry: synthetic capture is 7s old; speech has about 1s remaining.')
            ticket = begin(7)
            delivered = ticket is not None and controller.deliver(ticket, DESCRIPTION)
            _, before = observed.snapshot()
            pause(1.3)
            _, after = observed.snapshot()
            expiry_stops = after[len(before):]
            independent_stop = bool(expiry_stops and ticket is not None
                                    and expiry_stops[0][0] >= ticket.expires_at)
            overshoot = (max(0, (expiry_stops[0][0]-ticket.expires_at)*1000)
                         if independent_stop else None)
            late_blocked = not controller.deliver(ticket, DESCRIPTION)
            controller.cancel()
            answer = observe('expiry', 'Did speech stop around the one-second deadline without restarting?')
            records.append(dict(repetition=repetition, case='expiry',
                software_pass=bool(delivered and independent_stop and late_blocked and sink.healthy()),
                timer_stop_after_deadline_ms=None if overshoot is None else round(overshoot, 3),
                operator_pass=answer))
            emit(f'[{repetition}/{repetitions}] late_result: expired synthetic result; expect no new narration.')
            ticket = begin(7.95)
            count, _ = observed.snapshot()
            pause(.1)
            rejected = not controller.deliver(ticket, DESCRIPTION)
            current, _ = observed.snapshot()
            controller.cancel()
            answer = observe('late_result', 'Was there no new narration for this expired result?')
            records.append(dict(repetition=repetition, case='late_result',
                software_pass=bool(ticket is not None and rejected and current == count and sink.healthy()),
                operator_pass=answer))
        if bluetooth_recovery:
            emit('RECOVERY: keep a way to stop the Pi locally. This test does not change Bluetooth routing.')
            emit('Disconnect the speaker while this fresh synthetic sentence is audible, then answer.')
            ticket = begin()
            delivered = ticket is not None and controller.deliver(ticket, DESCRIPTION)
            disconnected = observe('bluetooth_disconnect',
                'Was the sentence audible before you disconnected the speaker during playback?')
            # Explicit operator-reported loss, not inferred Bluetooth health.
            controller.set_priority(hazard=False, unavailable=True)
            count, _ = observed.snapshot()
            emit('Narration cancelled. Reconnect/select the speaker using the Pi audio controls; do not restart this bench.')
            reconnected = observe('bluetooth_reconnect',
                'After reconnecting, did the speaker remain silent with no old sentence resuming?')
            controller.set_priority(hazard=False, unavailable=False)
            replay_blocked = not controller.deliver(ticket, DESCRIPTION)
            unchanged, _ = observed.snapshot()
            fresh = heard = False
            # Unknown/no never authorizes the fresh recovery speech step.
            if disconnected is True and reconnected is True and sink.healthy():
                fresh_ticket = begin()
                fresh = fresh_ticket is not None and controller.deliver(fresh_ticket, DESCRIPTION)
                heard = observe('bluetooth_fresh',
                    'Did only this newly requested sentence play through the reconnected speaker?')
            controller.cancel()
            records.append(dict(repetition=1, case='bluetooth_operator_recovery',
                software_pass=bool(delivered and replay_blocked and unchanged == count and fresh and sink.healthy()),
                operator_pass=disconnected is True and reconnected is True and heard is True,
                disconnect_observed=disconnected, reconnect_silence_observed=reconnected,
                fresh_audio_observed=heard, automatic_route_detection=False))
            summary['bluetooth_recovery_attempted'] = True
        summary['complete'] = True
    finally:
        stop.set()
        controller.close()
        worker.join(timeout=1)
        summary['timer_fault'] = bool(faults or worker.is_alive())
        summary['software_checks_passed'] = bool(summary['complete'] and records
            and not summary['timer_fault'] and all(r['software_pass'] for r in records))
        summary['operator_reported_all_passed'] = bool(summary['complete'] and records
            and all(r['operator_pass'] is True for r in records))
    return summary


def ask(case, question):
    print(question + ' [y/n/u] ', end='', flush=True)
    line = sys.stdin.readline(16)
    if not line:
        raise EOFError()
    if not line.endswith('\n'):
        raise ValueError('Bounded observation input required')
    return {'y': True, 'n': False, 'u': None}.get(line.strip().lower())


def open_report(path):
    path = path.expanduser().resolve()
    repository = Path(__file__).resolve().parents[2]
    if path.is_relative_to(repository) or stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
        raise ValueError('Choose a private report directory outside the checkout')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(fd, 'w', encoding='utf-8')


def revision():
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=2)
        value = result.stdout.strip()
        if result.returncode == 0 and len(value) == 40 and all(c in '0123456789abcdef' for c in value):
            return value
    except Exception:
        pass
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--speak', action='store_true', help='Explicitly enable actual Pi speech for synthetic tests')
    parser.add_argument('--bluetooth-recovery', action='store_true',
                        help='Guided operator disconnect/reconnect and fresh-request test; no automatic routing')
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--interrupt-after', type=float, default=1.0)
    parser.add_argument('--output', type=Path, help='New JSON in an existing private directory outside Git')
    args = parser.parse_args(argv)
    if not args.speak or not 1 <= args.repetitions <= 20 or not .2 <= args.interrupt_after <= 3:
        parser.error('Use --speak, 1..20 repetitions and 0.2..3 seconds before interruption')
    report = sink = None
    summary = dict(mode='synthetic-speaker-bench', complete=False, physical_audio_accepted=False)
    status = 1
    try:
        if args.output:
            report = open_report(args.output)
        sink = EspeakSink()
        summary = run_bench(sink, observe=ask, repetitions=args.repetitions,
                            interrupt_after=args.interrupt_after, bluetooth_recovery=args.bluetooth_recovery)
        status = 0 if summary['software_checks_passed'] and summary['operator_reported_all_passed'] else 2
    except (KeyboardInterrupt, EOFError):
        summary['error'] = 'Bench interrupted; incomplete evidence'
        status = 130
    except Exception:
        summary['error'] = 'Bench unavailable; inspect installation/output and rerun'
    finally:
        if sink is not None:
            try:
                sink.close()
            except Exception:
                summary['error'] = 'Speech stop unavailable; inspect device'
                summary['complete'] = False
                status = 1
        summary['build_commit'] = revision()
        payload = json.dumps(summary, indent=2, allow_nan=False)+'\n'
        if report is not None:
            with report:
                report.write(payload)
        print(payload, end='')
    return status


if __name__ == '__main__':
    raise SystemExit(main())
