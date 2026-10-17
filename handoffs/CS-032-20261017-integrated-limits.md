# CS-032: completed session/worker quota integration for review

- Gavin / `gmarcialcalleja`; merged ownership claim #13.
- Branch: `task/CS-032-validation-limits`; PR #15.
- Initial base this checkpoint: `dd7c46830d869b24b0d76f490cd086c9ec5b118f`.
- Final accepted base: `9fedcf43d0dd3535dafacea8b96235a6dbeb5049` (CS-030
  merged during work; final combined suites rerun).
- Acceptance: reject NaN, oversize input and floods; bound memory and software
  watchdog work. Implementation is ready for Michael's review, not marked Done.

## Final changes

- `backend/app.py`: retain accepted session/worker options and composed lifecycle,
  install TrafficGuard, enforce trusted Pi quota before body/JPEG work for paired
  and fixed-grant paths. Session admission/scheduling retains its revocation lock.
- `backend/sessions.py`: pass the app's limiter to real relay; after typed parsing
  and trusted identity checks, phone depth quota runs before sequence/queue commit.
  Reconnecting sockets cannot reset the authenticated source/session/boot budget.
- `backend/limits.py`: bounded buckets, connection/byte/JSON/global/peer guards
  remain; preserve accepted malformed-packet code 1008 and reject boolean idle
  configuration. Credentials/payloads are not metric labels or bucket keys.
- `backend/server.py`: bounded launcher, one process, h11, WS size 8192/queue 4,
  concurrency/backlog 128, incomplete-header limit 16384; no access logs. Trusted
  proxies require explicit IP/CIDR values; wildcards/catch-all ranges are rejected.
  TLS tests run through this configuration, not a separate unbounded server setup.
- `backend/LIMITS.md`: actual integration, launch command, budgets and evidence
  limits. `tests/backend/test_limits.py` retains strict rejection expectations
  with accepted close codes. New `test_limits_integration.py` adds four combined
  transport/session/worker tests. Own task evidence, new fragment and rendered log.

Initial baseline integration exposed a malformed JSON close-code mismatch
(1007 versus accepted 1008); fixed the guard instead of weakening the accepted
CS-029 tests. Normal main merges retained accepted code and regenerated the log.
All other task records match main; no static acceptance, shared protocol,
governance or master-plan edit was made. Original handoffs/fragments are unchanged.

## Tests actually run

Windows Python 3.14 in a dedicated temporary venv with accepted requirements and
Vultr Linux Python 3.12, final combined tree:

- Backend discovery: **88 passed**, no skips.
- Separate shared/governance discovery: **39 passed**.
- `python -m backend.demo_replay`: health 200, readiness 503, upload 202,
  duplicate 409.
- New paired HTTP test: wrong role/missing auth never create source buckets;
  quota rejection precedes body reads and advances no stored sequence/image;
  refill permits validation again and oversize body is rejected.
- Real certificate-verified loopback HTTPS/WSS through bounded server config:
  ten phone depth messages on ten distinct connections pass unchanged; eleventh
  same-source message closes 1008 without advancing sequence; another session
  has its own budget. NaN, numeric overflow, duplicate keys, oversize and source
  impersonation reject. All active-socket slots are released. Trust stays enabled.
- Slow-worker fixture: real spawned model process deliberately blocked; 200
  authenticated frame submissions hit actual ASGI routes while health/software
  watchdog tasks run on the same loop. One active/one pending source job and
  two ledger records remain; only latest admitted work publishes. Rejected frames
  never advance ingress. Worker stop makes readiness unavailable.
- Retained Python heap measured after a warmed 500-request rejection batch and
  another 500 rejections; regression requires growth <1 MB. Table/worker bounds
  also asserted. This is not model-process RSS or a full capacity benchmark.
- Existing tests include 10,000 excess identities, atomic buckets, generic
  2,000-request flood, schema/JPEG/UTF-8 validation, model deadlines/revocation,
  freshness/replay/unknown semantics and real WSS clock calibration.

Software-only load samples (29 consecutive watchdog gaps; fixture timing only):

| Environment | Median gap ms | p95 gap ms | Max gap ms | Retained heap growth bytes |
|---|---:|---:|---:|---:|
| Windows | 13.814 | 15.969 | 16.280 | 3307 |
| Vultr Linux | 6.051 | 8.679 | 9.211 | 3647 |

The generous 1-second loop-gap assertion is a software regression bound, not a
500-ms sensor age budget or hardware acceptance. The temporary evidence runner
was corrected to use a spawn-safe main guard, then complete suites were rerun.
No production component uses that runner. Repository/changelog/whitespace checks
run through checked publishing before pushing the final branch.

## Deployment and review handoff

Linux tests ran in `/home/linuxuser/canesight-cs032-integrated-final`; they did not
replace the running private ingestion image or unblock the public HTTPS API.
The live CS-033 proxy remains health-only. After Michael merges #15, CS-033 must
build a new immutable image including limits, server, sessions and the accepted
worker/consumer modules needed by its selected runtime; use the bounded launcher
and explicit reviewed proxy trust. Keep operator credentials server-side, deliver
only scoped Pi credentials privately, and validate actual paired upload/WSS,
expiry and connection loss for issue #20. No public route is enabled by this PR.

The selected model and its memory/throughput still require CS-034 evidence; these
tests use synthetic images/adapters. Physical motor watchdog and capture-to-motor
latency remain hardware/integration work. Unknown/freshness/crossing invariants
are unchanged. Michael performs review/merge; no main push or self-merge.
