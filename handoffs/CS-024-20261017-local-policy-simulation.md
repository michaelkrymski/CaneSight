# CS-024 local policy and source expiry — simulated-output checkpoint

Branch: task/CS-024-pi-receiver-expiry. Existing receiver head:
dd80e3fef028873c6bb05c845c31f3e61cecb1c0. Accepted main merged normally:
78dc1e2ac8558078e7ecf72187401c2f951b654c (includes accepted CS-023 scheduler).
Before publication, also merged main 8394b17 (accepted CS-041 dashboard and
CS-040 assignment) without conflicts. Checked publishing now discovers the
additional dashboard tests as part of 59 shared cases.
Isolated managed checkout used; CS-041 checkout and Michael's work preserved.

## Changes

- edge/policy.py: trusted closed PhoneBinding; same-clock final-consumer policy;
  independent 20ms worker; health separate from sector hazards; two distinct
  covered observations for recovery, 1.2m entry/1.5m exit hysteresis and 100ms
  simulated pulses. Center requests both channels; side cues denote obstacle
  evidence, never turn instructions. Each sequence can request once with its
  original depth expiry deadline. Missing/stale/tracking/coverage loss removes
  eligibility. Clock or scheduler faults latch unavailable; close requests off.
- edge/receiver.py: optional explicit phone source/boot/drift enrollment; native
  bounded clock probes, depth/heartbeat/clock-reply admission using accepted
  CaptureAgeGate. Unknown drift stays unavailable. Pi-only enrollment defaults
  unchanged; no phone/operator tokens transferred or wire-driven identities.
  Existing verified TLS/no-redirect/bounded buffering and vision lineage retained.
- edge/uploader.py: --simulate-policy opt-in creates only SimulatedOutput;
  --phone-binding-file is a distinct trusted control-plane file, with no tokens.
  Independent policy and scheduler start/stop with the receiver process. Cleanup
  disarms/requests off before camera shutdown. Sanitized simulation/depth summaries.
- edge/POLICY.md and edge/README.md: usage, trusted binding, measured drift gate,
  simulation tuning, physical and independent-watchdog limitations.
- tests/edge/test_policy.py and test_policy_transport.py: deterministic final
  consumer cases plus real certificate-verified native phone relay simulation.
- Own task runtime, new immutable changelog fragment and this handoff only.
  No protected paths, backend, shared protocols, deployment or task scope changed.

## Validation actually run

- 71 edge tests passed on Windows Python 3.14 and Linux Python 3.12.
- 41 shared/governance tests passed on both platforms.
- Synthetic verified HTTPS/WSS test: operator-created session, explicitly enrolled
  simulated phone, native clock exchange, ready heartbeat, two fresh depth frames,
  matching simulated left pulse, then depth-unavailable heartbeat cancels it.
  Distinct real native roles use private ephemeral synthetic credentials; no logs
  print them or images. This is not a real iPhone or a real sensor/drift claim.
- Deterministic tests: original capture deadline clips pulse; healthy heartbeats
  cannot renew depth or trigger/retrigger; center/right mapping; unknown coverage
  and tracking interruption; expiry gaps and recovery; hysteresis without clear
  verdict; wrong identity/mode/future/stale rejection; clock and motor faults;
  disarm/cleanup and worker expiry while caller blocks. Scheduler cooldown/duty
  remains enforced by accepted CS-023 tests.
- Full edge suite retains previous TLS vision/uploader and scheduler regressions.
  Linux runs in a new isolated Vultr source directory using pinned test environment;
  no production backend service or environment changed.
- Shared repository/changelog/whitespace checks run through checked publishing;
  current-head GitHub checks inspected after push. Protected CI unchanged and
  does not discover tests/edge automatically; edge tests were run explicitly.

## Remaining limits and next steps

Software checkpoint for review, not Done. Review new policy/binding configuration
and simulation tuning. Numeric drift requires Michael's measured phone/Pi clock
budget; null stays unavailable and zero is only a synthetic same-clock test value.
Real phone app/session/clock exchange and new-commit Pi policy execution remain
unverified. Earlier 20/20 real Pi vision test applies only to exact snapshot
17441cee512bb29ae6ad5bd327706a45c0a8f107; no new phone connection is claimed.
Coordinate camera availability and manual 600s session/private Pi-only JSON
transfer before a hardware test. The rejected SSH runner was not retried.

No GPIO/physical output adapter shipped. CS-009 power/driver/current/thermal/kill
verification and physical mount/channel mapping are required before actuation.
Unavailable is explicit status rather than an unvalidated motor pattern. Silence
never means clear. Policy/scheduler threads do not establish hard real-time or
CS-026 watchdog/restart acceptance, and cannot force frozen GPIO low. Michael
owns review/merge and physical acceptance. Credentials and private images stay
outside Git.
