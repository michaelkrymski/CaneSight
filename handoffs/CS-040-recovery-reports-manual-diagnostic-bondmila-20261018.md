# CS-040 mixed Pi evidence and focused diagnostic — 2026-10-18

Branch task/CS-040-restricted-narration; base 990c5b9194a756dfd3231ab7d58bc7a24127bb91.
Accepted owner bondmila; PR #41 remains draft. User authorized continuing CS-027/040.

Two distinct pasted Pi recovery payloads from combined 6dfda42 retained verbatim
as structured reports in tests/context/evidence/CS-040-speaker-recovery-operator-reports-20261018.json.
Each appeared identically twice in its user message; store once per payload, not
as repeated-trial evidence. No agent SSH/audio observation. No private paths/IDs.

First: manual software true/operator false (operator clarified no audible speech),
hazard/unavailable/expiry/late observations true; recovery reconnect silence
unknown, so fresh speech correctly skipped. Overall software/operator false.
Second: manual software true/operator false; all remaining observations including
recovery true, software_checks_passed true but operator_reported_all_passed false.
Stop-call times and timer overshoot are software only. Preserve every flag; do not
promote either mixed report to acceptance or discard older separate passing run.

Changed backend/context/speaker_bench.py and README: explicit --manual-only subset,
rejected with --bluetooth-recovery, marked case_selection in output. Existing full
bench default unchanged. Diagnostic can compare two-second cutoff with earlier
one-second case; no production behavior, warmup, retry or output routing changes.
Tests/context/test_speaker_bench.py covers requested subset, negative/unknown
observations and incompatible flags before constructing audio. 73 context tests
pass on Python 3.13 with synthetic/silent fixtures; no local audible test.
Own task runtime/new evidence/new fragment/new handoff/generated changelog only;
no protected baseline or shared contract changes. Publisher runs shared checks.

Next: refresh combined test branch with the selector, repeat focused manual test
on Pi and determine whether speech starts audibly before cancellation. Later
recovery is positive operator evidence, not automatic OS route-loss detection or
PM acceptance. Keep #41/58 draft; actual phone/backend/GPIO context path remains
separate and phone readiness missing per issue #68. No task Done claim.
