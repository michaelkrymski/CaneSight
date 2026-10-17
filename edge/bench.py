"""CS-025 repeatable synthetic depth-to-simulated-output bench; no Pi or GPIO."""
import argparse
import json
from pathlib import Path
from backend.freshness import CaptureAgeGate
from .haptics import HapticScheduler
from .policy import LocalPolicy
from .trace import DecisionTrace
from .watchdog import PolicyWatchdog


def run(output, repetitions=3):
    if type(repetitions) is not int or not 1<=repetitions<=20:
        raise ValueError('Use 1..20 synthetic repetitions')
    now=1000
    clock=lambda:now
    gate=CaptureAgeGate('synthetic-session','replay','synthetic-pi','synthetic-pi-boot',clock_ms=clock,relative_drift_ppm=0)
    gate.enroll('synthetic-phone','synthetic-phone-boot',{'depth_observation','heartbeat'})
    scheduler=HapticScheduler(clock=clock)
    watchdog=PolicyWatchdog(scheduler.trip,clock=clock)
    scheduler.set_guard(watchdog.deadline)
    trace=DecisionTrace(output,provenance='synthetic-fixture')
    policy=LocalPolicy(gate,'synthetic-phone',scheduler,clock=clock,watchdog=watchdog,trace=trace)
    policy.arm(True)
    counts=dict.fromkeys(('left','center','right'),0)
    seq=0
    def heartbeat():
        gate.receive(dict(schema_version=1,type='heartbeat',session_id='synthetic-session',mode='replay',source_id='synthetic-phone',boot_id='synthetic-phone-boot',seq=int(now),capture_monotonic_ms=now,capture_utc=None,state='ready'))
    def calibrate():
        probe=gate.start_probe('synthetic-phone')
        gate.finish_probe(dict(probe,type='clock_reply',t2_ms=now,t3_ms=now))
    calibrate();heartbeat()
    def advance(ms):
        nonlocal now
        end=now+ms
        while now<end:
            now=min(end,now+10)
            scheduler.tick();policy.tick();watchdog.tick()
    def depth(stimulus):
        nonlocal seq
        seq+=1
        gate.receive(dict(schema_version=1,type='depth_observation',session_id='synthetic-session',mode='replay',source_id='synthetic-phone',boot_id='synthetic-phone-boot',seq=seq,capture_monotonic_ms=now-30,capture_utc=None,tracking='normal',sectors={name:dict(distance_m=None if stimulus is None else .7 if name==stimulus else 2,valid_fraction=1) for name in counts}))
        policy.tick()
    try:
        advance(300)
        for _ in range(repetitions):
            for stimulus in counts:
                if now-gate.last_probe_ms['synthetic-phone']>=1000:calibrate()
                heartbeat();advance(100)
                depth(None);advance(100);depth(None);advance(300)
                before=scheduler.accepted
                depth(stimulus);advance(100);depth(stimulus)
                expected={'left':stimulus in ('left','center'),'right':stimulus in ('right','center')}
                if scheduler.snapshot()['outputs']!=expected or scheduler.accepted!=before+1:
                    raise ValueError('Synthetic mapping/pulse did not match')
                counts[stimulus]+=1
                advance(300)
        # Continue worker ticks with no new captures: old data expires and cannot
        # retrigger, even though health and policy liveness continue independently.
        accepted=scheduler.accepted
        advance(700)
        if any(scheduler.snapshot()['outputs'].values()) or scheduler.accepted!=accepted:
            raise ValueError('Idle synthetic capture remained eligible')
    finally:
        policy.close();watchdog.close();scheduler.close()
        logging=trace.close()
    return dict(mode='replay',input_kind='synthetic-fixture',output_mode='simulation',
        stimuli_accepted=counts,trace=logging,outputs=scheduler.snapshot()['outputs'],
        gpio_used=False,physical_acceptance=False,
        limit='Software command observations only; no physical onset, phone measurement or crossing permission.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulate',required=True,action='store_true')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--repetitions',type=int,default=3)
    args=parser.parse_args()
    try:result=run(args.output,args.repetitions)
    except Exception:
        print('Synthetic bench failed; no physical acceptance claimed.')
        return 1
    print(json.dumps(result,sort_keys=True))
    return 0 if result['trace']['complete'] else 1


if __name__=='__main__':raise SystemExit(main())
