# CS-025 Swift-to-policy software integration

- Base: `94ccaaf14a88b990cc468433e55622b0b1e6681f`.
- Publication includes accepted main `e24279f` after Michael merged #72/#74;
  branch fast-forwarded with existing work preserved.
- Branch: `task/CS-025-swift-policy`; assigned owner unchanged from accepted main.
- Review dependency: CS-016 PR #64 at
  `0433fc94af1a1e3edfe2d2bb28925cb3be6df1ee`, exported unmodified by hash.

## Changed files

Only `tests/edge/test_swift_policy.py`, the fixture Swift project/generator/pins/
synthetic wire data/guide under `tests/edge/swift_policy_fixture/`, own task runtime
and new audit records. No production source, teammate package, protocol, plan or
workflow changes. Package code is materialized temporarily, not vendored.

## Tests actually run

Official Swift 6.0.3 Linux image by digest, network-disabled local Docker:
compiled the actual dependency package and fixture with complete strict
concurrency and warnings as errors; fixture ran and produced three synthetic
side scenarios preserving actual Swift wire bytes. Source/generator byte hashes
are recorded in the generated artifact and checked by the Python tests.

Windows Python: all seven focused tests passed. Actual role-bound backend relay,
consumer gate and local policy accept two fresh side/center observations and
request correct simulated channels; original capture deadline remains unchanged.
Limited tracking cancels an active simulated pulse; later health cannot restore
depth. Delayed, duplicate and foreign-boot packets cannot request another pulse.
Shared checked publishing runs root tests, governance/structure, generated log
and whitespace checks. Inspect current-head CI; default CI does not recompile
Swift or discover this separate edge test root.

## Limits and next steps

All inputs are synthetic replay. Offset +200ms and zero drift are explicit virtual
clock assumptions. No actual phone capture, calibrated device relation, native
WebSocket/actor runtime, network thread or physical receiver/output test. The
CS-017 synchronous invalidation hooks still need correct integration with actor-
isolated CS-016 transport methods; this fixture does not supply that host wiring.

Next: review this checkpoint and dependency #64, rerun on new dependency heads,
then integrate actual host/transport/clock/receiver and record controlled real-
phone left/center/right capture-age evidence after mount/power prerequisites.
Task remains blocked for full physical acceptance. No Pi, camera, SSH runner,
GPIO or motor used; no readiness, timing or crossing-permission claim.
