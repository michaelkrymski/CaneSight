# CS-041: opt-in read-only dashboard interface

Status: Proposed for Michael's review before activation. No shared/v1 contract,
master-plan text, native route, protected workflow or deployment configuration
is modified. Implementation stays in dashboard/, backend/telemetry/ and tests/dashboard/.

## Reason and alternatives

The preview is complete, but the native WSS endpoints deliberately reject browser
Origins and use phone/Pi credentials. Giving a browser one of those credentials
or weakening native Origin checks is rejected. A separate metadata projection
with a session-scoped, read-only credential supplies browser diagnostics without
introducing a new device role or claiming a capture-age bound from server receipt.
Keeping the existing fixture-only preview remains the fallback and default.

## Proposed private dashboard interface

- Separate factory: backend.telemetry.live:create_dashboard_app. Original
  backend.server:create_session_app remains unchanged and does not install routes.
- POST /v1/dashboard-viewers: HTTPS, original operator bearer header, no Origin
  or query; closed body containing only session_id. Returns a separate random
  viewer credential with no-store. At most 16 viewers; lifetime cannot exceed
  that native session or 600 seconds. Only hashes are retained server-side.
- POST /dashboard/api/login: exact configured HTTPS origin and Host, bounded
  closed JSON viewer_token body; sets a Secure/HttpOnly/SameSite=Strict __Host-
  cookie. Native operator/phone/Pi credentials are not accepted as viewers.
- GET /dashboard/api/snapshot: cookie scoped to ONE enrolled session; no caller
  session selector or query. At most four polls per second per viewer. No CORS.
- POST /dashboard/api/logout: same-origin, removes cookie and revokes that viewer.
- Native session revocation/expiry clears viewers and projections immediately.
  Process restart loses everything; browser failures clear its current display.

Snapshot version 1 is a dashboard-private display projection, not a new device
wire message. It whitelists session/source/boot/mode/sequence/frame/model metadata,
native socket presence, elapsed backend activity and up to eight event labels.
No JPEGs, detections, depth distances, GPS, grant tokens, clock nonce or operator
credential are returned. Observers run only AFTER native validation/admission;
no socket queue is consumed or model work duplicated. A result observed before
sending is labeled offered, not proof of Pi receipt.

## Timing and product behavior

The backend cannot bound either device clock from current accepted traffic.
Capture-age upper bounds therefore stay null/Unknown in the live metadata view.
Original capture timestamps are preserved as metadata, never subtracted from
the backend/browser clock. Backend receipt activity is labeled separately and
never establishes source readiness. The browser adds local elapsed time/full
request duration only to activity age, not capture age. Distances and boxes stay
unavailable; signal/countdown remain unknown. The actual session mode is retained.
Fixture replay remains explicit and never connects to production automatically.

## Impact, activation and rollback

No public activation is performed in this PR. Michael reviews this auth/interface
and the exact code head before opting into the new factory/image. The optional
Dockerfile extends a reviewed immutable vision runtime and copies only explicit
code/static assets; no secrets/models/private data enter its build context.
The operator sets exact CANESIGHT_DASHBOARD_ORIGIN and keeps the existing operator
secret server-side. The existing Caddy TLS, private upstream and resource bounds
must be preserved. Activation changes the factory/image and restarts the backend,
so coordinate devices and re-enroll new processes afterward. Roll back to the
original reviewed backend image/factory; its native API and fixture preview remain.

True bounded live capture ages would require a separately reviewed source-clock
exchange or authenticated final-consumer report; this projection does not invent it.

## Validation

Tests cover credential/role/session isolation, TLS/Host/Origin/query restrictions,
secure cookies, bounded body/poll/storage, logout, native revocation/expiry,
original metadata, no queue consumption and unchanged native WSS rejection.
Real certificate-verified local HTTPS/WSS is tested using generated replay data.
Node tests cover unknown capture ages, actual mode, activity growth, malformed
snapshots and clearing metadata on loss/logout. Browser harness data is synthetic;
no real phone, motor, public dashboard deployment or age calibration is claimed.
