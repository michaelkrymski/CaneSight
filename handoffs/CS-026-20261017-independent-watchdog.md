# CS-026 independent policy watchdog and restart checkpoint

Task: CS-026. Branch: task/CS-026-independent-watchdog.
Base: 429ce276f5a366a1a4e7aa2eb7932d8cb92ea7a6 (merged assignment #40).
Before publishing, also merged current main 3f33063 (CS-039 assignment only)
without conflicts; no teammate ownership changes.
No Raspberry Pi connection, physical camera access or deployed service change.

## Changed files

- edge/watchdog.py: separate supervisor with 200ms default completed-policy lease,
  10ms checks, same monotonic clock, sticky expiry/clock failure, local stop callback
  outside its lock, bounded start/close and credential/camera-free simulation demo.
- edge/haptics.py: optional one-time local guard before arming, admission-time
  lease clipping and independent tick validation, sticky watchdog trip/off requests.
  No guard means existing scheduler behavior is preserved; no remote actuation API.
- edge/policy.py: only successful completed policy ticks feed the optional watchdog;
  sensor health remains separate from worker liveness. Clock callable must match.
- edge/uploader.py: automatic watchdog for --simulate-policy, cleanup on startup
  failure/termination, and SIGTERM enters normal CLI cleanup. New processes retain
  existing fresh boot/enrollment requirement; no token/session restoration logic.
- edge/WATCHDOG.md, edge/README.md and uninstalled
  edge/systemd/canesight-simulation.service.example: restart limits, private file
  creation, graceful stop timeout, manual fresh 600s enrollment procedure and limits.
- tests/edge/test_watchdog.py: lease, real blocked policy lock, callback lock order,
  failure/cleanup, subprocess restart/abrupt death and Linux SIGTERM synthetic camera.
- Own task runtime, new immutable fragment and this handoff. Protected files,
  baseline, shared contracts, credentials and actual service files unchanged.

## Tests actually run

- Linux Python 3.12: all 83 edge cases passed, including SIGTERM synthetic-camera
  cleanup. Windows Python 3.14: 82 passed and one POSIX SIGTERM case skipped.
- Linux shared/dashboard discovery: all 59 passed. Checked publishing runs current
  repository/shared/changelog/whitespace validation; current PR head CI inspected.
- Demo on Windows/Linux: initial outputs false/readiness false; after stopped feeds
  outputs false and sticky fault. gpio_used=false, credentials_loaded=false.
  Local diagnostic epochs differ across subprocess starts; no state/pulse queue is
  restored. Abrupt subprocess exit is observed, but old physical output off is NOT
  asserted. No actual hardware exists in these tests.
- Original lease clips a requested pulse even after later feeds. Late feed and
  admission after expiry fail. Reversed/nonfinite clocks fault. Actual policy lock
  can remain blocked while supervisor/scheduler stop simulated outputs independently.
  Camera-start failure closes real policy/watchdog/scheduler; credentials suppressed.
- Linux ran in a separate Vultr source directory with existing pinned test runtime;
  no backend production container/environment was changed. No Pi SSH runner retried.

## Remaining limits and next steps

Software ready for Michael review, not Done. Review lease tuning and example unit
paths before any installation. No service installed/enabled. Actual Pi restart,
physical startup/crash/kill/off behavior and electrical acceptance remain pending.
A restart generates a new uploader boot, waits at most 300s for matching fresh
Pi-only enrollment, and cannot reuse the old credential. Coordinate camera
availability and manual 600s enrollment/private mode-0600 transfer before testing.

Python threads cannot force a frozen GPIO-high process or blocked adapter low.
Supervisor still needs the scheduler lock; GIL/OS stalls and abrupt death/power loss
can prevent cleanup. Keep physical kill, verified passive startup and separately
engineered hardware timeout as required. Restart=on-failure handles process exits,
not a camera call stuck forever or systemd WatchdogSec. No hard-real-time,
phone/calibration, GPIO, electrical, motor, all-clear or crossing claim is made.
