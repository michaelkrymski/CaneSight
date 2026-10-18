# CS-016 depth stream continuation

Owner: Michael Krymski. Branch: `task/CS-016-michaelkrymski`.
Accepted base: `a7b0214dd0c28316b61449d72c81215753b94993`, merged ownership PR #81.
Preserved implementation: Mila's PR #64 at
`0433fc94af1a1e3edfe2d2bb28925cb3be6df1ee`; integration merge `598d534`.
Publication refresh: merged accepted main `f6af886` (CS-049 evidence/tests) after
the checked publisher detected main had advanced. Merge was clean; no reset/rebase.
No rewritten history, scope/dependency/acceptance change, self-merge or governance edit.

## Changes

- Preserve all original bounded telemetry implementation/tests/history. Resolve
  the inherited task conflict to accepted main ownership and regenerate the log.
- Add `ios/DepthTelemetry` Swift package: `DepthTelemetryAdapter` converts CS-014
  source-image columns, original capture seconds to milliseconds, measured coverage
  and unknowns. Reject missing/invalid time and live/replay mismatch. No arrival-time
  replacement, guessed tracking state or physical side-mapping claim.
- `DepthTelemetryStream` binds producer and client to the same enrolled session;
  forwards explicit lifecycle/readiness calls and uses synchronous latest-only
  submission. No default clock, network start in init or per-frame tasks/images.
- Seven conversion/producer-to-wire tests cover unknown coverage, tracking loss,
  bad time, mode mismatch, latest-only blocked send, sequence retention and
  post-resume readiness/new-capture requirements using synthetic data/fake sockets.
- Add native URLSession tests in `ios/CaneSightTelemetry/Tests` and a Python
  loopback harness in `tests/ios/test_native_websocket.py`: generated untrusted
  certificate rejected before HTTP authentication; real stalled handshake cancelled.
  Never install a CA, override trust or use an external server/real grant.
- Update telemetry README, own task runtime, new changelog and sanitized evidence
  `tests/ios/evidence/CS-016-depth-stream-20261018.json` with source hashes.

## Verification actually run

- Strict concurrency complete + warnings-as-errors: seven bridge Mac tests passed;
  21 existing transport tests passed (two harness-only cases skipped in this run).
- Python native loopback harness passed; it executed both native Swift cases with
  zero skips. No successful trusted WSS or authentication claim follows from this.
- Four Swift fixture-to-current-backend/schema contract tests passed.
- Generic iOS SDK build of `CaneSightDepthTelemetry` succeeded, unsigned.
- Final iOS Simulator result: seven passed, zero skipped/failed. Local result:
  `/tmp/canesight-cs016-bridge-simulator-final.xcresult`.
- Repository discovery: 217 tests passed. Structure, generated log and whitespace
  checks passed before publication; checked publishing runs shared checks again.

Commands: `swift test --package-path ios/DepthTelemetry --jobs 2 -Xswiftc
-strict-concurrency=complete -Xswiftc -warnings-as-errors`, equivalent telemetry
package test, explicit Python native/contract test discovery, and `xcodebuild`
with the bridge package scheme for generic iOS and an iOS Simulator test target.
All Apple tools used `/Applications/Xcode.app/Contents/Developer`.

## Limits and next steps

Michael explicitly reserved his phone: no phone control, install, signing,
screenshots, ARKit or physical device test was performed here. Do not use it until
he says it is free. Current app stays local preview; this package is available for
integration but does not enable app networking or create/store enrollment grants.

Capture-clock alignment, suspension behavior, privacy-purpose review before
transmitting boot-derived timestamps, native trusted authenticated WSS, paired Pi
reattachment/clock drift, measured on-device rate/freshness and network failure
behavior remain acceptance gates. The documented public HTTPS health request
failed from this Mac; establish a reachable authorized backend first. Synthetic
inputs and conversion tests prove no sensor timing, mount calibration or electrical
behavior. Task remains blocked and the continuation PR remains draft.

Open a PM-authored continuation linked to #64, preserving Mila's source commits.
Only after linking its replacement, close the unchanged superseded #64 as agreed
in accepted transfer CR. Independent review is still required before implementation
merge; no automatic merge is authorized.
