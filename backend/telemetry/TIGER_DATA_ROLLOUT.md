# CS-042: live database and proposed deployment integration

This follows accepted PR #57. The existing event store, writer, application and
operator helper are reused, not replaced. Live database checks use synthetic
replay inputs only. The deployed backend has not been switched or restarted.

## Provisioned service and private configuration

The supplied Tiger download identifies `canesight-event`. Its actual endpoint
authenticated with PostgreSQL 18, TimescaleDB installed and TLS 1.3
(`TLS_AES_256_GCM_SHA384`). Hostname verification stayed `verify-full`; the trusted
CA file is a copy of the installed certifi public root bundle, not a certificate
accepted from an unverified connection. No provider CA file was supplied. A valid
unrelated CA is tested against the actual endpoint and must fail certificate
verification. Provider region, compute/plan, backup window and control-plane
settings have not been authenticated through a Tiger Console/API session.

The operator-provided credential download and private configuration directory
were restricted to the current Windows user with inheritance disabled. The
administrator, runtime and analytics JSON files and CA bundle remain outside
Git, with the exact six-key format in EVENT_LOGGING.md. Configuration values,
passwords, endpoints, connection strings and stream receipts are not evidence
artifacts. Keep the administrator credential out of the deployed application.

The existing `event_store initialize` command created the existing schema. Two
new independently generated password logins were provisioned: `canesight_events_runtime`
and `canesight_events_analytics`. Neither is superuser, database/role creator,
replication or RLS-bypass role; neither has role memberships or public-schema
CREATE. Both have database CONNECT, schema USAGE and a per-database public search
path. PUBLIC grants were removed only from the two newly created event objects.
No database-wide PUBLIC permissions or unrelated objects were changed.

Runtime grants:

```sql
GRANT INSERT, DELETE ON public.canesight_event_rows TO canesight_events_runtime;
GRANT SELECT (event_id, stream_id, expires_at)
  ON public.canesight_event_rows TO canesight_events_runtime;
```

Analytics grant:

```sql
GRANT SELECT ON public.canesight_events TO canesight_events_analytics;
```

Real connections verified the grants and denied capabilities. Runtime cannot
SELECT the whole table, read its `mode` column, UPDATE/TRUNCATE, or read the
analytics view. Analytics cannot read any base-table column or insert/delete.
Credentials for these new accounts were generated and saved privately; no
passwords belong in SQL examples, shell arguments or PR text.

## Reproduce live evidence

Install existing backend test requirements and optional
`backend/telemetry/requirements-events.txt` in a private environment. The test
requirements supply trustme for a deliberately unrelated test CA.

```powershell
python -m backend.telemetry.live_probe `
  --admin-config C:/PRIVATE/events-admin.json `
  --runtime-config C:/PRIVATE/events-runtime.json `
  --analytics-config C:/PRIVATE/events-analytics.json `
  --output C:/PRIVATE/sanitized-live-report.json
```

This explicitly writes synthetic test streams, briefly locks the event table and
purges expired event rows. Run against a coordinated development service, not
concurrently with real participants or production logging. It deletes only its
generated streams on exit; it does not delete another active stream. Stop on a
failed cleanup report and resolve that failure privately before retrying.

The committed report under tests/dashboard contains real TLS/database outcomes,
source hashes and fixed aggregate checks. Local native admission uses ASGI
TestClient, not a deployed network listener. The refused loopback endpoint is an
injected connectivity failure, not an induced Tiger outage; only synthetic
credentials are sent to that destination. Queue saturation and a held table lock
exercise the real spawned writer. Capture expiry uses the actual accepted
CaptureAgeGate with explicitly synthetic clock bounds while the real table lock
is held. It proves software independence, not physical motor shutdown or measured
device timing. All generated streams were removed after the run.

The probe's success does not certify provider backup policy or deployment. The
existing event_control enable/delete/status commands remain the operator path
after rollout; exercise them against the reviewed real HTTPS origin, saving
private deletion receipts. A queued receipt is not a confirmed deletion.

## Image prepared for review; no deployment files edited

`backend/telemetry/Dockerfile.events` layers only the existing logging runtime and
the pinned optional Psycopg adapter over a reviewed immutable dashboard/vision
image. Its Docker-specific ignore file allowlists only those sources; no private
configuration, model files or credentials enter the build context. The parent
must already contain the reviewed dashboard/native/vision runtime and assets.

```sh
docker build --file backend/telemetry/Dockerfile.events \
  --build-arg BASE_IMAGE=REVIEWED_DASHBOARD_IMAGE_AT_SHA256 \
  --tag canesight-events:review .
```

The recipe has not been built in this session: Docker is unavailable on this
Windows host and its Ubuntu WSL environment. It retains UID/GID 10001, the
existing bounded single-process launcher and internal port 18083. Build, inspect
and pin the resulting image digest before activation; test inherited assets and
configured model loading against that exact image.

Michael/deployment-owner review is required before changing any
`backend/deploy/` file. Proposed changes, not applied here:

1. Select the reviewed logging image digest and command
   `python -m backend.telemetry.logging_app --port 18083` in the existing backend
   service. If another override also sets command/image, review the final private
   composition rather than silently dropping its model configuration.
2. Read-only mount an operator-provisioned runtime JSON and trusted CA file at
   `/run/canesight/events-runtime.json` and `/run/canesight/tiger-ca.pem`. The JSON
   CA path must name that container path, not a Windows path. Make files readable
   by container UID 10001 without granting other host users access. Mount neither
   administrator nor analytics credentials.
3. Set `CANESIGHT_EVENT_DB_CONFIG=/run/canesight/events-runtime.json` and the
   exact reviewed HTTPS `CANESIGHT_DASHBOARD_ORIGIN`. Preserve the existing
   operator credential, `CANESIGHT_VISION_WEIGHTS`, model mounts, loopback bind,
   proxy trust, Caddy volumes/certificate configuration, resource bounds and
   native HTTPS/WSS role/session behavior. Do not expose 18083 publicly.
4. Agree a restart window with Michael and the deployment owner. Stop the old
   app gracefully, deploy once, and re-enroll fresh phone/Pi sessions; in-memory
   sessions/consent do not survive restart. Obtain new logging consent explicitly.
5. Verify the image and deployed HTTPS/WSS/native behavior, model readiness,
   unconsented/consented storage, operator helper receipts, withdrawal, deletion,
   startup purge, and DB-unavailable behavior. Existing readiness remains model/
   source readiness, not a database-logging availability signal.

Rollback selects the prior reviewed image/command and re-enrolls sessions again.
Preserve private deletion receipts and clear collected rows using the existing
deletion/retention procedure. A rollback must not promise that collected data or
provider backups vanished. No automatic deployment, restart, daemon or OS task
has been installed by this checkpoint.

## Retention and provider limits

The ordinary event table is not a hypertable; no Timescale retention job is
implicitly installed. The view excludes rows after their 24-hour deadline using
database wall time. The writer tries physical purge on startup and each 30s while
running. During backend downtime or DB unavailability, expired base rows may
remain; successful later purge removes them. If continuous physical deletion is
required, propose a separately owned database/server scheduler and its monitoring
for Michael's review. No background scheduler is installed here.

Deletion and purge remove active database rows. They do not prove erasure from
provider backups/WAL, PITR forks, replicas, exports or operator/access logs.
Tiger's [backup documentation](https://www.tigerdata.com/docs/deploy/tiger-cloud/tiger-cloud-azure/high-availability/backup-restore)
describes backup/PITR retention separately. Confirm this service's actual
provider/plan and backup retention in Console or with provider support before
making deletion guarantees. The provider backup policy remains unverified in
the evidence and must be disclosed to participants. Application retention is
not a promise of provider-wide physical erasure.

## Failed-run recovery

The probe records generated stream IDs in a user-private `probe-recovery-*.json`
next to the runtime configuration before inserting. Successful confirmed cleanup
removes that receipt; failure retains it privately. Do not publish its contents.
Use the existing event_store delete operation for those exact IDs after restoring
verified connectivity, then confirm absence through the administrator connection.
Do not remove every replay stream or reset the database to recover a test.

One expanded development run returned incomplete and could not confirm cleanup;
its sanitized failed report is retained separately. The isolated event table was
empty before this run; its three residual synthetic rows were recovered and
removed using privately retained stream identifiers. The cause was not confirmed.
Later complete runs passed; the failed attempt is not counted as a pass. The
current probe adds private recovery receipts so failures retain deletion IDs.
