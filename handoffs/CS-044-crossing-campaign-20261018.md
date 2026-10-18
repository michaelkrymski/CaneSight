# CS-044 crossing-menu software campaign

- Base: `94ccaaf14a88b990cc468433e55622b0b1e6681f`.
- Branch: `task/CS-044-crossing-failures`; existing merged CS-044 ownership retained.
- Reviewed inputs: PR #58 `8f4d52100fa3e7bfe93cf4a8a2faedfd4495bc49`
  and PR #41 `ca88cd20205bc76dc88a06d1cd194689f5f05f90`.

## Changed files and evidence

New `qa/crossing_failure_suite.py`, manifest/guide/reports in `qa/failures/`,
`tests/failures/crossing_cases.py` and four report-integrity tests. Only own task
runtime and new audit records changed outside QA/tests. No teammate source,
protocol, baseline or workflow edits. Dependency source is temporarily exported
unmodified by exact commit and verified hash, never vendored as implementation.

19 fixed campaign cases passed on Windows Python 3.14.7 and local Linux Python
3.12 Docker with network disabled/read-only sources. Four integrity tests passed
locally and are discovered by normal CI. Runner verifies exact case identities,
rejects missing/skipped/failed cases and suppresses raw child errors. Reports
identify tested QA and dependency bytes, not an invented clean Git commit.
Shared checked publishing runs repository structure, root tests, governance,
generated log and whitespace checks. Verify final PR head CI before review.

## Findings and limits

No failing case was found in this 19-case synthetic interaction campaign. Real
menu/audio composition passed threshold/release/cancel/timeouts, no-default/wrap,
loss/recovery, local epoch replacement, priority and clock tests. Standalone
controllers reject old-generation audio and cancelled delayed-worker tickets.

The production menu/request/result bridge remains absent from the pinned inputs;
live scenario switch/result correlation is not proven by controller tests.
Automatic Bluetooth readiness monitoring and real phone/Pi/audio timing also
remain absent. Consent/source/route/hazard states are explicit injected fixtures.
Do not conflate optional narration's 8s deadline with 500ms depth/1500ms vision.

Next: independent review of this QA PR and dependency PRs #58/#41; repin/rerun
after changes; add real production bridge/result/cancellation tests once that
integration exists; coordinate controlled physical audio/button/phone/Pi failure
evidence after prerequisites. Keep task blocked for those acceptance gaps.
No Pi/camera/SSH runner/GPIO/motor access or physical readiness claim.
