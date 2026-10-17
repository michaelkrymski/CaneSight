# CS-044 N01–N05 software failure campaign

Run from the reviewed checkout using `backend/requirements-test.txt` and Python
3.12+ (test suite also checked on Windows Python 3.14):

```sh
python -m qa.failure_suite --output /PRIVATE/new-cs044-report.json
python -m unittest discover -s tests/failures -v
```

Create a private parent directory first. The report must be new and outside the
checkout; Linux creation mode is 0600. On Windows verify a user-only parent ACL.
The runner does not connect to any Pi, public backend, camera, GPIO, production
model or external inference provider. Native tests use temporary local trusted
TLS certificates and synthetic observations/model adapters. Spawned inference
processes are test fixtures, not hardware daemons.

The fixed campaign runs 25 named cases, including five new multi-stage fault
campaigns plus accepted gate/transport/worker/watchdog tests. No remote input
selects commands or imports. Missing tests/imports, errors, failures, skips and
source changes during the run prevent `all_software_passed=true`. Fast campaign
and report tests are discoverable by existing shared CI; the 25-case native/flood
campaign is run explicitly. No protected workflow changes are required.

| Gate | Injection and software assertion |
|---|---|
| N01 | Interrupt the source, retire its boot and test recovery; stop packets without callbacks; exercise actual local TLS/WSS idle expiry/revocation and explicit phone interruption. Old depth expires independently of transport and requires fresh bounded recovery. |
| N02 | Submit an old captured packet repeatedly with increasing sequences and healthy heartbeats; verify no new pulse. Check independent depth/vision deadlines and resynchronization that cannot extend old observations. |
| N03 | Duplicate, reorder, wrong mode/session/source/boot and future timestamps; unknown drift/clock uncertainty, nonce reuse and authorized epoch replacement. Wire packets cannot enroll themselves or revive expired evidence. |
| N04 | Authenticated frame flood while spawned synthetic inference blocks; bounded latest work, quotas/heap checks and responding software watchdog. Block the actual policy lock; scheduler admission still checks its independent lease. |
| N05 | Invalid JSON/UTF-8/duplicate keys/NaN/permission fields, excessive bodies, malformed JPEG/dimension mismatch and cross-session/role misuse. Existing fresh evidence cannot be sustained beyond original expiry by malformed traffic. |

## Report interpretation

Each gate says **software_pass** or **software_fail**, with case IDs, outcomes,
counts and test execution duration. The N04 integration test may contribute only
allowlisted numeric scheduling/heap/flood metrics. Case elapsed time is not
capture-to-motor latency and is not a hard-real-time guarantee. Failure messages,
exception bodies, raw packets, credentials, JPEGs, GPS and private paths are not
serialized. No device enrollment or operator credential is read.

The report records HEAD plus a dirty-worktree flag, Python/platform and SHA-256
for tested runtime/protocol/test sources. A precommit run is explicitly dirty:
its HEAD alone does not identify the test changes. An exported source archive
without Git has null commit/dirty fields and git_metadata_available=false; it
never invents a commit or claims a clean tree. The source hash manifest
identifies those bytes; verify hashes against the intended checkout. Sources
must remain unchanged during a run. Sanitized Windows/Linux checkpoint reports
are committed in this directory; raw test payloads and actual device data are not.
Do not hand-edit report pass results or replace a failed run with guessed evidence.

## Physical limits and remaining work

`physical_acceptance` is always false. Tests use synthetic phone data, simulated
outputs, local socket teardown and virtual clocks where stated. They do not prove
real Wi-Fi timing, sensor/phone drift, motor off voltage, boot/frozen GPIO behavior,
thermal/current safety, actual physical onset or user cue distinguishability.
CS-025 real-phone/mount/power acceptance remains pending. Simulation results do
not waive CS-010/015/016 or final PM/hardware review.

Before a device repetition, coordinate camera availability with Michael, verify
phone/power prerequisites, identify exact commit and input/output mode, and use
fresh manually enrolled 600-second sessions with privately installed Pi-only
mode-0600 JSON. The previous rejected automated Pi SSH runner must not be retried.
No physical test or service installation is performed by this campaign.

For device N01–N05 evidence, record actual injected faults, original capture-age
bounds, observed outputs/failures and timing uncertainty. A physical kill and any
needed hardware timeout remain required: Python/GIL/OS stalls or a blocked driver
can prevent software cleanup. No test result implies crossing permission or
that absent detections establish a clear route.
