# CaneSight iPhone app — CS-013

Open `CaneSight.xcodeproj`, scheme **CaneSight**. The app targets iOS 16+;
its native UI test runner targets iOS 17+. Local signing remains in ignored
`Signing.local.xcconfig`. No team identifiers or credentials belong in Git.

Scheme **CaneSightTransport** hosts CS-016 tests inside the signed app on iOS 17+.
It compiles the existing core/client test files and the depth adapter source
directly; `DeviceTests/TelemetryDeviceTests.swift` adds real ARKit capture sampling
and a public HTTPS reachability probe. It does not enable streaming in the app.
Run this scheme on the connected physical phone using Xcode's normal signing.
The product-only Swift package scheme cannot run tool-hosted tests on a phone.

## Current features — calibrated mount continuation, 23 October 2026

- Camera tab: real portrait 9:16 rear-camera preview, explicit Start/Stop,
  scene-depth support and permission handling. The selected detection band spans
  the full preview width and has left/center/right thirds. A helper explicitly
  chooses its vertical position and height; the initial height is 1/8 of the view.
- The earlier yellow 20×40 debug patch was found in ContentView.swift and its
  corresponding 9×8 diagnostic cells in CameraController.swift. During physical
  setup Michael clarified that obstacle sectors should span the preview thirds.
  This explicitly supersedes using that tiny inspection patch as the entire ROI:
  the new band is 180 pixels wide on the 180×320 preview, initially 40 high.
- Required helper-assisted mount setup: stable neutral depth/pose window, three
  fresh broad-target records for each physical side, low obstacle check, explicit
  helper save. Calibrate mount or Mount moved clears eligibility and old source
  epochs synchronously. Normal restarts reuse a confirmed compatible profile.
- Gravity-level pitch/roll compensation uses the pose on the exact ARKit depth
  frame. The projected physical ray region is drawn on the preview. Its yaw
  follows the cane/camera heading, rather than a fixed world compass direction.
  Original depth samples are selected once; no unseen/low-confidence depth is filled.
- Current, confidently classified near-level floor geometry supports a narrow
  2 cm exclusion slab inside the observed boundary. Missing/ambiguous floor,
  unsupported pose/height, incompatible profile or out-of-view sectors stay
  unavailable. No blanket bottom crop, lowered confidence, all-clear or drop-off claim.
- The unchanged processor still needs high confidence, 25% valid coverage and
  32 samples and uses the near tenth percentile. Selected per-sector source
  samples are packed once into a rectangular processor input with NaN padding;
  all sectors use the largest selected-sector count rounded up to a bounded grid row as a conservative denominator.
  Null/unknown observations never create obstacle cues.
- Status tab: the unmodified CS-018 accessible view, labelled unknown/connection/
  audio values, large controls and system Dynamic Type. The host invalidates its
  display independently of view mounting. Display tokens travel with captures
  before asynchronous processing; late results cannot acquire a new token.
- Read app status aloud: one fixed local status utterance, no scene description,
  distance speech, network/provider call or automatic repeat. Cancel invalidates
  its callback identity before stopping AVSpeechSynthesizer immediately. A failed
  sink stop reports failure. Scene/depth invalidation cancels pending speech;
  VoiceOver and other system audio are not stopped. Speaker buffering is unmeasured.
- Location tab: explicit local consent, off each launch, foreground-only Core
  Location through the accepted CS-019 provider. Show availability/fix age/coarse
  uncertainty, not coordinates. Opt-out purges the host snapshot and provider
  context. No location is saved, transmitted or associated with lanes/signals.

The normal launch keeps networking disconnected. The **Connection** tab now
imports an existing phone-role bond file, saves it in this device's unlocked-only,
non-synchronizing Keychain, and explicitly connects to the fixed Vultr backend.
No bond or operator credential is generated. The native phone polls the existing
`/v1/bonds/connect` interface and uses the existing header-authenticated WSS sender;
**no persistent Mac helper is required**. A saved bond alone does not start a
connection or prove depth readiness. See the local integration checkpoint below.
GPS remains local and no image upload or Gemini request is wired into this host.

## Exact dependency preparation

```sh
git fetch origin
python3 ios/CaneSightApp/prepare_review_dependencies.py
```

`ReviewDependencies.json` records five immutable Git inputs: accepted lifecycle
and coarse-location source from #63/#87; review depth #62, accessible status #73
and portrait mapping #70. CS-016 telemetry resolves directly to the sibling
`../CaneSightTelemetry` package on this continuation branch. Preparation uses Git archives,
verifies every source hash on reuse and refuses to overwrite changed inputs.
Move/preserve an older prepared directory before switching manifests. It never
edits teammate source/task/branch or executes their scripts.

The depth package's nested location mirrors CS-015's declared relative package
path; both the host and mapping package resolve the **same** depth source folder.
Review dependencies are not copied into tracked app source or claimed as merged.
The host adopts only its own earlier CS-015 bench capture plumbing.

## Timing and lifecycle limits

Bounded capture uses one worker, one replaceable pending frame and one replaceable
main delivery. Critical AR interruptions fence the source epoch immediately.
Frame/depth/confidence transformation and thumbnail use the actual ARKit display
transform. Original source timestamps are preserved and must increase.

The 500 ms local callback-recency deadline is a stall detector, not sensor capture-
age calibration. Source-clock bounds, capture-to-Pi timing, final mount/motors and
paired transport remain unverified. Accepted CS-017 bridge code forwards native
lifecycle events; local preview does not mark its lifecycle guard clock-mapped. The optional
diagnostic connection uses its own explicitly unverified elapsed epoch. Unknown values never mean an empty path.

`PrivacyInfo.xcprivacy` declares on-device elapsed-time/timer use of system boot
APIs under 35F9.1. The normal app sends no boot-time-derived information. The opt-in CS-016
paired test sends elapsed intervals from one fixed test-start event; it keeps
the raw media-clock origin on device. Clock/capture values share that origin,
so rebasing preserves original age and does not replace capture with receipt.
Runtime checks reject clock jumps and captures outside the local 500 ms bound;
these observations do not prove general source-clock equivalence or sleep behavior.
Apple 35F9.1 allows elapsed intervals between in-app events to leave the device;
this remains an engineering interpretation, not App Store acceptance. See see [Apple required-reason API documentation](https://developer.apple.com/documentation/bundleresources/app-privacy-configuration/nsprivacyaccessedapitypes/nsprivacyaccessedapitype).

## Verification — 18 October 2026 integration checkpoint

- Signed physical-iOS SDK build with Xcode 27.1; strict signature verification,
  install and launch on iPhone 17 Pro Max / iOS 26.6.2.
- Five actual phone UI tests passed without skips: maximum text/large controls;
  live depth → Stop/Unknown → restart → Home Screen/background → live recovery;
  one-time GPS permission/coarse fix/opt-out; location default off; fixed status
  speech and real local cancellation hook. No audible stop-latency claim.
- Two Simulator UI tests passed: largest-text controls and unsupported camera
  displays unavailable with capture disabled.
- 60 strict-concurrency Mac XCTest cases passed: current accepted lifecycle 12,
  current coarse location 15, accessible status 17, mapping 11, PreviewState 5.
- Current accepted lifecycle ran 14 iOS Simulator cases, including both native
  ARKit/UIKit bridge cases. The earlier pinned 61-test report remains historical
  and does not replace this newer lifecycle verification.

UI tests launch/relaunch the app and stop the camera after successful capture
checks. Physical object placement, nonzero background counter reset, VoiceOver
listening/focus and measured accuracy/latency are not inferred from UI assertions.
Private screenshots/result bundles stay local. The one-time location test records
only availability; no coordinates or precise trace enter test evidence.

Earlier setup failures were corrected: free-profile app limit by removing only
the disposable old bench test runner; normal-size speech button hit area by moving
its minimum frame into the label; simulator package/app architecture mismatch by
using standard Debug active-architecture builds; wide SwiftUI switch test targeting
by tapping its actual switch end. No safety thresholds/checks were weakened.

Evidence: `tests/ios/evidence/CS-013-integrated-app-20261018.json`.
Handoff: `handoffs/CS-013-20261018-integrated-app.md`.

## CS-016 physical transport host checkpoint

On the iPhone 17 Pro Max / iOS 26.6.2, the hosted scheme passed 21 existing
transport core/client tests and one real depth/timing test. The public HTTPS
probe failed to connect (the earlier run timed out) and was explicitly skipped, so no native live WSS acceptance is
claimed. Fake-socket transport tests remain synthetic even when run on a phone.

The real test collects at most 30 source/receipt pairs per run, with at least
100 ms between processing attempts, and repeats after pausing/restarting ARKit.
No image or raw timestamp is saved or sent. The summary-to-telemetry adapter
preserves capture seconds multiplied by 1000. Only elapsed candidate timestamp
deltas are printed, never absolute uptime. Two short runs do not prove the source
clock's epoch, sensor accuracy, sleep/background behavior, a clock drift bound or
phone-to-Pi latency. Keep live networking disabled pending those gates.

## Local real-depth response demo

The **Demo** tab uses the same real depth snapshot and invalidation as the Camera
tab. Start depth demo, hold portrait upright/rear cameras forward, and place a
broad object in the left, center or right image column. At 1.2 m or closer its
orange card reads Near · simulated response; larger valid values read Above demo
threshold. Missing/nonfinite/nonpositive values stay Unknown. Stop, stale preview,
orientation loss or background clears the source readings and thus the indicators.
No pulses, movement guidance, Pi, credentials or network are used. This visual
threshold is not the edge/haptic policy and establishes no CS-025 acceptance.
A valid mount calibration is now required for this demo to expose distances. Physical motor mapping and calibrated
capture age remain unverified. Launch argument --depth-demo selects this tab only;
it does not inject data, grant permission or start capture.

## CS-013 local native bond integration — 18 October 2026

This is a local, uncommitted integration checkpoint. No GitHub contact, fetch,
publish or PR operation was performed. Shared contracts, lifecycle modules and
motor policy were not changed.

Earlier phone telemetry came from `CaneSightTransport` device tests, not the
normal UI. `testNativeStartingHeartbeatAndReconnect` consumed the private
`Documents/cs016-phone-pair.json` file and sent only starting heartbeats.
`LiveDepthPairTests.testRealDepthPairPauseReconnect` consumed
`Documents/cs016-depth-pair.json`, ran actual ARKit, rebased capture/send/probe
values to one diagnostic epoch and sent actual depth over two WSS connections.
Those files were single-use session grants and were deleted by their tests.
Neither path implemented durable bond import or a persistent Mac helper.
The only other pending local worktree edits found were CS-017 test wiring and
checkpoint records, not a newer persistent phone integration.

### Existing credential and connection

Use **Connection → Import existing phone bond** to select the original
`phone-bond.json` for the Pi's existing enrollment. It must be schema version 1,
role `phone`, and contain only `schema_version`, `base_url`, `bond_id`, `role`,
`source_id` and `token`. The host pins this import to `https://64.177.50.116`.
Never paste its token into source, UI text, logs or a report. There is no token
editor or provisioning button. Alternatively deliver the existing file over USB
into the app's `Documents/phone-bond.json`; Connect validates and saves it to
Keychain, then removes the device-side staging file. Keep the original private
file in secure storage. This host does not import a Pi/operator credential.

Connect polls every two seconds while waiting and every ten seconds while paired.
Both saved-bond clients must poll the same bond within the backend's 20-second
presence window. HTTP 202 means authenticated/waiting, not an open WSS or live
depth. Network failures pause WSS/depth and retry while foreground; rejected credentials
or a rotated session retain the bond but require Connect again. A rotated
session currently stops the connection and requires Connect again. In-process
WSS retries retain sender sequence/capture high-water marks. A fresh foreground
or explicit connection gets a new boot binding and diagnostic clock epoch;
credentials and old observations are never regenerated/replayed.

### Diagnostic depth only

Connect initially sends no depth. For an explicitly authorized stationary transport test, enable **Allow stationary
diagnostic transport**, enable **Send diagnostic depth**, and start the Camera
separately. The consent checkbox records permission to transmit; it makes no
assertion about the Pi motor state and does not control GPIO. The app never arms or operates GPIO.
The existing portrait summary is reused, including coverage/unknowns; the current
preview produces at most about five new summaries per second. The unchanged
sender caps wire sends at ten Hz; a five-Hz producer is not a ten-Hz measurement.
No image, precise position, motor command or crossing permission is sent.

A fixed local epoch is subtracted from original capture and sender/probe clocks;
new captures must follow connection/readiness and remain within the diagnostic
500 ms guard. Observed media/continuous-clock discrepancies over 100 ms fail this
diagnostic run. Those guards are inherited bench assumptions, **not calibrated
sensor capture-age uncertainty or receiver drift bounds**. Receiver capture-age
eligibility remains unknown. Producer `ready` here means a fresh local diagnostic
source only; it must not be treated as permission for physical guidance.

Stop, unknown/degraded source, interruption and background invalidate depth
permission synchronously and cancel the current socket. Actor queues are closed
asynchronously; bytes already handed to the OS cannot be recalled. Independent
receiver expiry remains required. Backgrounding also clears the depth opt-in and
transport consent. Foreground recovery re-pairs for heartbeat transport;
depth must be enabled again. No cached summary is restored.

Routine tests never authenticate with a real saved bond. The native UI bench is
opt-in using Swift define `CS013_NATIVE_PAIRING_BENCH`; diagnostic-depth actions
also require `CS013_NATIVE_DEPTH_BENCH` after explicit operator authorization of that diagnostic run. `--connect-saved-phone` selects Connection and starts one explicit saved-
bond connection at launch; it never enables depth. Optional launch argument
`--phone-connection-probe` writes only the latest status, WSS boolean, send count,
depth opt-in and unverified-age flags to `Documents/phone-connection-probe.json`.
The streaming probe also records elapsed source/send spans, original-capture
local delta maxima, successful clock-reply counts and foreground/camera booleans.
These are diagnostic intervals, not raw uptime or calibrated drift evidence.
It records no credentials, identities, absolute clock values, images or GPS. New opt-in local diagnostics include derived depth distributions and calibration progress; these remain on the phone unless explicitly copied for testing.
This local journal is diagnostic evidence, never a readiness input.

Validation and current live status are recorded in
`handoffs/CS-013-20261018-local-native-bond.md`. A successful SDK build or pairing
must not be reported as verified real phone-to-Pi depth delivery or physical
motor guidance. No clock/drift acceptance has been established by this change.

### Authorized ongoing streaming launch

`--stream-saved-phone` selects Connection, reuses the saved bond, starts the real
camera and enables diagnostic depth for an explicitly authorized stationary test.
It generates no bond and does not arm/disarm Pi outputs. The phone's idle timer is
disabled only while diagnostic streaming is active; backgrounding/disconnect still
stops depth and restores normal idle behavior. Returning from background requires
a new explicit depth opt-in. Ordinary launches still default to disconnected.
The operator's authorization to use connected motors is not recorded as evidence
that they are disarmed or that physical guidance is safe.

Measured send rate is the change in successfully completed native depth-send
count divided by the phone's elapsed interval. Source rate is the change in fresh
processed capture count divided by the corresponding original-capture span.
Successful clock-reply counts prove sends only; Pi receipt, mapping uncertainty
and drift/capture-age eligibility need independent receiver evidence. Zero clock
replies is not a passed clock exchange. Unknown capture-age remains unknown even
while the native socket sends live ARKit summaries.

## Mount calibration v2: profile, operating envelope and checks

Implementation: `PreviewState/.../MountCalibration.swift` (profile, intrinsics,
pose/ROI geometry, stable-window rules), `Sources/MountCalibrationController.swift`
(current-frame adapter and helper wizard), `CameraController.swift` (bounded
capture/source epochs and display/send gating), `ContentView.swift` (actual
projected yellow sectors), `PhoneConnection.swift` (existing native transport).
The older floor/portrait transform tests and read-only raw diagnostic worker are
preserved. `--target-inspection` selects Camera; it no longer creates the tiny
inspection patch as the detection region.

Tap **Calibrate mount**. Hold the assembled cane at its normal grip/forward angle
with a sighted helper. Adjust the phone mount, tap the preview to centre the
full-width band vertically, and explicitly set band height if needed. Keep floor,
hand and cane out of the intended useful region. Scrolling does not drag the band.
Enable helper presence, capture neutral while still, then place a known broad
near target in the requested LEFT/CENTER/RIGHT third and record three distinct
frames each. Each requested target must be measured and be 15 cm nearer than any other measured thirds. Unknown background stays unobserved; it is not interpreted as far or clear. The helper identifies the placed target.
Check an 8–20 cm high low obstacle in the actual region (32 retained pixels and
three fresh records), then explicitly save. This is not automatic physical target
recognition; the helper must truthfully position and identify each target.

The neutral window needs at least 12 valid frames spanning 2.5 s, monotonically
increasing captures with gaps below 500 ms, ≤2° pose variation, ≤3 cm camera-height
variation, at least one measured sector and 96 retained high-confidence samples across the band. All three sides must subsequently pass their own known-target check. Tracking/source loss resets the
unfinished wizard evidence. It does not delete a previously saved compatible mount
profile. The helper must restart incomplete neutral/target checks after loss.

The local Application Support file `mount-profile-v2.json` contains version/ID,
helper confirmation date and side/low-obstacle verification, this-device binding,
image/depth dimensions and normalized intrinsics/display transform, full-width
band position/height, neutral camera-to-level rotation and coordinate convention,
neutral camera height, operating limits and assumed floor uncertainty. It contains
no world position/anchor, raw frames, location or credential; do not commit the
private file. Version 1 experimental profiles cannot authorize v2 geometry.

Only the unconfirmed band position/height is also kept in Documents/mount-setup-region-v2.json to preserve setup edits; it carries no verification and cannot enable depth.

A valid profile loads automatically on ordinary relaunch. Fresh gravity pose,
current floor model, compatible camera geometry and fresh depth must still be
rebuilt before any source is ready. Changing/doubting the physical mount requires
**Mount moved / recalibrate**. That action clears the source epoch, displayed
values, local eligibility and stored profile immediately. A persisted invalidation
flag prevents ordinary restart from silently restoring a removed profile. The
phone IMU does not distinguish a slipping mount from normal cane movement.

Initial envelope: level floor only (normal within 3° of gravity), camera height
0.3–2 m with change ≤10 cm from neutral; pitch change ≤15°, roll change ≤10°;
measured slant ranges 0.25–4 m. A partial off-screen sector is entirely Unknown;
a visible sector may remain usable. The preview draws the actual physical region
projection, clipped to the real camera image. Ordinary supported tilt is not a
reason to delete the saved mount profile. Unsupported height/angle/visibility
waits for supported fresh geometry rather than asking for a helper on each tilt.

Floor band half-width 2 cm, polygon inset 5 cm and profile floor uncertainty 3 cm
are explicit engineering assumptions, not measured hardware accuracy bounds.
The initial low-obstacle test is 8–20 cm; smaller objects and arbitrary ramps,
steps, changes in ground level or large cane translations are not validated.
Pixels beyond the observed floor boundary remain observations, not inferred ground.
Removing floor points cannot be described as detecting a safe path or a drop-off.

Calibration setup distances/coloured exclusions are local diagnostics only. Until
helper save, Status/Demo/transport distances stay unknown and producer state is
existing degraded/starting. Red preview marks are low-confidence selections; blue
marks are floor exclusions. The raw read-only `current_input_quality` journal
is not the compensated production ROI. `floor_filter` records selected sample
counts, visibility, conservative denominator and processing duration. Calibration
metadata stays in `mount_calibration` of the local journal, not v1 wire packets.

No packet/receiver change is introduced: existing type/fields, sequence high-water
marks, original capture timestamps, nulls, sender clock probes and private bond
remain. The phone supplies calibrated ROI left/center/right summaries. The Pi must
keep its independent freshness/clock and bounded-pulse gates. A native socket/source
fence cannot recall bytes already delivered or prove a physical pulse stopped.
Windows must verify clear-on-close/degraded/expiry and channel mapping. Semantics:
left obstacle → left motor; center → both (priority); right → right. The user chooses
movement. No turn/route recommendation, continuous unknown buzz or all-clear.

New source/geometry tests, actual signed build, device observations and Windows
integration instructions are recorded in the October 23 calibration handoff.
Historical October 18 measurements above do not establish this new mount's
calibration, receiver drift/age eligibility or hardware guidance acceptance.

### Investigating apparent distance cutoffs

There is no 2 m cutoff. Selected measured slant ranges are limited to 0.25–4 m;
high-confidence coverage still needs 25% and 32 pixels. The local `sector_input_quality`
counts raw positive samples beyond 2 m and high-confidence samples beyond 2 m,
plus floor, range and visibility exclusions. “Why a sector is Unknown” exposes
those reasons without converting medium/low confidence to trusted obstacle depth.
Before confirmation, the ordinary distance cards intentionally remain Unknown;
use setup distances for the helper's diagnostic check. A sensor/confidence loss at
range must be measured with a steady, supported pose and real target before changing
any policy. Calibration target records no longer require unknown background to be
measured; the known placed target on each side still needs three fresh records.

The tall-band regression is also exercised against the unchanged pinned processor
by `tests/ios/test_mount_calibration_processor.py` on prepared Macs. It reproduces
the old 6864-row input's `invalidDimensions`, then verifies bounded 2D sector tiles
preserve all samples, numeric 2.7 m summaries and original capture time. The packet
schema and confidence gates are unchanged. This fixes the newly found tall-band
packing failure; it does not prove every earlier distance/confidence issue resolved.
