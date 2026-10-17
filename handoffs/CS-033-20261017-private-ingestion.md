# CS-033: real app private deployment and acceptance gaps

- Human: Gavin / `gmarcialcalleja`; task branch `task/CS-033-vultr-deployment`.
- Draft review: https://github.com/michaelkrymski/CaneSight/pull/11
- Accepted app base: `49a1332f5bbe35fb1ce709575318ae9a85894684` (merged CS-028).
- Integrated at task checkpoint `3f5cdd6`; prior handoffs remain immutable history.

## Actual deployment

Built the accepted ASGI app without modifying Adit's implementation. New
`backend/deploy/Dockerfile` uses the official Python 3.12 base digest:

`python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`

Tested local backend image ID:

`sha256:54004dc0e21b745d6904d594c53cc4650148a77857b464976d627ce94bd47955`

Runtime dependencies come from accepted backend/requirements.txt and are frozen
within that specific image; rebuilding can resolve newer transitive dependencies,
so retain/review the image identity and retest any rebuild.

The runtime directory is `/home/linuxuser/canesight-cs033-ingestion/backend/deploy`.
`compose.private.yaml` runs `canesight-private-backend-1` with the normal
`backend.app:app`, bound only to host `127.0.0.1:18000`, UID/GID 10001, read-only
root and bounded resources. `.env.private` contains only that immutable image ID.
No live session/model credentials, Gemini key or database secrets were configured.
The host remains CPU-only. UFW/public port exposure was not expanded.

## Tests and observed results

- Actual container: startup and restart returned health 200, readiness 503,
  missing/invalid upload credentials 401. The shortened test-only health timer
  confirmed Docker unhealthy while the process remains running. The deployed
  service retains its normal grace period and intentionally unready health check.
- Separate explicitly replay-only container of the same image used an ephemeral
  in-memory token: generated JPEG accepted with 202 and preserved frame ID;
  duplicate rejected with 409; readiness remained 503. Test container removed.
- Vultr component suite: **40 passed, zero skips**, including real image and Caddy
  tests enabled with their immutable references. Shared suite: **39 passed**.
- Actual Compose deployment started and was restarted; private smoke passed both
  times. Laptop-to-host SSH tunnel from loopback 18080 to server loopback 18000
  returned the same expected statuses; temporary tunnel closed afterward.
- Accepted `python -m backend.demo_replay` succeeded on both laptop and server:
  health 200, readiness 503, upload 202, duplicate 409; no inference/hardware.
- Local component suite: **40 discovered, 36 passed, four skips** (two built-image
  tests, real Linux Caddy and POSIX permissions). Shared suite: **39 passed**.
- Repository validation, generated changelog and whitespace checks passed before
  checked publishing; CI runs both roots per the accepted CS-028 amendment.

An initial real-image test kept reporting Docker health `starting`: a zero-valued
CLI override did not override the image's startup grace period. Setting explicit
one-second test-only start timings fixed the test; production health was preserved.

## Changes and compatibility

- New Dockerfile and dedicated Dockerfile.dockerignore allowlist: no checkout
  secrets, private assets, .git or venv are sent to the build context.
- New compose.private.yaml and private_smoke.py support unconfigured private
  rehearsal without manufacturing ready status or starting the public proxy.
- New test_backend_container.py plus private Compose config validation.
- Removed this PR's unmerged tests/backend/__init__.py: it shadowed the real
  backend package under root unittest discovery. Accepted CI explicitly runs
  shared and component roots separately. No tests removed or checks weakened.
- Deployment README, task runtime fields, this new handoff/fragment and generated log.

## What remains, exactly

CS-033 is **not complete**. CS-029 belongs to Adit and still needs paired-session
credentials and real WSS routes; CS-032 is backlog. Model/worker readiness is not
implemented, and no model/inference is installed here. Public HTTPS/WSS and
production credentials cannot be honestly accepted from a replay scaffold. User
explicitly deferred domain registration; public TLS is postponed accordingly.

The private default app is left running, rejecting all ingestion until enrollment
exists. Do not replace /readyz with constant success or expose it publicly to
silence unhealthy status. The laptop replay/tunnel rehearsal is partial fallback
evidence, not a complete ready HTTPS/WSS fallback. No physical device/electrical,
YOLO, Gemini, Tiger Data, real-session isolation or road-use evidence is claimed.

Next: integrate accepted CS-029/032 and model/worker health, then production
HTTPS/WSS/auth/secret failures and full laptop fallback. Keep the draft blocked;
PM reviews/merges, never this agent. No additional user secret is required now.
