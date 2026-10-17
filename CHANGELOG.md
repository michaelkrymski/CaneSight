# CaneSight master changelog

Generated from append-only `changes/*.json`; do not edit by hand.

## 2026-10-17 — BOOTSTRAP-20261017: Establish team coordination and protected baseline

Author: michaelkrymski (AI-assisted setup) · Task: TEAM-SETUP

Preserve master plan v1.1, map 58 existing Trello cards, add ownership/scope rules, immutable change fragments, handoff/PR templates, trusted-base governance and opt-in Trello progress sync. Teammates remain unassigned. No app/hardware acceptance is claimed.

Validation: Repository validation, governance/sync unit tests and offline Trello dry run; live auth, branch protection and workflow execution are verified separately in setup status.

## 2026-10-17 — CS-033-CLAIM-20261017-GMARCIALCALLEJA: Propose Gavin's ownership of Vultr backend deployment

Author: Gavin (gmarcialcalleja) · Task: CS-033

Claim CS-033 for gmarcialcalleja with status in_progress on claim/CS-033-gmarcialcalleja. Implementation waits for Michael to merge this claim and remains dependent on CS-029 and CS-032. Task requirements, master plan and other tasks are unchanged; no deployment or hardware acceptance is claimed.

Validation: Claim-only metadata change; repository check results are recorded in the claim PR. No Vultr, HTTPS/WSS, secret configuration, laptop fallback or hardware tests performed.

## 2026-10-17 — CS-033-DEPLOYMENT-PREPARATION-20261017-GMARCIALCALLEJA: Prepare Vultr deployment configuration and TLS/authentication probes

Author: Gavin (gmarcialcalleja) · Task: CS-033

Add Compose/Caddy deployment templates with private backend networking, digest-pinned input requirements, non-root read-only backend, bounded logs, readiness gating, server-only raw environment configuration, a safe input validator, TLS/authentication handshake smoke probes and a setup/rollback/fallback runbook. Mark CS-033 blocked pending infrastructure and CS-029/032 integration; no live deployment or acceptance is claimed.

Validation: Local Python 3.14.7: 32 unit tests discovered, 31 passed and one Linux permissions test skipped on Windows. Includes temporary HTTPS/WSS fixtures and Docker Compose configuration validation without an engine. Repository validation, changelog verification and whitespace checks passed. Docker engine/Caddy startup, Vultr deployment, actual backend authentication/secret validity, laptop fallback and hardware were not tested.

