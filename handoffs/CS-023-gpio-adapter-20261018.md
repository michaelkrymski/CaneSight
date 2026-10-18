# CS-023 GPIO adapter checkpoint

Task: CS-023. Owner: gmarcialcalleja.
Branch: task/CS-023-gpio-adapter.
Base: 0925c3af5d83d7ca86c091643f8e6fd5b5b7d5c9 (accepted main).

The human authorized implementing the adapter before CS-009 completion. The
accepted CS-023 owner is already gmarcialcalleja; no competing open CS-023 PR was
found. Preserve static acceptance/dependencies/allowed_paths and the protected
baseline. This is software implementation ahead of physical acceptance, not a
claim that CS-009 passed or that actual motor operation has been authorized here.

## Changed files

- edge/haptic_gpio.py: explicit active-high two-channel GPIO Zero adapter, lazy
  hardware import, pin validation (BCM21 reserved), initial-off construction,
  partial-start cleanup, sticky write faults, independent off/release attempts,
  context ownership and bounded opt-in bench CLI with SIGTERM/interrupt cleanup.
- edge/haptics.py: retain simulated defaults; report actual configured output
  mode and GPIO use instead of labeling every custom output simulation.
- edge/HAPTICS.md: adapter/bench usage, cleanup ownership, dependency and limits.
- tests/edge/test_haptic_gpio.py: 15 fake-device cases including partial startup,
  interruption, independent channels, expiry/lease bounds, peer write failure,
  unknown off failures, cleanup faults, invalid CLI opt-in and sanitized errors.
- tasks/CS-023.json: runtime checkpoint/evidence/branch only.
- New append-only changes fragment, this handoff, generated CHANGELOG.md.

## Verification actually run

- python -m unittest discover -s tests/edge -p test_haptic_gpio.py -v: 15 passed.
- python -m unittest discover -s tests/edge -p test_haptics.py -v: 28 passed.
- python -m unittest discover -s tests/edge -v: 220 run, OK, 8 platform skips.
- python -m edge.haptics --simulate: two accepted simulated pulses, both off,
  closed, no fault and gpio_used=false.
- python -m edge.haptic_gpio --help: passed without loading/opening hardware.
- git diff --check: passed. Checked publishing additionally runs structure,
  shared tests, generated-log and staged whitespace checks before commit/push.

## Limits and next steps

No GPIO library was installed/loaded for these tests, and no actual Pi, GPIO,
motor, physical voltage/current/temperature, pulse onset or output-off state was
measured. GPIO Zero API semantics were checked against official documentation:
https://gpiozero.readthedocs.io/en/stable/api_output.html#digitaloutputdevice.
Explicit active-high-only behavior retains the task's requested LOW-off polarity.
Closing/releasing a pin does not certify it remains low; retain passive off-state
wiring, verified drivers, separate motor power, flyback diodes and physical kill.
Python cleanup cannot run on SIGKILL/power loss or force a frozen GPIO low.

CS-009 and its power/wiring prerequisites still need accepted measured evidence.
After review, choose actual pins and verify off-only before bounded pulses on a
controlled bench. The CS-024 policy still rejects nonsimulated outputs; the new
adapter is usable through HapticScheduler or its standalone bench, while live
phone-policy-to-output integration stays in CS-025. No automatic movement,
crossing permission, service installation or deployment was added.
