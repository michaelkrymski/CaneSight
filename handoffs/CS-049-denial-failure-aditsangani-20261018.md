# CS-049 GPS/Gemini denial and failure QA

Owner: aditsangani. Branch: task/CS-049-denial-failure.
Base: accepted main 3baf4de7e28b20d7fa381d6eb52d2604c313cfaa, merged claim #85.
Dedicated worktree: cs049-claim/CaneSight. Original CS-018 checkout preserved.

## Changed files and result

Added tests/denial/test_policy_isolation.py (10 cases), package marker,
qa/denial_failure_suite.py, qa/denial/README.md, complete Python and portable
Swift reports plus an incomplete initial report. Own task runtime fields, new
changelog fragment, this handoff and generated CHANGELOG only. Production
Swift/Python, other tasks, contracts, workflows and baseline are unchanged.

Composition uses the accepted CaptureAgeGate, LocalPolicy, capped simulated
scheduler and ContextNarration. It demonstrates actual failure/late-result
transitions while checking unchanged policy state and pulse counts. Positive
control delivers fixed narration with healthy depth, then expires original
depth and stops narration. Hazard preemption preserves the valid simulated
obstacle pulse and its original deadline. Same-clock zero drift is a declared
synthetic assumption. No GPIO or speech engine is started.

GPS is not a supported v1 wire message. New rejection checks establish that
unreviewed location/description/permission fields cannot enter depth admission.
The actual portable location component is separately exercised in Swift; these
two results are not represented as an integrated GPS pipeline.

## Tests actually run

- New isolation module: 10 passed, no skips. Initial test development used the
  wrong expected exception for schema rejection; corrected to actual jsonschema
  ValidationError. No production validation was weakened.
- Fixed QA campaign: 43 passed, no failures/errors/skips. Includes accepted
  provider, service, HTTP TestClient and consumer cases plus the 10 new cases.
  First reporter run completed tests but referenced nonexistent backend/protocol.py;
  preserved incomplete report with no success claim, fixed reference manifest,
  reran all 43 and generated the separate complete report.
- Existing CoarseLocation: 15 XCTest cases passed on Swift 6.0.3 Ubuntu/WSL with
  complete strict concurrency and warnings as errors. Denied/restricted/no
  consent/inactive/stale/invalid/provider failure, cache purge, late-fix barriers,
  original age and clock failure exercised with synthetic clocks/fixes. Linux
  excludes the actual Apple Core Location bridge.
- Shared repository checks run by checked publisher before commit/push; current
  CI and Michael feedback must be inspected after a PR is opened.

Commands and normalized source hashes are in qa/denial reports/README. Python
campaign does not call Gemini, read real credentials, run a live endpoint or
claim Swift results automatically. Generated image remains in memory.

## Limits and handoff

Software checkpoint for independent review, never Done. No Xcode, demo phone,
native prompts, live Gemini/provider credentials, real TLS/Pi session, physical
audio/motor or electrical verification performed. CS-019/040 native/transport/
device acceptance remains with current owners. New GPS wire contracts require
their own PM review. No crossing permission or inference from silence.

Michael should assess the evidence and remaining boundaries. If publishing/PR
creation hits an actual permission limit, preserve the branch and report the
exact blocker without claiming a PR exists. Never merge or push main.
