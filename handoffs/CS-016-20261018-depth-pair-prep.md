# CS-016 real-depth pair preparation

Owner Michael; branch task/CS-016-michaelkrymski; draft PR #89.
Base 8a6c7b207b48fa4ff859ca02811247c21d882721; accepted main a239e221b1d51d7673a78e8fb84e6df274b36e39.

Add DeviceTests/LiveDepthPairTests.swift and its host target reference, manual Pi
observer and six tests, PHONE_PI_DEPTH.md, sanitized evidence, README privacy
explanation, task runtime evidence and new changelog fragment/generated log.
Normal app streaming remains off. No shared contract or plan changes.

Actual signed physical build succeeded. Two selected device tests passed without
skips: deterministic clock discontinuity/age guard and 41 real ARKit depth frames
across foreground pause/restart, with no network client started. Local result:
/tmp/canesight-cs016-depth-local.xcresult (private device metadata, not committed).
Six Pi observer software tests passed, including actual loop with fake sockets
and clocks. Real paired depth test has not run: do not claim receiver success.
Use checked publisher for shared checks; inspect current-head CI after push.

One private fixed origin rebases both original captures and source clock/replies
to elapsed test intervals; it never stamps a frame with callback time. Guard media
vs ContinuousClock elapsed discrepancy, backward time, future/pre-start/stale
captures. This is bench-only and runtime observation, not documented general clock
identity, a live relative drift budget or actual sleep acceptance. Review of Apple
35F9.1 elapsed-in-app-event exception supports this approach; normal app manifest
unchanged. Source: https://developer.apple.com/documentation/bundleresources/app-privacy-configuration/nsprivacyaccessedapitypes/nsprivacyaccessedapitype

Phone requires actual newly processed sensor frames before local producer ready,
requests forty sends each side of pause/reconnect, and checks no pending depth or
new sends during suspension. Pi checks per-type sequence and increasing capture
across connections, separates source/arrival rates, and correlates bounded clock
probes. Diagnostics before a ready heartbeat never establish eligibility. No clock
map or guessed/zero drift is supplied. Age stays unknown; no camera/GPIO on Pi.

Human confirmed backend ready. Next: user fetches published harness on dedicated
Pi worktree, starts observer with fresh reserved phone IDs, reports actual process
Pi IDs; backend operator issues matching role files privately. USB-install the
phone-only file, run only real-depth test, record separate receiver counters, revoke
and clean up. No automated Pi SSH. Actual delay/backlog, sleep/lock, joint drift,
remote freshness and physical hardware acceptance remain open. Keep draft/blocked.
