# CS-016 software checkpoint — bondmila — 2026-10-17

Base: `1dcead2e4e61396a059985c7d1ac792c733ec3fb` (accepted main).
Branch: `task/CS-016-bounded-telemetry`.
Assignment: merged [PR #61](https://github.com/michaelkrymski/CaneSight/pull/61),
Michael approval verified on final claim head `1bae160` before implementation.
The accepted task owner is bondmila. Requirements/dependencies/allowed paths remain unchanged.

## Changed files and behavior

- `ios/CaneSightTelemetry/Package.swift`, `.gitignore`, README: isolated package,
  integration contract and deferred gates; no root app project or teammate files.
- `Sources/CaneSightTelemetry/Wire.swift`: typed samples/grants, strict bounded
  clock-probe parsing, exact accepted v1 envelopes and credential redaction.
- `TelemetryCore.swift`: 100 ms depth spacing, independent heartbeat/depth sequence,
  original capture freshness, one pending sample/control/send, explicit readiness,
  clock-fault latch, replay/rate/cap bounds and no reconnect queue replay.
- `NativeWebSocket.swift`: default OS TLS, Bearer phone grant, actual open delegate,
  bounded receive buffer, redirect rejection, cancellation and sanitized failures.
- `TelemetryClient.swift`: actor plus synchronous latest-only producer mailbox,
  explicit source clock, send/dial watchdogs, bounded task ownership, generation
  fencing and suspend/resume hooks. No per-frame task accumulation.
- `Sources/TelemetryFixtures/main.swift`: synthetic replay generator, no network.
- Package `Tests/CaneSightTelemetryTests/{CoreTests,ClientTests}.swift` and
  `tests/ios/test_telemetry_contract.py`: meaningful fake-socket/deterministic tests
  and original Swift byte validation through accepted Python schema/session relay.
- Own task runtime, new changelog fragment and script-generated CHANGELOG.

## Verification actually run

- `swift test --package-path ios/CaneSightTelemetry`: 21 passed on host Swift 6.4.
- `swift build --package-path ios/CaneSightTelemetry -Xswiftc -strict-concurrency=complete`:
  passed without warnings.
- `python -m unittest discover -s tests/ios -v`: 4 passed, no skips; synthetic Swift
  replay output accepted by existing Python schema and paired-session relay.
- `python scripts/validate_repo.py`: repository structure valid.
- `python -m unittest discover -s tests -v`: 110 passed.
- Checked publisher additionally reruns these shared checks, generated changelog
  verification, governance/path checks and staged whitespace before commit/push.

Tests cover rates/latest overwrite, unknown/null, timestamps/identities, safe
sequence limits, stale/future/duplicate frames, suspend/readiness gates, clock
reversal/failure, blocked sends, dial timeout/late factory cancellation, rejected
auth, strict malformed control/duplicate keys, clock t2/t3 and backend replay/role
rejection. No real network traffic, private imagery or physical assertions.

## Limits and next steps

This is the complete standalone CS-016 transport software checkpoint. It is not a
finished iOS app. Keep draft and blocked. User explicitly authorized deferring
Xcode/app/device verification; host SwiftPM compilation was still available and run.
CS-014 must supply real summaries and verified matching capture/source-clock units;
CS-017 must wire lifecycle hooks and app permissions/privacy. No ownership takeover
or changes to those tasks. App enrollment/storage must provide the phone-role grant.
A new process/client or clock reset needs a newly authorized session/boot; reconnect
inside one client retains counters. Backend detach closes both paired peers, so Pi
reattachment and clock freshness must also be verified during end-to-end recovery.

Later: build/sign the actual iOS app, validate native TLS/auth/redirect behavior,
run a LiDAR phone through packet age/rate, backpressure, network loss, suspension
and reconnect with the paired backend/Pi. Only Michael can accept hardware evidence.
No crossing permission, all-clear inference or movement command is implemented.
No changes to protected contracts, workflow/governance or master plan.
