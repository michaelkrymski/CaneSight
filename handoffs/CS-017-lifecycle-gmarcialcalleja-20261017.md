# CS-017 software implementation checkpoint

Owner: Gavin (`gmarcialcalleja`). Claim #59 merged before implementation.
Initial base: `0a1a1cf9c15b8c7b126fe7b4e8c51870ef454545`.
Updated base: `1dcead2e4e61396a059985c7d1ac792c733ec3fb` (fast-forward accepted
main assignment update for CS-016, no teammate task edited locally).
Branch: `task/CS-017-ar-lifecycle`.

## Scope and behavior

Acceptance remains: no cached depth after interruption; Pi expires observations;
recovery requires fresh data. Allowed implementation paths are `ios/` and
`tests/ios/`; dependency remains CS-016. Neither shared contracts nor master plan
were edited. Software implementation is prepared; task remains blocked for host
integration and Xcode/device acceptance, not Done.

- `ios/Lifecycle/Package.swift`, `.gitignore`: standalone SwiftPM package, iOS 16+.
- `Sources/CaneSightLifecycle/DepthLifecycle.swift`: MainActor guard, generation
  leases, one pending value snapshot, cancellation/purge/clock/unknown hooks,
  fresh mapping/capture recovery, strict capture age/uncertainty checks at admission
  and send, sequence continuity, explicit new enrollment on local clock reversal.
- `Sources/CaneSightARLifecycle/ARLifecycleBridge.swift`: scene-specific lifecycle
  observation and AR delegate forwarding; does not steal the host AR delegate.
- `Tests/`: 10 portable XCTest cases; 2 deferred Apple bridge cases.
- `ios/Lifecycle/README.md`: concrete CS-014/016 integration sequence and device
  acceptance matrix, including clock-domain mapping requirements.
- `tests/ios/__init__.py`, `test_lifecycle_receiver.py`: 3 synthetic regressions
  against the actual consumer CaptureAgeGate used by the Pi receiver: expiry
  without a final packet, heartbeat cannot refresh depth, reconnect needs new
  calibration/capture with preserved sequence history.
- Own task runtime fields, new changelog fragment and generated log only.

## Tests actually run

Portable Swift tested on the existing Vultr host in an isolated throwaway Docker
container with network disabled, 1 CPU, 2 GiB limit; production services untouched.
Official image `swift:6.0.3-jammy`, resolved digest
`sha256:a159706c0c52c1025998a87bc2ab3ceba71416a00110b31cc2ab08d9184341c9`.

```text
swift test --jobs 1 -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
10 tests passed; no warnings/errors. ARKit/UIKit source and Apple tests excluded.
python -m unittest tests.ios.test_lifecycle_receiver -v
3 tests passed.
python -m unittest discover -s tests -v
113 tests passed (includes those 3).
```

The first test pass exposed fixture setup mistakes: one reused a source timestamp,
and one retained the example heartbeat's degraded state. Fixtures were corrected;
production checks were not weakened. Complete strict-concurrency compiler checks
passed for the portable source. Linux build output mentioning the AR target does
not mean its conditional Apple body was compiled.

## Limits and next steps

Mila owns CS-016 after merged #61. This package supplies integration hooks; no
CS-016 host/transport exists on this base to wire them into. CS-014's depth package
is proposed separately in #62. Keep this standalone package separate from those
implementations. The host must synchronously purge all queues/in-flight sends,
serialize capture/lifecycle/send admission, verify clock mappings and preserve
source timestamp/boot/sequence. Already delivered network bytes cannot be recalled;
consumer capture-age expiry remains required even if the phone suspends silently.

On a Mac, build the Apple bridge and run its two tests with the supported iOS
target. Wire host delegate/scene callbacks and transport hooks, then perform the
README matrix on a real LiDAR phone and Pi: lock/background, AR interruption,
limited tracking/failure, Wi-Fi outage and clock/epoch changes. Retain metadata
only, no tokens/images/precise GPS. No Xcode, physical phone/Pi, camera, inference,
motor/electrical readiness or crossing permission is claimed by this checkpoint.

Stop at independent review; do not merge or push main.
