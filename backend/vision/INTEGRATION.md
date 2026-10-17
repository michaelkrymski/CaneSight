# CS-035 result integration boundary

Adapter and bounded-worker result generation fit CS-035's allowed paths. Public
delivery and deployment require PM scope approval before editing the files below.
This proposal changes no shared message contract or source permissions.

## Available now

`InferenceWorker(YoloFactory(operator_controlled_weights_path))` loads the pinned
model in its spawned process. Existing validated ingestion can submit frames.
`worker.take_result(authenticated_pi_grant)` returns one schema-valid observation
internally, preserving original frame lineage and measured processing duration.
It supplies no capture-age verdict: the originating-Pi ledger and `CaptureAgeGate`
must enforce the complete capture-to-receipt budget.

COCO objects map to the accepted vocabulary and normalized boxes relative to the
uploaded image. Traffic-light boxes do not identify pedestrian heads. Signal is
unknown, candidate_count zero (no pedestrian-head detector), confidence/countdown
null. Empty detections establish neither clear space nor crossing permission.

## Proposed scope expansion for Michael's review

| File / area | Necessary integration | Required validation |
|---|---|---|
| `backend/server.py` | Explicit factory/worker configuration; preserve no-model default, without automatic downloads or synthetic health. | Missing/bad weights and runtime failures keep readiness unavailable; child loads once and stops on shutdown. |
| `backend/sessions.py` | Bounded server-generated results to the existing native Pi event socket, checking current authenticated session/boot/mode and socket identity. | Cross-session/phone isolation, expiry/revocation, disconnect/reconnect, superseded frames, late socket cleanup, slow consumers and shutdown. |
| `tests/backend/` | Extend existing HTTPS/WSS and session tests for the reviewed handoff. | Clients cannot publish vision or enroll from observations; preserve Origin/query/role/TLS and queue bounds. |
| `backend/deploy/` | Package reviewed runtime/adapter and verified operator-controlled weights in an immutable image or reviewed read-only mount. | Target-host CPU/memory and deadlines, actual authenticated result lineage, rollback and truthful readiness. |

Revalidate grant lifetime and current socket before delivery, discard work on
revocation/interruption, and preserve sequence state across reconnect. Do not
route model output through client publishing or manipulate session internals from
this adapter to evade task scope. Retain worker/result/queue bounds and avoid
replaying cached observations or creating an unbounded relay backlog.

Alternatives: accept the adapter separately and assign transport/deployment work,
or explicitly expand CS-035 scope through PM review. New unauthenticated endpoints,
weakened native browser-Origin checks and dashboard device credentials do not
resolve this boundary. Browser read-only authorization remains a separate reviewed
integration decision. Native result delivery does not prove phone/motor readiness.
