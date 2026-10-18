# CS-017: depth lifecycle guard

Software implementation for interruption, suspension and reconnect. This is a
standalone Swift package for the CS-014/016 host app. The draft CS-013 host in
PR #69 now pins this package as a review dependency; that preview does not wire
this guard into a live telemetry transport. It does not implement depth extraction,
telemetry serialization, enrollment, haptic policy or clock calibration.

## Integration with CS-014/016

Add this local package to the host's Xcode project. Import `CaneSightLifecycle`
and `CaneSightARLifecycle`. Own one `DepthLifecycle<YourDepthSummary>` and one
`ARLifecycleBridge` per enrolled phone source, on MainActor. Payload must be a
value snapshot conforming to Sendable, not a retained mutable ARFrame/pixel buffer.

1. Inject a finite nondecreasing local monotonic clock **in milliseconds** and
   four synchronous `LifecycleHooks`. Purge all transport queues, cancel existing
   sends and close the old socket, discard clock mappings, and clear any UI depth
   cache in these hooks. All transport transitions must use the same actor.
   `depthBecameUnknown` clears local sensor evidence; it must never imply clearance.
2. From the host scene delegate, forward active/inactive/background changes or
   call `bridge.observe(cameraScene)`. Retain the bridge; call `stopObserving()`
   when detaching the scene. Other windows must not resume the camera scene.
3. Keep the host's existing ARSession delegate. Forward interruption start/end,
   failure, and camera tracking changes into the bridge, serialized on MainActor.
   Forward `cameraTrackingChanged(frame.camera.trackingState)` on each frame before
   asking to process depth, not only on tracking-change callbacks. AR delegates
   running on a worker queue must stop delivery and serialize lifecycle events
   with frame/send admission; a fire-and-forget Task is not a synchronization
   barrier. Do not read/send cached frame data from an independent queue.
4. After the app is active and newly observed tracking is normal, obtain a
   `beginConnection()` lease. On the async connection completion, pass that lease
   to `connectionReady`; close the newly opened socket if it returns false. The
   guard rejects old or competing connection completions. Never drain an old queue.
5. Establish fresh verified clock mappings and the protocol's fresh ready health
   exchange. Only then call `clockMappingReady(connectionLease)`. This method is
   an acknowledgement of the host's verified mapping, not a calibration algorithm.
   On mapping expiry/unavailability, call `disconnected()` and recalibrate. A
   successful WebSocket handshake or ingestion ACK alone is insufficient.
6. At each frame callback, take `beginCapture()` before worker depth extraction.
   Keep the original source capture timestamp (AR seconds converted to protocol
   milliseconds), source boot, session and strictly increasing sequence intact.
   Submit the value summary with that lease on MainActor when work finishes.
   Supply a `CaptureTime` whose local earliest/latest bounds come from a verified
   source-to-local monotonic mapping. Do not substitute callback arrival time,
   wall time or assume ARFrame's clock matches an arbitrary injected clock. If
   mapping/drift is unknown, submit nothing. A frame captured before recovery or
   calibration, even if delivered afterward, must not acquire a new timestamp.
7. At the existing bounded telemetry send tick, call `takeForImmediateSend()`.
   Serialize the original source capture timestamp and sequence. If serialization
   or other work awaits, call `maySend(sample)` again on MainActor immediately
   before handing bytes to the socket; do not await between validation and handoff.
   The transport must bound its in-flight sends too, cancel them on hooks and
   never replay them on reconnect. Old bytes already delivered cannot be recalled;
   the Pi checks original capture age on its own independent policy clock.
8. On AR failure, remain unknown until the host explicitly runs a new supported
   AR configuration and calls `sessionDidRunNewConfiguration()`. On source capture
   clock reset or identity/session change call `requireNewEnrollment()`, stop the
   old guard, and construct a replacement only after explicit operator enrollment.
   Ordinary resume/reconnect keeps boot/sequence history. Do not silently enroll
   or clear sequence counters.

Every loss event rotates the lease, clears the one pending depth slot, invalidates
mapping and disconnects. Tracking/scene recovery alone restores no sample. Captures
must be bounded to 500 ms with at most 100 ms half-width uncertainty; send-time
checks prevent queued work from growing stale. No heartbeat API can renew depth.
The guard does not validate depth sectors: CS-014/016 must honor v1 null distances
for non-normal tracking and preserve the shared message schema.

Cleanup hooks may synchronously report socket closure or read unknown UI state.
The guard fences admission throughout cleanup and suppresses nested invalidation;
do not attempt to reconnect from a cleanup callback. Once a clock fault requires
reenrollment, reads remain unknown without repeatedly notifying the host.

## Tests and remaining device checks

Portable core tests (Swift 5.9+; tested using official Swift 6.0.3 Linux image):

```sh
cd ios/Lifecycle
swift test --jobs 1 -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
```

Receiver regressions, using the repository backend/contract test dependencies:

```sh
python -m unittest tests.ios.test_lifecycle_receiver -v
```

The latest local run passed 12 portable tests with strict concurrency and warnings
as errors, plus the three Python Pi-consumer regressions. Linux excludes the
conditional ARKit/UIKit bridge body. It **does not validate an iOS build**.
Michael's PR #69 reports macOS tests, iOS SDK builds and simulator test-bundle
compilation for the earlier pinned commit
`0edb2229977b93eae00df6842286d87d4870aea4`; those are useful native compilation
evidence, not a build of subsequent changes or execution of native bridge tests.
Its phone preview lock/background report is not a paired telemetry expiry test.
See `tests/ios/evidence/CS-017-cleanup-20261018.json` for exact scope and hashes.
On a Mac update the reviewed dependency pin, build both products, then use a
supported LiDAR phone and the enrolled Pi to record this matrix. No private images,
credentials or precise GPS traces should be retained as test evidence.

| Test | Required evidence |
| --- | --- |
| Background, screen lock, loss of focus, scene disconnect | Local caches/queues clear; Pi loses depth within original capture-age budget even if no final packet arrives. |
| AR interruption and end | No pause call from interruption callback; no cached depth after end, mapping recalibrated and fresh normal frame required. |
| Limited/unavailable tracking, AR failure | Unknown evidence; explicit AR restart for failure; no stale queued worker result restores depth. |
| Wi-Fi outage, delayed send/reconnect callback | Old queue/sends dropped; sequence continues; clock/ready exchange and newly captured frames required. |
| Clock reset, source/app restart | Old epoch invalid; operator enrolls new boot, no automatic adoption. |
| Clock drift and capture time conversion | Verified conservative bounds across suspend/resume; unknown mapping cannot establish readiness. |

Report capture sequence/time, receive/expiry times and counters only. These tests
establish software evidence, not physical motor readiness or crossing permission.

References: [AR session interruption](https://developer.apple.com/documentation/arkit/arsessionobserver/sessionwasinterrupted(_:)),
[frame capture timestamp](https://developer.apple.com/documentation/arkit/arframe/timestamp),
[scene lifecycle](https://developer.apple.com/documentation/uikit/uiscenedelegate),
[Swift test tooling](https://www.swift.org/documentation/server/guides/testing.html).
The repository's shared v1 contract and Pi `CaptureAgeGate` remain authoritative.
