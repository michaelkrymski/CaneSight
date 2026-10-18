# CS-039 integrated context deployment preparation

Owner: bondmila. Branch: task/CS-039-deployment-composition.
Starting prior task head: cb71eb134c546632cae6e0bd04e04c156d109b30.
Base accepted main: a239e22 (full SHA available in branch history).
Read AGENTS, team workflow, master plan, own task/dependencies and deployment
factory/packaging guidance. Ownership remains the accepted bondmila assignment.

## Scope and changes

- backend/context/server.py extracts configured_service() so both standalone and
  integrated factories use the same model/key validation and ContextService.
  Existing standalone/default backend factories and HTTP contracts unchanged.
- backend/context/deployment.py explicitly selects exactly one accepted native
  sessions/vision, dashboard, or logging base. No dynamic arbitrary factory path,
  fallback mode or second manager. install_context nests the existing lifespan.
  Loopback-only launcher reuses existing single-worker transport/proxy bounds.
- backend/context/Dockerfile.context and Docker-specific ignore: five explicit
  context modules only, no extra dependencies/model/assets/private config. Parent
  must be a reviewed digest and contain the selected existing runtime. Inherits
  native healthcheck, sets loopback port 18083 and UID 10001. No secrets in build.
- backend/context/DEPLOYMENT.md and SERVICE.md pointer: concrete image/service
  command/env proposal, preservation requirements, startup verification failure
  behavior, public checks, restart/fresh enrollments/consent and rollback.
- tests/context/test_deployment.py: six meaningful composition/lifecycle cases.
- Own runtime task, new changelog fragment and generated log.

## Tests actually run

Python 3.13/macOS: all 106 context tests passed. Backend suite: 128 ran, 119
passed and nine existing optional/environment skips. Tests instantiate actual
accepted base factories with synthetic provider, logging writer and model worker.
They verify shared native credentials/context, viewer role separation/login,
logging consent/start/stop, model readiness and image submission, WSS heartbeat
relay during provider verification failure, native transport limits, invalid
selection/missing-key refusal and worker shutdown. ASGI TestClient transport is
local, not real public TLS/device/provider acceptance. Existing context transport
and provider/process regression cases also run in the context suite.

Shared checked publisher runs repository/root/generated-log validation before
commit/push. Inspect exact-head CI and Michael feedback after publication.

## Honest limits / next action

Docker command is unavailable on this host. No image was built/smoked, no digest
claimed, no credentials transferred/configured and no real Gemini call made in
this checkpoint. No live service/proxy/compose/mount/restart or native-session
mutation was performed. No Pi, physical audio, model accuracy or Done claim.

Task scope excludes backend/deploy and other owners' code. The proposal stays
inside backend/context; Michael/deployment owner must choose the actual current
base and reviewed parent/image digest, approve the concrete service command/
private environment changes, build/smoke and perform coordinated restart and
public regression tests. It must preserve current dashboard/logging/model/mounts
rather than replace the service with standalone context. Re-enroll after restart.
This PR is software review preparation, not an authorization to change deployment
files or a claim that merely merging it activates Gemini. Provider startup failure
keeps native service operational; context availability is separate from /readyz.

Full accepted base: a239e221b1d51d7673a78e8fb84e6df274b36e39.
Review PR: https://github.com/michaelkrymski/CaneSight/pull/94.
Checked publication passed all 228 shared/root tests and repository/governance/
generated-log checks. Current-head CI is inspected after final evidence push.
