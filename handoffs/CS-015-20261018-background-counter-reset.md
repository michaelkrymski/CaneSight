# CS-015 nonzero target background reset

Initial accepted base: 3baf4de7e28b20d7fa381d6eb52d2604c313cfaa.
Integrated accepted base: a7b0214dd0c28316b61449d72c81215753b94993.
Branch: task/CS-015-device-background-reset. Owner Michael; original assignment
and implementation PR #70 verified authored by michaelkrymski and merged.
No competing open CS-015 PR existed when starting. Follow-up authorized by
Michael's request to perform a task requiring his Xcode/iPhone access.

The earlier device evidence covered background recovery with zero target counts.
Added a separate operator-assisted test requiring a real physical left target,
normal Record control and actual Left 1/3 before any background-reset claim.
It waits for the unchanged 0.20 m separation from both other measured columns.
The original camera smoke check remains independently selectable. No production
app, mapping, source capture, confidence or freshness thresholds changed.

Actual tests: Xcode 27.1 / physical iPhone 17 Pro Max / iOS 26.6.2:
- Baseline camera Start/Stop, Unknown, restart, Home Screen background and live
  recovery: one passed, zero failures/skips.
- Operator-assisted test: one passed, zero failures/skips. Log contains actual
  `BEFORE_BACKGROUND_COUNTS=Left 1/3 · Center 0/3 · Right 0/3`, background state 3,
  and `AFTER_BACKGROUND_COUNTS=Left 0/3 · Center 0/3 · Right 0/3`. Live depth
  returned; final Stop cleared all columns to Unknown.
- 11 mapping XCTest cases passed with complete strict concurrency.
- 212 shared unittest cases passed after installing repository-declared test
  dependencies in an isolated temporary environment. Initial system-Python run
  had 14 import errors due to missing dependencies; no product defect inferred.
- Checked publisher reruns structure/shared/changelog/whitespace validation.

Setup/failed attempts: first test build passed but runner installation hit free
Personal Team app limit. Removed only the prior CaneSight UI-test runner; both
prototype apps retained. First physical attempt could not record because columns
were about 0.90/0.95/0.97 m; second timed out awaiting separation (initially
0.94/0.97/0.97 m). Operator repositioned target before final successful run.
No reset acceptance inferred from those failures. The target-specific wait and
separate test keep that prerequisite explicit. No fake sensor/count seeding.

Local private results: /tmp/canesight-cs015-background-baseline.xcresult and
/tmp/canesight-cs015-background-target-final.xcresult. Failure bundles remain in
/tmp as background-result, background-retry and background-separated xcresults.
They contain camera attachments and must stay out of Git. Sanitized evidence
records test-source SHA-256, tested dependency pin and results without unique
device IDs, signing IDs, private images or GPS.

Changed files: ios/MappingBench/UITests/BenchUITests.swift,
ios/MountMapping/README.md, tasks/CS-015.json, new sanitized evidence JSON,
this handoff, new changes fragment and generated CHANGELOG.md.

Limits/next steps: this closes the previously disclosed nonzero-counter reset
evidence gap in handheld portrait. One left capture is sufficient for that check;
it does not establish nine captures, every orientation, final cane/grip/motor
mapping, sensor numerical accuracy, original capture age, latency, networking,
electrical behavior or road use. No full-task Done claim. Review the follow-up
independently; preserve the prior target/orientation evidence and remaining limits.
