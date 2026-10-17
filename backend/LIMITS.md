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
non-finite JSON with 1007, and message-rate excess with 1008. UTF-8 bytes count
toward 8192, including multibyte text. After closure, downstream sees disconnect;
invalid payloads are not forwarded. Valid ASGI messages are forwarded unchanged.

## CS-029 integration boundary

No real WebSocket route is added by this task. The guard automatically wraps
future `/v1/` HTTP/WS routes, but **never** provides enrollment, role authorization,
sequence/boot checks or session isolation. Strict generic JSON checking is only
an envelope check; use the accepted typed protocol validator afterward.

After authenticating a phone and validating its identity, CS-029 must call
`app.state.traffic_limits.telemetry_allowed(grant)` for depth admission across
reconnects, closing/rejecting on false. The grant supplies trusted `session_id`,
`source_id`, `boot_id`. Never derive limiter identities or authorization from
unvalidated packet fields. Frame admission is already invoked after the existing
ingress authenticates its grant. A fixed byte ceiling cannot replace identity,
capture-age or schema validation. No heartbeat refreshes a capture timestamp here.

Peer admission uses the ASGI socket peer and never reads X-Forwarded-For itself.
Configure the ASGI server to trust forwarded headers only from the reviewed proxy;
do not expose a backend port to untrusted clients with unrestricted proxy trust.
NAT/proxy peers may share a budget, so authenticated source budgets remain separate.

The ASGI server must also bound transport buffers **before application code**:
for Uvicorn WebSocket integrations use `--ws-max-size 8192 --ws-max-queue 4` with
the selected supported WS transport. A guard cannot undo a huge frame already
buffered by a server. No WS transport or auth backend is invented in this task.
One process is required; more workers need shared quotas/state and separate review.

## CS-031 and verification boundary

Admission never waits for tokens. Decode remains off the event loop via the
existing worker-thread call and four upload slots. CS-031 must still bound its
inference queue and scheduling; HTTP admission alone does not prove that worker
or physical motor watchdog remains responsive under inference load.

Run both accepted roots:

```sh
python -m unittest discover -s tests/backend -v
python -m unittest discover -s tests -v
python -m backend.demo_replay
```

The new tests use fixture sockets, synthetic credentials and an injected monotonic
clock. They check 10,000 rejected identities without table growth, atomic bursts,
refill/clock regression, pre-body rejection, JSON/UTF-8 limits, socket cleanup,
unchanged timestamps and a scheduled software task during 2,000 synthetic requests.
This proves only the tested software boundary. CS-029 live endpoint integration,
CS-031 inference-load behavior and hardware remain separate pending evidence.
