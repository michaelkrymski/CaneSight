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

## 2026-10-17 — CS-029-CLAIM-ADITSANGANI-20261017: Claim paired authenticated WebSocket sessions for Adit

Author: aditsangani · Task: CS-029

Propose aditsangani as CS-029 owner. Preserve acceptance, dependency and allowed paths. Implementation waits for Michael to merge this claim and accept the CS-028 prerequisite, currently under review in PR #9. No WebSocket, pairing, TLS or credential implementation is claimed.

Validation: Claim metadata only; shared repository checks, generated changelog verification and scope validation run through the checked publishing helper. No application or hardware tests are claimed for this ownership change.

## 2026-10-17 — CS-032-ADMISSION-LIMITS-20261017-GMARCIALCALLEJA: Bound request/source admission and WebSocket message envelopes

Author: Gavin (gmarcialcalleja) · Task: CS-032

Add hard-capped monotonic token buckets, pre-body global/peer admission, authenticated Pi frame budgets, WebSocket connection/byte/depth/JSON guards and fixed rejection metrics. Preserve source timestamps, authentication ownership, schema/JPEG checks and unavailable readiness. Provide a reconnect-stable authenticated phone budget for CS-029 integration; keep full acceptance blocked on CS-029/031.

Validation: Windows and Linux: all 31 component and 39 shared tests passed, plus accepted replay smoke. New tests cover 10,000 rejected identities with bounded tables, 2,000 synthetic requests with scheduled software task, atomic bursts, exact refill, NaN/Infinity/overflow/duplicate/deep JSON, UTF-8 limits, socket cleanup and pre-body flood rejection. No physical watchdog, inference-load or real paired-session acceptance claimed.

## 2026-10-17 — CS-032-CLAIM-20261017-GMARCIALCALLEJA: Propose Gavin's ownership of backend validation and rate limits

Author: Gavin (gmarcialcalleja) · Task: CS-032

Claim CS-032 for gmarcialcalleja with status in_progress on claim/CS-032-gmarcialcalleja. Implementation waits for Michael's merged claim and coordinates with Adit's CS-029 and the CS-031 worker dependency. Requirements, master plan, other task records and prior fragments are unchanged; no rate-limit implementation or acceptance is claimed.

Validation: Claim metadata only. Shared/backend suites, repository validation, replay rehearsal and changelog/whitespace check results are recorded in the claim PR. No deployment, flood performance, inference, physical watchdog or hardware acceptance claimed.

## 2026-10-17 — CS-033-CLAIM-20261017-GMARCIALCALLEJA: Propose Gavin's ownership of Vultr backend deployment

Author: Gavin (gmarcialcalleja) · Task: CS-033

Claim CS-033 for gmarcialcalleja with status in_progress on claim/CS-033-gmarcialcalleja. Implementation waits for Michael to merge this claim and remains dependent on CS-029 and CS-032. Task requirements, master plan and other tasks are unchanged; no deployment or hardware acceptance is claimed.

Validation: Claim-only metadata change; repository check results are recorded in the claim PR. No Vultr, HTTPS/WSS, secret configuration, laptop fallback or hardware tests performed.

