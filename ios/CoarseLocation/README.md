# CS-019: consented coarse location

Standalone Swift package for the future iOS host. Portable policy code is tested;
Core Location SDK compilation and device acceptance are pending. No network GPS
transport is enabled: the accepted v1 contract explicitly excludes GPS fields.
See `decisions/CR-CS-019-location-context-contract.md` for the review request.

## Host integration

Add this package locally in Xcode and use `CaneSightCoreLocation` on MainActor.
Create `CoreLocationSource(policy: try LocationPolicy(),
purgeCachedAndQueuedContext: ...)`. The purge closure must synchronously clear
any UI/context cache and cancel any queued or in-flight location delivery. Keep
this closure separate from depth/vision freshness and motor policy.

The host must add `NSLocationWhenInUseUsageDescription` to its Info.plist, for
example: "Share coarse location context only when you opt in. Location does not
identify a lane or pedestrian signal." No Always authorization or background
location capability is needed. Explain that the provider may supply precise fixes
transiently, but only rounded coordinates leave this adapter's local policy cache.

1. Show an explicit optional sharing control, default off. OS permission is not
   sharing consent. Call `setSharingConsent(true)` only for that user action.
   Consent is memory-only, never silently restored after a process restart.
2. Forward the owning scene's active/inactive/background/lock transitions through
   `setForegroundActive`. Collection requires both foreground activity and consent;
   start does not bypass OS permission. Forward inactive synchronously, before
   queued context can be used. Call `stop()` before releasing the source.
3. Poll `source.context.snapshot()` for local UI. Show **Location unavailable**
   whenever `unavailable` is nonnull; unavailable snapshots have no location fields.
   The latest fix is cleared on permission/consent/activity change or provider
   failure. Resume and re-consent require a newly dated fix, not CLLocationManager's
   pre-resume cache. Core Location delegate callbacks run synchronously on the main
   run loop because the manager is constructed on MainActor.
4. A future approved P1 publisher can poll `nextContextSnapshot()` on a timer for
   an in-process snapshot at most once per second. It must re-read/validate at send
   time, purge on revocation, and drop old work instead of reconnect replay. Do not
   persist snapshots, print CLLocation/error descriptions or store precise tracks.
   **Do not serialize this local model into depth/heartbeat/vision v1 packets.**
   There is no transport endpoint, serializer, database write or logging callback
   in this package. CS-016 integration awaits its merge and a reviewed GPS contract.

## Time, accuracy and privacy rules

Defaults are the plan's context gate: original fix age at most 10 seconds and
sensor horizontal accuracy at most 20 metres, configurable via `LocationPolicy`.
These are context thresholds, not validated navigation specifications. The adapter
requests nearest-ten-metre provider accuracy to support that gate and never asks
for temporary full accuracy. Reduced-accuracy permission can remain enabled;
a fix failing the configured accuracy gate is simply unavailable.

Age includes the fix's original UTC-to-receipt delay, then advances on the local
monotonic clock. Negative/future, stale, duplicate/out-of-order, nonfinite and
out-of-range fixes are rejected. Wall-clock steps exceeding one second relative
to monotonic progression, reversed monotonic time or invalid clock values clear
the fix and latch clockFault; recreate the source after resolving the clock fault.
An initially wrong phone UTC cannot be proven correct by this local gate; a
remote publisher must establish a reviewed bounded clock relation independently.

The cache stores only latitude/longitude rounded to 0.001 degree cells. The
output distinguishes original sensor `horizontalAccuracyMeters` from
`coarseAccuracyMeters` (sensor radius + 80 m rounding allowance). Rounded coordinates
must never be displayed with the sensor's smaller accuracy radius. Original fix
UTC and fix age are preserved; polling/heartbeats never refresh them. Precise raw
fixes are transient input and not retained in this package. No track history,
heading, altitude, lane, curb, signal association or movement decision is produced.

## Verification

```sh
cd ios/CoarseLocation
swift test --jobs 1 -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
```

13 portable XCTest cases pass with official Swift 6.0.3 on Linux. Linux excludes
the Core Location/UIKit source body; this does not establish an Apple SDK build.
On a Mac, build both libraries for the host's iOS target. On an iPhone verify:
default off/no prompt; opt-in prompt; denied/restricted/reduced/full authorization;
Settings revocation; stale cached initial fix; indoor poor accuracy; future time;
background/lock/resume; opt-out purge; and at most one context handoff per second.
Use synthetic fixtures and counters; do not retain a participant's precise tracks.
After approval of GPS transport, test delayed/replayed deliveries and revocation
across the actual consumer before claiming end-to-end telemetry acceptance.

Primary references: [CLLocation](https://developer.apple.com/documentation/corelocation/cllocation),
[desiredAccuracy](https://developer.apple.com/documentation/corelocation/cllocationmanager/desiredaccuracy),
[When In Use authorization](https://developer.apple.com/documentation/corelocation/cllocationmanager/requestwheninuseauthorization()).
