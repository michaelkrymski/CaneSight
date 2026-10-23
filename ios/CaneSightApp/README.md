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

## Current features

- Camera tab: explicit Start/Stop, scene-depth support/permission handling,
  portrait 9:16 rear-camera image and matching depth/confidence column mapping.
  Only physical portrait upright is supported. Orientation, Stop, background,
  interruption and stale callbacks clear the image/readings and side check.
- Left/center/right distance or Unknown, plus the existing high-confidence
  coverage/sample-count reason. Thresholds remain CS-014 defaults: high confidence,
  25% coverage and 32 samples, with near 10th percentile. Full-height columns
  include floor samples; there is no floor/obstacle or curb/drop classifier.
- A session-only physical target check uses the unchanged CS-015 core, requiring
  three distinct fresh captures per requested side. No persistent mount, grip or
  motor calibration is produced. Repeat after remounting.
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

These are local app features. Telemetry remains unavailable: no TelemetryClient,
backend enrollment, credential store or network request is instantiated. Before
live streaming, review capture-clock alignment/uncertainty, pairing, original-age
bounds and accepted dependency integration. GPS requires its separately reviewed
wire contract. No Pi, motor, crossing permission or generative narration control.

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
lifecycle events; this preview does not mark its transport guard connected or
clock-mapped. Unknown values never mean an empty path.

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
The floor may trigger several columns. Physical motor mapping and calibrated
capture age remain unverified. Launch argument --depth-demo selects this tab only;
it does not inject data, grant permission or start capture.
