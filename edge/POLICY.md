# Local policy and CS-025 GPIO integration

The existing receiver is opt-in with `--receive-vision`. Add `--simulate-policy`
to run the local policy and capped scheduler using **simulated outputs only**.
This flag explicitly arms only the simulation. Without a policy output flag,
the uploader/receiver never instantiate a scheduler. The separate `--gpio-policy`
option below explicitly selects the CS-023 physical-output adapter.

```sh
python -m edge.uploader --receive-vision --simulate-policy --frames 20 \
  --session-file ~/.canesight-session.json
```

With only the existing private six-field Pi credential, phone depth remains
unconfigured and **no obstacle pulse is generated**. Vision results and generic
object detections never become motor commands, crossing permission, a clear
route, or a pedestrian-signal decision. The final output labels simulation,
health and hazards separately, and reports output cleanup without credentials
or images. Snapshot health is not evidence of electrical or sensor readiness.

## Explicit phone binding and clock gate

For a coordinated bench run with a real phone, obtain the actual source/boot
identity from the operator's matching enrollment. The Pi must not discover or
reenroll identities from incoming messages. Supply a separate local file via
`--phone-binding-file /PRIVATE/phone-binding.json` with exactly:

```json
{"source_id":"ACTUAL_PHONE_SOURCE","boot_id":"ACTUAL_PHONE_BOOT","relative_drift_ppm":null}
```

This is not the Pi enrollment JSON. Keep the six-field Pi session file unchanged
and mode 0600. Never transfer the phone or operator token to the Pi. The binding
file accepts no token or extra/duplicate fields. Its phone source must differ
from the Pi. Compare its source/boot with the trusted operator response; do not
use names guessed from network messages or an old boot.

`null` drift leaves depth unavailable. Before setting a numeric joint drift
budget, Michael must supply measurements supporting the phone/Pi clocks under
the intended operating conditions. **Zero is used only for synthetic same-clock
tests, not a measured physical-device assertion.** The receiver sends bounded
native clock probes approximately every 1.1 seconds, only with an explicitly
configured numeric drift. It validates nonce, enrolled identity, session/mode,
uncertainty, capture floor and original capture age using accepted CS-030 rules.
Missing/expired calibration or heartbeat cannot establish fresh depth. No TLS,
Origin, shared protocol or backend changes are needed.

## Explicit configured GPIO policy

After review of the actual wiring, mapping and CS-009/010 prerequisites, replace
`--simulate-policy` with `--gpio-policy` and supply both reviewed BCM pin numbers
and active-high polarity. BCM21 remains reserved for the context button. Neither
pins nor clock drift values are inferred from incoming packets. The phone binding
must match the operator's current session; null drift is rejected before session
enrollment or any GPIO claim in this mode. Use a measured bound for real devices;
zero in the automated tests is an explicitly synthetic same-clock choice.

```sh
python3 -m edge.uploader --receive-vision --gpio-policy --frames 20 \
  --session-file ~/.canesight-session.json \
  --phone-binding-file /PRIVATE/phone-binding.json \
  --motor-left-bcm LEFT --motor-right-bcm RIGHT --motor-active-high \
  --policy-trace /PRIVATE/new-gpio-policy.jsonl
```

Substitute only verified pin numbers for LEFT/RIGHT. This is a live motor-capable
command, not a software simulation. No such physical run was performed for this
implementation. GPIO Zero remains lazily imported only after explicit selection
and authenticated receiver startup. The same process owns uploader identity,
receiver, CLOCK_BOOTTIME gate, scheduler, watchdog and output adapter.

GPIO policy requires a live enrolled phone, numeric drift budget and attached
same-clock watchdog. Freshness still requires successful native clock probes,
ready source heartbeat and two recovered depth observations. Ready sockets or
backend heartbeats cannot arm normal pulses, renew capture time or clear a
latched fault. Late/replayed/mismatched observations remain unavailable.

The CLI attaches the watchdog before starting the scheduler/policy workers.
Camera initialization failure, Ctrl+C/SIGTERM and normal exit request policy,
watchdog and scheduler shutdown, then release the motor adapter before slower
audio/trace/network/camera cleanup. Every motor-stop attempt runs even if another
stop fails. Any stop/adapter-release failure makes the command unsuccessful;
successful software writes still do not certify electrical off state.

The policy snapshot and private decision trace identify `output_mode: gpio`.
Simulation defaults and existing trace formats retain `output_mode: simulation`.
Context input/audio may use either policy mode with its existing explicit consent
and phone binding; hazard/source/epoch cancellation behavior is unchanged. Context
report `gpio_used` describes the button input; policy trace/output mode describes
motor GPIO separately. Provider/scenario availability is not enabled by choosing
GPIO policy. Automatic deployment, arming on reconnect or service installation
is not introduced.

Coordinate camera availability with Michael before a physical run. Start a fresh
uploader, obtain its new boot ID, enroll a fresh 600-second paired session and
privately install the matching Pi-only JSON with mode 0600. The existing 300s
wait starts when the uploader launches: prepare everything and coordinate first.
Do not retry the rejected automated SSH runner; execute Pi commands manually.
No new Pi test or enrollment was performed for this policy checkpoint.

## Policy behavior

- Health and hazards are separate. Healthy heartbeats cannot create obstacles,
  renew captures or trigger pulses. No signal/vision result drives haptics here.
- Two consecutive distinct covered depth observations recover a sector. Unknown,
  interrupted or stale evidence resets its recovery/hazard state. Coverage >=0.5,
  entry <=1.2m, exit >=1.5m, 100ms pulses are **simulation tuning parameters**,
  not validated sensing or stopping-distance limits. Mid-band values retain the
  prior classification; unknown stays unknown. A farther observation means only
  `not-nearby-observed`, never clear.
- Center takes priority and requests both channels; otherwise left/right represent
  obstacles on those sides, never instructions to turn. Physical mount/channel
  calibration is still required before any hardware implementation.
- Every request retains the original final-consumer capture deadline. No queue,
  heartbeat/tick retrigger or active-pulse extension. The accepted CS-023 scheduler
  independently enforces pulse, cooldown and rolling-duty caps. A denied request
  is dropped; a later fresh sequence can request again.
- Policy polls every 20ms independently from camera/HTTP/WSS reads; the scheduler
  runs its own 10ms worker. Gate and scheduler must share the exact same clock
  callable, using CLOCK_BOOTTIME on the Pi. Source loss, invalid tracking, missing
  data, clock reversal, disarm or cleanup remove pulse eligibility. A policy or
  motor scheduler fault stays unavailable until a new instance/session.
- Unavailable is explicit status, not a normal obstacle pulse. This checkpoint
  does not invent a motor unavailable pattern before physical distinguishability
  testing. Silence never means clear. Python/OS stalls can delay cancellation;
  this is not hard real-time, CS-026 watchdog/restart acceptance, or protection
  against a frozen GPIO-high process. Keep the physical kill requirement.

## Verification and remaining evidence

```sh
python -m unittest discover -s tests/edge -v
python -m unittest discover -s tests -v
```

Synthetic tests exercise real native TLS/WSS phone clock/depth/interrupt routing,
original-deadline clipping, heartbeats-only, unknown coverage, tracking loss,
center/side mapping, hysteresis, recovery, clock fault and independent idle expiry.
Existing camera/uploader/vision lineage tests remain. Real Pi's earlier 20/20
vision run applies only to snapshot 17441cee512bb29ae6ad5bd327706a45c0a8f107;
it does not validate the new depth policy or prove a phone was connected.

Remaining physical gates: real phone pairing and supported depth app; measured
joint drift/calibration and latency; camera/phone interruption tests on the new
commit; mount/channel calibration; CS-009 power/driver/thermal/kill verification.
No physical actuation is available in this implementation. Review/merge remains
Michael's; software evidence does not close the hardware gates.
