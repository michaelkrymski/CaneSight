# CS-033: Vultr deployment package

Status: the accepted CS-028 application is packaged and running **privately,
intentionally unready for live use**. The Vultr host has Ubuntu 24.04, 2 vCPUs,
4 GB RAM and 128 GB disk; it is CPU-only. Docker Engine and Compose are installed.
See the latest CS-033 handoff for image identity and test evidence. CS-029 is now
accepted, but the running ingestion image has not yet been replaced with paired
sessions. CS-032 rate-limit integration and actual model/worker readiness remain
dependencies. The user deferred domain registration; a public IP certificate now
provides the health-only HTTPS stage below.

## Public HTTPS bootstrap (health only)

Live origin: **https://64.177.50.116**. `GET /healthz` returns backend liveness
200; `GET /readyz` remains 503. All other methods/routes, including enrollment,
JPEG uploads and WebSocket upgrades, return 503 before reaching the private
backend. This is a public TLS endpoint, not the integrated Pi upload service.

The pinned Caddy 2.11.7 image uses an explicit Let's Encrypt ACME issuer with the
`shortlived` profile. Public IP certificates are supported; Caddy's default
private CA behavior for bare IPs is explicitly replaced. Certificate verification
and IP matching remain enabled on clients. No domain purchase, third-party DNS
alias, client-installed CA or insecure TLS option is needed for this stage.
The current certificate expires **2026-10-23 23:17:11 UTC**. Caddy renewal is
configured with persistent storage, but a future renewal has not been observed.

Runtime directory: `/home/linuxuser/canesight-cs033-https-bootstrap/backend/deploy`.
Its non-secret `bootstrap.env` contains `CANESIGHT_ADDRESS` and the pinned
`CADDY_IMAGE`; keep actual runtime configuration on the server. It is separate
from the private backend's `.env.private`. `compose.bootstrap.yaml` joins only
the existing private Docker network and publishes TCP 80/443 for certificate
validation and HTTPS. The existing backend stays on loopback port 18000.
The proxy does not receive application credentials. Access logging/admin API
are disabled and Docker logs rotate.

On the host, after the existing private backend is running:

```sh
cd /home/linuxuser/canesight-cs033-https-bootstrap
# Set/export the two non-secret values from bootstrap.env locally first.
python3 backend/deploy/bootstrap_check.py
sudo docker compose --env-file backend/deploy/bootstrap.env -f backend/deploy/compose.bootstrap.yaml config --quiet
sudo docker compose --env-file backend/deploy/bootstrap.env -f backend/deploy/compose.bootstrap.yaml up -d
python3 -m backend.deploy.bootstrap_probe --base https://64.177.50.116
```

The verifier checks certificate/IP trust, health 200, readiness 503 and closed
API routes. Run the same command from the operator laptop. Restart testing
preserved the same public certificate and passed both probes. Stop only this
proxy with the same Compose arguments followed by `stop` to disable public
HTTPS; preserve certificate volumes. UFW permits SSH plus TCP 80/443; no backend
or Docker administration port is opened. No new server was purchased.

Before replacing this stage with the full proxy, integrate accepted CS-029/032,
review the backend factory/image and operator secret configuration, enroll fresh
scoped sessions privately, then test authenticated HTTPS uploads/WSS, expiry and
connection loss. Do not remove the bootstrap API block just to make a Pi connect.
The full production stack below still waits on actual readiness and uses a DNS
hostname; stop the bootstrap proxy before starting another service on 80/443.
Preserve the tested HTTPS address during any later domain migration.

References: [Let's Encrypt IP certificate availability](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability),
[Caddy ACME issuer profiles](https://caddyserver.com/docs/caddyfile/directives/tls).

## Current private deployment

The server checkout is `/home/linuxuser/canesight-cs033-ingestion`. Its
`backend/deploy/.env.private` stores only the built immutable local image ID.
The private Compose service publishes **127.0.0.1:18000**, runs as UID/GID 10001
and accepts no real credentials. It uses the normal `backend.app:app` entry point,
not the replay factory. `/healthz` returns 200, `/readyz` correctly returns 503,
and missing/invalid upload credentials return 401. Docker will report unhealthy
after the startup grace period because readiness is unavailable; that is expected,
not a reason to change health checks or restart repeatedly.

Build from repository root on the authorized Docker host:

```sh
sudo docker build -f backend/deploy/Dockerfile -t canesight:cs033 .
sudo docker image inspect canesight:cs033 --format '{{.Id}}'
```

The Python 3.12 base is digest-pinned. The Dockerfile and its dedicated ignore file
allowlist only runtime code, dependencies, readiness check and shared contracts;
no checkout credentials or private assets are sent as build context. Store the
reported local image ID as `BACKEND_IMAGE` in a private environment file. From
`backend/deploy`:

```sh
sudo docker compose --env-file .env.private -f compose.private.yaml config --quiet
sudo docker compose --env-file .env.private -f compose.private.yaml up -d
python3 private_smoke.py
```

This private stack has no proxy or healthy-start gate. The independent bootstrap
proxy above exposes only its health checks. To reach the private service from
the operator laptop, keep this SSH tunnel open in a terminal:

```powershell
ssh -i "$env:USERPROFILE\.ssh\canesight_vultr" -N -L 127.0.0.1:18080:127.0.0.1:18000 linuxuser@64.177.50.116
```

Then run `python backend/deploy/private_smoke.py --base http://127.0.0.1:18080`
from the laptop checkout. Only loopback HTTP and the encrypted SSH connection are
used. Stop the tunnel when finished. This check expects unready/rejected-upload
states; use `smoke.py` only for the eventual ready HTTPS/WSS service.

For optional real image tests, set `CS_BACKEND_TEST_IMAGE` to its local immutable
image ID (or registry digest) while running the component test suite on Docker.
The tests verify startup, restart, unready Docker health, missing/invalid credentials,
and an explicitly replay-only instance's synthetic upload/duplicate rejection.
Replay credentials are ephemeral, never logged, and test containers are removed.

## Inputs needed before deployment

- An operator-approved Vultr instance, spending limit, SSH destination/key and DNS
  hostname. Do not provision a billable instance based on this file alone. Size
  the machine using actual backend/model measurements; the Compose backend caps
  are an initial CPU-only evaluation envelope (1.5 CPU, 2 GiB), not measured needs.
  GPU passthrough and model installation are outside this package.
- Linux with Docker Engine and Compose **2.30+**, Python 3.11+, registry access,
  outbound DNS/HTTPS, and adequate disk space. Follow official installation docs.
- Reviewed immutable backend and Caddy image references, including sha256 digests
  for the public stack (the private stack can use the locally built image ID).
  The backend image must contain Python, run as UID/GID 10001, start a **single**
  application worker on `0.0.0.0:8000`, and expose `/healthz` and `/readyz`.
  Model assets must already be readable in the image; the root filesystem is read
  only, with bounded writable `/tmp`. Use a separate reviewed configuration if the
  integrated backend needs writable caches or additional memory.
- The accepted CS-029 secret names and authentication flow. The smoke tool supports
  bearer headers; if CS-029 chooses another flow, adapt the tool in a follow-up
  before claiming authenticated WSS acceptance. It does not define a new contract.
- `/readyz` must return 503 until secrets, model and worker are ready; `/healthz`
  reports process liveness independently. Docker health checks call `/readyz`.
  Unhealthy status does not restart a hung-but-running container automatically.

## Prepare the server without exposing the application

On an authorized fresh Ubuntu 24.04 host, `sudo bash prepare_host.sh` installs
Docker from its official signed apt repository, Compose, Python venv support and
OpenSSL. Review it first. It does not change SSH, add users to the Docker group,
modify firewall rules or publish application ports. Use sudo for Docker commands
unless a separately approved access configuration exists. The currently prepared
host has only SSH allowed in its active UFW rules.

Use a dedicated checkout of the reviewed commit. From `backend/deploy` on Linux:

```sh
umask 077
cp .env.example .env
mkdir -p secrets
chmod 700 secrets
cp backend.env.example secrets/backend.env
chmod 600 secrets/backend.env
```

Edit `.env` locally with `CANESIGHT_DOMAIN`, `BACKEND_IMAGE` and `CADDY_IMAGE`.
Fill `secrets/backend.env` directly on the server with the exact configuration
required by the integrated backend. Never paste secrets into chat or commit them.
Compose reads the secret file in raw format, preserving literal dollar signs and
quotes. Only the backend receives it; the proxy receives the DNS hostname.
The input checker enforces presence, Linux permissions and image digests; it
cannot establish whether application credentials are valid. Missing/invalid
required credentials must fail backend readiness; rehearse that failure too.

Restrict SSH at the Vultr firewall to the operator's address. Ensure no existing
service is using ports 80/443. Point DNS A (and AAAA only if working) to the host.
When authorized to expose the service, allow inbound TCP 80 and 443 for Caddy's
certificate issuance and HTTPS. Do **not** open 8000, Docker's API, or Caddy's
admin port. The backend has no published host port; the proxy's admin API is off.
The backend's auth/rate limits must be accepted before public exposure. Docker
published ports can bypass UFW rules; use the cloud firewall as well.

## Validate and start

```sh
python3 check_config.py
docker compose --env-file .env config --quiet
docker compose --env-file .env pull
docker compose --env-file .env run --rm --no-deps proxy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose --env-file .env up -d --wait --wait-timeout 120
docker compose ps
```

The proxy waits for initial backend readiness. Caddy obtains and renews public
certificates and handles WebSocket upgrades; `/data` and `/config` persist across
restarts. Do not use self-signed certificates or disable verification for a live
demo. This full stack uses a DNS hostname; the IP bootstrap is described above.

Application logs must redact credentials and avoid raw images/precise GPS. Docker
log rotation limits disk growth; Caddy request access logging is not enabled.
Never paste `docker compose config` output, environment inspection, or logs into
issues: they can expose backend secrets. Use `config --quiet` for validation.

## Live acceptance and failure rehearsal

Obtain a short-lived Pi/dashboard credential and a session-specific events path
using the **accepted** pairing procedure. Set `CS_SMOKE_BASE_URL` to the HTTPS
origin, `CS_SMOKE_WS_PATH` to its `/v1/events` path (with session query only if the
accepted contract requires it), and `CS_SMOKE_TOKEN` locally via a secret input
mechanism. Do not put credentials in command arguments, URL queries or shell
history. Then run:

```sh
python3 smoke.py
unset CS_SMOKE_TOKEN
```

The tool verifies HTTPS liveness/readiness; rejects untrusted certificates and
hostnames; requires missing/invalid WSS tokens to receive HTTP 401/403; and requires
the configured token to receive a valid HTTP 101 upgrade. It sends no observation
payloads. It suppresses response bodies, paths and credentials from output. A
handshake pass does not prove session isolation, message validation, expiry or
model accuracy; retain CS-029/032 evidence separately.

On an isolated test instance, remove a required secret and restart the backend:
readiness must fail and the smoke command must return nonzero. Restore it, verify
fresh session pairing, and rerun. Also interrupt the model/worker and network to
verify readiness loss, reconnect behavior and source expiry. The proxy does not
make a running backend healthy or renew observation ages. Record actual results;
do not prefill passes.

Record commit, image digests, host sizing, timestamp, operator, readiness/startup
duration, HTTPS and auth outcomes, restart results and limitations in a new handoff.
Exclude tokens, raw scene images and precise location. CS-033 remains blocked until
live acceptance and the laptop fallback rehearsal have evidence accepted by PM.

## Recovery and laptop fallback

Record the previous image digests before updating. To roll back, restore the
previous reviewed references in `.env`, run `check_config.py`, `config --quiet`,
`pull`, then `up -d --wait --wait-timeout 120` and rerun the probes. Use a new paired
session after restart; process-local sessions and queued observations must reset.

For an outage, `docker compose stop` stops the service without deleting certificates.
Keep a separate, tested laptop checkout of the same backend image and contracts.
Bind that backend to loopback for operator-only tests. For phone/Pi access, use an
authorized reachable HTTPS/WSS hostname and valid certificate; rerun the same
probes and reconnect clients with fresh sessions. A laptop terminal showing
`/healthz` alone is not a rehearsed fallback. If HTTPS/auth/freshness gates fail,
use the master plan's labeled replay/disconnected demo. No crossing permission.

## Local verification

From repository root:

```sh
python -m pip install -r tests/contracts/requirements.txt
python -m pip install -r backend/requirements-test.txt
python -m unittest discover -s tests/backend -v
python scripts/validate_repo.py
python -m unittest discover -s tests -v
python -m backend.demo_replay
python scripts/render_changelog.py --check
git diff --check
```

Tests generate temporary self-signed certificates and synthetic credentials for
local fixtures only. OpenSSL is required for the TLS tests. Compose configuration
tests require the Docker CLI with Compose, but not a running engine. These tests
do not deploy the application or certify physical hardware.

To run the optional real Caddy integration test on Linux, pull a reviewed Caddy
image, resolve its digest, then set `CS_CADDY_TEST_IMAGE` to that immutable image
reference when running `python -m unittest discover -s tests/backend -v`. Docker
Engine access is required (on this host, use sudo with the environment explicitly
set). The fixture binds only loopback, creates a temporary internal CA, verifies
HTTPS/WSS and readiness failures, then removes its uniquely named test container.
This is proxy evidence; it does not establish real backend/session acceptance.

References: [Docker Compose services](https://docs.docker.com/reference/compose-file/services/),
[Docker Engine installation](https://docs.docker.com/engine/install/),
[Docker firewall behavior](https://docs.docker.com/engine/network/packet-filtering-firewalls/),
[Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https),
[Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
