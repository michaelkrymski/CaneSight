# CS-033: actual Vultr host preparation

- Human: Gavin / `gmarcialcalleja`.
- Task branch: `task/CS-033-vultr-deployment`; successor draft to PR #6.
- The newly accepted publishing helper requires `task/` or `claim/` names, so the
  earlier `codex/` branch was renamed locally and published as a successor without
  force-pushing; the old PR is retained as closed history. New PR URL is recorded
  in the task runtime field after creation.
- Original implementation base: `628ef17b570831758338226f47f1cf11a7dd8522`.
- Accepted main integrated for current governance/contracts:
  `1ed21a63fbea4e50241dd975e728f4321b9410a6`, task-branch checkpoint `22d214c`.
- The prior preparation handoff is historical; this new record supersedes its
  statements about missing server/runtime tests, without altering that record.

## Observed host and operations

SSH as `linuxuser` works after the user unlocked the private key locally through
Windows SSH Agent. No private key/passphrase was transmitted to the server or Git.
Ubuntu identifies as 24.04.5 LTS; measured resources are two vCPUs, 3.8 GiB usable
RAM, 128 GB virtual disk and 8 GiB swap. No NVIDIA device or nvidia-smi is present.
The deployed server is the CPU plan, not the L40S option discussed earlier.

Ran `sudo bash prepare_host.sh` after inspection. It installs Docker Engine
29.9.1, Compose 5.6.0, Python venv tooling and OpenSSL using Docker's signed
official apt repository. Docker is enabled. UFW was already active and remains
SSH-only; no HTTP/HTTPS, debug, Docker API or Caddy admin ports were opened.

Copied a task-specific code snapshot to
`/home/linuxuser/canesight-cs033-host-test` without GitHub credentials. Its venv
contains the accepted contract test dependencies. No actual backend secrets were
configured. Pulled the official Caddy image, then used its immutable reference:

`caddy@sha256:685ae3d7c34d9b5f8caeddc5d14051db7bbd88ff1f5a2fa0c16bd8ca328fb7af`

Reported Caddy version: 2.11.7. The temporary proxy used internal test certificates,
synthetic credentials, host loopback binding and a fixture upstream. It was removed
after verification; `docker ps` showed no running containers. `ss` showed only SSH
public listeners (plus loopback DNS).

## Files changed

- `backend/deploy/prepare_host.sh`: reproducible Ubuntu host setup, no auth/firewall changes.
- `tests/backend/test_caddy_proxy.py`: optional real TLS proxy integration and cleanup.
- `backend/deploy/README.md`: current state, host setup and integration-test procedure.
- CS-033 runtime fields, this handoff, a new immutable fragment and generated log.

## Tests actually run

- Server: `CS_CADDY_TEST_IMAGE=<digest> .venv/bin/python -m unittest discover -s tests -v`
  under sudo: **56 passed**, zero skips. This includes protocol/governance, Compose
  configuration, real Caddy HTTPS health/readiness and authenticated WSS upgrades;
  missing/invalid credentials reject, and fixture readiness failure propagates.
- Server: digest-pinned `caddy validate` on the production Caddyfile with a reserved
  `.invalid` test hostname: valid configuration. This did not request a public cert.
- Local Windows after installing accepted `tests/contracts/requirements.txt`:
  **56 discovered, 54 passed, two skips** (POSIX permissions and opt-in real Caddy).
  The initial local contract import failed because jsonschema was not installed;
  installing the accepted dependency resolved it without modifying the contract.
- `python scripts/validate_repo.py`, generated-changelog verification and
  `git diff --check`: passed before publishing.
- `bash -n backend/deploy/prepare_host.sh`: passed on the host.

## Remaining acceptance

User confirmed no domain is registered. CS-029 and CS-032 are still backlog; accepted
main contains only a backend README. CS-028 now belongs to Adit; do not implement his
task in this checkout. CS-034 has no merged ownership for Gavin. No model installed.
No live application, valid public certificate, real secret validation, application
restart/expiry/session-isolation evidence, laptop fallback, Gemini/Tiger Data or
electrical/device verification is claimed.

Next: obtain DNS, wait for a reviewed runnable backend image and accepted auth/rate
limits, then configure and test the actual deployment. Keep CS-033 blocked/draft
until those inputs exist. Stop at review; do not merge or push main.
