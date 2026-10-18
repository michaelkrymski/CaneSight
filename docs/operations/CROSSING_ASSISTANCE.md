# Crossing assistance implementation brief

Status: proposed plan amendment, pending PR approval and merge. This document
specifies work; it does not claim a working crossing assistant. Decision:
`decisions/CR-CS-001-crossing-assistance-20261018.md`.

## Interaction contract

Use the existing debounced input and monotonic clock. A held button at startup,
after reset, or after recovery cannot dispatch: observe stable release first.
Measure holds from the debounced down edge. One gesture has one meaning.

| State | Input/event | Required behavior |
|---|---|---|
| Idle | Release before 3000 ms | Retain the consented one-shot context request, when eligible; never request on the down edge |
| Idle | Continuous hold reaches 3000 ms | Open menu once; suppress the short-press context request; acknowledge audibly |
| Menu entry | Activation button remains down | Wait for release; this same hold cannot confirm a selection |
| Menu | Initial announcement | "Select crossing type. Press to cycle; hold to select." No scenario selected |
| Menu | First short press/release | Select and speak "Pedestrian walk-and-hand signal" |
| Menu | Next short press/release | Select and speak "Flashing yellow pedestrian beacon", then "Street without a crossing signal", then wrap |
| Menu | New hold reaches 1000 ms with a selected option | Confirm the option once, announce active scenario, and wait for release |
| Menu | Hold with no selected option | Remain in menu and prompt to press to select; do not default silently |
| Menu | 15 seconds without a new debounced interaction | Close menu and discard selection; no activation |
| Active, after confirmation release | New debounced down edge | Cancel immediately; do not wait for release or a hold threshold |
| Any state | Manual cancel, consent withdrawal, session/boot change, shutdown | Cancel jobs/audio, clear selection, evidence and held input; require release and a fresh activation |
| Menu/active | Audio unavailable or disconnected | Cancel to unavailable; no silent confirmation or automatic restart/replay |
| Active | Required observation source becomes stale/unavailable | Cancel analysis and old narration; announce unavailable only if audio is usable; require a new activation |

Menu short presses are committed on release before 1000 ms. A confirmation hold
must not also cycle. Confirmation/activation release barriers must not be mistaken
for active-mode cancel. Menu inactivity uses the local monotonic clock, not
network receipt. A long hold cannot keep the menu alive indefinitely; a stuck
button remains unavailable until released. Cap menu residence at 30 seconds as
an additional stuck-input guard. Clock reversal/failure cancels and latches
unavailable until a new controller. Debounce remains the existing 30 ms starting
value pending physical verification. Terminal adapters must expose press/release
with equivalent timing; tests use a virtual clock rather than sleeping.

Entry: "Crossing observations. This does not tell you when to cross."
Cancellation: "Crossing assistance stopped." Do not defer cancellation behind
the speech queue or a network operation. Higher-priority obstacle/fault audio
preempts menu and crossing narration; recovery never resumes it automatically.
The long hold is not consent: keep the explicit scene-sharing consent gate.

## Three explicitly selected scenarios

| Scenario | Proposed evidence path | Output boundaries |
|---|---|---|
| Pedestrian signal | Verified custom YOLO ROI/symbol detector for walking figure/raised hand; separate supported digit reader and temporal checks | Observed symbol and nullable observed number; unknown on ambiguous target, geometry, glare, occlusion, low confidence, loss or expiry |
| Flashing yellow pedestrian beacon | Purpose-validated beacon detector plus temporal flashing evidence; separate vehicle detections/tracks | Beacon activity and bounded visible vehicle-motion observations only; beacon activity does not establish yielding |
| Street without a crossing signal | Explicit user selection, optional restricted Gemini object description, separately validated temporal vehicle observations | Describe visible evidence and visibility limits; do not infer absence of a crosswalk or unseen traffic from the selected mode |

No automatic scenario inference or GPS-based signal association. A selected mode
does not prove scene type or applicable signal identity. The yellow beacon is
the pedestrian-activated crossing beacon, not a yellow vehicle traffic light.
Do not call flashing from a single yellow image or from an undersampled sequence.

YOLO remains useful for specific verified detections. Generic COCO traffic-light
boxes and the current CS-036/037 schematic profile are not live pedestrian
recognizers. Existing synthetic regression scores are not independent accuracy.
Review real source/video/intersection splits, licenses, per-condition errors,
abstentions and night support before enabling real-camera claims. Unsupported
night operation stays unavailable; synthetic condition variants do not establish
real night performance.

The existing Gemini adapter returns only uncertain object labels. Keep it for
optional descriptions, never signals, vehicle-stop decisions, movement advice or
motor commands. Video/temporal Gemini experiments would be separate reviewed
work, with evidence and a contract proposal before activation. Vehicle tracking
also needs source-specific frame timing, camera-motion/occlusion handling,
bounded track continuity and evaluation. Do not equate unchanged boxes with
stationary cars, estimate speed from uncalibrated box growth, or assume 1 Hz is
sufficient for approaching traffic. Do not raise existing age budgets to make
analysis fit; retain depth 500 ms and vision 1500 ms final-consumer bounds.

Never output "safe to cross", "go", "all clear", "all cars stopped" or "cars
have yielded" as an assurance. A stationary-looking vehicle is limited visible
evidence and may move or conceal another vehicle. No detection is not absence.
No audio/haptic pattern grants permission; no road crossing demonstration.

## Work allocation and rollout

Existing GitHub owners remain responsible; this amendment assigns no new owner
and changes no runtime status or completion evidence. Follow-up PRs must fetch
the merged amendment before implementing revised acceptance.

| Task | Next deliverable |
|---|---|
| CS-027 (Mila) | Deterministic gesture/menu/scenario state machine, immediate cancellation, terminal adapter, then inspected physical button adapter; preserve single context request, cooldown and consent |
| CS-040 (Mila) | Fixed menu/acknowledgement/status phrases, audio readiness and preemption, no stale replay after Bluetooth reconnect; retain speaker cancellation bench |
| CS-036 (Adit) | Document real pedestrian/beacon/vehicle data and licenses; verify trained artifacts and deployment manifest; disclose night/data gaps |
| CS-037 (Adit) | Isolated scenario observation adapters, nullable countdown, beacon temporal evidence, bounded vehicle-track prototype; no production enablement without evaluation |
| CS-038 (Adit) | Held-out, per-scenario/per-condition evidence with denominators and abstentions; moving camera, multiple vehicles, occlusion, night gaps, false beacon/symbol cases |
| CS-039 (Mila) | Preserve restricted Gemini provider, consent, separate queue and cancellation; tag/correlate local scenario requests without interpreting Gemini as traffic readiness |
| CS-044 (Gavin) | Menu/hold/cancel failure campaign; original-age, source loss, session changes, speaker reconnect and blocked-worker tests |

Order: (1) merge amendment; (2) implement and test menu with explicitly synthetic
adapters and available speaker; (3) evaluate pedestrian detector/countdown before
opting into live observations; (4) develop/evaluate beacon and vehicle temporal
adapters independently; (5) controlled bench integration with known button/audio,
phone/Pi identity, clock bounds and physical prerequisites. Unsupported adapters
announce unavailable. Do not ship a working-looking menu backed by canned live
observations. No hardware claim from a software test. Existing P0 depth/haptics
work remains independent and higher priority.

New scenario or track fields crossing processes require a separate shared
contract CR. This amendment introduces no wire schema and deploys no service.
Record evidence by exact commit, input provenance, devices, failures, timing,
audible cancellation delay/buffering and remaining limitations. User-reported
speaker playback is useful setup evidence, not an adapter cancellation pass.

## Required acceptance matrix

- Thresholds: 2999/3000 ms entry; 999/1000 ms confirm; bounce; startup held;
  one-shot context only on idle short release; no double dispatch.
- Menu: no default, all three spoken labels, wrap, confirmation without cycling,
  release barriers, inactivity/stuck-input expiry and no queued stale presses.
- Active: cancel on down edge; repeated/held input cannot restart; one analysis
  job at a time; fresh explicit activation required after cancellation/failure.
- Audio: unavailable at entry/confirmation, stop during long speech, Bluetooth
  loss/reconnect, priority preemption, expiry, Ctrl+C and buffered speech evidence.
- Sources: heartbeat-only, old result after scenario switch, wrong session/boot,
  camera/network interruption, target loss and clock failure cannot restore state.
- Vision: multiple/ambiguous heads, beacon vs vehicle yellow signal, insufficient
  temporal sampling, camera motion, hidden/lost vehicles and unsupported night
  inputs stay unknown; no invented countdown, stationary or crossing assurance.
- Privacy/resources: explicit consent, no production images in Git, bounded
  queues/caches, cancellation propagation and existing cooldown remain enforced.

Rollback: select previous application build/feature configuration and cancel all
new jobs/selection/audio. Preserve the established one-shot context path and
independent depth expiry. Never restore a selected or armed mode after restart.
