# CS-042 consented event logging handoff

- Author: aditsangani (AI-assisted)
- Branch: task/CS-042-event-logging
- Base commit: 5fbbed2f0143710ceba3849eb85e8e2d5914eb5b
- Assignment claim PR #56 merged; dashboard dependency PR #25 merged.

## Changed files

- backend/telemetry/event_store.py and event_schema.sql: closed minimal records, private config, fixed parameterized SQL, verified-TLS connection settings, UTC/minute rounding, 24-hour expiry and explicit initialization/purge/deletion administration.
- backend/telemetry/event_writer.py: bounded lossy queue, single spawned DB worker, FIFO deletion, bounded attempt-specific receipts and bounded shutdown/termination.
- backend/telemetry/logging_app.py: separate opt-in factory, per-session operator consent, post-admission observer and native-only deletion/status routes. No existing factory is modified.
- backend/telemetry/event_control.py: native operator helper with verified HTTPS, explicit consent acknowledgement, private/exclusive stream receipts and sanitized failures.
- backend/telemetry/requirements-events.txt: optional Psycopg binary adapter pinned to 3.3.6; no global backend dependency change.
- backend/telemetry/EVENT_LOGGING.md: configuration, schema/privileges, consent, failure/deletion states, retention limits, live validation procedure and rollback.
- tests/dashboard/test_event_logging.py: eighteen new tests.
- Task CS-042 runtime fields, this handoff, new changelog fragment and generated CHANGELOG.md.

## Tests actually run

- New logging suite: 18 tests passed. Covers consent defaults/session isolation, withdraw-before-delete under full queue, real admitted HTTP frame and offered vision without private payload, unchanged native queues/capture-age semantics, native operator auth/TLS/Origin/query/closed-body restrictions, parameterized queries/TTL construction, private operator helper, failed/stale deletion receipts and actual spawned hung-worker isolation/termination.
- Full dashboard suite before the final added integration case: 35 tests passed, including existing verified HTTPS/WSS test.
- Installed optional Psycopg 3.3.6/binary 3.3.6 in ignored local .venv and imported it; libpq version reported 180004. This does not test a DB connection.
- Checked publishing runs the full root shared suite (including these dashboard tests), repository structure, changelog consistency and whitespace checks. Actual results are reported with the PR.

## Evidence, privacy and limits

No raw images, GPS, native identifiers, source payload, narration or credentials are persisted by the event type. Each session requires new operator consent; only a random stream UUID, random event UUID, backend minute, mode, role and enum kind reach the worker. Capture age stays null. Sampled admissions/offers are not delivery, health or freshness evidence.

A blocked database is isolated behind a 32-command queue in a spawned process. Failed writes are dropped, and shutdown can lose pending work. Consent withdrawal stops new enqueues immediately; queued/in-flight writes may finish until a deletion executes. Queue acceptance is not deletion confirmation; failed/unknown requests require explicit retry with the saved private receipt. Deletion is not durable across a process restart.

The view hides expired rows by DB wall clock. Physical purge is attempted every 30 seconds while the writer runs; outages/downtime can delay physical deletion. Provider backups/exports need separate retention. Runtime and analytics privileges must be provisioned by the database administrator as documented.

No live database credentials, cloud service or local PostgreSQL server were supplied. Actual schema execution, cloud connectivity/TLS, privileges, persisted retention/deletion and production integration are unverified. No hardware, inference accuracy, road use, crossing permission, public activation or deployment change is claimed.

## Next steps

Michael reviews the new opt-in interface and software evidence. Before live acceptance, provision the database/CA and least-privilege config outside Git, run the documented consent/isolation/retention/deletion/outage tests and retain actual private evidence. Task remains Review, not Done. Existing deployed factories remain available for rollback.
