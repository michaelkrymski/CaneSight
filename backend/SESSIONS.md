# Paired sessions — CS-029

The session server adds operator-created, short-lived pairs to the accepted
CS-028 ingestion app. It implements phone/Pi roles and session-isolated relays
using the accepted `shared/protocol/v1` messages. It runs in one process with at
most eight sessions (16 enrolled sources), and no durable credentials or images.
It does not run vision inference or make freshness/motor decisions.

## Start with TLS

Install `backend/requirements-test.txt` for all tests, or
`backend/requirements.txt` for runtime only. Configure a random operator secret
through `CANESIGHT_OPERATOR_TOKEN` in your private service environment. Use at
least 32 ASCII characters; `secrets.token_urlsafe(32)` is suitable. No default
operator credential exists. Keep credentials out of Git, prompts and logs.

For direct TLS with your certificate and private key outside the repository:

```text
python -m uvicorn backend.server:create_session_app --factory --host 127.0.0.1 --port 8443 --workers 1 --ssl-certfile ABSOLUTE_CERTIFICATE_PATH --ssl-keyfile ABSOLUTE_PRIVATE_KEY_PATH --ws-max-size 8192 --no-access-log --log-level warning
```

Certificate/hostname verification stays enabled in clients. A public deployment
needs a valid certificate for its hostname. CS-033 supplies the proxy/deployment
work; no public domain or Vultr deployment was tested in this task.

Behind a TLS-terminating reverse proxy, keep the upstream private and accept
forwarded scheme headers **only from that proxy's exact trusted address** using
Uvicorn's `--proxy-headers --forwarded-allow-ips EXACT_PROXY_IP`. Do not use `*`,
expose the plain upstream to clients, or let a caller spoof HTTPS. The app checks
the ASGI scheme; it never trusts `X-Forwarded-Proto` itself. The proxy must preserve
Authorization and WebSocket upgrades. Disable URL/access logging and avoid info
level WebSocket handshake logs, as in the command above. Keep one worker until
shared session/sequence/queue state is designed and tested.

`/healthz` remains process liveness. `/readyz` remains 503 without real selected
model availability and worker-health input. Creating a pair does not supply those
dependencies. A separate CS-033 readiness probe must not claim readiness from a
WebSocket handshake alone.

## Operator API

`POST /v1/sessions` requires HTTPS and `Authorization: Bearer <operator secret>`.
Body is JSON (<=2048 bytes), closed shape, with explicit mode and source process
bindings. Source/boot IDs follow the accepted ASCII 1–64 character identifier
rules; phone and Pi source IDs must differ. Example artificial replay binding:

```json
{
  "mode": "replay",
  "ttl_seconds": 300,
  "phone": {"source_id": "phone-1", "boot_id": "phone-boot-1"},
  "pi": {"source_id": "pi-camera-1", "boot_id": "pi-boot-1"}
}
```

TTL defaults to 300 seconds and is limited to 1–600. `mode` is required and is
either `live` or `replay`; the server never upgrades a replay packet/session to
live. Bind actual devices using new random process boot IDs at startup. The
operator explicitly authorizes enrollment; incoming observations cannot reenroll.

HTTP 201, `Cache-Control: no-store` response contains `schema_version: 1`, a
random `session_id`, `mode`, `expires_in_seconds`, and `phone`/`pi` objects. Each
contains a distinct random `token`, its bound `source_id` and `boot_id`, and
`websocket_path`. Deliver each credential only to its intended device through the
operator's secure configuration channel. Possessing a session/source ID alone
never authorizes access. No list endpoint exposes credentials later.

`DELETE /v1/sessions/{session_id}` requires the same operator authorization and
HTTPS. It returns 204; absent/expired sessions return 404. It revokes both device
credentials, clears frame/sequence/control state, drains buffers and closes both
sockets. Expiry does the same without an operator request. The active server
sweeps expiry every 100 ms; admission always rechecks the deadline before use.
An in-flight JPEG cannot commit after revocation.

For a source restart, revoke the old pair and create a new session with the new
boot binding; reconnecting the old boot does not reset sequence counters. Process
restart loses all sessions/credentials and queues; old tokens never reenroll.
Rotate the operator secret through service configuration and restart when needed.

## Native device WebSockets and upload

Use an Authorization bearer **header**, never URL parameters. Native phone and
Pi libraries support this (including URLSessionWebSocketTask). Browser Origins
and URL parameters are rejected; browser/dashboard auth is separate future work.

| Role credential | Route | Allowed client messages |
|---|---|---|
| Phone | `wss://HOST/v1/telemetry` | `depth_observation`, phone `heartbeat`, correlated `clock_reply` |
| Pi | `wss://HOST/v1/events` | Pi `heartbeat`, `clock_probe` addressed to its paired phone |
| Pi | `https://HOST/v1/frames` | Accepted CS-028 multipart JPEG + original `frame_metadata` |

Phone depth/heartbeat and clock replies relay unchanged only to the paired Pi.
Pi heartbeat/probes relay only to the paired phone. There is no wildcard or
client-selected subscription. A client cannot publish vision/actuator messages
or impersonate another source/boot/session/mode. Backend-generated vision relay
remains CS-035 integration work, requiring original accepted frame lineage.

Only one socket per role is admitted per session. A duplicate role connection
is denied rather than evicting an existing client. Reconnect keeps per-type
sequence high-water marks. No messages are replayed to a newly attached socket.
Each outgoing queue holds at most eight messages. Overload closes the pair and
discards its queued observations rather than allowing an ever-growing delay.
Loss of either socket clears pending clock control and invalidates the other
socket; reconnect both and wait for new captures. New sessions are required for
source reboot. Device adapters must invalidate guidance on any socket loss.

JSON is UTF-8 text or binary bytes, <=8192 bytes and <=12 nesting levels. Schema,
finite numbers, identity, boot, mode, role and ordering are checked before relay.
Clock probes are bounded to one per second and one outstanding exchange; reply
must match nonce/session/mode/identities/t1, arrive within one second, and have
non-reversing source times. The Pi still consumes its own nonce and validates
its measured t4, drift/uncertainty and capture ages using the accepted protocol.
No backend receive time replaces source capture time. A valid heartbeat does
not renew an observation.

Relay admission does **not** establish capture-age eligibility: CS-030 must wire
clock mappings, source health and independent expiry into consumers. Keep all
phone-derived haptic guidance unavailable until that integration is tested.
Broader frame/telemetry rate quotas remain CS-032; the connection/session/queue
bounds here do not replace those quotas.

Before upgrade, denied credentials/role/transport receive HTTP 403 from the WS
server. After upgrade, close codes include 1008 for malformed/unauthorized data,
1009 for oversized messages, 1012 for peer interruption, 1013 for slow consumers,
4401 for expiry/revocation and 1000 for operator closure. A duplicate socket is
denied with application code 4409 in ASGI tests (HTTP 403 on a real handshake).
Treat every close as unavailable, regardless of code. No error includes tokens
or image data. Plain HTTP session creation/frame uploads return 403.

## Verification and limits

```text
python -m unittest discover -s tests/backend -v
python -m unittest discover -s tests -v
python -m backend.demo_replay
```

The backend suite includes a real HTTPS/WSS test: generate a temporary CA and
server key outside Git, require certificate verification, create replay pairs,
reject invalid/missing credentials, relay a synthetic depth fixture, verify
other-session isolation, upload a generated JPEG and revoke the pair. It also
checks that a client without the test CA rejects the server certificate. Temporary
keys and the local server are cleaned up. This test is discovered by accepted
backend CI without changing protected workflow files.

Unit tests also cover malformed enrollment, TLS scheme enforcement, role/identity
impersonation, session bounds, duplicate/reordered messages, reconnect, socket
expiry, bounded queues and clock-control correlation. Device, clock drift,
hardware, public-network/proxy, real model and live deployment verification are
not claimed. Python 3.12 Linux behavior is checked by the PR's existing CI;
local execution is Windows Python 3.14.3.
