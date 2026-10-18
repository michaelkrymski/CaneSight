# CS-016 native pair preparation

Task CS-016, owner Michael, branch task/CS-016-michaelkrymski, PR #89.
Phone-host checkpoint: 7119070e7cff9c1a1174f5e11c54b7014b85d9da.

Backend operator restored the existing public server. Mac health returned 200;
readiness 503 reported ingestion_configured false and model/worker healthy. Actual
iPhone default-OS HTTPS retry: one passed, zero skipped/failed. Earlier unreachable
evidence remains historical. No server deployment or credentials were changed here.

Add hosted native starting-heartbeat/reconnect test. It consumes/removes a USB-
delivered private phone-role JSON before creating one client in a fresh enrolled
process epoch. Peer metadata has no Pi token, no operator key is accepted, and
origin is restricted to the authorized HTTPS endpoint. Actual URLSession TLS and
Bearer-header authentication are retained. Clock measures elapsed time since
test start, never absolute uptime. Source remains starting; no ARKit sample or
depth packet is transmitted. Native completion is not receiver delivery.

The signed physical-iOS build-for-testing passed. This native authenticated test
has not run without fresh credentials: do not claim it passed. Do not include
credential data in launch arguments, environment variables, screenshots or logs.
See tests/ios/PHONE_PI_TRANSPORT.md for role-separated private file formats.

Michael confirmed an actual Pi, existing old CS-022 and PR32 checkouts, and a
password-based manual SSH preference. Old PR32 snapshot 17441ce only handles
vision and predates phone reception. Prepare a separate CS-016 review worktree;
do not modify those existing checkouts or retry the formerly rejected automated
SSH runner. No SSH to the Pi, camera, GPIO or hardware test was performed here.

Add tests/ios/pi_phone_transport_probe.py as a manual transport-only observer.
It creates fresh source/process boot IDs, waits for its own matching private
Pi-only six-field credential, then observes five identity/schema/sequence-checked
starting heartbeats. Sequence high-water survives same-process reconnect. Bound
connection attempts, receive time, frame size and queue; reject redirects and
use default TLS. Print counters only. No camera, policy, GPIO or clock mapping.
Five Python tests passed, including the actual observer loop across fake peer
disconnect/reconnect, cross-role/identity rejection and private-file controls.
They are software fixtures, not physical Pi or native network evidence.

Phone/Pi actual process IDs and credentials must be coordinated afresh; do not
use the earlier unconnected bench counterpart for the real Pi. Native phone and
Pi receive counters must be recorded separately. Revoke the pair after the run.
Task remains blocked for this run and subsequent real-depth clock/freshness gates;
no drift budget, sensor eligibility, haptic or electrical acceptance is inferred.
