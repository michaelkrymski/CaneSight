# CS-035 result integration boundary

Michael approved and merged the narrow scope expansion in PR #29. Native result
delivery and opt-in runtime packaging are now implemented in PR #28, without
changing the shared message contract or granting browser access.

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

## Implemented boundaries under the approved scope

| File / area | Necessary integration | Required validation |
|---|---|---|
| `backend/server.py` | Absolute `CANESIGHT_VISION_WEIGHTS` opts into the verified factory; no-model default remains. | Real model over certificate-verified HTTPS/WSS, configuration rejection and existing readiness tests. |
| `backend/sessions.py` | Current Pi socket polls one worker result; latest-frame lineage and grant/socket identity are checked before and during bounded sending. | Cross-session/phone isolation, expiry/revocation, disconnect/reconnect, supersession, late cleanup, queue overflow and backpressure cancellation. |
| `tests/backend/` | Synthetic lifecycle tests plus actual configured-model TLS test with explicit pinned weights. | Native role/Origin/query restrictions, original metadata, isolation, shutdown and truthful availability. |
| `backend/deploy/` | Separate vision Dockerfile and opt-in Compose overlay, verified read-only weights and bounded writable settings. | Isolated Vultr candidate, 20 generated HTTPS/WSS results, restart, runtime/source provenance and resource constraints. |

Revalidate grant lifetime and current socket before delivery, discard work on
revocation/interruption, and preserve sequence state across reconnect. Do not
route model output through client publishing or manipulate session internals from
this adapter to evade task scope. Retain worker/result/queue bounds and avoid
replaying cached observations or creating an unbounded relay backlog.

There is no extra vision relay queue: at most one result remains in the worker
and one send is active. A slow send has a one-second deadline, with checks every
10 ms to cancel revoked, invalidated or superseded delivery. Bytes already sent
to the network cannot be recalled; receiving-side lineage and expiry still apply.
Pi admission and transport interruption discard older pending/result generations.

The candidate was validated on a private loopback TLS endpoint on Vultr. This is
not a promotion of the public deployment. Normal review/merge and the documented
rollout remain required. Browser read-only authorization is still separate;
native result delivery does not prove phone connectivity or motor readiness.
