# CS-028 independent verification and CI completion

Task owner remains Adit (`aditsangani`). Implementation PR #9:
https://github.com/michaelkrymski/CaneSight/pull/9 . Reviewed starting head
7ec3529b920a745dc7dccf39b6e02b891b8c6e23, incorporating accepted main db952b3.

Michael requested confirming actual implementation and fixing remaining gaps.
Adit's source already implements distinct liveness/readiness and real bounded
frame ingestion with decoded JPEG checks, original lineage and replay rejection.
No backend rewrite was needed. Correct the generated changelog using its renderer;
preserve all fragments and existing handoffs.

Independently executed: all 19 backend endpoint tests and 39 shared tests (58
total) through their two explicit discovery roots. The real
loopback rehearsal uses a generated image/ephemeral token and observes health
200, readiness 503, upload 202 with original frame ID and duplicate 409. No token
or frame saved. Structural validation, rendered log and whitespace checks pass.
Current-head Linux/Python 3.12 CI is verified separately on the PR.

The protected CI amendment installs declared backend dependencies and explicitly
executes both test roots plus the HTTP rehearsal in required repository-checks. See
decisions/CR-CS-028-backend-ci.md. It requires current-head PM authorization;
the earlier green shared-only checks were not backend verification. TestClient's
httpx deprecation warning is non-failing; no unrelated dependency migration.
Adding tests/backend/__init__.py experimentally exposed a package-name collision
with the application backend; it was removed before publication. Explicit CI
discovery avoids that collision without changing shared test/governance modules.

For Adit: after accepted merge, pull main and implement CS-029 in a separate
task branch using the documented ingress/readiness seams. Ownership of CS-029
is accepted; paired-session/WSS implementation is still outstanding. Keep this
endpoint suite passing and replace fixed replay grants with proper lifecycle.

For Gavin: package backend.app:app with backend runtime requirements and shared
contract files, one worker on container port 8000. Default readiness remains 503
until actual enrollment/model/worker integration. Continue host/image/proxy prep;
CS-029 and CS-032 are still required for authenticated deployment acceptance.
No cloud changes, billable resources, model/worker, TLS/WSS or hardware tests ran.

Task is Review pending accepted merge, not falsely Done. No owners, static task
requirements or master plan changed. PM reviews/merges through existing rules.
