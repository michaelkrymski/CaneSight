# CS-016 depth-to-telemetry integration

`CaneSightDepthTelemetry` connects the accepted CS-014 depth summaries to the
CS-016 bounded transport. It does not start a camera or touch UIKit. Add the local
`ios/DepthTelemetry` package alongside the existing app packages.

```swift
// grant: authorized PHONE-role PhoneSession. Enrollment stays outside this package.
// verifiedCaptureClockMS: source clock verified against original capture times.
let stream = DepthTelemetryStream(session: grant, clock: verifiedCaptureClockMS)
await stream.start()                          // producer starts as .starting
await stream.setProducerState(.ready)         // explicit producer readiness only
try stream.submit(summary)                   // original CS-014 DepthSectorSummary
await stream.suspend()                        // interruption or background
await stream.resume()                         // .starting; new readiness/frame needed
await stream.close()
```

The stream binds the adapter's live/replay mode to the same session as its client.
Submission converts seconds to milliseconds without replacing, rebasing, rounding
or estimating capture time from arrival. Missing/invalid timestamps and a foreign
mode throw before submission. Image left/center/right remain camera coordinates;
conversion does not verify a mount or physical motor mapping. The caller must
preserve the exact geometry used to produce the summary.

Measured coverage is retained, including low-coverage unknown sectors. CS-014
unavailable summaries have no usable tracking subtype, so they map conservatively
to `unavailable`, all distances null. Missing coverage maps to zero usable evidence.
No prior good frame supplies a missing distance, timestamp or tracking state.

The existing client's single latest mailbox handles the converted value
synchronously; no task or queue is created per frame. Core rules still require an
open connection, explicit producer readiness, a new post-open/post-ready capture,
capture age at most 500 ms, and at least 100 ms between depth send starts. Dropped
work is discarded through interruption/reconnect; sequence marks survive.

**Clock gate:** this package deliberately supplies no default ARKit/uptime clock
or offset calibration. Verify that the injected milliseconds use the same time
base as original capture seconds, including interruption and suspension. A
conversion test is not capture-clock/device-drift evidence. Until that evidence
and authorized pairing exist, keep the phone app in local preview. The existing
app's SystemBootTime privacy declaration covers local timers; review its actual
API purpose before enabling transmission of boot-derived timestamps.

Run `swift test --package-path ios/DepthTelemetry -Xswiftc
-strict-concurrency=complete -Xswiftc -warnings-as-errors`. Tests use generated
depth samples and injected transports. Native OS TLS rejection/cancellation is
tested separately with `python -m unittest discover -s tests/ios -p
test_native_websocket.py -v` on macOS. No phone, physical Pi, live camera, measured
sensor latency, accepted network enrollment or electrical verification is claimed.
