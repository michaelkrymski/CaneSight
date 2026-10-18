# CS-014 confidence-aware depth sectors

Standalone local Swift package for confidence-aware depth summaries. Accepted
CS-013 PR #69 pins source commit `5f73dbf33ba9b2395f27b429c22344d41fb6162a`
and records 15 passing macOS XCTest cases, physical-iOS SDK builds and simulator
test-bundle compilation. Later signed installation and five physical-phone host
UI tests include live depth, Stop-to-Unknown and background/restart recovery.
These are Michael's attributed Apple/device results, not Apple tests rerun on
this Windows host. See `tests/ios/evidence/CS-014-readiness-20261018.json` for
source identity, acceptance evidence and remaining limits.

This package provides depth summaries; the accepted CS-013 host owns the app,
ARSession and display integration. Transport, physical accuracy and final
cane/grip/motor mapping retain separate acceptance gates.

## Components

- `CaneSightDepth`: owned depth/confidence arrays, validated configuration,
  stateless sector processor, and bounded strided Float32/UInt8 byte decoder.
- `CaneSightDepthARKit`: Apple CoreVideo buffer copier and iOS 14+ ARFrame adapter.
- `CaneSightDepthTests`: 15 XCTest methods, including seven replay fixtures and
  two Apple-only native pixel-buffer tests. All 15 passed on macOS in the
  attributed CS-013 evidence; the 13 portable methods can also run on Linux.

There are no third-party Swift dependencies or network calls. The package is
separate from CS-016 telemetry and CS-017 lifecycle. The CS-013 app uses an exact
review-source pin as a local package dependency; do not copy these types into
another package. A source-only review cannot validate the Apple SDK APIs.

## Summary contract

```swift
import CaneSightDepth

let configuration = try DepthSectorConfiguration()
let processor = DepthSectorProcessor(configuration: configuration)
let replayFrame = DepthFrame(
    width: width, height: height,
    metres: ownedFloatSamples, confidence: ownedConfidenceBytes,
    captureTimestampSeconds: originalSourceTimestamp,
    mode: .replay, tracking: .normal
)
let summary = processor.process(replayFrame)
```

The internal summary has actual `mode`, original source timestamp in seconds,
frame-processing reason and three sectors with optional distance/coverage,
valid/total sample counts and evidence state. It is **not** a v1 wire message,
readiness verdict or motor command. Timestamp values are never replaced with
processing/receipt time, compared across devices or interpreted as UTC. Invalid
timestamps become nil with unknown distances. A later transport encoder must
preserve the source epoch and apply the accepted clock/freshness protocol.

Sector names are `imageLeft`, `imageCenter`, `imageRight`: ascending depth-image
columns. Every summary declares `coordinateSpace=depth_image_columns` and
`physicalMappingVerified=false`. They cannot establish physical grip left/right
or alignment with a crossing. **CS-015 orientation/mount verification is still
required before mapping them into physical sectors.** No orientation transform,
floor/cane exclusion, mirror correction or geometry calibration is assumed.

## Numerical rules and bounds

Initial configurable engineering defaults are high confidence (raw value 2),
at least 25% valid coverage, at least 32 valid samples per sector, and the 10th
percentile. These thresholds have not been calibrated or validated on a phone.
Medium confidence (raw value 1) can be selected explicitly; raw 0 and unknown
confidence values do not pass the high/medium threshold. Missing confidence is
unavailable, not implicitly high confidence.

The default region is the entire input depth image. An optional normalized ROI
has finite ordered bounds in [0, 1]. Lower edges round inward with ceil and upper
edges with floor; the result is a half-open pixel rectangle. It must contain at
least three columns and one row. Integer partition boundaries divide all of its
columns into three strips, including uneven-width remainders. Coverage uses every
pixel in the corresponding strip as denominator, including rejected pixels.

Only finite strictly positive depths with accepted confidence contribute to a
sector. Coverage and minimum sample count are separate gates; failure leaves
distance nil and retains measured coverage/counts. Missing/malformed frames,
bad timestamps or degraded tracking yield unavailable sectors with nil coverage.
Unknown never becomes zero distance, an invented far distance or clearance.

For enough samples, sort ascending and select nearest-rank
`ceil(percentile * validCount) - 1`. This is neither the minimum nor the mean.
It can ignore isolated near outliers, and can also miss small real obstacles;
it is not collision avoidance, curb/drop detection or a stopping-distance model.
Stateless processing never caches or reuses a previous sector on bad input.
There is no temporal smoothing or filling holes with adjacent/older values.

Maximum geometry is 2048 per dimension and 262,144 pixels total. Geometry is
checked before multiplication/indexing/allocation. Byte planes must have enough
row storage and at most 16 MiB each; reads account independently for depth and
confidence stride and reject truncated buffers. The byte decoder explicitly
reads little-endian IEEE Float32 and UInt8 confidence. Current targeted Apple
platforms use this representation. No resize/interpolation changes confidence.

## ARKit boundary

On iOS, construct `ARKitDepthAdapter(configuration:)` and invoke `process(frame)`
on the host's bounded depth-processing worker, **not the UI thread**. The host
owns ARSession creation/permissions, enabling `.sceneDepth`, latest-frame
scheduling and lifecycle. The adapter does not start or modify a session.

It checks scene-depth support, finite source time, normal camera tracking, raw
`sceneDepth`, a confidence map, supported nonplanar pixel formats and matching
dimensions. It uses raw depth, not `smoothedSceneDepth` history. It checks buffer
sizes/strides, pairs successful read-only locks with defer/unlock, and creates
owned samples before releasing the buffers. Sorting occurs after unlock; no
raw pointer or CVPixelBuffer enters a summary. Failure returns unknown rather
than an old result. The native adapter always emits `.live`; synthetic buffer
tests use the lower-level reader with explicit `.replay`.

Frame expiry while no new callback arrives, interruptions, background/thermal
transitions and restart recovery still belong to the host/CS-017. Consumers must
clear or expire a retained summary independently and require fresh data after
recovery. Merely retaining the last value, or receiving a heartbeat, cannot
renew its source capture time. No 10 Hz, memory-performance or timing guarantee
is claimed before profiling on the actual phone.

## Recorded checks and reproduction

The accepted-main records are `tests/ios/evidence/CS-013-apple-builds-20261018.json`
and `tests/ios/evidence/CS-013-integrated-app-20261018.json`, with the corresponding
CS-013 handoffs. The first records Xcode 27.1 / iOS SDK 27.1 and all 15 depth
XCTest cases on macOS, including CoreVideo cases. Its simulator test bundles
were compiled, not executed. The later record supersedes its initial phone
signing/launch limitation: the signed host ran on iPhone 17 Pro Max / iOS 26.6.2.
Do not describe those host UI tests as execution of all depth tests on iOS.

Windows checks:

```powershell
.venv/Scripts/python.exe -m pip install -r tests/ios/requirements-audit.txt
.venv/Scripts/python.exe tests/ios/validate_depth_fixtures.py --syntax
```

The Python helper audits fixture structure/provenance and optional Tree-sitter
grammar parsing. It **does not run a Python copy of the depth algorithm** and
cannot prove Swift types, SDK compatibility, linking or runtime behavior. Source
hashes use UTF-8 text normalized to LF. Reports use exclusive new filenames.
The fixture file contains authored requirements. Swift XCTest execution, rather
than this structural audit, supplies the observed algorithm results.

To reproduce and extend the recorded checks:

1. Run `swift test --package-path ios/DepthSectors`. Check all portable numerical,
   byte-layout and fixture cases plus the Apple-only CoreVideo tests. The tests
   exercise nonfinite data, confidence/coverage, quantiles, malformed/overflowing
   geometry, source time, tracking, padding, mismatched planes and owned copies.
2. Open this package/host app in Xcode and build for an iOS SDK destination.
   A host macOS `swift test` excludes the iOS ARKit branch and cannot validate it.
3. Recheck host support/lifecycle behavior when changing the source or app.
   Accepted CS-013 evidence covers signed phone execution, unsupported simulator
   presentation and host Stop/background recovery; it does not measure accuracy.
4. Complete CS-015 actual orientations/mount mapping and CS-020 measured surface,
   coverage/error cases before claiming depth accuracy or physical guidance.
   Profile worker latency/allocation/thermal behavior and retain actual evidence.

The implementation is ready for independent CS-014 review against finite depth,
confidence/coverage filtering, percentile, nullable unknowns and source timestamp.
Its reviewed Swift implementation/tests remain identical to the Apple-tested pin.
No workflow, shared protocol, other task requirements or deployment was modified.
Measured range/surface accuracy (CS-020), final mount/motor mapping (CS-015),
cross-device clock/transport and end-to-end haptics (CS-016/025) remain separate.
No electrical or road-use validation is implied. Review is not task Done.

Primary API references: [ARDepthData](https://developer.apple.com/documentation/arkit/ardepthdata),
[confidence map](https://developer.apple.com/documentation/arkit/ardepthdata/confidencemap),
[frame timestamp](https://developer.apple.com/documentation/arkit/arframe/timestamp),
and [Swift PackageDescription](https://docs.swift.org/package-manager/PackageDescription/PackageDescription.html).
