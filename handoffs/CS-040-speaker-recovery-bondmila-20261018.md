# CS-040 speaker recovery checkpoint — 2026-10-18

Branch task/CS-040-restricted-narration; prior head 0ac1230; synchronized base
81f6776ab34ed57c9d92e656ddf47003ee2057e0 includes accepted main 5dd5fa3. Accepted owner bondmila; PR #41 stays draft.
User reports Pi set up; detailed camera/phone/backend readiness has not been confirmed.

Changed backend/context/speaker_bench.py and README: opt-in guided Bluetooth
recovery, explicit operator loss -> unavailable/cancel, old ticket suppressed,
reconnect silence observation, then fresh ticket only on affirmative observations.
No automatic route detection/rerouting/volume change or hardware acceptance.
Consumer snapshot exposes request counters/closed/delivery state for CS-027's
allowlisted metadata report; no frames, grants or request identity included.
Tests changed in tests/context/test_speaker_bench.py and test_consumer.py.
Own runtime task, new immutable changelog fragment, handoff and generated log.
No protected files/shared contract changes.

Actually run: 71 context tests pass on Python 3.13, including silent executable,
recovery, unknown/no, interrupted observation and consumer request-count checks.
CS-027 combined overlay: 152 edge tests pass with these modules (no skips).
Publisher runs root validation/tests, governance, changelog and whitespace checks.
No audible output or hardware was used locally. Prior operator 15-case evidence
at combined 9607f76 is preserved and is distinct from this unrun recovery phase.

Next: publish both draft task heads, refresh combined test-only branch
codex/cs-040-027-speaker-bench, run the documented --bluetooth-recovery command
as the Pi audio user and return its private JSON report. PM reviews observations;
physical acceptance flags remain false. Need actual paired phone/camera/context
backend and accessible-controls evidence separately; never fabricate readiness.
