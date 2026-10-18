# CS-040 parallel route-query candidate — 18 October 2026

Owner: bondmila. Branch: task/CS-040-bluetooth-route. Existing PR #92.
Base diagnostic head: 9a626216bd6395ddf84a126951aad79979806c27.
Last fetched accepted main: a239e22 (CS-023 GPIO adapter integration).
No other owner's task, protected baseline/contract/governance or motor code edits.

## Diagnostic evidence and reproduction

User attachment shows complete manual-only Pi run on exact 9a62621: software
false, operator unknown, timer fault false; route fault observation_expired during
stream_query. Generator exit -13 is recorded as observed; no unsupported
assertion that it is the primary cause. Two repeated commands reused the same
exclusive report filename and were refused before audio; original file remained
unchanged. Preserve the complete first report once and describe the later
refusals separately. No human or software pass is inferred from these attempts.

New host regression injected independently timely 80 ms reads. Before the fix,
it FAILED, latching observation_expired during device_query. Serial latency plus
post-round poll waits exhausts the start-anchored 350 ms budget. The same
regression passes with parallel reads. This establishes a software scheduling
problem consistent with the Pi failure; it is not physical confirmation that
all causes of silence are fixed.

## Changes

RouteProbe runs the independent sink/device/active-stream queries concurrently,
at most three daemon workers in one round. A nonblocking call lock prevents
reentrant rounds or new worker accumulation while any reader is stalled. All
round workers finish before the round returns; failed launches still join
already-started workers. Production helpers retain 100 ms work and bounded
kill/reap; independent monitor expiry remains active during a blocked reader.

Retain all validation, round-start age, 350 ms observation/100 ms poll/200 ms
registration budgets, 64 KiB per-helper cap, moved-stream rejection and terminal
loss latch. New stalled-stream regression proves expiry still happens, late
success cannot rearm, and ten concurrent attempts create no further helpers.
Responses in fixtures are keyed by command rather than assumed thread order.
No executor queue, provider job, source-age change or route configuration change.

Speaker bench now explains existing-report refusal without echoing private paths,
starting audio or overwriting evidence. Test checks original bytes and no sink
construction. README documents resource/scheduling bounds and test limits.
Own task runtime, new operator record, new handoff/fragment and generated log.

## Verification

108 context tests pass with pinned requirements on Python 3.13/macOS.
Edge/shared/checked publication results appended after completion below.
Fixtures use synthetic OS replies and disposable local processes, not actual
Pi sound. No new audible result or Bluetooth reconnect acceptance is claimed.

## Next

Publish to the existing draft #92, inspect exact-head checks and PM feedback.
Have the operator test the exact candidate with the SAME private selected route
and a NEW report filename. Check audible sentence/cancellation plus diagnostics.
Only after monitored playback succeeds proceed to physical loss/reconnect and
fresh-adapter tests. Preserve failed/unknown evidence and PM acceptance gates.

Integrated accepted a239e22 without conflict before publication.
Initial edge verification: 205 tests passed, no skips, on the pre-sync baseline.
Rechecking the accepted edge delta before publishing.

Final accepted-baseline edge regression: 220 tests passed, no skips.
All tests used pinned dependencies in isolated Python 3.13/macOS.
