# CS-040 silent monitored playback diagnostics — 18 October 2026

Owner: bondmila. Branch: task/CS-040-bluetooth-route.
Starting accepted head: a7b0214dd0c28316b61449d72c81215753b94993.
Fast-forwarded accepted main 0925c3a (CS-015 device-background and CS-049 QA).
Original operator test build: f2a6dca6df87ffe1daf0a9f265590ca9ba6a393e.
PR #80 is merged; this is an in-scope follow-up, not another task takeover.

## Actual operator evidence

All four required Pi binaries were reported installed at their /usr/bin paths.
Private automatic route selection and RouteProbe observed a route in 63.7 ms,
without audio. Config/device identifiers remain on the Pi, outside Git/chat.
The supplied complete manual-only monitored speaker report has complete=true,
manual_cancel software_pass=false, operator_pass=false, stop_call_ms=0.065,
timer_fault=false, all software/operator pass summaries false. The operator
explicitly selected “No speech at all”. Duplicate report retained once.
A later isolated fixed “Description unavailable.” eSpeak-WAV/paplay diagnostic
was reported audible (“i do”); its process exit-status JSON was not supplied.
This narrows investigation but does not establish the root cause or a fix.

## Changes and rationale

- backend/context/bluetooth_route.py records fixed failure stages and the first
  latched monitor failure code. Diagnostic snapshots only read cached state;
  they do not run helpers/read clocks/callbacks or recover/rearm the monitor.
  Injected probe attributes/exceptions are filtered to a closed vocabulary.
- backend/context/pi_speech.py exposes cached closed sink failure codes, natural
  observed child exit codes and nested native monitor diagnostics. No IDs, stream
  tags, credentials, command output or raw exception text are serialized.
- backend/context/speaker_bench.py snapshots native diagnostics before cleanup;
  report failure cannot skip closing audio, change test results or imply a pass.
- README documents the real failure, scope of diagnostics and unchanged limits.
- Tests cover rejected moved streams vs query errors vs stale observations,
  cached reads that cannot probe/rearm/leak, diagnostic attributes that raise,
  actual generator failure after process cleanup and report-failure cleanup.
- Own runtime, new failure evidence/changelog/handoff and generated log only.
  No source/protocol/governance/crossing contracts, timing limits, routing settings,
  pairing, GPIO or other owners' task fields are changed.

## Validation and next step

Run context and edge suites in the pinned isolated Python 3.13 environment;
actual final results appended below. Shared checks run through the required
checked publisher. Real helpers/processes in host tests are disposable fixtures,
not Pi Bluetooth or physical audio evidence. No guard bypass or timeout increase.

Publish a draft diagnostic follow-up PR. Have the operator preserve the original
failure and run the same manual-only bench once with a new private output filename
on the exact diagnostic build. Read sink_diagnostics to identify the failed stage
before changing behavior. Speaker-loss/reconnect testing must wait for functioning
monitored playback. Keep task blocked and physical_audio_accepted=false; no road,
phone/backend/Gemini/model or motor evidence is claimed.

Final task-specific verification: 105 context tests and 205 edge tests passed
with no skips on Python 3.13/macOS using pinned backend test requirements.
Includes real disposable process cleanup tests, not actual audio output.
