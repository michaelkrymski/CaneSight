# CS-032 admission and transport limits

The existing JPEG/metadata validator remains authoritative for `/v1/frames`:
finite numbers and typed contract checks, 8192-byte metadata, 1,000,000-byte JPEG,
1,024,000-byte multipart body, maximum 1920x1080 raster, nesting 12, four concurrent
uploads and five-second upload deadline. Rate rejection happens before body reads
or JPEG work. Rejected frames do not update ingestion sequence or stored data.

`create_app(..., traffic_limits=TrafficLimits(...))` installs `TrafficGuard` and
exposes the same object at `app.state.traffic_limits`. The default single-process
envelope is:

| Budget | Refill | Burst / bound |
|---|---:|---:|
| All `/v1/` requests, WS opens and incoming WS messages | 128/s | 128 |
| Same ASGI peer across requests/connections | 32/s | 64 |
| Authenticated Pi frame source/session/boot | 1/s | 8 |
| Depth messages on one WebSocket | 10/s | 10 |
| Authenticated phone source via `telemetry_allowed` | 10/s | 10 |
| Active `/v1/` WebSockets | — | 64 |
| Peer/frame/phone bucket tables | — | 128 entries each |

These are configurable demo starting values, not throughput or safety claims.
`Limits` configures service budgets; `RateTable` validates finite positive rates,
bounded burst/capacity and an idle lifetime at least as long as a complete refill.
Service tables expire idle entries after 60 seconds. If full, new identities are
rejected instead of evicting active buckets and resetting their budgets. Peer
identities are fixed-size hashes; no token, query or JSON payload is retained.
Counters have fixed names and no dynamic labels. No per-rejection log is emitted.

HTTP rate rejection returns 429 with an advisory `Retry-After: 1`. Connection
admission rejection closes WebSockets before application acceptance (1013).
Accepted sockets reject oversized payloads with 1009, malformed/duplicate/deep or
non-finite JSON with 1008 (preserving CS-029), and message-rate excess with 1008. UTF-8 bytes count
toward 8192, including multibyte text. After closure, downstream sees disconnect;
invalid payloads are not forwarded. Valid ASGI messages are forwarded unchanged.

## Accepted session and worker integration

The guard wraps the accepted CS-029 `/v1/` HTTP/WS routes. Enrollment, TLS/role
authorization, sequence/boot checks and session isolation remain in that module.
Strict generic JSON checking is only an envelope check; the typed protocol
validator remains authoritative. Existing malformed-packet close codes are
preserved. Invalid payloads never reach a relay queue or the inference worker.

The real telemetry route passes `app.state.traffic_limits` to session relay.
After typed parsing and trusted session/source/boot checks, relay calls
`telemetry_allowed(grant)` for depth admission before advancing sequence state
or a peer queue. The trusted grant supplies `session_id`, `source_id`, `boot_id`;
socket reconnects keep the same budget. No unvalidated packet field becomes a
limiter identity. Pi quotas run after either paired or fixed-grant authentication
and before body reads. Accepted frame scheduling retains CS-031's atomic session
revocation hook, latest-only queue, isolated model process and truthful readiness.
A fixed byte ceiling cannot replace capture-age eligibility. No heartbeat
refreshes a capture timestamp here.

Peer admission uses the ASGI socket peer and never reads X-Forwarded-For itself.
Configure the ASGI server to trust forwarded headers only from the reviewed proxy;
do not expose a backend port to untrusted clients with unrestricted proxy trust.
NAT/proxy peers may share a budget, so authenticated source budgets remain separate.

## Bounded server entry point

The ASGI server must bound transport buffers **before application code**; a guard
cannot undo a huge frame already buffered by a server. With the accepted operator
token configured privately, use the reviewed launcher:

```sh
python -m backend.server --host 127.0.0.1 --port 8000
```

It starts the accepted session factory with one process, 8192-byte WebSocket
messages, receive queue 4, concurrency/backlog 128, and h11 incomplete-header
limit 16384. Access logs are disabled. The pinned Uvicorn/websockets combination
is exercised in a real TLS test. The currently supported `websockets` transport
is selected explicitly so its receive-queue setting applies; changing transport
or dependency pins requires revalidation. Default loopback proxy trust may be
replaced using `--forwarded-allow-ips` with reviewed proxy IPs/CIDRs only; wildcard
and catch-all networks are rejected. Deploy behind the reviewed TLS proxy and
keep the backend port private. For container use, set host `0.0.0.0` and specify
the actual trusted proxy address. The operator token remains server-side.

Using `uvicorn backend.server:create_session_app --factory` directly bypasses the
launcher settings, so supply equivalent reviewed transport limits explicitly.
One process is required; more workers need shared quotas/state and separate review.
Health/readiness bypass application token buckets; the server still has finite
connection capacity and may reject connections under overload.

## Verification and limits

Admission never waits for tokens. Decode remains off the event loop via the
existing worker-thread call and four upload slots. Accepted CS-031 keeps model
loading/inference in one child process, latest pending work per source, bounded
results and explicit drop metrics. The combined load test uses that real worker
with a deliberately blocked synthetic model, actual paired uploads and a software
watchdog on the same ASGI event loop. It checks latest work, rejection state,
loop progress and bounded retained Python heap during repeated denied traffic.

Run both accepted roots:

```sh
python -m unittest discover -s tests/backend -v
python -m unittest discover -s tests -v
python -m backend.demo_replay
```

Tests cover 10,000 rejected identities without table growth, atomic bursts,
refill/clock regression, pre-body rejection, JSON/UTF-8 limits, socket cleanup
and unchanged timestamps. Certificate-verified loopback WSS tests prove the real
source budget survives 10 reconnects, the eleventh depth message is rejected
before sequence advancement, another session has its own budget, and malformed,
oversized or impersonating messages are rejected. TLS trust is never disabled.
Load evidence uses synthetic images/models only. The 1-second loop-gap regression
bound and retained-heap check are software tests, not physical motor-watchdog,
model RSS/accuracy or capture-to-motor latency acceptance. Production model sizing,
CS-030 capture-age eligibility and public authenticated deployment remain separate.
