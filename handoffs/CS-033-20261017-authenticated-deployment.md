# CS-033 authenticated Vultr deployment — 2026-10-17

Owner: Gavin (`gmarcialcalleja`). Branch: `task/CS-033-vultr-deployment`.
Starting task head: `b2e4f86a5d7052761c5c5032d480f74975301157`.
Accepted integration base: `56cbd7aa5b14c7db011c98a994909421f2989825`
(main after CS-032 PR #15). PR: https://github.com/michaelkrymski/CaneSight/pull/11.
Status: Review, not Done. Michael must review/merge; no main push or PR merge.

## Acceptance and dependencies

Task acceptance: test HTTPS/WSS, startup readiness and secret configuration;
laptop remains rehearsed fallback. Accepted CS-029 sessions and CS-032 admission
limits are integrated. Changes stay within backend/, tests/backend/, this task's
runtime fields, new handoff/changelog fragment and generated changelog. Incoming
main changes preserve teammates' tasks and protected baseline files.

## Changed files

- `backend/deploy/Dockerfile` and `Dockerfile.dockerignore`: explicitly package
  the accepted sessions, bounded launcher, limits, freshness and worker modules.
- `backend/deploy/compose.yaml`, `Caddyfile`, `.env.example`, `backend.env.example`,
  `check_config.py`, `readiness.py`: private bounded session launcher, raw private
  operator configuration, public IPv4 TLS, persistent certificate reuse and
  actual readiness on the configured internal port. The proxy may start once the
  process starts so authenticated enrollment is possible before source/model
  readiness. Model/worker checks remain unchanged and false.
- `backend/deploy/session_probe.py`: verified HTTPS/WSS session acceptance using
  synthetic replay inputs and a private operator file. Comma-combined duplicate
  Cache-Control no-store directives are accepted correctly.
- `backend/deploy/switch_upstream.py` and `laptop_fallback.py`: explicit loopback
  production/laptop selection, target liveness check, rollback and full laptop
  backend rehearsal through an encrypted reverse SSH tunnel.
- `tests/backend/test_authenticated_deployment.py`, `test_backend_container.py`,
  `test_deployment.py`: real TLS session acceptance, missing operator startup
  refusal, private input validation and deployed Compose/port configuration.
- `backend/deploy/README.md`, backend README deployment section, CS-033 task
  runtime fields and new changelog fragment: operator runbook, evidence and limits.

## Deployed configuration

Origin: **https://64.177.50.116** on the existing authorized Vultr instance.
No new instance/domain was purchased. CPU-only Ubuntu 24.04, 2 vCPUs,
approximately 4 GiB RAM, 128 GB disk. Docker requires sudo.

Runtime: `/home/linuxuser/canesight-cs033-authenticated/backend/deploy`.
Private operator file: `secrets/backend.env`, mode 0600, directory 0700.
Generated directly on the server; never copied into chat, logs, Git or Caddy.
Runtime `.env` is also private and contains only non-secret image/origin settings.

Backend image:
`sha256:67eef5da4e34862ea31facbcea2388e9cd7459f1eb4db6d35ca6deccaaa2ad6a`.
Caddy image:
`caddy@sha256:685ae3d7c34d9b5f8caeddc5d14051db7bbd88ff1f5a2fa0c16bd8ca328fb7af`.
Python base:
`python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`.

The backend runs `python -m backend.server` with one process and accepted CS-032
transport bounds, binds 127.0.0.1:18083 and trusts only 127.0.0.1 proxy headers.
UID/GID 10001, read-only root, dropped capabilities, no-new-privileges, 1.5 CPU,
2 GiB RAM, 256 process limit and bounded temporary storage/logs are configured.
The Linux host network is shared, so the explicit loopback bind is essential.
Caddy alone serves public TCP 80/443; admin API/request access logging disabled.
From the laptop, ports 18000, 18081, 18083 and 2019 were unreachable. Server socket
inspection confirmed backend loopback binding and no leftover fallback listener.

The existing Let's Encrypt public IP certificate and persistent bootstrap volumes
are reused. Certificate SHA256:
`7ecdadda860ec9a6321b841a171fc4a9ed3f4a7b636c990f6471f89dda0734b1`.
Expires **2026-10-23 23:17:11 UTC**. Default trust and IP matching verified on
Windows and Linux. Renewal configured; future renewal not yet observed.
The old bootstrap proxy is stopped and preserved for rollback; the old CS-028
private backend remains on 127.0.0.1:18000. Do not run both public proxies together.

## Tests actually run

- Linux Python 3.12 backend component suite: **115 tests, all passed**, with both
  `CS_BACKEND_TEST_IMAGE` and `CS_CADDY_TEST_IMAGE` explicitly set to the immutable
  references above. Includes actual packaged startup/restart, missing operator
  factory refusal, replay container ingestion, real Caddy TLS/WSS proxy and
  bootstrap routing tests; no optional image tests skipped.
- Windows isolated Python 3.14 test venv with exact pinned test dependencies:
  **115 discovered, 109 passed, 6 skipped** (POSIX permission and optional actual
  Linux/container tests). Real temporary TLS session acceptance passed.
- Shared suite: **39 tests passed on Windows and Linux**. The publisher test's
  CS-001-test push message comes from its isolated temporary Git fixture.
- Synthetic replay smoke on both hosts: health 200, readiness 503, upload 202 and
  duplicate 409. No scene image/token saved.
- Repository structure validation and diff whitespace checks passed before
  publishing; checked publisher reruns shared checks/changelog validation.
- Full Caddy configuration validated and immutable backend image built on Vultr.
- Actual public session probe: trusted HTTPS, absent/incorrect operator refusal,
  authenticated pair enrollment, unauthenticated WSS refusal, authenticated phone
  to Pi WSS relay preserving capture metadata, phone-role JPEG denial, Pi JPEG
  202 with matching frame ID, duplicate 409, expired token 401, peer disconnect
  1012 and reconnect replay 1008. Probe pairs revoked afterward.
- Production proxy restart: same certificate fingerprint; complete public probe
  passed again. Production probe passed again after laptop fallback restoration.
- Actual Windows laptop fallback rehearsed twice, including after restoration
  hardening: ephemeral laptop operator secret, local bounded backend on
  127.0.0.1:18082, reverse SSH tunnel bound to server 127.0.0.1:18081, public proxy
  switched to laptop, production backend stopped, complete public HTTPS/WSS/JPEG
  probe passed. Production backend restarted/selected; laptop server and tunnel
  terminated; final production probe passed.

The first public probe rejected a valid combined Cache-Control header because
both backend and proxy set no-store. The check now parses directives; a real TLS
regression exercises that combined header. No server authentication change or
weakened readiness check was needed.

## Limits and next steps

- `/healthz` 200. `/readyz` **503**, reporting ingestion configured and
  model_available/worker_healthy false. Docker unhealthy is expected; do not
  replace this with a constant success. The acceptance probe defaults to this
  explicit transport-only state, with a separate `--expect-ready` option.
- No real selected YOLO model/worker is loaded. CS-034 belongs to Adit; model
  installation/wiring, measured inference sizing, Gemini and Tiger Data remain
  their respective integrations. This task makes no inference accuracy claim.
- All session/JPEG acceptance used synthetic replay inputs. Real Pi/iPhone
  enrollment uses actual source/boot identities and private role credentials;
  physical capture, clock mapping, freshness and haptic/electrical acceptance
  remain separate. Sessions are process-local and require re-enrollment after a
  backend restart or fallback switch. Never deliver the operator key to devices.
- Laptop fallback covers a backend outage while Vultr SSH/proxy remains alive.
  It does not cover a complete Vultr host outage or lost Internet connection.
  Use labeled replay/disconnected demo if those dependencies fail.
- Domain registration remains deferred; the trusted IP endpoint is operational.
- PM review/merge is the remaining CS-033 integration gate. Do not mark Done or
  merge this PR automatically. Review the deployment runbook before any model,
  certificate, resource or firewall change.
