# CS-026 policy watchdog and restart behavior

Software supervision for **simulated outputs only**. Nothing in this change
installs a service, connects to a Pi, captures an image or accesses GPIO.

`--simulate-policy` now starts an independent policy watchdog automatically:

- Only a completed local policy tick can feed its 200ms lease. Camera, network,
  heartbeat and upload callbacks cannot feed it. Normal unavailable policy ticks
  may feed the lease: worker liveness is separate from sensor readiness.
- The supervisor checks every 10ms, independent of policy/camera/network locks.
  Expiry, clock reversal/nonfinite clock, or closure latch unavailable and request
  both simulated outputs off. Late feed never recovers an expired instance.
- Scheduler admission checks the same lease even if the supervisor has not run.
  Each pulse ends at the earliest of requested duration, original capture expiry
  and the lease deadline at admission. Later policy feeds cannot extend that pulse.
- One clock callable is shared by policy, scheduler and watchdog; CLOCK_BOOTTIME
  is used on the Pi. No cross-device monotonic comparison is introduced.
- Shutdown closes policy, watchdog and scheduler before camera cleanup; SIGTERM
  enters the CLI cleanup path. Camera initialization failure also runs cleanup.

## Local failure demonstration

```sh
python -m edge.watchdog --simulate
python -m unittest discover -s tests/edge -v
```

The demonstration uses no camera, network, credentials or GPIO. It starts outputs
off/unarmed, models completed policy ticks, requests one capped simulated pulse,
then stops feeds. Its JSON shows a unique local epoch, initial off/unarmed state,
expired fault and outputs off. This watchdog epoch is diagnostic only, not a
replacement for the uploader's new enrollment boot ID.

Tests block the actual policy lock while the independent watchdog/scheduler
continue, reject a late feed and new pulse, verify original lease clipping,
exercise camera-start cleanup, abruptly exit a subprocess, and start new processes
with fresh epochs, no arming or pending pulses. An abrupt process exit does not
prove that old physical outputs went low; only the new process's simulated state
is examined. Real device evidence remains pending.

## Restart procedure and optional service example

Each uploader process generates a fresh boot ID. Its prior session file cannot
match that new identity: it waits at most 300 seconds for a freshly enrolled file
and otherwise exits without capture/upload. Do not edit a boot ID into an old
credential, preserve an armed state, restore a queued pulse, copy sequence history
from a dead process, or automatically create sessions on the Pi. The operator
credential stays off the Pi.

After coordinating camera availability, use a reviewed separate checkout and
compatible environment. Follow `edge/POLICY.md` and `backend/SESSIONS.md`: start
the uploader, provide its new boot ID, create a fresh 600-second session with the
intended phone binding, and privately install only the Pi JSON owned by the Pi
user with mode 0600. Phone calibration/recovery and simulation arming are rebuilt
from new process state; old captures cannot supply the new epoch.

`edge/systemd/canesight-simulation.service.example` is an **uninstalled example**
for a user service. Review its checkout/environment paths first; no enable/start
commands are executed here. It explicitly requests simulated outputs, limits
failed restarts to three within 15 minutes, waits five seconds between failures,
uses private file creation, sends SIGTERM and kills remaining processes after a
five-second stop timeout. No operator token or automatic enrollment is configured.
It does not configure the optional phone binding; add only an operator-reviewed
binding path after following the measured-drift gate in POLICY.md.

Restart=on-failure handles actual process exits. It does not detect a camera call
that never returns, implement systemd's WatchdogSec protocol, or guarantee cleanup
on SIGKILL/power loss. Stop/restart and reenroll manually if the capture process
is stuck. This template is not an installed or physically tested service.

## Limits

This is independent **software** expiry, not hard real-time protection. Python,
OS scheduling, interpreter/GIL stalls, a blocked output adapter, suspend/freeze,
SIGKILL, process crash or power faults may prevent or delay writes. The supervisor
must obtain the scheduler lock; a frozen adapter holding that lock cannot be
forced low by another Python thread. No GPIO adapter is shipped. Software cannot
guarantee off after GPIO freezes high: retain a reachable physical kill switch,
verified passive startup states and a separately engineered hardware timeout if
needed. CS-009 power/driver/current/thermal checks and physical boot/crash/kill
validation remain required. No electrical acceptance, all-clear or crossing
permission follows from the synthetic tests.
