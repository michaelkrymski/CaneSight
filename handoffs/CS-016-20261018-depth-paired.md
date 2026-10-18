# CS-016 actual real-depth phone/Pi checkpoint

Owner Michael; task/CS-016-michaelkrymski; draft PR #89.
Base and directly tested phone source: 6762777adb2e7cb4ad9d4affeb04a5ea81756c40.
Accepted main a239e221b1d51d7673a78e8fb84e6df274b36e39.
Changed files: new sanitized evidence and handoff, runtime-only task update,
new append-only fragment, generated changelog. No implementation changed.

Signed physical-iPhone test-without-building selected only
LiveDepthPairTests/testRealDepthPairPauseReconnect. Direct Xcode result: 1 passed,
0 failed/skipped, 13.489 seconds. 181 processed frames, 80 completed real depth
sends over two connections. Asserted no pending depth and no additional completed
sends during 1.2-second suspension; resumed with new frames. Local private result:
/tmp/canesight-cs016-depth-paired.xcresult (not committed).

Michael reported actual Pi final summary: 40 depth packets on each connection;
strict sequence order and increasing original captures; source rate 9.066 Hz on
each, arrival rates 9.080 and 9.078 Hz. Eight correlated clock exchanges: RTT
median41.049/max145.109 ms; interval-width diagnostic median33.396/max141.986 ms.
Pi had five/six depth packets before ready heartbeat receipt, counted only as
transport diagnostics, with no eligibility. Pi camera/GPIO/guidance false.
Pi checkout was updated by human instructions; final revision not independently
inspected via SSH. Keep direct phone and operator-reported Pi evidence distinct.
Exact sanitized summary and source hashes: tests/ios/evidence/CS-016-depth-paired-20261018.json.

Real transport passed; exact 10 Hz delivery was not achieved or claimed. Rates
and clock round trips do not establish capture age, one-way delay, a joint drift
budget or actual sleep/lock behavior. Pause/reconnect is not forced delayed-network
backlog testing. No policy, motors or physical/electrical verification. Normal app
streaming remains disabled; task blocked and PR draft pending these gates.

Original replacement role grant had reused old phone identity and was withheld;
corrected role files matched fresh reserved phone and actual Pi process bindings.
The phone test consumed its on-device file once. Remove own local role files;
human must remove Pi private file and ask backend operator to revoke test session.
No automatic Pi SSH, operator credential or token in source/logs/evidence.

Checks: previous harness head had all required CI passing. Checked publisher runs
shared checks for this metadata-only checkpoint; inspect new current-head CI.
Independent review/merge still required; no Done or merge claim.
