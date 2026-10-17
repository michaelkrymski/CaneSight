# CaneSight master changelog

Generated from append-only `changes/*.json`; do not edit by hand.

## 2026-10-17 — BOOTSTRAP-20261017: Establish team coordination and protected baseline

Author: michaelkrymski (AI-assisted setup) · Task: TEAM-SETUP

Preserve master plan v1.1, map 58 existing Trello cards, add ownership/scope rules, immutable change fragments, handoff/PR templates, trusted-base governance and opt-in Trello progress sync. Teammates remain unassigned. No app/hardware acceptance is claimed.

Validation: Repository validation, governance/sync unit tests and offline Trello dry run; live auth, branch protection and workflow execution are verified separately in setup status.

## 2026-10-17 — CS-001-CHECKED-PUBLISHING-20261017: Prepare automatic checked publishing for active teammate sessions

Author: michaelkrymski (AI-assisted) · Task: CS-001

Add explicit-file task publishing, current-head CI/comment reader and teammate instructions; correct cross-platform changelog ordering without rewriting historical fragments. Shared amendment requires exact-head PM authorization and review. No remote agent wakeup, automatic merge, master-plan edit, ownership change or Trello activation.

Validation: 21 unit/integration tests including isolated local bare-repository push and failed-check/unrelated-file rejection; structural validation, generated changelog check and whitespace check. Live GitHub CI verified separately on the amendment PR. No hardware or app acceptance claimed.

## 2026-10-17 — CS-001-PUBLISHING-RETRY-FIX-20261017: Allow checked-publishing retry after failed validation

Author: michaelkrymski (AI-assisted) · Task: CS-001

Recognize the generated staged CHANGELOG.md on retry and regenerate it before validation. Other unrelated staged and working files remain rejected. Integrate accepted main and preserve Gavin's CS-033 ownership claim and immutable fragment; resolve the generated log conflict by rendering all fragments. No main push, automatic merge or protection change.

Validation: 21 tests including regression coverage that failed before the fix and passes without resetting the staged files; verifies unrelated staged/working files remain blocked and only the task branch is pushed in isolated local repositories. Repository structure, rendered changelog and whitespace checks pass; current-head GitHub CI reported separately.

## 2026-10-17 — CS-003-PROTOCOL-V1-20261017: Propose shared core observation and freshness protocol v1

Author: michaelkrymski (AI-assisted) · Task: CS-003

Add closed versioned message schema, six replay fixtures, reference validation/clock/identity/lineage checks and normative transport/freshness agreement. Assign Michael as CS-003 owner with status review pending protected-contract acceptance. Preserve the master plan, capture-age budgets and no-crossing-permission invariant; install declared test dependency in CI. No live hardware, authentication service or deployment implementation is claimed.

Validation: 34 repository/contract tests pass, including duplicate/order/epoch/session/mode handling, unknown fields, nonfinite and oversize input, clock bounds, frame lineage and heartbeat-independent expiry. Structural validation, generated log and whitespace checks pass. Current-head GitHub CI is verified separately; PM/collaborator acceptance remains required.

## 2026-10-17 — CS-021-CS-022-MICHAEL-CLAIM-20261017: Assign Pi capture and latest-only uploader work to Michael

Author: michaelkrymski (AI-assisted) · Task: CS-021, CS-022

PM assignment proposes Michael as owner of CS-021 (Picamera2/in-memory CSI validation) and CS-022 (latest-only 416-square quality-75 JPEG upload at 1 Hz). Both were unclaimed. User reports successful SSH and IMX708 wide NoIR still capture; full acceptance is not claimed. Preserve scope/dependencies and all other owners. Separate task implementation branches follow accepted assignment.

Validation: Task structural checks, generated changelog check, scoped assignment guard and whitespace check. Shared/backend CI runs separately. No Picamera2 in-memory loop, uploader, hardware safety or live backend integration acceptance is claimed by this metadata assignment.

## 2026-10-17 — CS-022-LATEST-UPLOAD-20261017: Implement bounded latest-only Pi JPEG upload for review

Author: michaelkrymski (AI-assisted) · Task: CS-022

Add nominal 1Hz 416-square quality75 in-memory capture, conservative original sensor timing, reversible letterbox mapping, one-slot replacement queue, two-entry lineage ledger and verified-HTTPS multipart sender. Reject stale/future pending frames and stop on authentication/order/ACK errors. Document capture-only Pi verification and short-lived live session enrollment without operator credentials on the device.

Validation: 13 local edge tests pass, including blocked-sender replacement, no retry, timing rejection, ACK/epoch identity and actual backend multipart ingestion with synthetic JPEG. No execution of this new module on Pi, live HTTPS upload, WSS, inference, electrical or readiness acceptance. Existing CI does not discover edge test root; explicit execution required.

## 2026-10-17 — CS-028-CLAIM-ADITSANGANI-20261017: Claim FastAPI skeleton and frame endpoint for Adit

Author: aditsangani · Task: CS-028

Propose aditsangani as CS-028 owner after the prior claim PR #3 closed unmerged. Implementation waits for Michael to merge this claim and coordinate the CS-003 dependency. Task requirements and scope are unchanged; no application or hardware completion is claimed.

Validation: Claim metadata only; repository validation, unit tests, generated changelog verification and whitespace checks are recorded in the claim PR after execution.

## 2026-10-17 — CS-028-FASTAPI-INGESTION-20261017: Add bounded FastAPI frame ingestion and software replay rehearsal

Author: aditsangani · Task: CS-028

Separate liveness from enrollment/model/worker readiness; validate authenticated multipart metadata and actual JPEG bytes/dimensions against the accepted v1 contract; retain original capture lineage with bounded memory and atomic replay guards. Add an explicit loopback-only synthetic replay demonstration. Session issuance, inference, TLS deployment and device verification remain separate tasks. Ready for PM review, not Done.

Validation: 19 backend tests and 39 shared repository/contract tests passed locally on Python 3.14.3. Real loopback HTTP replay returned health 200, readiness 503, upload 202 and duplicate 409. Backend suite runs explicitly per backend/README.md; existing shared CI does not install backend dependencies. No hardware or inference verification.

## 2026-10-17 — CS-028-VERIFIED-CI-20261017: Verify implemented frame ingestion and include it in required CI

Author: michaelkrymski (AI-assisted verification of Adit's implementation) · Task: CS-028

Preserve Adit's endpoint implementation and ownership; regenerate the combined log, explicitly run backend and shared test roots in required CI, install backend CI dependencies and run the real loopback replay rehearsal. Document accepted-app seams for CS-029 and deployment packaging for CS-033. Protected CI amendment awaits review; no auth/WSS, inference or live deployment acceptance claimed.

Validation: 58 total tests (19 backend and 39 shared) and real local HTTP replay: health 200, readiness 503, upload 202 with original frame ID, repeated upload 409. Structure, rendered log and whitespace checks pass. Current-head GitHub CI verified separately; no real device, TLS or cloud tests.

## 2026-10-17 — CS-029-CHANGELOG-REPAIR-20261017: Regenerate changelog after resolving PR14 main integration

Author: michaelkrymski (AI-assisted) · Task: CS-029

Repair generated CHANGELOG.md formatting after the browser conflict resolution omitted a blank line before the accepted CS-030 claim entry. Preserve all immutable fragments and all implementation code; record the correction in its own fragment and handoff.

Validation: Original head 00b1ed6 reproduces render_changelog.py --check failure. Regenerated output is verified by structure, rendered log, shared/governance tests and whitespace checks before publication. Runtime code is unchanged from reviewed head 83e1bfb; no new hardware acceptance.

## 2026-10-17 — CS-029-CLAIM-ADITSANGANI-20261017: Claim paired authenticated WebSocket sessions for Adit

Author: aditsangani · Task: CS-029

Propose aditsangani as CS-029 owner. Preserve acceptance, dependency and allowed paths. Implementation waits for Michael to merge this claim and accept the CS-028 prerequisite, currently under review in PR #9. No WebSocket, pairing, TLS or credential implementation is claimed.

Validation: Claim metadata only; shared repository checks, generated changelog verification and scope validation run through the checked publishing helper. No application or hardware tests are claimed for this ownership change.

## 2026-10-17 — CS-029-PAIRED-SESSIONS-20261017: Add paired authenticated HTTPS and WebSocket sessions

Author: aditsangani · Task: CS-029

Add an operator-authenticated session API, separate short-lived phone/Pi bearer credentials, bounded session-isolated WSS relays, explicit revocation/expiry and Pi-token frame upload integration. Require TLS schemes, reject URL credentials/browser origins, preserve original capture metadata and sequence state across reconnects. Add a certificate-verified loopback HTTPS/WSS test. No shared protocol, protected CI, task scope or baseline edits.

Validation: 35 backend tests passed locally, including real TLS pairing, invalid/missing credentials, isolated telemetry, generated JPEG upload, expiry, revocation, replay and bounded queues; legacy HTTP replay also passed. Shared repository checks run through checked publishing. No public deployment, hardware, device clocks, inference or capture-age eligibility claimed.

## 2026-10-17 — CS-029-RECONNECT-CLEANUP-20261017: Prevent stale socket cleanup from closing replacement peers

Author: aditsangani · Task: CS-029

Address Michael's PR #14 reconnect finding: an already-invalidated connection drains only its own queue during detach and does not invalidate replacement peers or clear their control state. Reject relay through detached connection objects, and immediately clear overloaded pairs' buffers/control state. Preserve sequence high-water marks and normal disconnect invalidation; add the exact ordering regression with successful fresh relay after reconnect.

Validation: Regression reproduced the original 1012 closure before the fix and passed afterward. 36 backend cases including real HTTPS/WSS and the legacy loopback replay passed locally. Shared repository tests, scope, rendered changelog and whitespace validation run through checked publishing. No device, hardware or public deployment acceptance claimed.

## 2026-10-17 — CS-030-CAPTURE-AGE-20261017: Bound consumer capture age with correlated clocks and original frame lineage

Author: aditsangani · Task: CS-030

Add a stateful final-consumer freshness gate and certificate-verified WSS client using the accepted protocol. Bound phone depth/heartbeat through one-time local clock exchanges and justified drift, and vision through the originating Pi's bounded capture ledger. Preserve original deadlines and sequence marks; invalidate unknown, expired, future, replayed or mismatched evidence. Heartbeat and clock resync never renew observations. Relay clocks, shared schemas and baseline budgets remain unchanged.

Validation: 57 backend tests passed locally, including 21 freshness cases and actual loopback WSS calibration, fresh-depth eligibility and stale rejection. Legacy HTTP replay passed. Shared repository/contract, scope, structure, rendered log and whitespace checks run through checked publishing. Test drift values are synthetic; no real phone/Pi drift, edge motor integration, electrical or deployed-service acceptance claimed.

## 2026-10-17 — CS-030-CLAIM-ADITSANGANI-20261017: Claim capture-age bounds and replay rejection for Adit

Author: aditsangani · Task: CS-030

Propose aditsangani as CS-030 owner to continue the backend lane. Acceptance, dependency and allowed paths remain unchanged. Implementation waits for Michael to merge this claim and accept CS-029 in PR #14. No freshness, clock synchronization or replay-policy implementation is claimed by this ownership change.

Validation: Claim metadata only. Checked publishing runs shared repository/contract tests, structure, ownership/scope, generated changelog and whitespace verification; actual results are recorded in the claim PR. No runtime or hardware acceptance claimed.

## 2026-10-17 — CS-031-BOUNDED-WORKER-20261017-GMARCIALCALLEJA: Isolate inference and bound latest work per source

Author: Gavin (gmarcialcalleja) · Task: CS-031

Add one spawned model process with a single load, one active job, latest-only pending work and bounded results per source. Preserve capture lineage, validate observations, expose fixed drop metrics and fail readiness closed on model failure or deadline. Integrate trusted frame admission and ASGI lifecycle without adding a public result API or selecting YOLO weights.

Validation: Windows and isolated Vultr Linux: all 30 backend and 39 shared tests passed; replay smoke preserved. Tests cover 2000-frame flood, bounded identity tables, one load, latest results, slow prediction with software task progress, failures, hung load/prediction, expiry/revocation and shutdown. Synthetic adapters only; no physical watchdog, live YOLO throughput or capture-age acceptance claimed.

## 2026-10-17 — CS-031-CLAIM-20261017-GMARCIALCALLEJA: Propose Gavin's ownership of the bounded inference worker

Author: Gavin (gmarcialcalleja) · Task: CS-031

Claim CS-031 for gmarcialcalleja with status in_progress. Implementation waits for Michael's merged assignment. Scope remains backend and backend tests; acceptance remains one model load, no event-loop blocking, per-source latest work and explicit drop metrics. Dependency CS-028 is accepted. No implementation or model performance is claimed.

Validation: Metadata-only claim; actual repository, shared/backend test and replay results are recorded in the claim PR. No inference, watchdog or hardware acceptance claimed.

## 2026-10-17 — CS-031-REVIEW-PROVENANCE-SESSIONS-20261017-GMARCIALCALLEJA: Protect original provenance and compose authenticated session-worker lifecycle

Author: Gavin (gmarcialcalleja) · Task: CS-031

Address Michael's PR19 feedback: give model adapters a separate deep copy and build observation provenance from an untouched original. Integrate accepted CS-029 while preserving TLS/auth/role enforcement, compose lifespans and bind atomic frame scheduling and session disposal to the same worker. Add mutation, paired success/isolation, revocation/new epoch and expiry-sweeper regressions.

Validation: Reproduced the old mutation failure in an isolated Linux checkout, then restored the fix. Windows and Vultr Linux each passed 51 backend and 39 shared tests plus replay smoke. Existing real certificate-verified HTTPS/WSS tests passed; combined worker tests use ASGI HTTPS scopes and synthetic models. No live YOLO, public deployment or physical watchdog acceptance claimed.

## 2026-10-17 — CS-032-CLAIM-20261017-GMARCIALCALLEJA: Propose Gavin's ownership of backend validation and rate limits

Author: Gavin (gmarcialcalleja) · Task: CS-032

Claim CS-032 for gmarcialcalleja with status in_progress on claim/CS-032-gmarcialcalleja. Implementation waits for Michael's merged claim and coordinates with Adit's CS-029 and the CS-031 worker dependency. Requirements, master plan, other task records and prior fragments are unchanged; no rate-limit implementation or acceptance is claimed.

Validation: Claim metadata only. Shared/backend suites, repository validation, replay rehearsal and changelog/whitespace check results are recorded in the claim PR. No deployment, flood performance, inference, physical watchdog or hardware acceptance claimed.

## 2026-10-17 — CS-033-CLAIM-20261017-GMARCIALCALLEJA: Propose Gavin's ownership of Vultr backend deployment

Author: Gavin (gmarcialcalleja) · Task: CS-033

Claim CS-033 for gmarcialcalleja with status in_progress on claim/CS-033-gmarcialcalleja. Implementation waits for Michael to merge this claim and remains dependent on CS-029 and CS-032. Task requirements, master plan and other tasks are unchanged; no deployment or hardware acceptance is claimed.

Validation: Claim-only metadata change; repository check results are recorded in the claim PR. No Vultr, HTTPS/WSS, secret configuration, laptop fallback or hardware tests performed.

## 2026-10-17 — CS-034-CLAIM-ADITSANGANI-20261017: Claim pinned YOLO baseline and class inspection for Adit

Author: aditsangani · Task: CS-034

Propose aditsangani as CS-034 owner. Preserve acceptance, dependency and allowed paths. CS-028 implementation is accepted; implementation waits for Michael to merge this claim. No model download, hash/class/license verification, inference or pedestrian-signal recognition is claimed by this ownership change.

Validation: Claim metadata only. Shared repository checks, generated changelog, scope/ownership and whitespace validation run through checked publishing; actual results are recorded in the claim PR. No application or hardware acceptance claimed.

