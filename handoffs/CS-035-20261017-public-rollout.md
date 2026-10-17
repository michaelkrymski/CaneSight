# CS-035 public rollout — 2026-10-17

Base: 2af3150dfaeb0efa5ce37f26d66e552fe8147f15 (accepted PR #28).
Branch: task/CS-035-public-rollout.

## Changes
Built the accepted merged source archive on Vultr with Dockerfile.vision.
Promoted its immutable image with the opt-in Compose overlay and verified read-only
model artifact. Preserved the previous private deployment configuration for rollback.
Recreated only the backend; existing Caddy container and certificate volumes remain.
Repository changes contain sanitized QA reports, integration status, task runtime
evidence and a new changelog fragment. No credentials or images are included.

## Verification actually run
Public certificate-verified HTTPS/WSS vision_probe: 20 generated replay JPEGs,
original lineage, phone/other-session isolation, Origin/query/role rejection,
operator revocation and TTL expiry all passed. Median 127.358 ms, p95 169.14 ms,
max 198.5 ms. Probe pairs were revoked.
Docker inspection: running/healthy, read-only root, 2 GiB memory, 1.5 CPU.
Public health returned alive; readiness reported model and worker available with
an enrolled source. Availability does not establish observation freshness.
Repository checks are run by the checked publisher before commit.

## Private enrollment and limits
A fresh live Pi process was enrolled for 600 seconds using the existing private
operator credential and an explicitly unconnected bench phone counterpart.
Only the Pi credential was written to a private local JSON file with a user-only
ACL for the human's secure transfer. The phone credential was discarded.
No credential, session identifier, boot identifier or private file is recorded here.
Successful enrollment does not prove the uploader received the file or sent frames.

Next: obtain a credential-free uploader status/count from Michael; restart/re-enroll
if the 300-second process wait or session TTL elapsed. Preserve the Pi's ownership
and mode 600 on ~/.canesight-session.json. No real camera latency, detection accuracy,
phone connectivity, receiving-side freshness or motor readiness is established.
CS-041 browser projection/auth remains a separate reviewed boundary.
Michael retains review/acceptance; this task is not marked Done.
