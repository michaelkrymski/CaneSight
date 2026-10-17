# CS-027 — primary-reader lock contention follow-up

Author: bondmila (AI-assisted), 2026-10-17.
Branch: task/CS-027-context-button.
Base commit: c1eee14ae4ce16b3b540e321b4aa7ab5bfe286ad.
PR: https://github.com/michaelkrymski/CaneSight/pull/55

Final inspection found that primary-source readiness could wait on a stalled
policy, freshness gate or watchdog lock. edge/context_runtime.py now acquires
these accepted RLocks nonblocking and treats contention as unavailable, releasing
all acquired locks. This preserves cancellation/expiry worker responsiveness.
The existing independent button deadline remains in force. Busy healthy workers
may conservatively suppress context; recovery still requires a fresh press.

Changed files: runtime, tests/edge/test_context_runtime.py, edge/CONTEXT_BUTTON.md,
own task runtime PR/evidence fields, new immutable change fragment and generated
CHANGELOG.md. Master/protocol/governance baseline untouched.

Tests actually run: all 132 tests under tests/edge passed on Python 3.13 using
/tmp/canesight-gemini-venv/bin/python. The added test holds each affected lock on
another thread and proves the reader returns unavailable without waiting, then
recovers after release. Checked publisher reruns repository validation, root tests,
generated changelog and governance/whitespace checks before commit/push.

No device, cloud, Gemini API, audio or electrical verification. Prior handoff
CS-027-manual-uploader-bondmila-20261017.md remains applicable. Task remains
blocked for actual-device acceptance. PR #41 stays draft. Independent PM review
required; no merge performed.
