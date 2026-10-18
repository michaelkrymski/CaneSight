# Debounced context request button — CS-027

`edge.buttons.ContextButton` is an opt-in software coordinator with injected input,
latest-frame and request adapters. `edge.context_client.ContextClient` supplies a
Pi-role HTTPS adapter for the accepted CS-039 context service. The originating
uploader has mutually exclusive terminal and optional GPIO21 input adapters,
text output by default and a separate audio opt-in. No motor GPIO is armed.

## Behavior

- A raw boolean level must remain stable for 30 ms. Startup-held buttons do not
  trigger: first observe a stable released level, then a stable press. A long
  hold never repeats. A second debounced press cancels an outstanding request,
  including during cooldown. `cancel()` provides immediate software cancellation.
- One outstanding request, no queued button presses, no automatic retries.
  Every attempted request factory call starts a ten-second minimum interval;
  cancellation, input bounce, failed requests, health changes and rearming do not
  reset it. The server also enforces its own cooldown/capacity. A server 429
  remains unavailable: wait for a new user press, never retry silently. Its
  32-request history bound requires a newly authorized session.
- Default state is disabled. `set_state(ready=True, consent=True, hazard=False)`
  must come from trusted local session/camera readiness, actual scene-sharing
  consent and local hazard policy. Unknown/missing health, consent withdrawal,
  hazards, backgrounding, source loss and session change must cancel immediately.
  Recovery requires release and a new press; it never resumes a cancelled job.
  Gemini output cannot supply or modify these flags.
- A request uses the producer's original `edge.uploader.Frame` on the same Pi
  CLOCK_BOOTTIME timeline. Start age must be between zero and 1500 ms. The full
  local deadline is capture + 8000 ms, including both network directions and
  service time, never receipt + 8000 ms. Invalid, unknown, future or old captures
  do not start work. Clock exceptions, reversal or invalid readings latch a
  controller fault; replace it and reenroll rather than resetting cooldown.
- Replies must exactly match request and original frame metadata, session,
  source, boot and live/replay mode. Only supported object labels with explicit
  uncertainty are returned. No raw prose, crossing decision or motor command is
  accepted. `take_result()` consumes one still-fresh structured reply. It does
  not authorize speech; local narration must validate priority/age independently.
- `start()` runs a separate 10 ms timer for debounce and expiry; blocked camera,
  network or input code does not need to call `tick()`. `sample(bool)` supplies
  raw level changes; deterministic tests can call `tick()` themselves. The frame
  supplier, factory and handle polling must return promptly and must not reenter
  the controller. Python scheduling and OS stalls are not hard real-time timing
  guarantees. Only the request child performs blocking HTTP work.

## Integrating in the originating Pi process

The earlier no-button assumption is superseded by Michael's
[hardware handoff #68](https://github.com/michaelkrymski/CaneSight/issues/68).
Terminal mode remains available with explicit scene-sharing consent:

```sh
python -m edge.uploader --receive-vision --simulate-policy \
  --phone-binding-file /PRIVATE/phone-binding.json \
  --session-file /PRIVATE/pi-session.json --frames 0 \
  --context-stdin --context-consent
```

Use the existing enrollment procedure for the uploader's newly printed source
and boot. The service must expose the accepted opt-in `/v1/context` endpoint over
verified HTTPS; `--ca-file` supports a private test CA. A phone binding must come
from verified phone identity and drift evidence, never a fabricated drift value.
These flags do not establish phone readiness: missing or expired depth, unknown
sectors, disconnected receiver, sender failure, fault or expired policy lease
suppress requests. A busy policy, freshness-gate or watchdog lock is also treated
as unavailable without waiting on that worker. A nearby obstacle cancels context. Haptic outputs remain
simulated, and context cannot change the policy, watchdog or motor requests.

Commands are case-sensitive, each followed by Enter:

- `press`: hold the synthetic input pressed. After 30 ms stable input, request
  context (or cancel an outstanding request on a second debounced press).
- `release`: release the input. Release before another press; holding never repeats.
- `cancel`: immediately cancel and release; the ten-second cooldown remains.
- `status`: print allowlisted software state and request counters without pressing
  the input. Audio mode uses the narration bridge's sole button counters. Unknown
  counters stay unknown if the installed dependency lacks diagnostics.
- `off`: withdraw consent, cancel, and purge the retained frame. Restart and
  reenroll for another consented session. EOF or input failure also withdraws.

After readiness recovery, release and press again. Commands entered before
readiness are not queued. Unknown commands cancel without echoing input;
oversize lines are drained with bounded reads. Terminal input is not an API for
arbitrary commands. Output contains only closed object labels with an AI and
uncertainty label in default text mode. Audio mode uses the restricted narration
gate instead of creating a second request loop.

`edge.context_runtime.ManualContext` runs inside the originating uploader and
shares its session/source/boot, capture clock and original frames. It holds at
most one latest JPEG, copied metadata, and one outstanding request; replacing
the latest frame never retimes a request. A separate 20 ms worker checks camera
capture age, primary-source state and results, while the button has its own
10 ms debounce/expiry worker. Blocked camera capture or terminal reads cannot
keep stale context eligible. Camera loss, consent withdrawal and cleanup purge
the retained frame. A blocked daemon stdin reader may remain until input/EOF;
cleanup never closes caller-owned stdin and the reader cannot dispatch after
close. Python scheduling is not a hard real-time guarantee.

The injected `ContextButton` API is shared by terminal and GPIO21 input. Use the application's `if __name__ == '__main__':` entry guard for
multiprocessing spawn. Do not launch a second camera process, reuse a prior boot,
fabricate capture timestamps or substitute a server clock. Replay fixtures must
keep `mode=replay`. On a new epoch, close the old runtime/client and reenroll.

The client takes only the existing private six-field Pi credential:
`base_url`, `session_id`, `source_id`, `boot_id`, `mode`, `token`. Never put a
Gemini or operator key on the Pi. HTTPS and certificate/hostname verification are
mandatory; redirects and ambient proxy configuration are refused. A private test
CA is supported without disabling verification. Credentials appear only in the
Authorization header, never the multipart payload, URL, repr or error messages.

One spawned network child holds at most one JPEG. Cancelling kills and reaps it,
closing the socket so the server can cancel its provider child. Polls and reads
are bounded; malformed/oversize replies are dropped. If cancellation cannot reap
the child within 200 ms, the controller faults and refuses further work. This is
best-effort socket cancellation, not a guarantee that the provider incurs no
charge or has not already processed a frame. Killing a process cannot undo an
external request already made.

## Optional Pi audio

After narration dependency PR #41 is accepted and installed with the Pi checkout,
append `--context-audio` to the manual invocation above. The flag requires
either `--context-stdin` or `--context-gpio21`; both require explicit
`--context-consent`, trusted phone binding and simulated local policy. No speech module is loaded in default
text mode. Missing narration modules or an unavailable eSpeak NG installation
refuse audio startup with a sanitized error; there is no silent text fallback.
This integration PR stays draft while #41 is draft/unmerged.

Audio mode connects the same latest original frame, Pi session/client, capture
clock, camera freshness and primary priority to CS-040 `ContextNarration`.
It replaces the text-mode button/request worker, so one press cannot create two
requests. The narration bridge independently drives capture-based audio expiry
and priority checks; the existing bounded terminal reader supplies level changes.
`cancel`, `off`, EOF, input failure, camera loss and shutdown stop narration and
cancel provider work. New frames do not renew the original speech deadline.
Holding `press` does not repeat requests or interrupt its own delivered speech.
Camera staleness independently cancels while capture or terminal input is blocked.

The owned `EspeakSink` uses `/usr/bin/espeak-ng` and the Pi user's OS-selected
output. Pair/select and audibly test the Bluetooth speaker on the Pi before
opting in. This code does not pair, reroute or change volume. Only restricted
uncertain narration reaches the engine; no raw provider prose, shell commands,
keys or images are passed to it. Cleanup closes both narration and speech even
if stop fails; a sanitized fault records that device inspection is required,
without interrupting primary policy/camera teardown. The snapshot reports audio
opt-in separately from delivery: `audio_used` is unknown and
`audio_delivery_verified` remains false, never inferred from process success.

Tests that require the real narration dependency explicitly skip until it exists
in the checkout. They were also run locally against the exact draft #41 modules
without copying them into this task branch; that combined result is documented
in the handoff. They include manual terminal -> spawned verified HTTPS client ->
accepted context route/fake provider -> synthetic speech and manual preemption.
No Bluetooth delivery or instant physical silence is established by software:
OS/speaker buffering, disconnect/reconnect and audible priority need device tests.

## What remains

Issue #68 reports installed active-high GPIO21 wiring and standalone raw input
operation. The new application adapter still needs its own Pi run. No physical
GPIO activation was performed by this local coding session. Camera scheduling
and combined phone/context runs still require actual-device evidence. The manual uploader adapter is software-tested; its actual Pi/phone
run still needs device evidence and coordination with CS-025. The service must
be packaged/deployed through its deployment
owner; this change does not activate `/v1/context` on the existing Vultr service.
CS-040 remains draft PR #41 and owns the narration gate and Pi speech adapter;
this uploader integration depends on its acceptance/installation. CS-018 owns
accessible controls. Actual speaker behavior remains unverified. Stop/preempt local audio
first, independently of waiting for network cancellation. A returned description
never changes haptic policy, source health or movement permissions.

## Verification

Install the existing `edge/requirements-receiver.txt` (or the pinned backend test
requirements for development), then run:

```sh
python -m unittest discover -s tests/edge -v
python -m unittest discover -s tests -v
```

Tests use synthetic button levels, generated JPEGs, fake grants/provider outputs
and an in-process HTTP adapter. A generated local CA test also exercises manual
input through a real spawned HTTPS child, accepted paired session and context
route with a fake provider, then verifies child cleanup. These checks do not
prove physical switch behavior, actual phone readiness, cloud deployment or
Gemini accuracy. TLS configuration tests require certificate/hostname verification. Existing
required CI runs root/backend suites, not the separate edge root: edge results
are explicitly recorded locally; no workflow/protection was changed here.


## Private run report (CS-027)

For the next real Pi run, create a private result directory outside Git and add
`--context-report "$results_dir/context.json"` to the enrolled context uploader
command (with `--context-audio` for speaker testing):

```sh
results_dir=$(mktemp -d "$HOME/canesight-context-results.XXXXXX")
# Add --context-report "$results_dir/context.json" to the enrolled command above.
# While running: status / release / press / cancel / off, each followed by Enter.
# After stopping the uploader:
cat "$results_dir/context.json"
```

Private report files are supported only on POSIX hosts (including Raspberry Pi
OS/Linux and macOS). Windows ACL verification is not implemented: requesting a
report on Windows fails before opening any output or starting GPIO/audio. The
GPIO observer and menu bench require a report and therefore require POSIX;
report-free uploader and pure gesture/state tests remain available on Windows.
Report-file success tests are explicitly POSIX-only; portable tests verify
unsupported-platform refusal without filesystem access. Earlier 182-case combined
passes were on macOS/POSIX, not Windows validation.

The file is created exclusively with mode 0600 and refuses checkout/public
folders or existing files/symlinks. It is written on normal exit or failure,
including enrollment/startup failures after argument validation. It contains
only build commit, run outcome, input mode/selection, opt-in/consent/closed/fault flags and request
counters from the runtime. No images, precise positions/times, grant/session/
source/boot IDs, endpoint, paths or arbitrary exception text are recorded.
`complete` means the process returned normally, not that a request succeeded.
`physical_audio_accepted` and `phone_backend_verified` remain false; report counts
are evidence for inspection, never automatic acceptance. An abrupt power loss or
SIGKILL can leave an empty report; rerun to a new filename after inspection.
The report never supplies readiness or bypasses missing phone/clock/backend
prerequisites. Pairing a speaker alone does not unblock context requests.


## Installed GPIO21 input — issue #68

Michael reports OUT on BCM21 (physical pin 40), VCC at 3.3 V (pin 1), ground on
pin 39, HIGH pressed and LOW released. `edge.context_gpio.GPIO21Input` opens only
`DigitalInputDevice(21, pull_up=None, active_state=True, bounce_time=None)`, matching
that installed active-drive configuration. It never configures GPIO18/19 or any
output. No internal pull is enabled: the circuit must drive a stable input, as
explained in the [GPIO Zero input documentation](https://gpiozero.readthedocs.io/en/stable/api_input.html).
The issue records actual wiring separately from the master plan's proposed pin;
this opt-in adapter does not amend that protected baseline or adopt the unshared
local motor bench package.

For an input-only observation on the refreshed combined checkout, as the Pi user
whose GPIO Zero installation already worked:

```sh
results_dir=$(mktemp -d "$HOME/canesight-button-results.XXXXXX")
python3 -m edge.context_gpio --observe --seconds 30 --output "$results_dir/input.json"
cat "$results_dir/input.json"
```

Release, press, hold, then release while it runs. This observer uses only the
standard library plus GPIO Zero; it does not import camera/backend dependencies,
activate audio/motors, or send context requests. It records raw edge counts, not
application debounce or electrical acceptance. Reports remain explicitly unverified
for PM inspection; no endpoint or device identity is saved. GPIO selection is recorded separately from successful reads; startup failure
keeps `gpio_used` unknown. `motor_gpio_used` remains false. GPIO Zero is an
optional Pi system dependency, never imported by default terminal operation.

Once real phone/session/backend prerequisites are established, replace
`--context-stdin` with `--context-gpio21` in the existing enrolled uploader command;
keep consent, receiver, binding and simulated-policy flags. `--context-audio` and
`--context-report` work with either input. The flags are mutually exclusive.
The initial real level is read before timers start: a held button cannot benefit
from the terminal adapter's synthetic released state. Release-to-arm, 30 ms debounce,
10 s cooldown and a second press cancelling pending work remain the same. A long
hold does not repeat. GPIO reads are polled every 10 ms; read failures withdraw
consent and cancel. The independent runtime checks input age and suppresses/cancels
if no successful read arrived for over 100 ms, even while the GPIO reader stalls.
This is best effort Python scheduling, not instrument-measured response time.
Cleanup closes only this input device and owned runtime resources. Ctrl+C/SIGTERM
stops the uploader; physical-button mode does not read terminal commands.

Issue #68 confirms earlier real camera uploads and reported motor operation; it
explicitly says phone depth streaming is not ready. A working button or speaker
therefore cannot satisfy the live readiness gate. Keep the context/audio PRs draft
until current-head Pi input/audio evidence and the actual enrolled path are reviewed.
CS-023/CS-025 motor work and CS-018 accessible controls remain with their owners.


## Merged crossing-menu rollout — CS-027

[PR #71](https://github.com/michaelkrymski/CaneSight/pull/71) merged the normative
`docs/operations/CROSSING_ASSISTANCE.md` brief into accepted main `5dbb6ad`.
`edge.context_menu.CrossingMenu` is the deterministic interaction component:
30 ms debounce, idle context event only on short release, 3000 ms menu entry,
no default selection, three labels and wrap, separate 1000 ms confirmation hold,
entry/confirmation release barriers, active cancellation on a new debounced
press, 15 s inactivity and 30 s absolute menu cap. Startup/recovery-held input
cannot dispatch. Source/consent/audio loss and epoch changes clear selection;
clock faults latch until replacement. Events carry a local generation/epoch,
are returned directly with no FIFO, and do not introduce wire fields.

Capabilities default to empty: unsupported confirmation announces unavailable
and cannot activate. The component emits a context gesture; it does not create
requests, override the existing ContextButton cooldown, invoke Gemini, or infer
signals/traffic state. This checkpoint **does not replace the existing uploader
input path**. Production gesture/request integration still needs the reviewed
adapter bridge and trusted CS-018 audio/source readiness. Existing uploader flags
remain the previous one-shot path and rollback target.

### Controlled interaction bench

The combined test checkout also contains CS-040's fixed phrase audio component.
From that checkout on Pi, after checking the current speaker output:

```sh
git pull --ff-only
results_dir=$(mktemp -d "$HOME/canesight-menu.XXXXXX")
python3 -m edge.menu_bench --speak --audio-confirmed --consent --synthetic-adapters --gpio21 --output "$results_dir/run.json"
cat "$results_dir/run.json"
```

This is an explicitly synthetic **interaction-only** bench. It does not acquire
images, create analysis jobs/requests or emit traffic observations. Motor GPIO is
unused. Synthetic capability selection is explicit; omit `--synthetic-adapters`
to exercise unsupported-mode refusal. Use `--simulate-audio` instead of real
speech for silent tests; no automatic fallback. GPIO Zero is needed only for
`--gpio21`; omit that flag to use timed terminal `press`/`release` commands.
No phone/backend/camera/dependency installation is needed for this bench.

1. Release, hold 3 seconds, then release: hear the observation disclaimer/menu.
2. Short press/release: hear the first label. Repeat to cycle all three and wrap.
3. Hold a selected option for 1 second, then release: hear confirmation. This
   demonstrates interaction only, with no observation adapter or model job.
4. A new press cancels. Holding the entry/confirmation gesture cannot double-dispatch.
5. Let a menu idle 15 seconds; it closes. A held menu cannot survive its 30 s cap.
6. In SSH, `status` prints bounded state/counters; `audio-off`/`audio-on`,
   `source-off`/`source-on`, and `hazard-on`/`hazard-off` inject labeled test state.
   Loss cancels, and recovery never restores a selected/active scenario.
7. `cancel`, `consent-off`, `quit`, EOF or Ctrl+C stop the owned optional audio.
   Consent withdrawal is permanent for this bench instance.

The normal hardware device has no automatic route-health adapter in this bench.
`--audio-confirmed` is an operator assertion, not OS Bluetooth monitoring. Use
`audio-off` immediately for reported loss; automatic disconnect detection remains
an integration gate. The independent worker drives expiry while stdin is blocked;
GPIO read failures/stalls suppress state. No model/source health is inferred from
a button, successful process, heartbeat or missing detection. Speech clarity and
buffered audible cancellation still need human observations. Reports save fixed
state/counters only and keep physical acceptance false. No road-use test.

## Opt-in uploader menu/request bridge (CS-027 follow-up)

The follow-up `--context-menu` path uses the same enrolled uploader frame/session,
ContextClient, one ContextButton and narration controller. A debounced short
release in idle dispatches the existing bounded request; it never dispatches on
the initial press. Holding 3000 ms opens the fixed spoken menu without a request.
Existing one-outstanding request, ten-second cooldown, original capture +8s
expiry, consent and primary-source gates remain. Entering/cancelling the menu
cancels old requests before optional speech; late replies cannot replace the menu.
An input edge can stop old optional narration early, even before debounce, but
cannot start a request early. No scenario or other field is added to the wire.

This path depends on the separately reviewed CS-040 completed-gesture API and
speech channels; without that installed it refuses startup and closes owned audio.
It is off by default. With the existing enrolled input/consent/policy flags,
add all three flags only for a controlled run:

```sh
--context-audio --context-menu --context-menu-audio-confirmed
```

`--context-menu-audio-confirmed` means the operator has just checked audible
output. It is manual confirmation, **not automatic Bluetooth route detection**.
Stop the run on speaker loss. In terminal mode `audio-off` immediately stops
optional audio and latches route loss until a new controller/run; `audio-on`
cannot undo it. Programmatic composition may instead supply a prompt, trusted
`audio_ready()` callback; missing, failed or non-true readiness fails closed.
Recovery does not replay speech and requires stable release and a fresh gesture.

All three scenario capabilities remain unavailable. Selecting and confirming a
scenario announces unavailable and cannot activate a job or initiate a context
request. This connects the actual one-shot request path and fixed interaction;
it does not implement pedestrian recognition, beacon/vehicle tracking or a
scenario-specific provider job. Higher-priority hazards, source/camera/input
loss, consent withdrawal, clock faults and cleanup retain cancellation. Separate
speech ownership prevents the idle description timer from silencing menu phrases.
No motor GPIO is introduced. Paired-device, real-provider, route-monitoring and
physical audible-cancellation acceptance remain pending.
