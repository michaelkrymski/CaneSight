# CS-014 depth-sector software checkpoint

Standalone local Swift package for confidence-aware depth summaries. Code and
synthetic XCTest cases are prepared on Windows. **Swift compilation, XCTest,
Xcode/iOS SDK, simulator, signing and physical LiDAR checks have not run.**
CS-013 remains a prerequisite. This checkpoint does not provide an app project,
ARSession lifecycle, telemetry, mounting calibration or a verified phone build.

## Components

- `CaneSightDepth`: owned depth/confidence arrays, validated configuration,
  stateless sector processor, and bounded strided Float32/UInt8 byte decoder.
- `CaneSightDepthARKit`: Apple CoreVideo buffer copier and iOS 14+ ARFrame adapter.
- `CaneSightDepthTests`: 15 authored XCTest methods, including seven replay
  fixtures and two Apple-only native pixel-buffer tests. All remain unrun.

There are no third-party Swift dependencies or network calls. The package is
separate from the pending CS-016 telemetry and CS-017 lifecycle work. Add it as a
local package dependency when the host iPhone app exists; do not copy its types
into another package or claim a source-only review validates the Apple SDK APIs.

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

## Checks available now / checks pending

Windows checks:

```powershell
.venv/Scripts/python.exe -m pip install -r tests/ios/requirements-audit.txt
.venv/Scripts/python.exe tests/ios/validate_depth_fixtures.py --syntax
```

The Python helper audits fixture structure/provenance and optional Tree-sitter
grammar parsing. It **does not run a Python copy of the depth algorithm** and
cannot prove Swift types, SDK compatibility, linking or runtime behavior. Source
hashes use UTF-8 text normalized to LF. Reports use exclusive new filenames.
The authored expected fixture outputs are test requirements, not observed results.

When a Mac/toolchain is available:

1. Run `swift test --package-path ios/DepthSectors`. Check all portable numerical,
   byte-layout and fixture cases plus the Apple-only CoreVideo tests. The tests
   exercise nonfinite data, confidence/coverage, quantiles, malformed/overflowing
   geometry, source time, tracking, padding, mismatched planes and owned copies.
2. Open this package/host app in Xcode and build for an iOS SDK destination.
   A host macOS `swift test` excludes the iOS ARKit branch and cannot validate it.
3. Complete CS-013 signing/physical support checks. Verify unsupported devices,
   missing depth/confidence, tracking loss and interruption remain unavailable.
4. Complete CS-015 actual orientations/mount mapping and CS-020 measured surface,
   coverage/error cases before claiming depth accuracy or physical guidance.
   Profile worker latency/allocation/thermal behavior and retain actual evidence.

No workflow, shared protocol, other task requirements or deployment was modified.
Keep this checkpoint draft and the task blocked for Apple/device acceptance until
actual build/test evidence exists. No electrical or road-use validation is implied.

Primary API references: [ARDepthData](https://developer.apple.com/documentation/arkit/ardepthdata),
[confidence map](https://developer.apple.com/documentation/arkit/ardepthdata/confidencemap),
[frame timestamp](https://developer.apple.com/documentation/arkit/arframe/timestamp),
and [Swift PackageDescription](https://docs.swift.org/package-manager/PackageDescription/PackageDescription.html).
