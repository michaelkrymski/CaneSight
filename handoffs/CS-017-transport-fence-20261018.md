# CS-017: host transport lifecycle fence

Initial base: 20d69c9f43a3a19a3aa102ca04933f9d0e379284.
Published software checkpoint incorporates accepted main f2a6dca6df87ffe1daf0a9f265590ca9ba6a393e.
Branch: task/CS-017-transport-fence. Owner: gmarcialcalleja (merged assignment #59).

## Changes

- ios/CaneSightApp/Sources/LifecycleTelemetry.swift: opt-in coordinator around the unchanged CS-016 TelemetryClient, with a synchronous cancellation fence shared with AR callbacks, capture-time admission tickets, bounded cleanup/recovery tasks, original capture bounds and sequence preservation. Late sockets are cancelled even if their factory ignores Task cancellation. Missing mappings purge transport; reversed clocks require enrollment again.
- CameraController.swift: forwards activity/Stop/interruption/tracking loss, binds worker results to their capture ticket, clears preview/status/check state on transport invalidation and converts existing three-sector output while retaining original capture time.
- Xcode project includes the new source. README documents opt-in configuration and limits.
- tests/ios/LifecycleTransportTests.swift and run_lifecycle_transport.py compile the production coordinator with the real pinned CS-016 actor and unchanged accepted lifecycle package, using fake sockets/clocks only. Evidence JSON records executed results and source hashes.
- Own task runtime fields and new append-only changelog only. No teammate source, shared contract or master-plan change.

## Validation actually run

- 13 Swift XCTest cases: all passed in network-disabled pinned Swift 6.0.3 Linux Docker, complete strict concurrency and warnings as errors. Covers synchronous cancellation before actor cleanup, stale worker tickets, cancelled late connects, callback-thread revocation, pending-mailbox disposal, sequence preservation, missing/retimed/future mapping, clock reset and terminal close.
- Three existing CS-017 Python receiver expiry/reconnect regressions: all passed. These are synthetic consumer tests, not phone/Pi evidence.
- plutil -lint on the Xcode project: passed. swiftc -frontend -parse CameraController.swift: passed; syntax only, no Apple SDK/type checking.
- Checked publishing runs repository validation, full root unittest discovery, generated changelog and whitespace checks. Their actual result is in the publishing output/CI; no physical test inferred.

## Remaining gates / next steps

Default app remains a local preview. configureTelemetry has no automatic caller: reviewed phone-only enrollment and independently measured source-clock bounds must be supplied first. An evidence ID alone is not calibration. CS-016 remains an exact review dependency at 0433fc94af1a1e3edfe2d2bb28925cb3be6df1ee; this PR neither changes nor accepts it. The accepted host dependency manifest's lifecycle source is identical to the tested current package.

Build this changed host with Apple SDKs and run native runtime checks. Existing CS-013 phone evidence is historical for its exact earlier source; it does not validate this wiring. Then coordinate camera availability and run paired LiDAR phone-to-Pi tests: fresh enrollment/mapping, normal captures, interruption, background/lock, stale expiry, reconnect and fresh-data-only recovery. Record original age bounds and timing, zero replay, source identity and exact commits without credentials/images/GPS. Check the real NativeWebSocket cancellation contract; bytes already handed to the network cannot be recalled and the Pi must independently expire them.

Task remains blocked on these gates. No Raspberry Pi, camera, phone, GPIO, motor, audible stop latency or electrical test was run in this work. No remote SSH runner was retried.
