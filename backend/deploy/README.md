# CS-033: authenticated Vultr deployment

The deployed origin is **https://64.177.50.116**. Accepted CS-029 sessions and
CS-032 admission limits run behind Caddy with verified HTTPS/WSS. Synthetic
replay acceptance covers operator enrollment, role-scoped JPEG upload, WSS
relay, duplicate/expired credentials, and disconnect/reconnect behavior.

`/healthz` returns 200. `/readyz` deliberately returns 503: ingestion is configured,
but a real selected model and inference worker are unavailable. Docker therefore
reports the backend as unhealthy after its startup grace period. This does not
restart the process automatically. Enrollment and authenticated transport work
before model readiness; the proxy starts after the backend process starts, rather
than waiting for a readiness condition that enrollment itself needs. This is
transport evidence, not live perception or hardware acceptance.

## Runtime and exposure

The authorized existing Vultr host is Ubuntu 24.04, 2 vCPUs, approximately 4 GiB
RAM, 128 GB disk, CPU-only. No replacement instance or domain was purchased.
Docker Engine and Compose are installed; Docker commands require sudo.

Current runtime directory:
`/home/linuxuser/canesight-cs033-authenticated/backend/deploy`.
Its `.env` holds non-secret origin, upstream, immutable image references and
certificate volume names. `secrets/backend.env` contains the operator credential,
with directory mode 0700 and file mode 0600. The credential stays on the server.
Only the backend receives it; Caddy does not receive application credentials.
Do not paste environment files, resolved Compose configuration or enrollment
responses into chat, issues, logs or Git.

The production Compose file requires Linux host networking. The backend's
bounded single-process launcher binds **127.0.0.1:18083**, trusts forwarded
headers only from 127.0.0.1, and runs as UID/GID 10001 with a read-only filesystem,
dropped capabilities, bounded temporary storage, CPU, memory, process and log
limits. Host networking gives containers access to host network interfaces;
protection of the API port depends on this explicit loopback bind. Caddy alone
listens publicly on TCP 80/443; its admin API and request access logs are disabled.
UFW permits SSH and TCP 80/443; backend ports remain closed publicly.

Both images are immutable; the Dockerfile base is digest-pinned and its build
context explicitly allowlists runtime code and shared contracts. No environment
files, private keys or scene images enter the build context. Compose overrides
the image's unconfigured ingestion default with `python -m backend.server`, which
refuses to start without a valid operator credential. Readiness checks still use
actual `/readyz`, not liveness.

The proxy uses an explicit Let's Encrypt ACME issuer with the `shortlived`
profile and HTTP validation. Clients retain certificate and hostname/IP
verification. The existing certificate expires **2026-10-23 23:17:11 UTC**;
renewal is configured but a future renewal has not yet been observed. The existing
`canesight-https-bootstrap_caddy_data` and `_caddy_config` volumes are reused, and
proxy restart preserved the certificate. Never delete these volumes during a
restart or rollback. Domain registration remains deferred.

The previous health-only bootstrap proxy is stopped, with its configuration and
volumes preserved. The previous CS-028 private ingestion container remains on
127.0.0.1:18000 for rollback. `compose.bootstrap.yaml`, `bootstrap_probe.py`,
`compose.private.yaml` and `private_smoke.py` describe these earlier stages;
they are not the active authenticated deployment.

## Build and configure

Use an authorized Linux host and dedicated checkout of the reviewed task commit.
Install the backend test requirements into a dedicated venv for acceptance probes.
The host preparation script installs Docker from its official signed repository,
Compose and Python venv support. It does not provision an instance or alter SSH
or firewall access; review it before running on another host.

From repository root:

```sh
sudo docker build -f backend/deploy/Dockerfile -t canesight:cs033 .
sudo docker image inspect canesight:cs033 --format '{{.Id}}'
cd backend/deploy
umask 077
cp .env.example .env
mkdir -p secrets
chmod 700 secrets
cp backend.env.example secrets/backend.env
chmod 600 secrets/backend.env
```

Set `.env` locally with a public IPv4 address or DNS hostname and reviewed image
references: either a local `sha256:<64 hex>` image ID or registry `@sha256:` digest.
Use the existing certificate volume names when upgrading the bootstrap stage.
Generate a cryptographically random operator credential directly into the private
file, using the accepted `CANESIGHT_OPERATOR_TOKEN` configuration (32–128 ASCII
characters, no whitespace). Do not enter actual credentials as shell arguments.
Compose raw-format environment files require Compose 2.30 or later.

From `backend/deploy`:

```sh
python3 check_config.py
sudo docker compose --env-file .env config --quiet
sudo docker compose --env-file .env run --rm --no-deps proxy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo docker compose --env-file .env up -d backend
# Verify private liveness; ensure any previous proxy on 80/443 is stopped.
sudo docker compose --env-file .env up -d proxy
```

Do not use `up --wait` while a selected model/worker is unavailable: readiness
must remain false. Do not change it to 200 to satisfy Docker health. Model asset
installation, a runtime worker factory, GPU passthrough, Gemini credentials and
Tiger Data configuration require their respective accepted implementations.
The current image does not provide them. Additional caches or model memory need
a reviewed deployment configuration and actual measurements.

## Verify the live service

From the checkout root, using the dedicated test venv:

```sh
python -m backend.deploy.session_probe --base https://64.177.50.116 --operator-file backend/deploy/secrets/backend.env
```

The probe uses the private operator file, creates fresh short-lived replay pairs,
and verifies trusted HTTPS, absent/incorrect credentials, authenticated WSS relay,
role separation, synthetic JPEG acknowledgment, duplicate rejection, expiry,
peer interruption, and reconnect sequence protection. It revokes its test sessions
and prints only boolean results and readiness checks. No credentials, images or
session identities are printed. Tests intentionally preserve capture metadata;
they do not establish real device clock mapping or freshness acceptance.

By default the probe requires readiness 503, matching this model-unconfigured
transport deployment. Only add `--expect-ready` after a real model and worker are
configured and available. `smoke.py` remains a separate strict readiness/handshake
probe; its 200 requirement must not be weakened to hide missing perception.

Live devices use the accepted flow in `backend/SESSIONS.md`: the operator enrolls
the actual source and boot identities in **live** mode over authenticated HTTPS,
then delivers each role's token through a private configuration channel. Never
send the operator token to a Pi or phone. Restart loses process-local pairs, so
re-enroll after restart. Current evidence uses synthetic replay inputs; physical
Pi/iPhone uploads and inference are not claimed.

## Rehearsed laptop fallback

From the operator laptop checkout with backend test requirements installed:

```powershell
python -m backend.deploy.laptop_fallback --base https://64.177.50.116 --ssh-host linuxuser@64.177.50.116 --identity "$env:USERPROFILE\.ssh\canesight_vultr" --remote-directory /home/linuxuser/canesight-cs033-authenticated/backend/deploy --simulate-backend-outage
```

The helper starts a bounded laptop backend on 127.0.0.1:18082 with an ephemeral
operator key, opens a loopback-only reverse SSH forward to Vultr 127.0.0.1:18081,
and switches Caddy to that upstream. It stops the production backend when the
outage flag is supplied, then runs the complete verified HTTPS/WSS/JPEG probe
against the laptop. Its distinct operator credential proves requests reached
the laptop. Finally it restarts and selects the production backend, then stops
the laptop child process and SSH tunnel. This rehearsal passed with the actual
Windows laptop and Vultr proxy. Run the normal production probe afterward.

`switch_upstream.py` accepts only `production` or `laptop`, checks target liveness
before changing the proxy, and restores previous configuration on a Compose
failure. It suppresses private command output. If a fallback rehearsal fails,
verify restoration directly on the server before reconnecting devices:

```sh
python3 backend/deploy/switch_upstream.py --target production
```

This fallback requires the Vultr SSH/proxy host to remain reachable; it covers a
backend process outage, not a complete Vultr host or Internet outage. Actual
devices require fresh pairing with the selected backend. If the public host or
HTTPS/auth gates fail, use the master plan's labeled replay/disconnected demo.

For a deployment rollback, stop the active full proxy and restart the preserved
health-only bootstrap proxy, retaining its certificate volumes. That disables
public enrollment, uploads and WSS with 503 while preserving public health TLS.
For image rollback, restore the previous reviewed immutable reference, validate
configuration, restart, re-enroll and rerun probes. Do not print secret config.

## Verification and evidence

```sh
python -m unittest discover -s tests/backend -q
python scripts/validate_repo.py
python -m unittest discover -s tests -q
python -m backend.demo_replay
python scripts/render_changelog.py --check
git diff --check
```

On a Docker-enabled Linux host, set `CS_BACKEND_TEST_IMAGE` and
`CS_CADDY_TEST_IMAGE` to the immutable built/backend and reviewed Caddy references
to enable real-container integration tests. These exercise startup, missing
operator refusal, restart, readiness failures, real TLS proxying and replay
uploads. Temporary local test certificates are fixture-only; the public probe
uses normal system trust. The latest CS-033 handoff records exact results and
image identities. Review is not Done; Michael accepts the task by review/merge.

References: [Let's Encrypt IP certificates](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability),
[Caddy TLS configuration](https://caddyserver.com/docs/caddyfile/directives/tls),
[Docker Compose services](https://docs.docker.com/reference/compose-file/services/).
