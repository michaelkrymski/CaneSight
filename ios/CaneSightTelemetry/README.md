# CS-016 bounded phone telemetry

A standalone Swift package for timestamped phone summaries and the accepted v1
paired-session WebSocket protocol. It supplies the transport component; it does
not acquire ARKit depth, enroll devices, or provide an iOS app/Xcode project.
CS-014 owns the depth producer and CS-017 owns app lifecycle wiring.

`../DepthTelemetry` supplies a session-bound CS-014 summary adapter and
`DepthTelemetryStream`. It preserves original capture timestamps, image-column
order and unknown values, rejects a mismatched live/replay mode, and forwards
explicit readiness/lifecycle calls to this client. It supplies no implicit clock
verification or app networking activation.

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

Mac URLSession rejection/cancellation tests use generated loopback fixtures via
`python -m unittest discover -s tests/ios -p test_native_websocket.py -v`. They
prove default OS rejection before HTTP authentication and cancellation of a real
stalled TLS handshake, without changing the trust store. They do not prove a
successful trusted WSS connection, live phone/Pi pairing or sensor timing.

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
The Python tests build the current `TelemetryFixtures` product when Swift is
available and validate its original
replay bytes with the accepted backend/schema/session relay.
If Swift is unavailable, provide `CANESIGHT_TELEMETRY_FIXTURES_BIN` pointing
to a compatible built executable. No phone/backend connection occurs in these tests.
To inspect synthetic replay output: `swift run --package-path ios/CaneSightTelemetry TelemetryFixtures`.
This separate test root is explicit; existing repository CI does not run Swift or
these cross-language tests automatically. No protected workflow is changed.

## Review evidence and integration boundaries

CS-016 acceptance remains: "Send 10 Hz starting summaries, session/boot/sequence
IDs and reconnect without old queue replay." The 100 ms minimum separation is a
10 Hz starting cap, with no catch-up burst; it is not a hard real-time delivery
promise. The deterministic fast-producer test sends ten times in a simulated
second. The measured real pair delivered about 9.07 Hz on the tested network.

See [CS-016 acceptance evidence](../../tests/ios/CS-016_ACCEPTANCE.md) for the
source-to-test mapping and actual phone/Pi counters. Physical-iPhone core/client
regressions cover a blocked send, independent timeout/cancellation, latest-only
mailbox, retained sequence state, cleared reconnect queue and fresh post-open
capture. Those socket/clock fault injections are synthetic even on a real phone.
Separate native tests exercised real default-TLS authenticated WSS, real ARKit
summaries, and operator-reported real Pi receipt across reconnect.

This component is ready for independent transport review. It does not enable
normal-app streaming or make receiver observations eligible. CS-017 owns actual
host lifecycle/background/lock integration; CS-030 owns final-consumer capture-age
bounds with a justified joint drift budget. Those gates remain open, preserve
unknown/unavailable, and must be completed before live guidance. Motor/electrical
acceptance is separate. No ownership, acceptance, protocol or plan requirement
is changed by this division. Review is not Done or permission to merge own work.
