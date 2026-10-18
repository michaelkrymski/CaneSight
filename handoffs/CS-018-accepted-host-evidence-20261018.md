# CS-018 accepted-host evidence reconciliation

Owner: aditsangani. Branch: task/CS-018-accessible-status. PR #73 remains draft.
Accepted main base: 185aa3afaca1bdd6ba5380ba0e7113917f86b2df.
Starting task head: 6ddb7fc4166eda69db5153025d29ceea164b315e.
Accepted main merged cleanly into this existing task branch at 48648b1; no shared
history reset/force, other task takeover or protected change was performed.
Before publishing, accepted CS-014 advanced main to
1385e110eae223c221b8eff22e7417f028e19e35. It was merged cleanly at
6d13e285a2c97d35155eb69fa56541d674fe441b; the evidence snapshot above remains
at its original attribution base. No CS-018 runtime source changed.
The publisher detected pre-existing schedule-field mojibake in the task branch.
Restored the task's non-runtime fields exactly from accepted main; no requirement
or schedule amendment is proposed.

Michael's actual GitHub review on PR #73 (18 October) identified no new code
defect and asked to distinguish accepted #69's Apple/host evidence from remaining
VoiceOver listening/focus, CS-040/Pi and measured audible-cancellation gates.

## What changed

Updated ios/AccessibleStatus/README.md's stale "no host/Apple verification"
statements and added ACCEPTANCE.md with completed evidence and exact remaining
manual checks. Added tests/ios/evidence/CS-018-accepted-host-20261018.json,
runtime-only CS-018 task updates, this handoff, a new changelog fragment and the
renderer-generated log. Runtime Swift/host/teammate source remains unchanged.
Historical evidence/handoffs/fragments are preserved.

## Tests and attributed evidence

Independently matched all four package Swift files to accepted host pin 6ddb7fc
using normalized UTF-8/LF bytes and matched all nine host-file hashes in
CS-013-integrated-app-20261018.json. That accepted evidence reports five physical
phone and two Simulator UI cases, signed app build/install/launch, 17 status Mac
cases and 14 current-lifecycle Simulator cases. These tests were not rerun on
this Windows host and do not establish VoiceOver listening or audible delay.

Reran locally using cached official Swift 6.0.3 Ubuntu toolchain in WSL with
task-local ncurses runtime, no system installation:

```sh
swift test --package-path ios/AccessibleStatus --jobs 2 -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
swift test --package-path tests/ios/cs018_lifecycle_integration --jobs 2 -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
```

17 status and two actual accepted-lifecycle integration cases passed, zero
failures. Linux excludes SwiftUI. Source-hash/evidence consistency and whitespace
checks passed before publication; checked publisher reruns repository checks.

## Human observation and limits

Human confirmed installed Camera/Status/Location tabs and Read status/Cancel audio
controls, then corrected an earlier no-speech reply: speech is audible and cancels
with Cancel audio. The installed commit, device/OS, route and timing are unknown.
Record the corrected report as an observation, not exact-head or Bluetooth
acceptance. A separate subsequent answer reports VoiceOver labels, Unknown values
and reachable/activatable Cancel accessible. This is positive operator evidence,
not exact-build attribution; Escape, full focus/hint/layout and route checks remain.

Keep draft and blocked. Current exact-source Apple build/host-local-speech checks
are completed by attribution; remaining manual VoiceOver/layout/route/buffering
and CS-040/Pi job/request cancellation integration must be reviewed with owners.
Do not invent a remote cancellation contract, claim physical silence or mark
Done. Preserve Michael's host and Mila's speech/state machines. Next reviewer
should use ACCEPTANCE.md and the source-pinned native evidence, not the obsolete
initial PR description or initial portable-only evidence as current status.
