# CS-032: admission and WebSocket envelope limits

- Gavin / `gmarcialcalleja`; claim #13 merged before implementation.
- Base: `690ed12ac266952ac92e7da9cc6f1cbbc8c6f319`.
- Branch: `task/CS-032-validation-limits`; PR URL recorded in task runtime field.
- Acceptance: reject nonfinite/oversize/flood inputs while keeping memory and
  watchdog work bounded. This checkpoint tests the transport/ingestion seam;
  full CS-029/031 integration remains outstanding.

## Files and behavior

- `backend/limits.py`: hard-capped idle-expiring token-bucket tables, fixed metrics,
  generic strict JSON envelope parsing, pure ASGI `/v1/` traffic/socket guard and
  trusted identity-based frame/phone admission.
- `backend/app.py`: optional limits injection, middleware registration and Pi
  admission after existing authentication and before body reads/JPEG work.
- `backend/LIMITS.md`: exact starting budgets, deployment transport requirements,
  adapter boundary and test limits.
- `tests/backend/test_limits.py`: 12 meaningful guard tests; prior 19 endpoint
  tests preserved. CS-032 runtime fields, new handoff/fragment and generated log.

Defaults: frame 1/s burst 8; peer 32/s burst 64; global 128/s burst 128; socket
depth 10/s burst 10; maximum 64 active sockets; 128 entries per peer/frame/phone
table. Full tables reject new identities rather than resetting active budgets.
Invalid JSON, nonfinite numbers and oversized WebSocket messages never reach
downstream fixtures. Existing typed schema/JPEG/bounded-body validation is retained.
Counters have no token/payload labels. Freshness/readiness and movement policy are
unchanged. HTTP admission does not wait for tokens or decode a rejected body.

## Tests actually run

On Windows (Python 3.14.7) and an isolated Vultr Linux checkout (Python 3.12):

- `python -m unittest discover -s tests/backend -q`: **31 passed**.
- `python -m unittest discover -s tests -q`: **39 passed**.
- `python -m backend.demo_replay`: health 200, readiness 503, synthetic upload 202,
  duplicate 409. No inference/hardware.
- New guard tests: 10,000 unknown identities cannot grow a full table; concurrent
  budget is atomic; exact refill and invalid/regressed clocks; source identities
  survive reconnects; pre-body rejection; forwarded-header spoofing does not alter
  directly supplied ASGI peer; UTF-8/JSON/nesting limits; socket capacity cleanup;
  valid message timestamps preserved; scheduled software task during 2,000 requests.
- Repository validation, generated changelog and whitespace checks passed before
  checked publishing.

The tests do not measure p95/max event-loop latency, actual inference load or a
physical motor watchdog. WebSocket handlers in tests are explicitly synthetic.
No production endpoint or accepted shared protocol is invented by them.

## CS-029/031 integration

Adit's PR #14 was pushed during this work and inspected read-only. Do not change
its ownership or session contracts. When combining accepted changes, retain both
`session_manager` and `traffic_limits` create_app keywords. Place frame admission
after either authentication path, preserving `require_tls` and role checks.

CS-029 must call `app.state.traffic_limits.telemetry_allowed(grant)` after trusted
phone authentication/identity validation; per-connection depth budgets alone do
not enforce source quotas across reconnects. The guard does not authorize sources,
replace schema/sequence checks or grant freshness. Configure actual transport
buffer bounds before deployment (`--ws-max-size 8192 --ws-max-queue 4` with the
selected WS transport). The server must only trust the reviewed proxy's headers.

CS-031 must still bound inference and prove worker/watchdog behavior under load.
Therefore task remains blocked/draft for dependency integration and no Done claim
is made. Proposed code was tested in a separate Linux directory; it did not replace
the currently running private CS-033 image. Next: PM reviews this draft, CS-031 claim
and worker work; integrate accepted CS-029/031 then run full adversarial load tests.
