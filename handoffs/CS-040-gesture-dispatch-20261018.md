# CS-040 completed-gesture request and speech ownership

Owner: bondmila. Branch: task/CS-040-gesture-dispatch.
Base accepted main: d64dc5d0ca6cc8b4c5c16e12e48a1bc58de4ab66.

Changes: edge/buttons.py extracts the existing request admission into _dispatch
and adds request() for already debounced/released gestures; no second engine,
queue, cooldown reset, clock fabrication or capture renewal. Existing raw-level
sample remains unchanged. backend/context/consumer.py exposes that dispatch under
its existing lock/state gates. backend/context/speech_channels.py offers exactly
two local owners (context/menu); an idle owner cannot stop another owner's audio.
Replacement preempts, global stop interrupts both, failures latch, close prevents
late speech. It creates no process, route monitor or replay queue.

Tests actually run: 83 context tests passed on macOS/Python 3.13. Four new cases
cover completed-gesture single-slot/cooldown/capture expiry/priority/clock behavior
and speech replacement, owner-specific stops, global preemption and stop failure.
Existing narration, TLS/client and speech-process tests also pass in that suite.
No new real API/device/audio test. Shared checked publishing runs root tests,
repository/changelog validation before push; inspect current-head CI.

CS-027 follow-up consumes these APIs; it must remain unavailable if this dependency
is absent. No task acceptance/protected contracts changed. Full-task blockers
(route monitoring, evaluated scenario adapters and paired hardware integration)
remain. This is a software checkpoint for independent Michael review, not Done.

Review PR: https://github.com/michaelkrymski/CaneSight/pull/77.
Shared checked publication passed all 195 root tests and repository/log checks.
