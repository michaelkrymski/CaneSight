# CS-027 GPIO21 input checkpoint — 2026-10-18

Branch task/CS-027-context-button; base 04ddfca87bbbb2a53539d30b1c3e17cc1c3ed3d1.
Accepted owner bondmila; existing draft PR #58, narration dependency draft #41.
User authorized continued CS-027/040 work and pointed to Michael-authored issue
#68. Read full handoff: GPIO21 active-high/no internal pull, previous camera
uploads and standalone speaker available; phone depth not ready. The local motor
bench package is unshared; no dependency on those unavailable files.

## Changes

- edge/context_gpio.py: lazy GPIO Zero input only on BCM21 using the reported
  DigitalInputDevice(21, pull_up=None, active_state=True, bounce_time=None).
  Read 0/1 only, sanitized errors, owned cleanup. Optional --observe CLI emits
  private raw edge/sample counts with no camera/audio/backend/context/motors.
- edge/context_runtime.py: initialize real level before timers, separate physical
  reader, preserve release-to-arm and 30ms debounce in the original sole controller.
  Input read failure withdraws consent; independent 100ms input-age gate cancels
  on a stalled reader. Audio uses the existing sole narration/button path.
- edge/uploader.py: --context-gpio21 mutually exclusive with --context-stdin;
  same mandatory phone/receiver/consent/simulated-policy gates. Closes input during
  teardown including camera startup failure. Does not configure motor pins.
- edge/context_report.py: input mode, requested versus actual/unknown GPIO use;
  motor_gpio_used false. Git revision lookup is lazy for report opt-in.
- Tests in tests/edge/test_context_gpio.py and test_context_runtime.py; current
  edge/CONTEXT_BUTTON.md corrects stale no-button language and documents commands.
  Own runtime fields, new immutable fragment, this handoff and generated changelog.

## Actual tests and limits

164 combined edge tests passed, no skips, Python 3.13, using external file-based
CS-040 module overlay. Final standalone discovery: 164 tests, 158 passed and six
explicit skips for the unmerged narration dependency. GPIO devices and speech are simulated; no local GPIO or
sound activation. Tests cover exact input-only configuration, bad values, startup
held release/repress, held no-repeat, second press cancellation of pending and
spoken output, stalled and failed input, startup read failure, CLI exclusivity,
cleanup after camera failure, and exact raw observer JSON flow with injected GPIO.
No dependency implementation copied into the CS-027 branch. Shared checks run by
checked publisher; existing CI does not run the separate edge root.

The optional GPIO21 adapter records installed wiring; protected master plan pin
proposal is unchanged. No motor source/driver integration, GPIO output activation,
owner takeover, assignment/static acceptance change, or automatic physical claim.
Raw input counts are not debounce/electrical acceptance or a successful context
request. Current camera/phone/session/backend and Bluetooth recovery evidence
remain required. Keep #41/58 draft. CS-018 controls and CS-023/025 motors retain
other owners. Next run the raw input observer on Pi, then the separate speaker
recovery bench; full enrolled path waits for real phone readiness.
