"""Explicit synthetic crossing-menu interaction bench; no traffic observations.

Optional real GPIO21/audio, no camera/network/Gemini/phone/motor output. Missing
production scenario adapters are never replaced by simulated live observations.
"""
import argparse
import json
from pathlib import Path
import sys
import threading
import time

from .context_menu import CrossingMenu, SCENARIOS
from .context_report import ContextRunReport, UnsupportedReportPlatform


class SilentMenuSink:
    def __init__(self): self.current = None; self.closed = False
    def speak(self, text): self.current = text
    def stop(self): self.current = None
    def healthy(self): return not self.closed
    def close(self): self.closed = True; self.stop()


class MenuBench:
    """One local state machine, no event FIFO, no model or analysis job."""
    def __init__(self, sink, *, synthetic_adapters=False, gpio=None, clock=lambda: time.monotonic()*1000):
        from backend.context.menu_audio import FixedMenuAudio
        self.clock, self.gpio = clock, gpio
        self.core = CrossingMenu(supported=SCENARIOS if synthetic_adapters else ())
        self.audio = FixedMenuAudio(sink, clock=lambda: clock()/1000)
        self.lock = threading.RLock()
        self.flags = dict(consent=True, ready=True, audio_ready=True,
                          epoch=('synthetic-session','synthetic-pi','synthetic-boot','replay'))
        self.priority_clear = True
        self.level = gpio.read() if gpio is not None else False
        self.input_at = clock()
        self.last_event = None
        self.context_gestures = 0
        self.counts = {kind: 0 for kind in ('context','entry','choose','selection','confirmation','activate','cancel','unavailable')}
        self.fault = False
        self.stop = threading.Event()
        self.worker = self.reader = None
        self.synthetic_adapters = synthetic_adapters

    def _apply(self, events):
        for event in events:
            self.counts[event.kind] = min(2**53-1, self.counts[event.kind]+1)
            self.last_event = dict(kind=event.kind, scenario=event.scenario, reason=event.reason)
            if event.kind == 'context':
                self.context_gestures += 1  # Observation only; no request is created.
            elif event.kind != 'activate':
                kind = 'unavailable' if event.kind == 'cancel' and event.reason == 'source' else event.kind
                ok = self.audio.speak(kind, generation=event.generation,
                    epoch=event.epoch, scenario=event.scenario)
                if not ok and event.kind in ('entry','selection','choose','confirmation'):
                    self.core.cancel('audio')

    def tick(self):
        with self.lock:
            now = self.clock()
            flags = dict(self.flags)
            if self.fault or not self.priority_clear: flags['ready'] = False
            if self.gpio is not None and not 0 <= now-self.input_at <= 100:
                flags['ready'] = False
            usable = self.audio.update(audio_ready=flags['audio_ready'], priority_clear=self.priority_clear and flags['consent'], epoch=flags['epoch'])
            flags['audio_ready'] = usable
            self._apply(self.core.sample(self.level, now_ms=now, **flags))
            if self.core.state == 'failed': self.audio.close()

    def command(self, line):
        with self.lock:
            if line in ('press','release') and self.gpio is None:
                self.level = line == 'press'
            elif line in ('audio-on','audio-off'):
                self.flags['audio_ready'] = line == 'audio-on'
            elif line in ('source-on','source-off'):
                self.flags['ready'] = line == 'source-on'
            elif line in ('hazard-on','hazard-off'):
                self.priority_clear = line == 'hazard-off'
            elif line == 'consent-off':
                self.flags['consent'] = False
            elif line == 'quit':
                self.audio.close(); self.core.close(); return True
            elif line == 'cancel':
                self._apply(self.core.cancel())
            elif line not in ('status','quit'):
                self._apply(self.core.cancel())
                return False
            self.tick()
            return True

    def start(self):
        if self.worker is not None or self.stop.is_set():
            raise ValueError('Start the menu bench once')
        def run():
            try:
                while not self.stop.wait(.01): self.tick()
            except Exception:
                with self.lock:
                    self.fault = True; self.audio.close(); self.core.close()
        def read():
            try:
                while not self.stop.wait(.01):
                    level, at = self.gpio.read(), self.clock()
                    if type(level) is not bool: raise ValueError()
                    with self.lock: self.level, self.input_at = level, at
            except Exception:
                with self.lock:
                    self.flags['ready'] = False; self.fault = True; self.tick()
        self.worker = threading.Thread(target=run, daemon=True); self.worker.start()
        if self.gpio is not None:
            self.reader = threading.Thread(target=read, daemon=True); self.reader.start()
        return self

    def snapshot(self):
        with self.lock:
            return dict(**self.core.snapshot(), last_event=self.last_event,
                context_gesture_events=self.context_gestures, event_counts=dict(self.counts), fault=self.fault,
                scenario_capabilities='synthetic interaction only' if self.synthetic_adapters else 'unavailable',
                gpio_used=self.gpio is not None, motor_gpio_used=False,
                phone_used=False, backend_used=False, gemini_used=False,
                context_requests_used=False, physical_audio_accepted=False,
                automatic_audio_route_detection=False)

    def close(self):
        self.stop.set()
        with self.lock: self.core.close(); self.audio.close()
        for thread in (self.worker,self.reader):
            if thread is not None: thread.join(timeout=.2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    audio = parser.add_mutually_exclusive_group(required=True)
    audio.add_argument('--simulate-audio', action='store_true')
    audio.add_argument('--speak', action='store_true')
    parser.add_argument('--audio-confirmed', action='store_true', help='Operator confirms current audible output; no automatic route monitor')
    parser.add_argument('--consent', action='store_true', help='Explicit bench consent; holding is not consent')
    parser.add_argument('--synthetic-adapters', action='store_true', help='Simulated interaction capabilities; no observations or jobs')
    parser.add_argument('--gpio21', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.consent or (args.speak and not args.audio_confirmed):
        parser.error('Use --consent; real speech also requires --audio-confirmed after checking current output')
    report, sink, gpio, bench = ContextRunReport(), None, None, None
    report.data.update(mode='synthetic-crossing-menu-bench', complete=False)
    code = 1
    try:
        report.open(args.output, audio=args.speak, gpio=args.gpio21)
        if args.speak:
            from backend.context.pi_speech import EspeakSink
            sink = EspeakSink()
        else: sink = SilentMenuSink()
        if args.gpio21:
            from .context_gpio import GPIO21Input
            gpio = GPIO21Input()
        bench = MenuBench(sink, synthetic_adapters=args.synthetic_adapters, gpio=gpio).start()
        print('SYNTHETIC MENU BENCH. No traffic observations, camera, provider, phone or motors.', flush=True)
        print('press / release / status / cancel / audio-off / audio-on / source-off / source-on / hazard-on / hazard-off / consent-off / quit', flush=True)
        print('Hold timing is real time between press and release commands. GPIO mode reads only the physical button.', flush=True)
        while True:
            line = sys.stdin.readline(65)
            if not line: break
            if len(line) > 64:
                bench.command('cancel')
                while line and not line.endswith('\n'): line = sys.stdin.readline(65)
                continue
            command = line.strip()
            bench.command(command)
            print(json.dumps(bench.snapshot(), sort_keys=True), flush=True)
            if command == 'quit': break
        report.data.update(complete=True, outcome='finished')
        code = 2 if bench.fault else 0
    except (KeyboardInterrupt, EOFError):
        report.data['outcome'] = 'interrupted'; code = 130
    except UnsupportedReportPlatform as error:
        print(str(error), flush=True)
    except Exception:
        print('Menu bench unavailable; inspect dependencies or device setup', flush=True)
    finally:
        try:
            if bench is not None:
                bench.close(); report.data.update(bench.snapshot())
            if gpio is not None: gpio.close()
            if sink is not None: sink.close()
        except Exception:
            report.data.update(complete=False, outcome='cleanup-unavailable'); code = 1
        report.finish()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
