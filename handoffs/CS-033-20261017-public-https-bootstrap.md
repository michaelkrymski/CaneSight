# CS-033: public IP HTTPS bootstrap

- Gavin / `gmarcialcalleja`; branch `task/CS-033-vultr-deployment`.
- Initial accepted base: `b3bb016b9ce97f197ad643a5cbe1bdb83d151377`.
- Final accepted base: `dd7c46830d869b24b0d76f490cd086c9ec5b118f` (CS-031
  merged during this checkpoint; final suite rerun against the combined tree).
- Branch reconciliation checkpoint: `c56fc09`; existing PR #11 remains draft.
- User authorized work on the public HTTPS endpoint; no new server/domain bought.
- Related integration issue: https://github.com/michaelkrymski/CaneSight/issues/20

## Live result and version

**https://64.177.50.116/healthz** is publicly reachable with default certificate
and hostname/IP verification. Actual backend liveness returns 200. Readiness
returns 503; all other methods/routes (including sessions, frames, events and
telemetry) return 503 before reaching the private upstream. API access remains
closed while CS-032 integration is pending; no public enrollment or token needed.

Caddy v2.11.7 image:
`caddy@sha256:685ae3d7c34d9b5f8caeddc5d14051db7bbd88ff1f5a2fa0c16bd8ca328fb7af`.
Explicit public ACME issuer, shortlived profile and HTTP challenge; default SNI
supports clients connecting directly to the public IP. Caddy admin/access logs
are disabled. Persistent data/config volumes retain certificate automation.
Actual renewal is configured, not yet observed.

Certificate: Let's Encrypt YE1; IP SAN `64.177.50.116`; expires
**2026-10-23 23:17:11 UTC**. Public certificate SHA256:
`7ecdadda860ec9a6321b841a171fc4a9ed3f4a7b636c990f6471f89dda0734b1`.
The same fingerprint was observed before and after proxy restart.

Existing backend remains the accepted CS-028 `backend.app:app` image:
`sha256:54004dc0e21b745d6904d594c53cc4650148a77857b464976d627ce94bd47955`,
on `127.0.0.1:18000`, intentionally unready. Its app.py SHA256 is
`d9de2088c18676a16e290de290238d84d5b0adc72112d2b7ffee4684e03e4644`.
No paired-session, inference or credential readiness is inferred from HTTPS.

## Files and host changes

New `backend/deploy/Caddyfile.bootstrap`, `compose.bootstrap.yaml`,
`bootstrap.env.example`, `bootstrap_check.py` and `bootstrap_probe.py` configure
the health-only proxy, reject invalid address/image inputs and verify public
TLS and closed API routes. `tests/backend/test_https_bootstrap.py` exercises
inputs and actual Caddy routes. Deploy README, own task evidence, new fragment
and generated changelog are updated. Accepted CS-029 main was merged normally;
README title conflict retained accepted heading and deployment link. Other task
records exactly match main and protected files are unchanged.

Runtime directory: `/home/linuxuser/canesight-cs033-https-bootstrap/backend/deploy`.
Actual `bootstrap.env` is server-local, non-secret and mode 0600. A separate
Compose project `canesight-https-bootstrap` joins `canesight-private_default`
and publishes only TCP 80/443. UFW now allows these alongside existing SSH.
Backend/Docker/admin ports remain unpublished publicly. Proxy resource/log
limits are set. Existing backend container, credentials and image were unchanged.

## Tests actually run

- Pinned Caddy validated the actual public ACME configuration before startup.
- Final Linux backend suite with `CS_CADDY_TEST_IMAGE` pinned: **74 tests discovered,
  72 passed, 2 optional actual-backend-image tests skipped**. This includes both
  real Caddy proxy tests; bootstrap uses a temporary internal CA only for its
  loopback fixture and retains the actual route configuration.
- Linux and Windows shared suite: **39 passed** (Windows via checked publishing).
- Windows bootstrap input test passed; Docker integration skipped on Windows.
- Linux replay smoke: health 200/readiness 503/upload 202/duplicate 409.
- Real public `python -m backend.deploy.bootstrap_probe --base https://64.177.50.116`
  passed from laptop and server with normal trust stores; health 200, readiness
  503, root/sessions/upload/events 503; no-store cache headers. No insecure flag.
- Proxy restart and repeat laptop probe passed with unchanged public certificate.
- Repository/changelog/whitespace checks run through checked task publishing.

No private image, API token or key is written to Git/logs. Only synthetic frames
were used in software fixtures; no real Pi JPEG upload has occurred in this work.

## Next steps and rollback

Stop only the bootstrap Compose service with its env/file arguments and `stop`
to disable public HTTPS; preserve certificate volumes. The private backend stays
running. A later full stack must stop this proxy before using 80/443.

CS-029 #14 is accepted. Integrate its `backend.server:create_session_app`, reviewed
secret setup and accepted CS-032 quotas into a new immutable image before opening
public API routes. CS-031 #19 is now accepted; selected
model readiness and full authenticated WSS, laptop fallback and issue #20 real
Pi upload/expired-token/connection-loss acceptance remain pending. Keep 202 as
ingestion only. No motor/hardware, YOLO, capture-age or crossing claim is made.

References: https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability
and https://caddyserver.com/docs/caddyfile/directives/tls .
