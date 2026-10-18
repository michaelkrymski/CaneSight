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
