# CS-015 operator target report and native runtime evidence

Original accepted base: 5dd5fa37009402b7eb7c9dbed3d20eacd4346c90.
Integrated accepted main: 5dbb6ad (PR #71); only generated CHANGELOG overlap was
resolved by the required renderer. Phone implementation remains
bd99b6cf043122d2d4548f4e97bfa70bbf868409, PR #70.

## Operator report

Michael explicitly confirmed Left 3/3, Center 3/3 and Right 3/3 on iPhone 17 Pro
Max / iOS 26.6.2 in handheld portrait, rear cameras forward. This is user-reported
stationary target evidence, not an independently recorded physical measurement.
He clarified rotation/Stop/background resets have not yet been tested in this
bench app. They remain pending, separately from earlier #69 host lifecycle checks.

He observed floor influence making all three distances similar, including while
kneeling. No pitch, numerical distances or accuracy series was supplied. The code
uses the full viewport height and the existing CS-014 near 10th percentile in each
column. It includes floor samples and performs no ground-plane classification.
Similar column values therefore cannot distinguish broad obstacles from floor.
The target check establishes side correspondence only in the reported setup;
it does not validate obstacle classification or final cane/motor mapping.

## Native runtime tests actually executed

Xcode 27.1 / iOS SDK 27.1 test bundles ran on iOS Simulator 27.0 (24A434),
iPhone 17, arm64: depth 15, lifecycle 12 (including two native bridge tests),
telemetry 21 and coarse location 13. All 61 passed; none failed or skipped.
Exact review commits and sanitized xcresult summary fields are in the JSON.
No teammate source or task was modified.

Correction: the earlier telemetry product scheme reported build-for-testing
success without generating any test bundle. Its first runtime attempt failed
with no test bundles available. Rebuilding with CaneSightTelemetry-Package
produced the bundle and all 21 cases then executed successfully. This corrects
the earlier premature claim that all four test bundles had already built.
Local result bundles are /tmp/canesight-depth-native-runtime.xcresult,
/tmp/canesight-cs017-native-runtime.xcresult,
/tmp/canesight-telemetry-package-native-runtime.xcresult and
/tmp/canesight-location-native-runtime.xcresult. Summaries exclude unique IDs.

Changed files: new evidence JSON, this handoff, new changelog fragment, task
runtime evidence/blocker, README limitation and generated changelog. No app source
changes: the prior 11 strict mapping XCTest cases, signed physical SDK build,
install and launch still describe the tested implementation. Checked publishing
reruns shared checks. No physical GPS, transport, sensor timing, electrical or
motor verification is inferred from Simulator results.

Next: collect each bench reset observation, retain portrait-only scope and floor
limitation, then independent review of #70 and its unmerged #62 dependency.
