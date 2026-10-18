# CS-042 live Tiger Data provisioning and review checkpoint

Owner/contributor: aditsangani. Branch: task/CS-042-event-logging.
Base: e24279f9f4f62bfb602e43333936c0ca51136fad (accepted main).
Existing implementation: merged PR #57, Michael's approving review verified.
No competing CS-042 PR was open when this session started. The previous merged
task branch was fast-forwarded in an isolated worktree; CS-018 stayed untouched.

## Actual live provisioning

Read AGENTS, team workflow, master plan, task/dependency and EVENT_LOGGING guide.
The human supplied only a local provider-download path, not credentials in chat.
Restricted that file and a new external private configuration directory to the
current Windows user. No other allowed principal was present on the directory.
Parsed the download privately; service label matches canesight-event. Verified
the actual endpoint with PostgreSQL 18, TimescaleDB, verify-full TLS 1.3 and
TLS_AES_256_GCM_SHA384. Used an explicit certifi trusted-root bundle; no provider
CA file was supplied and no unverified server certificate was trusted.

Initialized the existing schema through event_store. Provisioned independent
generated-password runtime and analytics logins with restricted grants, no role
memberships, schema CREATE or elevated role flags. Verified real login/privilege
queries, 2s statement and 1s lock limits, UTC and approved columns. Provider
control-plane region/plan/backup settings were not authenticated.

## Files and behavior

- Existing event_store, event_writer, logging_app and event_control are unchanged.
- backend/telemetry/live_probe.py: explicit real-DB synthetic acceptance with
  actual spawned writers, the accepted native manager/consumer gate, unrelated
  certificate and refused-endpoint injection, private recovery receipt and
  allowlisted results. Local native transport is ASGI, not deployed HTTPS/WSS.
- backend/telemetry/Dockerfile.events and its explicit allowlist: prepared image
  layer over a reviewed dashboard/vision image, retaining port 18083 and UID 10001.
- backend/telemetry/TIGER_DATA_ROLLOUT.md and EVENT_LOGGING.md pointer: provisioning,
  exact grants, live probe usage, pending deployment changes, restart/re-enrollment,
  retention, backup/replica/export limits and rollback. No scheduler installed.
- tests/dashboard/test_event_live_probe.py: three component/privacy checks; no
  cloud credentials or automatic cloud tests are used in normal discovery.
- tests/dashboard/cs042-live-tiger-20261018.json: current real-DB report and hashes.
- tests/dashboard/cs042-live-tiger-failed-20261018.json: incomplete earlier fault
  run, not accepted as a pass; source differs from final probe. Three generated
  residual rows were recovered/removed privately before rerunning. Cause unknown.
- Own runtime task fields, new changelog fragment and rendered CHANGELOG only.

## Validation

Existing 36 dashboard/component tests passed before edits. Expanded 39-case suite
passed, including real spawned blocked/failed writer and local TLS tests. Three
new probe tests pass without an optional Psycopg install in ordinary CI by
mocking only the driver boundary in failure/privacy tests. Live results are
separate and use actual Psycopg 3.3.6 with real verified database connections.
Current live report is the authority for individual outcomes and cleanup status.
Repository validation, changelog and whitespace checks passed before publishing;
checked publisher runs root unit/repository checks again. Inspect current-head CI.

## Remaining review gates

Task stays blocked, not Done. Michael/deployment owner must review the proposed
image/factory/read-only runtime-config/CA mounts before any backend/deploy edits.
No deployment files, proxy, model configuration, public listener or production
service were changed or restarted. Docker is unavailable on Windows/Ubuntu WSL;
the image recipe is unbuilt. Build and pin it, verify inherited model/dashboard
assets and native HTTPS/WSS, coordinate restart and re-enroll sessions, then test
event_control against the actual reviewed origin and preserve private receipts.

The view's 24h expiry and real purge were tested; continuous physical deletion
during downtime is not installed or guaranteed. Provider backup/WAL/PITR/fork,
replica/export/log deletion and the actual account's backup window remain outside
the demonstrated row deletion. Confirm/disclose them before participant use.
No credentials, connection endpoints, native identifiers, images, precise GPS or
stream receipts are committed. No device, electrical or physical readiness claim.
