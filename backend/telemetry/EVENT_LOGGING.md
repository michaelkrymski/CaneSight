# CS-042: consented minimal event logging

Optional software implementation for PostgreSQL/Tiger Data. Logging is off in
the existing backend and dashboard factories. Nothing is deployed or connected
to a live database by this change. Michael reviews the new factory and its
private operator interface before activation. The default dashboard stays
read-only; the browser never receives an operator or database credential.

## Recorded data and consent

`backend.telemetry.logging_app:create_logging_app` retains the accepted dashboard
projection and adds a separate logging observer after native admission. It does
not consume native queues, start inference twice, change readiness, modify v1
messages or affect policy. There is no new device credential or device role.

Each session starts with logging disabled. A trusted native operator may enable
logging only after obtaining participant consent to this particular collection.
The enable operation is idempotent. It returns a random stream UUID that is
different from native session/source/boot/frame identifiers. Keep its receipt
privately for later deletion. Enabling means consent was recorded in memory;
it does **not** confirm database connectivity or successful storage.

The fixed record contains a random event UUID, stream UUID, backend observation
time rounded down to a UTC minute, actual live/replay mode, source role and one
of four event labels: frame accepted, depth admitted, heartbeat admitted, vision
offered. These are admissions/offers, not delivery receipts or sensor-health
verdicts. The database view reports capture age as null: no device/backend clock
mapping or freshness bound is invented. Heartbeats never renew capture age.

No raw images, GPS or intersection label, source/boot/frame/session IDs, distances,
symbol/countdown, narration, arbitrary payload, model name or credentials enter
the event record. No raw native message reaches the writer. Events are sampled
at most once per second for each session/role/kind. This lossy diagnostic stream
is not an audit log, complete sensor history or measured latency evidence.

## Isolation and failure semantics

All connections, SQL, DNS/TLS work and retention cleanup run in one spawned
writer process. The observation callback validates a small immutable record and
uses `put_nowait` into a 32-command queue. A full queue or dead writer drops an
event. DB failures drop that write; there is no unbounded retry or disk spool.
The application never waits for a DB response to admit an observation. Startup
does not wait for database connectivity. Native health/readiness remain their
original concepts, not assertions about optional logging availability.

The writer is tied to app lifespan. Shutdown waits briefly, then terminates a
stalled child; pending events/deletion requests can be lost. No independent
daemon or automatic deployment/restart is installed. This is bounded software
isolation, not a hard real-time or physical hardware timing guarantee.

Withdrawal disables new submissions immediately, **even when deletion cannot be
queued**. Previously queued/in-flight writes may finish until the FIFO deletion
command executes. A withdrawn stream cannot be reenabled; use a freshly enrolled
session and newly obtained consent. Deleting a stream also disables its active
binding. Session revocation/expiry removes consent and no new session inherits it.
Already collected rows remain subject to the retention/deletion process.

Deletion response states have distinct meanings:

- `queued` (HTTP 202): accepted by the bounded local queue, not yet deleted.
- `retry_required` (HTTP 503): consent is disabled but deletion was not queued.
- `deleted`: the matching attempt's DB delete returned successfully.
- `failed`: DB delete raised an error; retry after correcting connectivity.
- `unknown`: receipt unavailable, evicted or lost on restart; explicitly retry.

The in-memory receipt cache holds at most 32 streams. Attempt IDs prevent an old
receipt from confirming a newer request. No exception/SQL/config text crosses
from the worker into receipts. Deletion is idempotent and applies only to the
specified random stream. The operator can delete historical streams after the
original native session expires, using the saved private receipt.

## Storage and retention

The schema uses an ordinary PostgreSQL table, compatible with Tiger Data's
PostgreSQL connection; it needs no hypertable, extension or sponsor account API.
Insert/delete values are bound parameters and identifiers are fixed constants.
The data adapter requires `sslmode=verify-full`, an explicit CA certificate,
3-second connection timeout, 2-second statement timeout and 1-second lock timeout.
These are extra DB limits; process isolation also covers DNS/driver stalls.

Each row expires 24 hours after its minute-rounded observation time. The
`canesight_events` view excludes expired rows using **database** wall time
(`clock_timestamp()`, rather than the start time of a long analytics transaction).
The insert rejects already expired or implausibly future-dated observations.
The worker attempts physical cleanup on startup and every 30 seconds thereafter.
While running, DB latency/failure can delay physical deletion. If the service is
stopped or cannot connect, old base-table rows remain until a successful purge.
The view still excludes them; physical deletion deadlines are not guaranteed by
an application-only worker. Arrange independently operated database cleanup if
physical deletion must continue during backend downtime. Provider backups,
replicas, admin exports and access logs need their own retention/deletion policy.

Use a dedicated database/schema owner to initialize the schema once, a runtime
role with INSERT/DELETE on `canesight_event_rows` plus column SELECT on
`event_id`, `stream_id` and `expires_at` for conflict/WHERE checks, and a separate analytics
role with SELECT on `canesight_events` only. Grant neither runtime nor analytics
roles schema modification rights. Do not grant analytics access to the base
table, which intentionally remains available to the deletion administrator.
Provision these privileges with the database administrator; the app does not
create users, grant itself privileges or weaken TLS.

## Provision and run after review

No live Tiger Data credentials or local PostgreSQL server were supplied in this
session. SQL binding/configuration and failures are tested with fakes, and a real
spawned blocked worker is tested. Actual schema execution, cloud connectivity,
CA verification, privileges and persisted expiry/deletion remain unverified.

1. Install the optional pinned adapter in the backend environment:

   ```powershell
   .venv/Scripts/python.exe -m pip install -r backend/telemetry/requirements-events.txt
   ```

2. In a private directory **outside this checkout**, create a small JSON config
   with exactly `host`, `port` (integer), `dbname`, `user`, `password`, and
   `sslrootcert` (absolute CA path). Use the host/port/CA for the actual service.
   Do not paste credentials into chat, command arguments, Git, Trello or PRs.
   Set user-only ACLs on Windows (or directory 0700/file 0600 on Linux). A filename
   check does not certify directory permissions. Only one host is accepted;
   URI/DSN overrides and weakened SSL settings are rejected.

3. Initialize using a private schema-owner config. Use a separate least-privilege
   config for the runtime. These commands write only the new event schema/data:

   ```powershell
   .venv/Scripts/python.exe -m backend.telemetry.event_store --config-file C:/PRIVATE/events-admin.json initialize
   .venv/Scripts/python.exe -m backend.telemetry.event_store --config-file C:/PRIVATE/events-runtime.json purge
   ```

4. Select the new factory explicitly, preserve the existing reviewed proxy/TLS
   mapping and single-process model, and keep the upstream on loopback. Set
   `CANESIGHT_EVENT_DB_CONFIG` to the absolute private runtime config path,
   retain the private `CANESIGHT_OPERATOR_TOKEN`, exact HTTPS
   `CANESIGHT_DASHBOARD_ORIGIN`, and optional verified
   `CANESIGHT_VISION_WEIGHTS`. Start with
   `python -m backend.telemetry.logging_app --port 18084`. The existing dashboard
   Dockerfile does not include these modules or the optional adapter; this PR
   does not change its image, deployed service or proxy. A production image and
   factory switch require operator review and re-enrollment after restart.

5. Enroll a fresh session using the existing native tooling. After obtaining
   participant consent, use the native operator helper from a trusted host:

   ```powershell
   python -m backend.telemetry.event_control enable --base https://BACKEND_ORIGIN --operator-file C:/PRIVATE/backend.env --session-id SESSION_ID --receipt-file C:/PRIVATE/new-event-stream.json --consent-acknowledged
   python -m backend.telemetry.event_control delete --base https://BACKEND_ORIGIN --operator-file C:/PRIVATE/backend.env --receipt-file C:/PRIVATE/new-event-stream.json
   python -m backend.telemetry.event_control status --base https://BACKEND_ORIGIN --operator-file C:/PRIVATE/backend.env --receipt-file C:/PRIVATE/new-event-stream.json
   ```

   The helper verifies HTTPS, disables redirects/environment proxies, accepts no
   query credentials and creates a new private receipt with exclusive creation.
   It prints only fixed status labels. A lost enable response can be retried
   idempotently with a new receipt filename; a failed reservation may leave an
   empty receipt. `queued` is never a confirmed deletion. Retry a failed/full
   queue after correction; preserve the private receipt across restarts. For an
   offline application, an administrator may delete directly:

   ```powershell
   python -m backend.telemetry.event_store --config-file C:/PRIVATE/events-runtime.json delete --stream-id STREAM_UUID
   ```

   Stream UUIDs are pseudonymous deletion identifiers, not credentials; keep them
   private anyway. The service never copies them to the browser projection.

The private operator-only routes are POST `/v1/event-logging/consent` (closed
string body `session_id`, `action=enable|disable`), `/v1/event-logging/delete`
(`stream_id`), and `/v1/event-logging/deletion-status` (`stream_id`). They require
HTTPS, the existing operator bearer header, no Origin/query, bounded closed JSON,
and return no-store. Phone/Pi/viewer credentials cannot grant consent or delete.
Disabling consent through the first route also requests deletion. These are
factory-private administrative routes, not new shared/device protocol messages.

## Verification and acceptance

Run `python -m unittest discover -s tests/dashboard -v` and the checked task
publisher. Tests use synthetic sessions/events, fake SQL connections, controlled
failures and actual spawned child processes. They exercise privacy/consent,
auth/transport boundaries, parameterized queries, TTL construction, FIFO deletion,
failed and stale receipts, bounded queues, blocked DB isolation, and shutdown.

Before live acceptance, independently verify a consented event appears via the
view, unconsented sessions produce no rows, withdrawal prevents new collection,
deletion removes that stream while retaining another, and expired rows are
hidden then physically purged. Test a denied certificate, unavailable database,
runtime privileges and service restart. Record actual results privately without
credentials. Rollback selects the existing backend/dashboard factory, then
handles collected rows through the saved receipts/retention procedure.

Primary implementation references: [Psycopg parameter binding](https://www.psycopg.org/psycopg3/docs/basic/params.html),
[PostgreSQL connection and TLS options](https://www.postgresql.org/docs/current/libpq-connect.html),
[Tiger Data connection details](https://www.tigerdata.com/docs/integrate/find-connection-details),
and [Psycopg 3.3.6 package](https://pypi.org/project/psycopg/3.3.6/).
