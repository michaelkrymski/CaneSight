# CS-023 capped haptic scheduler

The scheduler executes bounded **local** pulse requests. It does not interpret
observations, choose a hazard cue, accept server motor commands, or grant crossing
permission. Simulated outputs remain the default. The separate opt-in
`haptic_gpio.GPIOOutput` adapter supports two explicitly configured active-high
driver inputs. Normal uploader/policy commands still use simulation only.

Run on a laptop or isolated software-test environment:

```sh
python -m edge.haptics --simulate
python -m unittest discover -s tests/edge -p test_haptics.py -v
```

The demo prints an explicit simulation result with `gpio_used: false` and both
outputs off on exit. It needs no session file, operator credential, network,
phone or camera. The scheduler itself uses only Python's standard library.
Running all edge tests also needs the existing backend test dependencies:

```sh
python -m unittest discover -s tests/edge -v
```

## Limits and admission

| Setting | Default | Meaning |
|---|---|---|
| Normal pulse request | 150 ms | Local callers may request a shorter pulse or up to the maximum. |
| Maximum pulse | 500 ms | Latest logical stop is also clipped to the original eligibility deadline. |
| Minimum off-time | 200 ms | Per channel, including initial startup and after cancellation. |
| Rolling duty limit | 2,000 ms per 10,000 ms | Per channel; a conservative **simulation starting point**, not a measured motor rating. |
| Worker tick | 10 ms | Nominal independent expiry poll; configurable from 1–10 ms. |

The pulse/off envelope comes from the master plan's initial engineering targets.
The 20% rolling duty default is an implementation choice pending actual motor
current/thermal tests; it is not electrical acceptance of 5 V operation. Limits
may be tightened but not raised beyond these defaults through configuration.
The 3 V fallback and full master-plan wiring/power conditions still apply.

No pulse is queued. A busy, expired, unready, closed, faulted, cooldown-limited or
duty-limited request is rejected immediately. Repeating a request does not extend
the active pulse. A two-channel request is admitted only if both channels qualify;
one rejected channel cannot accidentally start its peer. Physical writes would
still be sequential; no simultaneous hardware actuation is claimed.

Reserve the entire proposed pulse against the current rolling usage, without
assuming an old interval will age out before it completes. Charge elapsed time
observed when stopping, including late ticks and cancellations. Disarming,
rearming and cancellation do not erase duty history or bypass minimum off-time.
At most about 52 recent intervals per channel are needed under the 200 ms off
rule; old intervals are pruned. The simulated transition trace keeps 256 entries.

## Local-policy integration boundary

`HapticScheduler()` starts with both outputs requested off and readiness false.
The trusted local CS-024 policy owns evidence eligibility and must call
`set_ready(False)` or `cancel()` when a source/cue becomes unavailable. A backend
heartbeat must not authorize a normal pulse or refresh observation age.

After actual local readiness is established and initial off-time has elapsed,
the API accepts a request shaped like:

```python
scheduler.pulse('left', 150, valid_until_ms=observation.deadline_ms)
```

This example is an API seam, not implemented hazard selection. Use the ORIGINAL
receiving-side deadline from the capture-age gate on the SAME clock; do not
replace it with receipt time plus a new validity interval. A request is clipped
to that deadline, and must never be regenerated from a cached expired observation.
Recheck the gate each policy tick. CS-024 still defines the cue mapping, source
health behavior and precedence; the scheduler knows neither depth nor vision.

On Linux the default clock is CLOCK_BOOTTIME, matching the Pi uploader/receiver.
Other platforms use monotonic time for laptop simulation. Clock reversal,
nonfinite/invalid time or an output fault latches unavailable and requests both
channels off. A scheduler observing a pulse longer than its maximum or actual rolling
duty above its cap also latches a fault and requests both channels off. New readiness calls cannot clear faults; a new scheduler is required.
The integration must also reset session/evidence on restart before rearming.

`start()` or a context manager runs expiry in a dedicated thread independently
of capture/network work. Deterministic tests may advance a fake clock and call
`tick()`. `snapshot()` enforces expiry too, but a saved snapshot is not an ongoing
eligibility lease. `close()` is terminal, disarms both channels and joins the
worker. Context-manager cleanup also runs when the caller raises an exception.

## Output failures and physical limits

Output `write(channel, enabled)` must return promptly. Each off request is attempted
independently even if another write fails. A failed off-write reports `None`
(unknown), never a false confirmation of low. A successful write only confirms
the adapter accepted the request; it cannot establish measured pin voltage or
motor behavior. Adapter cleanup must run after scheduler shutdown; the separate
GPIO adapter context provides this ordering.

Python/thread/OS scheduling, suspended execution, a blocking adapter or a frozen
process can delay an off request. The 10 ms ticker and logical 500 ms cap are not
hard real-time or electrical guarantees. A late observed tick is charged and
faulted when it exceeds the maximum; that cannot undo an already elapsed overrun.
This is not the independent watchdog/restart work of CS-026. Retain the physical
kill switch and documented driver/power/diode conditions.

Before physical integration Michael must supply accepted CS-009 evidence for
driver off states, 3.3 V logic compatibility, leakage and thermal behavior, along
with its power/wiring prerequisites. Hardware-specific adapters and actual
left/right mapping need separate review and bench validation. Software tests
cannot establish motor startup-off behavior, frozen-GPIO recovery, current at
5 V, supply integrity or electrical readiness. CS-023 is not marked Done here.

## Explicit GPIO adapter and bench command

`edge/haptic_gpio.py` supplies the missing two-channel output implementation.
It is implemented and tested with fake driver devices before CS-009 acceptance;
no motor or GPIO hardware was activated during development. It does not remove
CS-009 or establish readiness for physical operation.

Use Raspberry Pi OS's `python3-gpiozero` package for an actual device. The adapter
uses [GPIO Zero DigitalOutputDevice](https://gpiozero.readthedocs.io/en/stable/api_output.html#digitaloutputdevice)
with `active_high=True` and `initial_value=False`. Pins use BCM numbering and
have no defaults. Choose two distinct pins from BCM 2..27 based on the reviewed
circuit. BCM21 is reserved for the existing context button. Active-low drivers
are deliberately unsupported: this task requires startup/cleanup LOW.

Importing the module does not import GPIO Zero or claim pins. Constructing the
adapter claims each output initially off. If the second claim fails, it requests
the first off and releases it. Any write error latches the adapter unavailable
for further on-requests and attempts both outputs off. Cleanup attempts both
off writes and both releases independently; cleanup failure cannot produce a
successful bench report. Releasing a pin does not guarantee its voltage stays
low, so passive off-state wiring and the physical kill remain required.

After the circuit/pins and CS-009 evidence are reviewed, run the standalone
bench command with the verified pin numbers substituted for the placeholders:

```sh
# Claim both pins off, then release them; never requests a pulse.
python3 -m edge.haptic_gpio --enable-gpio --active-high --left-bcm LEFT --right-bcm RIGHT --off-only

# One explicit 150 ms local bench stimulus; no camera, phone or backend.
python3 -m edge.haptic_gpio --enable-gpio --active-high --left-bcm LEFT --right-bcm RIGHT --pulse left --duration-ms 150
```

`--pulse` accepts `left`, `right`, or `both`; it cannot combine with `--off-only`.
Every invocation requires explicit GPIO opt-in, polarity and pins. Pulse duration
must be finite and greater than zero, up to 500 ms. The existing scheduler still
enforces initial off-time, original deadline, rolling duty and independent expiry.
A successful report says `mode: gpio`, `gpio_used: true`, `bench_only: true` and
`physical_acceptance: false`. Its off states describe accepted software writes,
not measured pin voltages or motor onset. Ctrl+C/SIGTERM request cleanup and return
a failure/interruption status; SIGKILL, power loss or a frozen process cannot run
Python cleanup. A timing overrun may fault even on a requested 500 ms pulse.

Trusted future integration owns the adapter outside the scheduler context:

```python
from edge.haptic_gpio import GPIOOutput
from edge.haptics import HapticScheduler

with GPIOOutput(left_bcm=verified_left, right_bcm=verified_right, active_high=True) as output:
    with HapticScheduler(output) as scheduler:
        # Trusted caller supplies readiness and original same-clock deadlines.
        # No pulse is generated automatically.
        pass
```

The CS-025 policy integration accepts this adapter only with explicit GPIO
opt-in, a live enrolled phone binding, configured drift bound and the attached
same-clock watchdog. See [POLICY.md](POLICY.md). This adapter/bench command does
not enable that integration implicitly.

Developer checks (no GPIO package or Pi required):

```sh
python -m unittest discover -s tests/edge -p test_haptic_gpio.py -v
python -m unittest discover -s tests/edge -v
```
