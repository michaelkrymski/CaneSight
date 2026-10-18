# CS-015 direct phone inspection and automated UI checks

Original accepted base: 5dd5fa37009402b7eb7c9dbed3d20eacd4346c90.
Integrated main: 94ccaaf14a88b990cc468433e55622b0b1e6681f. Prior head: fa7b44402cf5ad4a90a36a216aa95da9bd45062a.
PR #70; independent review and dependency #62 acceptance required before merge.

Michael reported the diagnostic under View left: only 10% high-confidence depth.
Existing CS-014 requires 25% eligible coverage. This explains why that observation
was Unknown; it does not establish why sensor confidence dropped. During actual
UI test runs left coverage recovered to 95–98% without threshold changes. The
floor observation remains documented; no ground classifier or range calibration.

Direct devicectl screenshot inspection succeeded on the physical phone. At the
inspected instant all values were Unknown and tracking/depth was unavailable.
Local private snapshots and XCTest result attachments are excluded from Git.
The ordinary macOS iPhone Mirroring app cannot access camera/microphone, per
Apple https://support.apple.com/en-euro/120421; use Xcode device tools instead.

Added a native XCTest UI target/shared-scheme testable and stable accessibility
identifiers on the bench view. Signed Xcode test on iPhone 17 Pro Max / iOS 26.6.2
passed: one executed test, zero failures or skips. It obtains actual measured
depth, taps Stop, verifies all readings Unknown/stopped status, restarts and
obtains a measurement, activates SpringBoard (Home Screen), verifies background
state, reopens and obtains live readings, then stops and verifies Unknown again.
Local result: /tmp/canesight-cs015-ui-results-v6.xcresult.

Setup failures are retained locally: initial test couldn't find a lazily rendered
offscreen control; scrolling fixed it. Next expected an uncombined accessibility
label while SwiftUI included the column name; assertion now checks its Unknown
suffix. Later press(.home) attempts kept reporting foreground (state 4). Explicit
SpringBoard activation yielded background (state 3) and recovery passed. These
are harness corrections; no app thresholds, fake depth, injected counters,
permissions, freshness rules or app lifecycle logic were changed.

UI target uses iOS 17+ for current XCTest libraries; app deployment remains 16+.
The test skips explicitly if no supported sensor/live measurement is available;
such a skip is not physical acceptance. On this run it did not skip. Camera
permission stays controlled by iOS/operator. Cleanup stops camera when reachable.

Scope/limits: UI test begins with zero target counters, so it does not prove a
nonzero counter reset on background. Prior operator evidence established all nine
physical target captures, rotation reset and Stop count/distance reset. Live UI
recovery does not measure capture age, latency, numerical accuracy, electrical
behavior or final cane/motor mapping. Core mapping/dependency source unchanged;
prior 11 mapping cases and 61 native Simulator cases remain applicable. Checked
publishing reruns shared repository checks. Task now Review, never Done.

Changed files: bench view identifiers, project/shared scheme, UI test source,
new sanitized evidence, this handoff, README, task runtime and new changelog/
generated log. No private images or unique device/signing identifiers in Git.

Main advanced during testing with accepted #63/#67 lifecycle/location changes.
Integrated those unchanged and regenerated the only overlap, CHANGELOG.md, using
the required renderer. Earlier 61-test evidence remains explicitly pinned to the
older recorded review commits and does not certify those newer implementations.
The CS-015 phone test uses only its unchanged exact CS-014 review dependency.
