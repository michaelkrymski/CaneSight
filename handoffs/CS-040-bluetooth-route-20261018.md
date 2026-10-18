# CS-040 automatic Bluetooth route monitoring software checkpoint

Owner: bondmila. Branch: task/CS-040-bluetooth-route.
Base accepted main: 20d69c9f43a3a19a3aa102ca04933f9d0e379284.
Previous CS-040 PR #77 and uploader PR #78 are merged; task ownership retained.

## Changes

- backend/context/bluetooth_route.py: matching explicit bluez_output/device target,
  read-only bounded pactl sinks/active sink-inputs and BlueZ Connected queries.
  Requires exactly one matching unmuted/nonzero-volume BlueZ sink; RUNNING/IDLE/
  SUSPENDED supported. Unique owned stream tag verifies destination. Missing
  registration/completion has 200ms grace; move/duplicate binding is unavailable.
- Monitor polls after 100ms waits, timestamps observations at query start and
  independently expires at 350ms with a 10ms watchdog. Errors, stale/blocked
  observations and invalid/reversed clock latch. Callback runs outside state
  lock, stops only owned speech and never automatically recovers/replays.
- Helpers are no-shell owned process groups, 100ms read/exit budget, 64KiB stdout
  cap, no stderr capture and bounded kill/reap. Probe never holds monitor lock.
- backend/context/pi_speech.py: explicit constructor settings or paired private
  CANESIGHT_BLUETOOTH_SINK/CANESIGHT_BLUEZ_DEVICE settings enable Linux monitoring.
  Missing/partial config and startup query failure refuse audio. Unconfigured
  behavior retained. eSpeak WAV stdout pipes to an explicitly targeted owned
  paplay process with unique stream name; playback stops before generation.
  Existing channel/controller health gates cancel pending request/ticket and
  prohibit late speech through the latched sink. No edge source/scope changes.
- backend/context/README.md: setup, diagnostic, timing/resource bounds, fresh-run
  recovery and separation from old same-sink operator recovery bench.
- tests/context/test_bluetooth_route.py: seventeen new cases, including spawned
  real helper timeout/overflow/failure and owned synthetic speech/player cleanup.
- Own runtime task evidence, new change fragment and rendered CHANGELOG.

## Tests actually run

Python 3.13/macOS: all 100 context tests passed, no skips; all 205 edge tests
passed, no skips. Probe tests inject synthetic pactl/BlueZ observations; helper
and audio lifecycle tests use real disposable processes without sound. Covers
mute/volume/missing/duplicate/unsupported target, moved/absent stream, exact cache
expiry, slow or blocked query, clock reversal/failure, callback reentrancy,
startup/close, paired configuration, sanitized diagnostic, both process-group
stops and pending provider cancellation/late-result rejection after reconnect.
Shared checked publisher runs root tests/repository/generated-log checks before
push. Exact-head CI and feedback are inspected after publishing.

## Limits and next steps

No SSH attempt, Pi, live BlueZ/PulseAudio/paplay test, real WAV decode/playback,
Bluetooth audible stop/reconnect, Gemini or phone/backend acceptance performed.
Configuration remains private; committed addresses are synthetic fixtures only.
This is an opt-in software checkpoint, not hardware readiness or task Done.

Run the read-only documented check on Pi as its normal audio user, then verify
monitored speech and actual audible tail/no replay in a controlled bench. Do not
use the old same-sink --bluetooth-recovery flow with latched monitoring; observed
loss requires a fresh adapter/run and explicit new input. Measure query latency/
CPU cost before relying on the initial timing targets. Polling can miss outages
between observations; software timings do not certify physical buffering.

No changes to pairing, profiles, global default routes, services, sudo, native
wire contracts, source/capture age budgets, motor GPIO or evaluated scenario
capabilities. Automatic setup/installation/deployment was not performed. Remaining
live-observation adapters and paired-provider freshness belong to separate work.

Before publication, accepted main advanced to dddbd4b (CS-018 merged).
Fast-forwarded accepted source while preserving owned edits, and regenerated
the disposable changelog. No implementation collision or protected edits.
