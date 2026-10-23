# CS-013 — local portrait target inspection and recovery

Branch: `claim/CS-013-michaelkrymski`
Base: `c34520b60e85d6cd4b5efe18c94659ee236208c4`
Local continuation only. No GitHub contact, credential generation, motor controls,
shared dependency edits, or experimental production drift configuration.

## Changes

Extract the existing CoreImage portrait pixel transform into PreviewState's
PortraitPreviewTransform helper. Rendered pixel marker tests independently check
both quarter turns, identity/half turn, and aspect-fill crop. Exact recorded depth
crop maps the right sector to viewport x=2/3..1; left crop has a one-pixel outer
margin from existing ceil rounding. This does not establish physical chair mapping.

CameraController adds read-only sector and 9x8 patch confidence/depth distributions,
with geometry metadata. ContentView offers a tappable yellow patch on Camera.
Diagnostics compare all positive finite depths against high-confidence retention.
The unchanged production processor's synthetic tests show that low-confidence near
pixels can be excluded while retained distant pixels keep the sector numeric, and
that near pixels below the retained tenth percentile need not determine distance.
These are counterexamples, not measurements proving this chair's cause.

An initial synchronous diagnostic build was reported to crash, show black camera,
and cycle WSS. No matching system crash log was found. Relaunching without spatial
inspection restored 523 completed native sends, 517 with all three numeric sectors.
The identified diagnostic/capture coupling is now removed: one bounded utility
queue job at most once per second, epoch-checked delivery, no production observation
mutation. Snapshots expose age and patch results expire after two seconds. Local
probe writes are capped at one per second. Actual crash cause remains unconfirmed.

Changed files for this investigation: CameraController.swift, ContentView.swift,
PhoneConnection.swift, PreviewState/Sources/CaneSightPreviewState/PortraitPreviewTransform.swift,
PreviewState/Tests/PreviewStateTests/PortraitPreviewTransformTests.swift,
tests/ios/PortraitTargetTests.swift, README, task runtime evidence, this handoff,
new evidence and changelog fragment, generated CHANGELOG. Earlier local integration
changes remain preserved.

## Validation actually run

- Xcode physical iPhone Debug build succeeded, offline package resolution flags.
- Strict deep code signature verification passed; installed and launched app.
- PreviewState: 10 tests passed, including three new rendered transform tests.
- Synthetic chair production-processor test harness: two tests passed. Temporary
  package `/tmp/canesight-chair-processor-tests-py7keuqx` uses existing pinned depth
  processor; retained test source is `tests/ios/PortraitTargetTests.swift`.
- Local repository structure validation passed; generated changelog rendered.
- Corrected inspection build: 149 native depth sends, all 149 numeric in three
  sectors; live portrait camera, paired/WSS connected. Between snapshots, 83 sends
  across 17.409848 s = 4.767417 Hz. Source capture span 31.972889 s across 151
  samples at final check. Local clock guard did not fail; maximum local capture
  delta 242.913251 ms. Inspection snapshot age 1242.554667 ms.

These are phone-side completions. No new Pi receipt test, physical motor verification,
production capture-age eligibility or drift bound is established. No matching
chair tap/placement was operator-confirmed after recovery; default patch numbers
must not be attributed to the chair. App left foregrounded on Camera, inspection
and native streaming enabled using existing Keychain bond, without Xcode test runner.

Next: confirm visible camera stability, tap actual chair seat/back, compare the
matching patch's all-confidence vs retained depth and the entire right-sector p10.
