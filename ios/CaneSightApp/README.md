# CaneSight iPhone host — CS-013

Open `CaneSight.xcodeproj`, scheme **CaneSight**. This review host targets iOS
16 or newer, requests camera permission only after Start camera, checks
`supportsFrameSemantics(.sceneDepth)` at runtime, and shows unsupported hardware
as unavailable. An iPhone 17 Pro Max running iOS 26.6.2 was paired during setup;
that is not evidence that this app has run or that its depth output is accurate.

## Prepare the exact review packages

From the repository root:

```sh
git fetch origin
python3 ios/CaneSightApp/prepare_review_dependencies.py
open ios/CaneSightApp/CaneSight.xcodeproj
```

`ReviewDependencies.json` pins the exact source commits of draft PRs #62, #63,
#64 and #67. The helper reads those Git objects without executing their scripts,
materializes source into ignored `ReviewDependencies/`, and refuses to overwrite
changed files. All package source hashes are checked on a subsequent invocation.
It never modifies a teammate's source, task or branch. These inputs are explicitly
**unmerged review dependencies**. This PR must remain draft until dependencies
are accepted or the PM agrees a reviewed integration order. Pins are not silently
advanced when a teammate pushes new code.

To build without a signing account:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
  -project ios/CaneSightApp/CaneSight.xcodeproj -scheme CaneSight \
  -destination 'generic/platform=iOS' -derivedDataPath /tmp/CaneSight-build \
  CODE_SIGNING_ALLOWED=NO build
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test \
  --package-path ios/CaneSightApp/PreviewState
```

## Run on a physical phone

1. Connect/unlock the iPhone and trust the Mac. Enable Developer Mode on the
   phone and complete its restart/confirmation if prompted.
2. Sign in to Xcode Settings → Accounts. In the CaneSight target's Signing &
   Capabilities select the intended development team. Signing credentials and
   profiles remain outside Git. The project intentionally contains no team ID.
3. Select the physical phone and Run. Approve the development-app trust prompt
   on the phone if iOS requires it. Tap Start camera and grant camera permission.
4. Record whether scene depth is supported, whether new local depth appears,
   and whether Stop immediately returns every sector to Unknown. Denying camera
   permission must show unavailable. Test background/lock/AR interruption and
   camera recovery with fresh captures; never treat build success as these tests.

## Local preview boundaries

The host runs the CS-014 adapter off the main actor. Storage is one replaceable
pending ARFrame, one processing frame, and one replaceable UI delivery. Work is
nominally capped at 10 Hz. Epoch barriers reject pre-stop/background/interruption
work. Session loss fences the worker before delivering its invalidation and cannot
be overwritten by a later depth result. Stop/scene inactivity pauses ARSession,
clears local depth and stops the timer. An interruption requires explicit camera
restart. Five PreviewState tests cover old-epoch results, delayed/duplicate frames,
idle timeout, invalid source times and clock reversal.

UI recency expires after 500 ms **from local AR callback receipt**. This is a UI
stall detector, not capture-age calibration. Original ARFrame capture timestamps
are retained and must increase; clock reversal fails closed until restart. There
is no assertion that the callback deadline proves sensor freshness. Image-left,
image-center and image-right are depth-image columns, not verified physical grip
directions. CS-015 mapping and real surface/performance evidence remain required.

The host uses the CS-017 native bridge for interruption/failure invalidation;
its transport eligibility gate is not marked connected or clock-calibrated.
CS-016 and CS-019 products are compiled/linked for integration, but no telemetry
client, GPS provider, backend enrollment, credential storage or network request
is instantiated. GPS sharing stays off. A live source/clock/mount integration
must be reviewed before enabling phone telemetry; adding the imports does not
complete those tasks. No images are saved, no motors/narration are controlled,
and no crossing permission is produced.

## Verification recorded on 18 October 2026

- Xcode 27.1, iOS SDK 27.1: all four pinned packages built for physical iOS;
  all four iOS Simulator test bundles built, including native Apple bridge tests.
- 59 package XCTest cases executed on macOS: depth 15 (including CoreVideo),
  lifecycle 10, telemetry 21, coarse location 13. All passed.
- Four original Swift wire-to-accepted-backend/schema tests passed.
- Five host PreviewState XCTest cases passed on macOS.
- The host built for physical iOS with signing disabled. Simulator test bundles
  were compiled, not executed: no simulator runtime was installed at verification.
- Device launch, Apple signing, actual LiDAR, permission/lifecycle/clock/mapping,
  live WSS/Pi and GPS behavior remain unverified. No full task is marked Done.

Sanitized evidence: `tests/ios/evidence/CS-013-apple-builds-20261018.json`.
