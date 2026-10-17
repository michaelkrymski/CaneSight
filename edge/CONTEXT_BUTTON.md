# Debounced context request button — CS-027

`edge.buttons.ContextButton` is an opt-in software coordinator with injected input,
latest-frame and request adapters. `edge.context_client.ContextClient` supplies a
Pi-role HTTPS adapter for the accepted CS-039 context service. No GPIO driver,
speech sink or motor output is included or armed. Existing uploader/receiver,
policy, watchdog, deployed backend and task ownership are unchanged.

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

The following is a wiring example for a future reviewed adapter, not a runnable
GPIO setup or evidence that a physical button is connected:

```python
from edge.buttons import ContextButton
from edge.context_client import ContextClient
from edge.uploader import clock_ms

client = ContextClient(pi_session, ca_file=private_test_ca_or_none)
button = ContextButton(latest_frame_supplier, client.start, clock=clock_ms).start()
try:
    # Drive from trusted local state; do not infer consent or health from Gemini.
    button.set_state(ready=context_ready, consent=user_consented, hazard=hazard_present)
    button.sample(raw_pressed)  # Adapter supplies subsequent level changes too.
    result = button.take_result()  # Poll independently; may be None.
finally:
    button.close()
```

Run under the application's `if __name__ == '__main__':` entry guard: request
workers use multiprocessing spawn. Use the originating uploader's same process,
source/boot/session, clock and latest original frame. Keep at most one latest
JPEG for the supplier, under its own short lock; return promptly. Do not launch a
second camera process, reuse a prior boot, fabricate capture timestamps, or
substitute a server clock. Explicit replay fixtures must keep `mode=replay`.
On a new epoch, close this controller/client and construct new ones from the
newly authorized Pi session. Call `close()` during normal cleanup.

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
performed. Uploader integration must be coordinated with the active CS-025
vertical-slice work. The service must be packaged/deployed through its deployment
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
and an in-process HTTP adapter. Real child lifecycle tests prove process cleanup;
they do not prove physical switch behavior or actual TLS deployment. The TLS
configuration test checks mandatory certificate/hostname verification. Existing
required CI runs root/backend suites, not the separate edge root: edge results
are explicitly recorded locally; no workflow/protection was changed here.
