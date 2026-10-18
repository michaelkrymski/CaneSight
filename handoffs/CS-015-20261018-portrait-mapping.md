# CS-015 portrait display mapping and target-check bench

Accepted main base: 5dd5fa37009402b7eb7c9dbed3d20eacd4346c90.
Branch: claim/CS-015-michaelkrymski. PR: https://github.com/michaelkrymski/CaneSight/pull/70.
Initial assignment-only commit: 5cd875e1cfa3ceae17d476d13d6561c3b296d4f5.
Actual PR author michaelkrymski and initial assignment-only diff were verified
before implementation. No competing CS-015 claim; main task owner was null.
All 110 shared tests passed before claim publication. User chose portrait upright,
rear cameras forward for this test. Work is isolated from pending CS-013 PR #69.

## Changes

`ios/MountMapping`: exact depth/confidence permutation plus aspect-fill ROI using
the native ARKit display transform, rejecting mirrored/uncovered/skew/invalid
geometry; original CS-014 processor and source provenance retained. Eleven tests.
Native portrait adapter with runtime depth/tracking/plane/aspect checks.

`ios/MappingBench`: separate camera/column/known-target app with bounded latest-only
frames and UI deliveries, callback-recency clearing and loss-generation tracking.
Three unique captures per physical target, distinct-side dominance gate, explicit
unknowns and reset after orientation/lifecycle/geometry losses. No implicit phone
body/motor mapping, network, GPS, stored images or actuation. Exact draft #62 source
is prepared into ignored local review dependencies with hash validation. No teammate
task/source, #69 file, protected contract or master plan changed.

## Verification actually run

- 11 Mac XCTest cases passed with complete strict concurrency and warnings as errors.
- Physical-iOS SDK build of the new core, native adapter and bench app passed with
  Xcode 27.1 / iOS SDK 27.1 and signing disabled.
- Dependency materializer verified original pinned package hashes.
- Shared structure/test/changelog/whitespace checks run by checked publisher.

## Remaining evidence

Signed install/launch and actual portrait three-target observations still pending
at this checkpoint. Do not infer physical alignment from synthetic rotations.
Minimum manual sequence: three left, three center, three right captures, then
rotate/Stop/background reset. Phone-to-body/grip relationship must stay fixed;
the handheld check does not certify a final cane mount. UI receipt timeout is
not calibrated sensor capture age. Draft #62 acceptance and independent review
remain required before main integration. Task blocked/PR draft until evidence.
