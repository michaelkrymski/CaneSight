# CS-016 transfer proposal and implementation handoff

Base: dddbd4be0ba06a78a6f43b2806d2656d7b9abb03. Branch: claim/CS-016-transfer-michaelkrymski.
Current accepted owner is bondmila. GitHub #64 contains her explicit release/
transfer request; she reports work stopped at 0433fc94af1a1e3edfe2d2bb28925cb3be6df1ee.
Michael requested continuing the task on the connected LiDAR iPhone/Xcode host.

This checkpoint proposes only a guarded runtime ownership transfer. It adds the
CR, task runtime evidence/blocker, this handoff, append-only changelog and rendered
log. No implementation is changed before reassignment is accepted. Existing
acceptance, dependencies and allowed paths are unchanged. Repository checks and
read-only existing-package verification are reported in the PR, not prefilled.

The existing package already supplies latest-only 10 Hz depth, original capture
age, role-bound WSS, identity/sequence validation, clock probes, watchdogs and
reconnect without old queue replay. The existing host #69 now has local camera,
status, speech and GPS but does not instantiate/enroll live telemetry.

After reviewed transfer: preserve #64 source history in a new PM-authored
continuation (GitHub cannot change its original author; owner enforcement would
otherwise reject it), link replacement before closing the superseded draft,
integrate current accepted modules, establish conservative capture/source-clock
binding, audit boot-time privacy reasons for off-device timestamps, enroll real
phone/Pi identities, and test native WSS rate/age/backpressure/background/reconnect.
Physical Pi drift/clock/motor evidence cannot be inferred from a phone UI test.
No secret, private image, signing identity or precise GPS trace is included.

## Verification actually run

195 current repository unit tests passed; structure, rendered-log and whitespace
checks passed. Existing unmodified telemetry at 0433fc94af1a1e3edfe2d2bb28925cb3be6df1ee:
21 strict-concurrency/warnings-as-errors Swift tests passed; four generated replay
wire-to-current-accepted-backend/schema tests passed; unsigned physical-iOS SDK
package build passed with Xcode 27.1. No new implementation or phone/Pi acceptance
is inferred. Temp verification used a Git archive outside tracked source.

The documented HTTPS origin https://64.177.50.116/healthz timed out after 8 seconds
from this Mac with normal TLS verification. This is a failed reachability probe,
not proof that the service is down elsewhere. Confirm its current reachable route
before live native WSS pairing. No credentials were used in that health request.

Routine publish_task deliberately refuses guarded ownership amendments; this
transfer uses the explicit reviewed-CR route with the same structure/unit/log/
whitespace checks, normal task-branch commit/push and no force/main push or merge.
Local governance inspection must report approval required; server governance is
expected to wait/fail until Michael's exact-head GitHub authorization exists.
