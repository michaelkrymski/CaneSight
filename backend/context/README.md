# Optional context narration — CS-040

`narration.py` is a local speech gate. `consumer.py` now composes the accepted
Pi button, context client and speech gate on one original capture clock. This is
a local adapter API with a synthetic speech sink in tests; it is not installed
in the backend server, iOS app or uploader terminal path yet.
No context messages are added to the accepted shared observation protocol.

Provider output must have exactly this private shape:

```json
{"objects": ["chair", "table"], "uncertain": true}
```

Only one to three labels from `narration.OBJECTS` are accepted. All spoken words
come from a fixed template of at most 20 words, labeled as an uncertain AI
description. Provider instructions/prose, unknown labels, extra properties,
missing uncertainty and invalid structures produce `Description unavailable.`
This restricts language, not factual accuracy: a permitted object can still be
hallucinated. Scene text is untrusted data. No walking-symbol interpretation,
crossing permission, motor command, or movement recommendation exists here.

## Consumer integration

1. Provide a nonblocking local speech adapter with `speak(text)` and immediate
   `stop()`. Calls are serialized; adapters must not reenter the controller.
2. Drive `set_priority(hazard=..., unavailable=...)` from trusted local health
   and obstacle policy. Startup/unknown is unavailable. Gemini never sets these
   flags. Either priority stops current audio and invalidates pending speech.
3. Only with explicit scene-sharing consent, call `begin` with the conservative
   capture-age upper bound in seconds measured on the receiving device. Unknown,
   negative, nonfinite or eight-second-old age is rejected. Do not compare raw
   clocks across devices or reset age at network receipt.
4. Correlate the returned ticket with the context request. Pass the structured
   result to `deliver`. New requests supersede old tickets; delivery is single
   use. The deadline is eight seconds from the bounded capture time.
5. Call `tick()` on an independent local timer while audio is active, even if
   network/provider work is blocked. Expiry stops audio. Call `cancel()` for
   manual cancel, backgrounding, session/epoch change or disconnect, and cancel
   provider work separately. Recovery needs a new request. Call `close()` during
   teardown; a failing stop adapter permanently disables this controller.

Every begin, delivery and tick checks the clock against the highest previous
reading. A reversal, exception, invalid or nonfinite reading stops audio and
invalidates the pending ticket. Cancellation/new requests do not reset clock
history. After reversal, new requests are refused until a valid reading reaches
the previous high-water mark; recovery never revives the old ticket.

This gate has no authority to change health, haptic patterns, signal state or
permissions. Integration still requires CS-039 (provider), CS-027 (button) and
CS-018 (accessible phone audio/manual cancel). No hardware audio, VoiceOver,
background execution or GPIO behavior has been verified.

Run from the repository root:

```sh
python3 -m unittest discover -s tests/context -v
```

## Local button/client composition

`ContextNarration` runs in the originating Pi process, never on the cloud server:

```python
from backend.context.consumer import ContextNarration
from backend.context.pi_speech import EspeakSink
from edge.context_client import ContextClient
from edge.uploader import clock_ms

sink = EspeakSink()  # Opt-in only after testing the selected Pi audio output.
consumer = ContextNarration(
    latest_original_frame, ContextClient(private_pi_session), sink,
    priority=trusted_camera_and_primary_priority,
    consent=current_explicit_scene_sharing_consent,
    clock=clock_ms,
).start()
try:
    consumer.sample(raw_pressed)  # Adapter supplies release and press transitions.
finally:
    consumer.close()
    sink.close()
```

This is an integration API example, not a second camera runner or GPIO setup.
The frame supplier must return the originating uploader's canonical `Frame` on
this exact clock/session/boot. The priority callback must include current camera
readiness/freshness and trusted primary-source state and return `(ready, hazard)`;
unknown is disabled. Do not infer readiness from Gemini or socket connectivity.
Consent is a separate current callback; unknown or exceptions disable requests.
All callbacks and the speech sink must return promptly and must not reenter the
consumer. Its single independent 10 ms worker drives button debounce, network
polling, capture expiry and narration priority; it does not also start a separate
button worker. A stalled frame supplier/priority/sink violates that adapter
contract; Python threads are not a hard real-time guarantee.

When the debounced button actually starts a request, the consumer binds one
speech ticket to that request. It uses `begin_capture` with the original local
capture timestamp in seconds: expiry is capture + 8 s, never a new eight-second
window at receipt. Client/button validation checks reply lineage and closed
labels before the speech gate renders it. Failed, cancelled or late jobs cannot
speak. Cooldown survives cancellation. A new press interrupts active optional
speech; repeated held samples do not. Hazards, unavailable state and consent loss
stop local audio before requesting network cancellation. Recovery cannot replay
a response. The independent timer also stops active speech on expiry or clock
failure/reversal. Manual `cancel()` stops both paths, and `close()` tears down.

A generated local HTTPS test exercises release/press -> actual spawned Pi HTTP
client -> accepted paired-session context endpoint -> fake provider -> synthetic
speech sink, then obstacle preemption. It proves software composition and TLS
transport, not physical audibility, a real phone/camera, public deployment or
Gemini accuracy. No external scene/API request is used. PR #41 remains draft:
the user selected a Bluetooth speaker connected to the Pi. The eSpeak adapter
is implemented, but uploader installation, speaker routing, accessible controls
and device priority/cancellation evidence remain unfinished. CS-027 terminal output
continues to be text only. No out-of-scope uploader/runtime or shared protocol
changes are included here.

## Pi speech through the selected Bluetooth output

The user selected a Bluetooth speaker connected to the Pi. `pi_speech.EspeakSink`
uses an installed absolute `/usr/bin/espeak-ng` executable and the system audio
output selected for the same user running the Pi agent. It does not pair devices,
change volume/routing or activate itself on import. Configure and audibly verify
the Bluetooth route before opting in. Do not assume process success proves a
speaker is connected; automatic fallback to another output is OS-dependent.

The adapter accepts only the renderer's closed uncertainty template or
`Description unavailable.` (at most 20 words). It passes bounded text on stdin
with fixed `--stdin`, without a shell, text in command arguments, temporary audio
files or provider prose. This follows the official [eSpeak NG usage guide](https://github.com/espeak-ng/espeak-ng/blob/master/docs/guide.md).
One owned process group plays at a time; replacement/cancel/close kills and reaps
that group within a bounded 200 ms wait. Engine failures latch unhealthy and
suppress further context until the adapter is replaced. Other cues/processes
and the audio server are not killed. The controller stops local audio before
cancelling provider work.

Tests execute a synthetic replacement executable, proving bounded stdin,
replacement, kill/reap, failure latching and input rejection without audio.
Actual eSpeak NG, Bluetooth delivery, disconnect/reconnect, startup/off-state,
obstacle/manual preemption and buffer-flush latency still require the Pi and
speaker. Bluetooth/OS buffering can outlast process termination; cancellation is
best effort until measured on that device. Do not claim instant physical silence
or prevent a higher-priority cue based solely on this software test. No pairing
credentials, Bluetooth addresses, recordings or images are committed.

## Synthetic Pi speaker/cancellation bench

`python3 -m backend.context.speaker_bench --speak --repetitions 3` uses the actual
Pi eSpeak sink with fixed synthetic labels, capture times and priority events.
It requires only the standard Python library and installed eSpeak NG; no phone,
camera, provider, network, API credential or GPIO is used. Run as the normal Pi
audio user with the already selected Bluetooth output; the bench does not change
routing or volume. The operator reported Bluetooth/eSpeak playback working, but
this is not yet evidence for the adapter's audible cancellation behavior.

Cases repeat manual cancellation, synthetic hazard, synthetic unavailable,
independent capture expiry (a synthetic seven-second-old capture leaves about
one second), and suppression of an expired result. The first three interrupt
a fixed sentence after one second; `--interrupt-after 1.5` may be used if startup
is slower. Answer each audible observation with `y`, `n` or `u` (unknown). These
are human observations; software process status cannot establish audible stop.
Ctrl+C/EOF stops the owned speech process and marks the run incomplete.

To retain a new private report outside the repository:

```sh
bench_dir=$(mktemp -d "$HOME/canesight-speaker-bench.XXXXXX")
python3 -m backend.context.speaker_bench --speak --repetitions 3 \
  --interrupt-after 1 --output "$bench_dir/results.json"
```

The JSON includes the tested Git commit, synthetic-input flags, per-case software
checks and operator answers. `stop_call_ms` measures the local stop call, and
`timer_stop_after_deadline_ms` measures software timer overshoot; neither measures
speaker latency or buffered audio. Note audible tail separately without claiming
an unmeasured duration. Reports are exclusive/new, mode 0600 in a private parent;
existing files and checkout paths are refused. Exit 0 requires software checks
and all operator answers yes; exit 2 means failed/unknown evidence, and Ctrl+C/EOF
is incomplete. Physical acceptance remains false until independent PM review.

Use a separate test-only checkout containing #41 and #58 to exercise the combined
software; this is not a main/PR merge or release. The speaker bench itself checks
#41's gate/sink, not live uploader sensing. Bluetooth disconnect/reconnect and
full phone/backend integration remain unverified; neither is fabricated as a
pass by this command. Record separate speaker disconnect/reconnect observations
before claiming that case. No speaker identities or credentials are written.


## Pi Bluetooth recovery follow-up (CS-040)

The earlier three-round operator run at combined commit `9607f76` passed 15
synthetic speaker cases; it did not test disconnect/reconnect. With the updated
combined test checkout and speaker selected as the same Pi user, run:

```sh
results_dir=$(mktemp -d "$HOME/canesight-speaker-recovery.XXXXXX")
python3 -m backend.context.speaker_bench --speak --repetitions 1 \
  --interrupt-after 1 --bluetooth-recovery --output "$results_dir/run.json"
cat "$results_dir/run.json"
```

First complete the five existing cancellation/expiry cases. For recovery, follow
the prompts: disconnect during an audible sentence, report the observation, then
reconnect/select the output using the Pi audio controls. The controller marks
output unavailable and cancels before waiting for reconnection. Confirm silence
with no old sentence returning. Only affirmative observations allow a new ticket
and fresh sentence. Answer `n` or `u` if unsure; no/unknown never passes. Ctrl+C or
EOF stops owned speech and writes an incomplete report. No pairing, routing or
volume changes are made by the script. Keep a local means of stopping playback.

The report records operator observations separately from software checks.
`bluetooth_disconnect_reconnect_verified` and `physical_audio_accepted` remain
false for PM review; software cannot detect the actual Bluetooth route or measure
an audible buffered tail. The explicit operator-reported unavailable transition
is not automatic OS route-loss detection. If eSpeak fails, restart only after
inspection; the sink intentionally does not clear a fault or replay old speech.
This uses synthetic labels/capture/priority, with no camera, phone, network,
backend request, Gemini or GPIO. Full phone/backend verification remains open.


## Hardware handoff #68 (2026-10-18)

[Michael's issue #68](https://github.com/michaelkrymski/CaneSight/issues/68)
supersedes the earlier no-button assumption: active-high BCM21 input now exists,
as do reported camera uploads, manual motor-channel operation and standalone
speaker playback. The local motor bench package mentioned there is not uploaded;
this narration implementation does not rely on it or claim its motor outputs.
CS-027's opt-in input-only GPIO21 adapter can feed the same context/narration
controller once the real phone/session/backend prerequisites exist. Those gates
remain mandatory; installed hardware cannot manufacture source readiness.

The earlier 15-case operator speaker report and the newer issue's motor bench are
separate evidence. Issue #68 supplies no new combined context/audio lifecycle or
Bluetooth recovery result and explicitly reports phone depth not ready. Keep #41
and #58 draft, retain prior evidence, and collect current combined-checkout input
and recovery reports. CS-018 owns accessible controls; CS-023/CS-025 own motor
integration. No baseline pin-map amendment or physical acceptance is made here.


## Focused manual-cancel diagnostic

Two operator recovery reports at combined commit `6dfda42` are retained in
`tests/context/evidence/CS-040-speaker-recovery-operator-reports-20261018.json`.
The later recovery observations passed (disconnect, reconnect silence, fresh
speech), while manual cancellation stayed operator-negative in both. The operator
clarified that the first run's manual sentence was inaudible. A fast stop-call
return does not establish audible cancellation; the earlier successful 15-case
run remains separate evidence. Neither mixed run is full acceptance.

The updated bench supports `--manual-only`, which runs only manual cancellation
and marks `case_selection: manual-only`. For a focused comparison, use a fresh
private report and a two-second diagnostic delay:

```sh
results_dir=$(mktemp -d "$HOME/canesight-manual-cancel.XXXXXX")
python3 -m backend.context.speaker_bench --speak --manual-only \
  --repetitions 1 --interrupt-after 2 --output "$results_dir/run.json"
cat "$results_dir/run.json"
```

Answer yes only if speech was audible and then interrupted without restarting;
answer no/unknown if it was absent or already finished. The longer stop delay is
a diagnostic variation, not a fix, production timing change or proof of the prior
one-second case. Do not combine `--manual-only` with `--bluetooth-recovery`.
The selector skips unrelated cases; subset success never establishes full bench,
physical speaker acceptance or phone/backend integration. No warmup, hidden retry
or automatic Bluetooth routing is added to make the first attempt appear to pass.


## Merged CS-040 crossing-menu speech component

Accepted main `5dbb6ad`/PR #71 adds the crossing-observation menu brief.
`menu_audio.FixedMenuAudio` renders a closed fixed set: disclaimer/menu entry,
three selected labels, confirmation, cancellation and unavailable. Only those
exact phrases are added to EspeakSink's allowed text. Existing uncertain object
rendering and its 20-word limit are unchanged; provider prose never enters menu
speech. No traffic evidence or permissions are generated.

The caller must supply trusted audio availability, higher-priority state and the
same local epoch/generation as CS-027's state machine. Engine success alone is
not Bluetooth readiness. Loss/preemption clears speech eligibility; recovery
requires a newer explicit entry. Clock/engine faults latch, wrong epochs/stale
generations are refused, and a 15-second independent tick expiry bounds optional
speech. No pending speech FIFO or silent confirmation is introduced. Call update
and tick from an independent worker and cancel before network/analysis teardown.

CS-027's `edge.menu_bench` composes these APIs in an explicitly synthetic
interaction-only bench, optionally with the reported GPIO21 and real speaker.
See edge/CONTEXT_BUTTON.md on the combined checkout for commands and observations.
Production adapters and automatic OS output monitoring are not supplied by this
component; the existing uploader remains its previous one-shot path. Preserve
old speaker reports as different builds; new menu speech clarity/stop buffering
and full lifecycle need current-head Pi evidence. Keep #41/#58 draft. No live
signal/beacon/vehicle adapters, wire fields, model training or road-use claim.

## Opt-in automatic Bluetooth route guard (CS-040 follow-up)

`EspeakSink` can monitor the explicitly selected Linux `bluez_output` sink using
read-only `/usr/bin/pactl` JSON and `/usr/bin/busctl` BlueZ observations. It checks
that the matching Bluetooth device reports connected, the sink exists exactly
once, is a BlueZ sink, is not muted, and has nonzero per-channel volume. IDLE and
SUSPENDED are normal connected idle states, not proof of disconnection. Ambiguous,
malformed, failed or oversized observations fail closed. Existing OS-selected
speech remains unchanged when neither new setting is present. Setting only one,
a mismatched address or an unsupported host refuses monitored startup.

Configure both values privately as the normal audio user, using the actual
existing sink and device path (the addresses below are synthetic placeholders):

```sh
export CANESIGHT_BLUETOOTH_SINK='bluez_output.AA_BB_CC_DD_EE_FF.1'
export CANESIGHT_BLUEZ_DEVICE='/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF'
python3 -m backend.context.bluetooth_route --check
```

The check performs one read-only observation. It emits only closed JSON status,
not sink/device identities, command output or arbitrary exception details; it
plays no audio and starts no background monitor. A positive check is not an
audible-delivery pass. Do not copy private device configuration into Git.

The Pi must have `espeak-ng`, `paplay`, JSON-capable `pactl` and `busctl` installed
at the documented absolute paths, with its existing per-user PulseAudio/PipeWire
session and BlueZ system-bus access. This checkpoint does not install packages,
services, pair/connect devices, set profiles, change global defaults or use sudo.
Missing/older unsupported tools stay unavailable; there is no silent fallback.

With both settings present, existing explicit `--context-audio` opt-in creates
the guard automatically. The monitored sink generates WAV through eSpeak stdout
and pipes it to owned `paplay --device=CONFIGURED_SINK`, rather than relying on
where eSpeak's platform audio backend happens to route direct playback. A unique
local stream tag lets the guard check that a live stream stays on that sink.
The tag and other applications' metadata are never logged. Stream registration/
completion has a bounded 200 ms missing-stream grace; an observed move or duplicate
binding is unavailable. Neither this nor BlueZ Connected proves physical sound.

An initial bounded observation must succeed before the adapter is returned to
menu/narration controllers. The monitor polls after 100 ms between observations;
its independent 10 ms watchdog expires cached observations at 350 ms from query
**start**, never completion. Each helper has a 100 ms read/exit budget and 64 KiB
output cap. These are local software limits, not measured or guaranteed audible
stop times; query latency/CPU scheduling and speaker/server buffering need Pi
measurement. Short outages between observations can escape a polling monitor.
No depth/vision/capture-expiry budget is extended by these settings.

Observed loss, query failure/stall, stale cache, stream movement or clock fault
latches the adapter unavailable and stops its playback process before its speech
generator. The independent guard can stop owned audio even if the input/network
worker makes no progress. Existing controller health gates cancel the pending
request/ticket on their next tick; a late reply cannot speak through the faulted
sink. Reconnection never clears this latch or automatically restarts playback.
Stop the run, check/reconnect the speaker using the existing operator setup, and
start a fresh controller/run requiring stable release and a new gesture.

The opt-in uploader menu still requires its explicit menu/audio confirmation
flags. That confirmation alone cannot override a failed automatic guard. Until a
separate change replaces those UI flags, keep both the guard configuration and
the existing controlled-run acknowledgement. Unconfigured audio remains the
previous manually verified OS-selected mode; do not call it monitored.

For a controlled speech/cancellation run, the existing `speaker_bench --speak
--manual-only` inherits these settings. Do not combine this latched mode with the
old `--bluetooth-recovery` bench: that older bench intentionally reuses its sink
for a fresh sentence, whereas this guard requires replacing the adapter after
observed loss. Physical testing must separately record whether playback stops,
any buffered tail, silence after reconnect and a new sentence only after a fresh
run. No actual Pi/BlueZ/paplay or audible verification was performed here.

Implementation references: [BlueZ Device Connected property](https://github.com/bluez/bluez/blob/master/doc/org.bluez.Device.rst),
[busctl property reads](https://www.freedesktop.org/software/systemd/man/257/busctl.html),
and [eSpeak WAV stdout](https://espeak.sourceforge.net/commands.html).
