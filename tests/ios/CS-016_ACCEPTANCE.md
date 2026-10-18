# CS-016 transport acceptance for independent review

Acceptance is unchanged: **Send 10 Hz starting summaries, session/boot/sequence
IDs and reconnect without old queue replay.** This is the bounded sender component
and depth adapter. Normal-app streaming is still disabled. No receiver freshness,
clock-drift, physical side/motor mapping or electrical acceptance is implied.

| Requirement | Implementation and evidence | Scope/limit |
| --- | --- | --- |
| 10 Hz starting summaries | TelemetryCore separates send starts by at least 100 ms; CoreTests.testTenHzRateUnderFastProducer sends ten in a simulated second; no catch-up bursts. Actual pair: source rate 9.066 Hz, arrival 9.080/9.078 Hz. | Best-effort 10 Hz cap, not hard real-time exact delivery. Report measured shortfall rather than changing original requirement. |
| Session/boot/sequence IDs | Exact enrolled identity in depth/heartbeat; independent counters; strict closed clock-control parser. Original bytes pass backend/schema conformance. Real Pi reported strict sequence and increasing capture across two connections. | Pi evidence operator-reported; no independent SSH/source revision inspection. |
| No old queue replay on reconnect | Single replaceable mailbox, cleared on disconnect/suspend, generation-fenced callbacks, retained sequence/capture marks, post-open/post-ready capture requirement. ClientTests.testBlockedSendTimesOutIndependentlyAndNoBufferedReplayOnReconnect injects blocked write and independent timeout; CoreTests/StreamTests cover fresh-only recovery. Actual native pair suspended and sent 40 new depth packets each side of reconnect. | Blocked socket tests use synthetic clocks/sockets. Native experiment is foreground suspension/reconnect, not actual network-delay/lock or an end-to-end freshness assertion. |
| Preserve timestamp and unknowns | DepthTelemetryAdapter preserves original capture seconds-to-ms, camera columns, coverage and nulls; rejects missing/invalid times and mode mismatch. Seven bridge tests. Separate opt-in bench rebases original capture and source clock by one fixed private origin, preserving elapsed age without emitting uptime. | No default clock equivalence/calibration in production adapter. |

## Latest selected device regression

After integrating accepted main 5234f04, signed physical-iPhone tests ran the
unchanged 13 CoreTests, eight ClientTests and one bench clock guard: **22 passed,
0 failed/skipped**. This directly reruns the 10 Hz deterministic cap and blocked
send/timeout/stale queue tests on iOS. They remain synthetic transport fault
injections, not a claim that an Internet connection was stalled physically.

Actual real-depth phone/backend/Pi run at source 6762777: physical phone test
passed with 80 completed sends, 181 processed frames and no pending/new completed
depth sends during a 1.2-second suspension. Pi operator reported 40 packets per
connection in order. Eight correlated clock exchanges reported RTT median41.049
and max145.109 ms; exchange width median33.396/max141.986 ms. These are diagnostic
round trips, not one-way latency, capture age or a drift bound. Eleven depth packets
preceded ready heartbeat receipt and were transport diagnostics only.

Evidence: `evidence/CS-016-depth-paired-20261018.json`,
`evidence/CS-016-review-regression-20261018.json`, earlier native/bridge/phone-host
checkpoints; source hashes identify tested files. No credentials or device IDs.

## Integration gates retained

CS-017 depends on CS-016 and owns actual app suspension/AR interruption/lock and
fresh-data recovery integration. Do not create a circular merge dependency by
requiring completion of that dependent task before this sender can be reviewed.
CS-030 owns final-consumer clock/capture-age eligibility; its live joint drift
budget remains unverified, so remote guidance stays unavailable. Normal-app
streaming, actual sleep behavior, forced network-delay capture-age measurements,
final mount/haptics and electrical acceptance remain unverified. This document
records task boundaries, changes no task requirements and grants no movement or
crossing permission. Independent review/merge is required; task is Review, not Done.
