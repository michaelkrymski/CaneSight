# CS-025 live output preparation

Task: CS-025. Owner: gmarcialcalleja.
Branch: task/CS-025-live-output.
Accepted base: a239e221b1d51d7673a78e8fb84e6df274b36e39.

The human authorized preparing integration task by task while Michael completes
CS-016. Accepted main already assigns CS-025 to this owner. No open competing
CS-025 PR was found; no CS-016 or other teammate source was edited. Requirements,
dependencies and allowed paths are unchanged. The implementation uses the accepted
phone wire contract already supported by the native receiver.

## Changed files

- edge/uploader.py: explicit --gpio-policy alternative to simulation, distinct
  pins/active-high/binding/drift validation before enrollment or GPIO access,
  attach watchdog before worker startup, preserve consented context compatibility,
  stop each output component before audio/trace/network/camera cleanup and surface
  failed stop/release attempts. No GPIO option is enabled by default.
- edge/policy.py: explicit GPIO admission only for the actual CS-023 adapter,
  live phone binding, numeric drift and attached same-clock watchdog; trace/output
  mode consistency. Existing freshness/recovery/sequence rules are unchanged.
- edge/haptic_gpio.py: share pure pin/polarity validation with the CLI.
- edge/trace.py: validated simulation/gpio output-mode label, same bounded closed
  metadata records and private writer behavior.
- edge/POLICY.md, HAPTICS.md, BENCH.md: setup/ownership/limits and next device steps.
- tests/edge/test_gpio_policy.py: nine deterministic synthetic/fake-pin cases for
  channel mapping, original expiry, interruption/unknown/disconnect, watchdog,
  missing opt-in/drift, trace labels and actual uploader camera-failure cleanup.
- tests/edge/test_policy_transport.py: run both default simulation and real
  GPIOOutput with fake devices through actual TLS native relay/clock/depth.
- Task runtime fields, new handoff/changelog fragment and generated log.

## Verification actually run

python -m unittest discover -s tests/edge -p test_gpio_policy.py -v: 9 passed.
python -m unittest discover -s tests/edge -p test_policy_transport.py -v: 2 passed.
python -m unittest discover -s tests/edge -q: 230 run, OK, 8 platform skips.
Existing policy/watchdog/bench/context-runtime focused checks passed while developing.
python -m edge.uploader --help and git diff --check passed.
Checked publishing additionally runs structure/shared/log/whitespace checks.

TLS tests use generated certificates and synthetic protocol-compliant phone
messages, a zero-drift same-clock fixture and injected fake output pins. GPIO Zero
and actual Pi/camera/motors were not accessed. Real GPIO mode refuses replay gates
and null drift; the fixture's live session label does not establish real sensors.
Trace timestamps remain software commands, never measured motor onset.

## Integration and remaining acceptance

After review, preserve the six-field Pi-only session format. Enroll the current
Pi process and actual phone source/boot, configure the separate trusted phone
binding with a measured joint drift bound and verify the actual mount/channel
mapping. No phone/operator token belongs on the Pi. The receiver already probes
the phone and enforces original capture ages; CS-016 supplies that phone endpoint.
Start in --simulate-policy, then use documented --gpio-policy with actual reviewed
pins only after CS-009/010 and wiring/kill gates are accepted. Context can use the
same policy priority source without making vision/Gemini control motors.

No automatic launch, remote deployment, motor arming on reconnect, task completion,
physical voltage/current/thermal/motor test or real-phone acceptance is claimed.
CS-017 review and current CS-016 host/native transport remain separate work. A
frozen interpreter/GPIO/driver still needs the physical kill/passive off states.
