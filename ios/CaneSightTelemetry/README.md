# CS-016 bounded phone telemetry

A standalone Swift package for timestamped phone summaries and the accepted v1
paired-session WebSocket protocol. It supplies the transport component; it does
not acquire ARKit depth, enroll devices, or provide an iOS app/Xcode project.
CS-014 owns the depth producer and CS-017 owns app lifecycle wiring.

## App integration

Add this local package to the phone app and import `CaneSightTelemetry`. Construct
`PhoneSession` with the authorized HTTPS backend origin, enrolled session ID,
phone source/boot IDs, paired Pi source/boot IDs, mode, and **phone-role** token.
The origin must have no credentials, query, fragment or non-root path. The package
uses `wss://<origin>/v1/telemetry` with a Bearer header. Keep enrollment and secure
credential storage in the app; never embed real grants in source or log requests.
The operator/backend/Gemini credentials do not belong on this transport.

```swift
// session: PhoneSession supplied by the authorized enrollment flow.
// sourceClockMS: @Sendable () throws -> Double supplied by the capture adapter.
let client = TelemetryClient(session: session, clock: sourceClockMS)
await client.start()                       // producer starts as .starting
// After CS-014 has established actual producer readiness:
await client.setProducerState(.ready)
// On each new producer summary, using its ORIGINAL capture timestamp:
client.submit(sample)                      // sample: DepthSample; synchronous
// CS-017 interruption/background handling:
await client.suspend()
await client.resume()                      // returns to .starting, not .ready
// Require producer readiness and a new capture again, then eventually:
await client.close()
```

Supply a finite, nonnegative, nondecreasing clock in milliseconds on the **same
verified time base** as `DepthSample.capturedAtMS`. There is deliberately no
implicit conversion from ARKit timestamps or default uptime clock. ARKit defines
[frame capture timestamps](https://developer.apple.com/documentation/arkit/arframe/timestamp),
but the app adapter must verify capture/clock alignment, units and suspend behavior
on its target device. Clock failure/reversal latches failure and cancels networking.
Audit required-reason API/privacy manifests for the actual app clock choice; see
[Apple systemUptime documentation](https://developer.apple.com/documentation/foundation/processinfo/systemuptime).
Do not reset the clock or recreate the client with old session/boot credentials:
sequences start at zero in a new instance; obtain a newly authorized session/boot
after process restart or clock reset. Keep the same client for ordinary reconnects.

`DepthSector` accepts a nullable distance and a finite valid fraction in [0,1].
Non-normal tracking requires all distances null. Unknown remains unknown; this
package infers neither crossing permission nor all-clear or movement commands.
The caller supplies truthful readiness and confidence; accepting a sample is not
proof of sensor quality. Heartbeats never modify a sample's capture age.

## Bounds and failure behavior

- One lock-protected latest producer slot, one pending core depth sample, one
  pending clock probe and one in-flight send. Submission creates no per-frame
  task/FIFO. Only one dial, receive and send task are owned at once.
- Depth sends are separated by at least 100 ms (10 Hz starting cap); heartbeat
  sends by at least 1000 ms, with independent sequence counters. No catch-up burst.
  The 10 ms scheduler is best effort, not a hard real-time timing guarantee.
- Samples must be newer than connection opening and the ready transition, strictly
  newer than the previous accepted capture, and no more than 500 ms old. Their
  original capture timestamp is serialized unchanged, with `capture_utc: null`.
- Send deadlines are at most 500 ms, shortened to the depth expiry boundary.
  A separate watchdog cancels blocked sends; native/API cancellation does not
  prove remote delivery or removal of bytes already received by a peer. Accepted
  receiver freshness checks remain required. No expired sample is resent.
- Dial timeout is 5 seconds. Retry backoff starts at 500 ms and doubles to 8 seconds.
  Disconnect/suspend discards pending work, cancels the owned socket and fences late
  callbacks. Reconnect retains sequence/capture/rate marks and accepts only fresh
  post-open captures. Ready is never inferred from network success.
- Suspend sets degraded; resume sets starting and requires explicit new readiness
  plus a post-ready capture. Transition away from ready cancels the current socket.
  The app must call these hooks; this package does not observe UIKit/ARSession.
- Only a closed-shape, identity-bound v1 clock probe is accepted inbound, at most
  once per second. Duplicate JSON keys, extra fields, malformed/nonfinite values,
  nesting and frames over 8192 bytes fail closed. Nonce history survives reconnect,
  is capped at 1024 without eviction, and fails closed at capacity (fresh enrollment
  required). Sequence counters stop at the v1 safe-integer maximum.
- Clock reply t2 uses local receipt time and t3 uses time immediately before send;
  Pi t1 is echoed, never compared directly with the phone clock. Replies expire
  locally after 500 ms; the receiver still validates the full exchange budget.
- Authentication rejection, invalid control, clock failure and sequence/nonce
  exhaustion latch failure; they do not enter an endless retry loop. Status exposes
  sanitized failure codes and bounded-slot counters, not credentials or raw frames.

The native adapter uses URLSession WebSockets, default OS TLS verification,
header authentication, no redirects, ephemeral cache/cookie/credential settings,
and no configured proxy dictionary. It waits for the WebSocket open delegate
before enabling submissions. Its
[maximum message buffer](https://developer.apple.com/documentation/foundation/urlsessionwebsockettask/maximummessagesize)
is 8192 bytes; parsing applies the same byte bound. Do not add a certificate trust
bypass to make a test server connect. Native TLS/auth/routing behavior still needs
real iOS verification; host fake-socket tests do not establish that evidence.

The accepted backend closes both paired peers when either detaches. Phone reconnect
alone therefore does not prove the Pi is connected or has a valid clock epoch.
Coordinate Pi reattachment/new authorized enrollment and receiver freshness gates;
never treat a heartbeat or successful dial as restored source freshness.

## Software verification

From the repository root, with the repository Python test dependencies installed:

```sh
swift test --package-path ios/CaneSightTelemetry
swift build --package-path ios/CaneSightTelemetry -Xswiftc -strict-concurrency=complete
python -m unittest discover -s tests/ios -v
```

Swift tests exercise the core and actor using synthetic samples, injected clocks
and fake sockets, including cancellation, watchdogs, late callbacks, reconnect,
clock reversal, bounded backpressure, malformed controls and sequence boundaries.
The Python tests run the built `TelemetryFixtures` binary and validate its original
replay bytes with the accepted backend/schema/session relay. Build the package
first; if Swift is unavailable, provide `CANESIGHT_TELEMETRY_FIXTURES_BIN` pointing
to a compatible built executable. No phone/backend connection occurs in these tests.
To inspect synthetic replay output: `swift run --package-path ios/CaneSightTelemetry TelemetryFixtures`.
This separate test root is explicit; existing repository CI does not run Swift or
these cross-language tests automatically. No protected workflow is changed.

## Deferred acceptance gates

Host SwiftPM build/tests are software evidence only. An iOS app target, CS-014
producer adapter, CS-017 lifecycle integration, verified capture clock mapping,
app privacy/permission configuration, iOS SDK build/signing, real LiDAR phone,
live native authenticated WSS/paired Pi tests, network loss/backpressure/background
runs and measured on-device rate/freshness remain unverified. The user authorized
finishing this software checkpoint while deferring Xcode/app/device verification.
Keep the implementation PR draft and task blocked until those gates have evidence;
this is not full phone/backend integration or physical acceptance.
