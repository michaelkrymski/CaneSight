# CS-033 accepted application packaging preparation

Task: CS-033. Owner: gmarcialcalleja.
Branch: task/CS-033-backend-refresh. Existing PR: https://github.com/michaelkrymski/CaneSight/pull/93.
Initial accepted base: a239e221b1d51d7673a78e8fb84e6df274b36e39.
Accepted composition/main integrated: 5234f04135270eedcfd65f520fd179a49af40ab5.
Starting published evidence head: 7c36b35ec55ffeb13f32044a59ab59b42406d63e.

The human requested task-by-task integration preparation while CS-016 completes.
Mila's CS-039 composition PR #94 merged during preparation. Adopt that accepted
backend.context.deployment factory; the initial duplicate uncommitted composition
was removed. No CS-039/040/041/042 service implementation, task requirements,
shared contract or default native factory is changed by this checkpoint.

## Changed files

- backend/deploy/Dockerfile.application and exact allowlist: package all required
  accepted context/telemetry modules and static dashboard assets over the reviewed
  vision image; install the accepted pinned DB adapter; runtime import smoke;
  UID 10001; no weights/images/private configuration or credentials in context.
- compose.application.yaml and application.env.example: explicit accepted
  CANESIGHT_CONTEXT_BASE sessions/dashboard/logging selection. Append private
  application env only to backend, retain native operator env, model mount,
  loopback/TLS proxy/resource restrictions and optional read-only DB config mount.
- build_application.py: exact installed base image ID, content-named local tag
  verified before/after build, refuse mutable bases/production tags/poisoned base
  tag. Docker FROM interprets raw sha256 IDs as repository names: initial direct
  build failed; verified local-tag helper succeeds. No container/service commands.
- Three new tests/backend/test_application_composition.py packaging/provenance/
  Compose cases. Accepted tests/context/test_deployment.py already exercises all
  three native factories, same session authority, native/context/viewer roles,
  provider failure and native transport. Reuse it without copying service logic.
- Deploy README, task runtime evidence, new handoff/fragment/build evidence.

## Actual verification

Three focused packaging tests passed. All six accepted composition tests passed
with synthetic images and fake provider/writer/model. On this Conda/Windows host,
standalone context tests require initializing normal SSL context before their
clear-environment fixture; this loads OpenSSL without changing TLS verification.
The root shared suite initializes SSL normally. No accepted test/source was edited.
Full backend suite: 131 tests run, OK with 7 optional Windows/container/runtime
skips. Checked publishing also runs shared structure/test/log/whitespace checks.

Docker Compose preserves exactly two backend env files, 2 GiB/1.5 CPU bounds,
read-only root, UID 10001, loopback command and verified read-only model mount.
Proxy receives no private env file. Config validation uses no-env-resolution,
without reading or printing actual private configuration.

Built on existing Vultr host in the dedicated staging directory
/home/linuxuser/canesight-cs033-application-prep-20261018. Only explicitly named
source/assets were transferred; no scene, environment, credential or weight.
Exact vision base: sha256:07c9d75f045b1eee9c31fc549c9e6cacdd07db0ce951cb61f91845415408f94a.
Final application image: sha256:b9a4679c8422564b9388116bc0ed04776bf9aec5e4431313e65f5b802008f3c9.
Runtime import smoke passed. Earlier unused preparation image e7c1888 was built
before accepted composition landed and is not the final candidate. No candidate
container started; active production image/configuration/sessions are unchanged.

## Next steps and limits

Review final PR #93 image/overlay/config before activation. Install server-only
current Gemini key/model; exact HTTPS origin for dashboard; private DB config
readable only by UID 10001 for logging. Logging stays per-session consented and
default-off. Select the accepted composition matching required features, quietly
validate, preserve prior image/config and certificate volumes, activate/re-enroll
only after review, and run feature-specific public probes. Generic native health
cannot prove Gemini/Tiger Data/dashboard or Pi-to-speaker success.

This is prepared packaging, not public rollout, live provider/database proof,
physical phone/Pi/motor acceptance or task completion. Earlier public backend
verification in this PR applies to its recorded active image, not this optional
application image. CS-016/017 phone/clock integration and CS-009/010 hardware gates
remain independent. No automatic deploy/reenrollment/arming is added.
