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

## 2026-10-17 — CS-028-CLAIM-ADITSANGANI-20261017: Claim FastAPI skeleton and frame endpoint for Adit

Author: aditsangani · Task: CS-028

Propose aditsangani as CS-028 owner after the prior claim PR #3 closed unmerged. Implementation waits for Michael to merge this claim and coordinate the CS-003 dependency. Task requirements and scope are unchanged; no application or hardware completion is claimed.

Validation: Claim metadata only; repository validation, unit tests, generated changelog verification and whitespace checks are recorded in the claim PR after execution.

## 2026-10-17 — CS-033-CLAIM-20261017-GMARCIALCALLEJA: Propose Gavin's ownership of Vultr backend deployment

Author: Gavin (gmarcialcalleja) · Task: CS-033

Claim CS-033 for gmarcialcalleja with status in_progress on claim/CS-033-gmarcialcalleja. Implementation waits for Michael to merge this claim and remains dependent on CS-029 and CS-032. Task requirements, master plan and other tasks are unchanged; no deployment or hardware acceptance is claimed.

Validation: Claim-only metadata change; repository check results are recorded in the claim PR. No Vultr, HTTPS/WSS, secret configuration, laptop fallback or hardware tests performed.

## 2026-10-17 — CS-033-DEPLOYMENT-PREPARATION-20261017-GMARCIALCALLEJA: Prepare Vultr deployment configuration and TLS/authentication probes

Author: Gavin (gmarcialcalleja) · Task: CS-033

Add Compose/Caddy deployment templates with private backend networking, digest-pinned input requirements, non-root read-only backend, bounded logs, readiness gating, server-only raw environment configuration, a safe input validator, TLS/authentication handshake smoke probes and a setup/rollback/fallback runbook. Mark CS-033 blocked pending infrastructure and CS-029/032 integration; no live deployment or acceptance is claimed.

Validation: Local Python 3.14.7: 32 unit tests discovered, 31 passed and one Linux permissions test skipped on Windows. Includes temporary HTTPS/WSS fixtures and Docker Compose configuration validation without an engine. Repository validation, changelog verification and whitespace checks passed. Docker engine/Caddy startup, Vultr deployment, actual backend authentication/secret validity, laptop fallback and hardware were not tested.

## 2026-10-17 — CS-033-HOST-PREPARED-20261017-GMARCIALCALLEJA: Prepare the actual CPU host and verify Caddy on loopback

Author: Gavin (gmarcialcalleja) · Task: CS-033

Confirm the deployed host is Ubuntu 24.04 with two vCPUs, 4 GB RAM and 128 GB disk, without an NVIDIA GPU. Install Docker Engine and Compose from the official repository using an in-scope preparation script. Add an opt-in real Caddy TLS/WebSocket integration test and record successful host results. Public application exposure remains blocked on DNS and accepted backend/auth/rate-limit integration.

Validation: Actual Vultr host: all 56 tests passed with Docker Engine 29.9.1, Compose 5.6.0 and digest-pinned Caddy 2.11.7; production Caddyfile validation passed. Windows: 56 discovered, 54 passed, two platform/opt-in tests skipped. Repository structure, generated changelog and whitespace checks passed. Only SSH remains publicly listening. No live application, public certificate, YOLO, Gemini, Tiger Data, laptop fallback or hardware acceptance claimed.

