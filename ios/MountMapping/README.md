# CS-015 portrait orientation and mount check

The supported physical configuration for this checkpoint is **portrait upright,
rear cameras facing forward**, selected by Michael. Mathematical rotation tests
cover quarter/half turns; landscape/upside-down physical use is not accepted.
This is a camera-to-portrait-view mapping and an operator-controlled target check,
not phone/Pi fusion, a physical motor mapping, or crossing permission.

## Mapping

`DisplayMapping` accepts ARKit's normalized image-to-viewport affine transform.
It permits only nonsingular axis-aligned rotation/scale/translation, rejects
mirroring, skew, nonfinite values, excessive scales and uncovered/letterboxed
viewports. The original depth and confidence grids undergo the same exact pixel
permutation. Samples are neither interpolated nor duplicated. Aspect-fill cropping
becomes a normalized ROI for the unchanged CS-014 confidence/coverage/percentile
processor. Original mode, tracking and capture timestamp remain unchanged.

The iOS `PortraitDepth` adapter uses the actual frame's
`displayTransform(for: .portrait, viewportSize: CGSize(width: 9, height: 16))`,
checks tracking, rear scene-depth support, matching image/depth aspect ratio and
owned CoreVideo sample copies. Missing/unusable data throws rather than restoring
old sectors. The fixed 9:16 camera preview uses that same transform, with explicit
top-left normalized ARKit versus bottom-left pixel CoreImage coordinate conversion.
The host permits physical portrait only and resets when physical orientation changes.

CS-014 source remains pinned/unmodified at commit
`5f73dbf33ba9b2395f27b429c22344d41fb6162a` (draft PR #62). Its summary retains
`physicalMappingVerified=false`: rotating image samples does not alone establish
the operator's body/grip alignment. These results are not v1 wire packets.

References: [ARFrame display transform](https://developer.apple.com/documentation/arkit/arframe/displaytransformfororientation%3Aviewportsize%3A),
[scene depth](https://developer.apple.com/documentation/arkit/arframe/scenedepth).

## Operator check

`MountCheck` requires three distinct increasing capture timestamps for each
requested physical target in left → center → right order. All three columns must
have usable depth, and the expected target column must be at least 0.2 m nearer
than both others. This margin is an initial **bench test setting**, not a calibrated
ranging/safety threshold. Replay, non-normal tracking, unknown sectors, old UI
delivery, reused source time and clock reversal cannot earn a check. Geometry or
session/orientation changes reset progress. The host records loss generations so
coalescing a later good frame cannot hide an intervening tracking/buffer failure.

Software cannot prove where a human placed a target. The operator must keep the
phone fixed and truthfully place a broad target on their physical left, center
and right while facing forward. Three passes per side establishes only that
specific current configuration. Repeat after remounting or changing the grip/
phone-to-body relationship; portrait alone cannot detect a changed yaw/mount.
No persistent calibration file or remote `ready`/motor authorization is produced.
This handheld bench result does not certify a final cane mount.

## Build and verify

From the repository root:

```sh
git fetch origin
python3 ios/MappingBench/prepare_review_dependencies.py
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test \
  --package-path ios/MountMapping -Xswiftc -strict-concurrency=complete \
  -Xswiftc -warnings-as-errors
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
  -project ios/MappingBench/MountCheck.xcodeproj -scheme MountCheck \
  -destination 'generic/platform=iOS' -derivedDataPath /tmp/MountCheck-build \
  CODE_SIGNING_ALLOWED=NO build
```

The materializer reads exact Git objects, verifies hashes if already prepared,
and refuses to overwrite changed source. Review/accept pinned draft #62 before
main integration. The core package's local dependency points to that prepared
review directory; no Swift source is vendored or modified in this PR.

The 11 Mac XCTest cases exercise independent pixel oracles for both quarter turns
and 180°, confidence alignment, crop ROI, mirror/skew/nonfinite/malformed rejection,
letterboxing, all nine target captures, wrong-side/repeated/replay/unknown samples,
geometry resets and stale/reversed-clock checks. They do not prove physical sides.
The iOS SDK app build validates the conditional native adapter and UI.

## Phone test

Open `ios/MappingBench/MountCheck.xcodeproj`. Select the intended development
team locally. `Signing.xcconfig` optionally includes ignored `Signing.local.xcconfig`;
no team identifier, credential or provisioning profile belongs in Git.
The bundle `com.michaelkrymski.CaneSight.MountCheck` installs as **Mount Check**
alongside the existing #69 app, whose source/installed build remains intact.

1. On a controlled stationary indoor bench, hold the phone portrait, rear cameras
   forward, screen toward you. Start and allow camera access. The in-memory image
   should be upright and match the three column outlines.
2. Put a broad flat object around 0.5–1 m away on your physical left; keep the
   background farther away. The corresponding view column should read nearer.
   Record three fresh frames about one second apart. Do not move the phone.
3. Follow the center then right prompts. Report actual counts/result or errors;
   do not prefill passing observations. Very close/unknown readings cannot pass.
4. After completion, rotate to landscape and back: the check must reset. Also
   Stop or background/lock: image/depth clear and the check resets. Recovery
   requires a new check, not a cached certification.

The camera thumbnail and depth stay in bounded memory only. Nothing is uploaded,
saved or shared; no GPS, session enrollment, telemetry, motor or narration runs.
Callback-recency checks are not verified sensor capture-age bounds. Source-clock,
surface accuracy, phone-to-grip/motor mapping, final mount and full WSS/Pi integration
remain separate acceptance work. Do not claim physical completion from SDK/tests.

## Device checkpoint — 18 October 2026

The exact implementation at `bd99b6cf043122d2d4548f4e97bfa70bbf868409` built
with Personal Team signing, passed strict deep signature verification, and was
installed/launched on the paired iPhone 17 Pro Max / iOS 26.6.2 through Apple's
device tools. Required CI passed on that implementation. The operator received
the target/reset procedure above; physical results are pending and not prefilled.
The original CaneSight app/#69 source remains unchanged.
