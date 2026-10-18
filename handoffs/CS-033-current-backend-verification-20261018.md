# CS-033 current deployment verification

Owner: gmarcialcalleja. Branch: task/CS-033-backend-refresh.
Base and verified accepted source: a239e221b1d51d7673a78e8fb84e6df274b36e39.
Origin: https://64.177.50.116.

The human explicitly requested deploying the backend and ensuring it works.
SSH access via the existing local key and trusted host entry succeeded. Public
TLS was verified normally throughout. No key, operator credential, session
identity, private image or precise location was printed or copied into Git.

## Deployment and evidence

Uploaded only a git archive of accepted source to the new private host directory
/home/linuxuser/canesight-cs033-refresh-a239e22-20261018. Created a dedicated test
venv and built accepted Dockerfile.vision using the existing pinned runtime/cache.
Candidate image: sha256:07c9d75f045b1eee9c31fc549c9e6cacdd07db0ce951cb61f91845415408f94a.
The current active image remains
sha256:8a7bcf8fa9dbcfedea2ecef6d0e5e94d766dc50c2505739229454a0ad851f3fa.

Automatic approval review rejected the isolated candidate-container launch with
the message "blocked by policy" and no detailed reason. The rejected command did
not run; no candidate containers were started and no candidate was activated.
Read-only hashing then established all 13 packaged application/vision runtime
files plus all three contract files and readiness.py already exactly match the
accepted source. No production replacement or service restart was needed to
deliver that implementation. Existing secrets, public proxy/certificate volumes,
model mount and service configuration remain in place.

## Verification actually run

- Public /healthz: 200 with system certificate verification.
- Initial /readyz: 503 because ingestion_configured=false, while model_available
  and worker_healthy were true. This is expected with no enrolled session.
- Accepted vision_probe over public HTTPS/WSS with 20 generated 416x416 JPEGs:
  passed original lineage, role/Origin/query restrictions, cross-session/phone
  isolation, unknown pedestrian signal, revocation and credential expiry.
  Median upload-to-result 125.588 ms; nearest-rank p95 169.779 ms; max 185.610 ms.
- Separate public session_probe --expect-ready: passed enrollment/readiness 200,
  matched frame ACK, duplicate/expired credential rejection, peer interruption
  and reconnect replay rejection. Temporary probe sessions were revoked.
- Dedicated Linux Python 3.12 venv, python -m unittest discover -s tests/backend
  -q: 128 run, OK, 6 skips for optional image/runtime prerequisites.
- Source hash comparison: all packaged runtime, contract and readiness files
  match accepted main. Only boolean comparisons are recorded in evidence.

## Changed files and limits

New sanitized backend/deploy/evidence/CS-033-public-verification-20261018.json,
task runtime evidence, this new handoff/changelog fragment and rendered log.
No service source, protocol, governance, task requirements or dependencies change.
Normal checked publishing runs shared checks before commit/push.

These are generated replay tests with actual CPU model execution and public
transport, not physical phone/Pi capture, scene-recognition accuracy or motor
acceptance. The generic COCO detector does not supply a pedestrian-signal
classifier/countdown. Optional context/dashboard/logging features are not proven
by this native server factory/probe. Laptop fallback was not rehearsed again in
this session; prior accepted evidence remains unchanged. CS-033 remains Review,
not Done; Michael accepts completion. Live devices need their own fresh paired
sessions and must retain receiver-side original capture-age checks.
