# CS-040 exact helper failure details — 18 October 2026

Owner: bondmila. Branch: task/CS-040-bluetooth-route. Existing draft PR #92.
Base/tested Pi candidate: 8b24e51f5b532d1cee2bad54b4b0a020debe93f0.
Accepted main remains a239e22; inspected fetched state before publishing.

## Actual evidence

Operator answered yes to audible/interrupted speech on the parallel candidate.
Its supplied report nevertheless has software_pass=false, route fault
probe_query_failed at sink_query, generator=-13, playback=null, timer_fault=false.
Keep operator_pass=true AND software failure; no manual-cancel pass is inferred,
since a guard fault could have stopped playback first. Previous failed/unknown
reports are unchanged. New evidence preserves this complete payload.

User then ran the read-only timing script (ten requested samples of each helper,
three concurrent bounded reads, no script audio). Sinks median/max 50.6/52.9 ms;
streams 48.05/56.0 ms; BlueZ 36.35/42.0 ms, no reported failures. Raw supplied
float retained. These are not monitored-speech load measurements or proof of
continuous availability. They do not explain the bench failure or justify a
budget increase. Device configuration remains private on Pi.

## Implementation

QueryFailure remains a ValueError with the same generic public message and a
closed reason code. Existing bounded runner now distinguishes launch, read
latency/I/O, byte cap, process wait/exit, decode and cleanup failures. Probe keeps
only the fixed reason from parallel worker failure, or invalid_json from parsing.
Monitor caches an allowlisted query_failure with its first failure/stage.
No arbitrary helper content, exception text, paths, addresses or raw JSON enters
the report. No deadline, poll/grace, freshness, identity, process cleanup, replay,
readiness or audio behavior is relaxed. Original monitor callback semantics stay.

Tests use real disposable helper programs for timeout/overflow/nonzero/UTF-8
classification, then verify reason survives a parallel round and close, and
malformed JSON cannot leak its contents. Existing suite covers bounded/stalled
queries and safe reporting/cleanup. No production/helper/source wire change.

## Verification and remaining work

111 context tests passed with pinned dependencies, Python 3.13/macOS, no skips.
Prior parallel baseline: 220 edge tests passed; not rerun for this diagnostic-only
change. Required publisher runs shared/repository/governance/log/whitespace checks.
No new actual Pi run, sound acceptance, audible-latency measurement or task Done.

Publish to draft #92 and inspect current-head CI. Next Pi manual-only run needs
an exact diagnostic commit and NEW report filename; the query_failure field
identifies the actual helper error under speech load. Do not repeat idle timing
or claim prior failure fixed. After monitored software/audio success, continue
physical disconnect/no replay/fresh-run checks and PM acceptance.
