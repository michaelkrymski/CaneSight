# Debounced context request button — CS-027

`edge.buttons.ContextButton` is an opt-in software coordinator with injected input,
latest-frame and request adapters. `edge.context_client.ContextClient` supplies a
Pi-role HTTPS adapter for the accepted CS-039 context service. No GPIO driver,
speech sink or motor output is included or armed. The originating uploader now
has an explicit opt-in manual terminal adapter; default operation is unchanged.

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

The user confirmed that no physical button is installed. Use the uploader's
manual terminal mode with explicit scene-sharing consent:

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
suppress requests. A nearby obstacle also cancels context. Haptic outputs remain
simulated, and context cannot change the policy, watchdog or motor requests.

Commands are case-sensitive, each followed by Enter:

- `press`: hold the synthetic input pressed. After 30 ms stable input, request
  context (or cancel an outstanding request on a second debounced press).
- `release`: release the input. Release before another press; holding never repeats.
- `cancel`: immediately cancel and release; the ten-second cooldown remains.
- `off`: withdraw consent, cancel, and purge the retained frame. Restart and
  reenroll for another consented session. EOF or input failure also withdraws.

After readiness recovery, release and press again. Commands entered before
readiness are not queued. Unknown commands cancel without echoing input;
oversize lines are drained with bounded reads. Terminal input is not an API for
arbitrary commands. Output contains only closed object labels with an AI and
uncertainty label; it is text, not audio or narration integration.

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

The injected `ContextButton` API remains available for a future reviewed hardware
adapter. Use the application's `if __name__ == '__main__':` entry guard for
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

## What remains

Physical button pin selection, voltage/pull-up/debounce behavior, boot/off-state
checks, camera scheduling and full Pi run evidence require their actual devices
and the accepted electrical prerequisites. No physical GPIO activation was
performed. The manual uploader adapter is software-tested; its actual Pi/phone
run still needs device evidence and coordination with CS-025. The service must
be packaged/deployed through its deployment
owner; this change does not activate `/v1/context` on the existing Vultr service.
CS-040 remains draft PR #41 and owns narration restrictions, cancellation and
hazard priority; CS-018 owns accessible device audio. Stop/preempt local audio
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
