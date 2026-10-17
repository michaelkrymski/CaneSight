# CS-033: deployment preparation handoff

- Human: Gavin / `gmarcialcalleja`.
- Base: `628ef17b570831758338226f47f1cf11a7dd8522` (accepted main, includes merged claim #2).
- Branch: `codex/CS-033-vultr-deployment`.
- PR: implementation draft; link recorded in the task runtime field after creation.
- Goal: prepare authenticated HTTPS/WSS deployment, readiness and secret configuration,
  with laptop fallback instructions. Live acceptance remains outstanding.

## Changes

- `backend/deploy/compose.yaml`, `Caddyfile`: private backend, Caddy HTTPS/WSS,
  non-root/read-only backend, readiness dependency, persistent certificate volumes,
  log rotation and raw server-side environment file. Image digests must be supplied.
- `backend/deploy/.env.example`, `backend.env.example`, `check_config.py`: empty
  templates and fail-closed input validation; no credential names invented for CS-029.
- `backend/deploy/readiness.py`, `smoke.py`: local readiness and TLS/WSS handshake
  checks, missing/invalid credential rejection, no scene payloads or secret output.
- `backend/deploy/README.md`, `backend/README.md`: prerequisites, firewall/DNS,
  startup, acceptance, rollback and laptop fallback procedure.
- `tests/backend/__init__.py`, `test_deployment.py`: synthetic configuration,
  actual local TLS handshakes, rejection cases and Compose config tests.
- CS-033 runtime fields, new changelog fragment and rendered `CHANGELOG.md`.

## Tests actually run

- `python -m unittest discover -s tests -v`: 32 discovered, 31 passed,
  one POSIX-permissions test skipped on Windows (Python 3.14.7).
- TLS fixtures generate ephemeral keys/certificates with OpenSSL, test trusted
  success, untrusted/mismatched certificates, unready status, anonymous access,
  malformed upgrades, credential injection and safe CLI errors.
- Compose CLI v5.5.1 configuration test passed without Docker Engine, checking
  private backend ports, environment isolation, readiness gate and hardening.
- `python scripts/validate_repo.py`: passed.
- `python scripts/render_changelog.py --check`: passed after rendering.
- `git diff --check`: passed.

## Limits and blockers

User confirmed no Vultr server exists. Spending limit, instance sizing, SSH and DNS
inputs are pending. CS-029/032 are backlog and the accepted backend is a placeholder,
so no reviewed backend image or accepted authentication flow exists yet. The smoke
tool supports bearer headers conditionally; reconcile it with the final CS-029
contract before acceptance. It verifies upgrades, not session authorization or
message behavior. No secrets or private scene data were used.

Docker Engine is not running locally. Caddy syntax/runtime, container startup,
Vultr networking, public certificate issuance, real secrets/readiness failures,
restart behavior and the laptop fallback have not been tested. The runbook lists
required live checks; it does not assert their success. No electrical/device tests.

## Next action

PM reviews the draft preparation. After approved server budget/DNS and accepted
backend image/auth/rate-limit integration, provision the authorized instance,
validate Caddy/container startup and run the live acceptance/fallback rehearsal.
Record actual evidence in a new handoff. Keep task blocked until those inputs exist;
do not mark Done without accepted merged evidence. Never merge or push main here.
