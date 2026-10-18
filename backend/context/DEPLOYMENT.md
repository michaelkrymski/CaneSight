# CS-039 Gemini integration: image and rollout proposal

This packages accepted context on an explicitly selected accepted backend. It
changes no deployed service, proxy, mounts, credentials or `backend/deploy/` files.
The deployment owner must review the final image/configuration before activation.

## One app and one native session authority

Set `CANESIGHT_CONTEXT_BASE` explicitly to the required existing service:

- `sessions`: accepted session/vision factory, including its configured model.
- `dashboard`: accepted dashboard/vision factory and viewer authorization.
- `logging`: accepted event-logging/dashboard/vision factory and its private DB
  configuration, consent, retention/deletion and worker lifecycle.

`backend.context.deployment.create_deployment_app` calls exactly one selected
factory, then installs context against that app's `state.sessions`. It does not
create another manager or mount an independent context server. Existing native
routes, model readiness, weights, viewer/DB roles and lifespan are retained.
Invalid selection or missing configuration fails; no fallback drops features.
Choose based on the actual active service, not assumptions about merged PRs.

Configure the existing server-only private environment with `GEMINI_API_KEY`, an
explicit `CANESIGHT_GEMINI_MODEL`, and `CANESIGHT_CONTEXT_BASE`. Keep the operator
secret, weights and required dashboard/DB settings intact. A key previously
shared in chat is not evidence that the runtime is configured. No key is included
in this source, image recipe or command examples. Do not put it on the Pi/phone,
in a build argument, command-line argument, PR or report.

Context startup verification retains its eight-second budget. A provider/quota/
verification failure disables `/v1/context` while native health, configured vision
readiness, session enrollment, WSS and viewer/logging routes remain available.
It does not turn model/source readiness green. Restart is needed after correcting
failed context startup verification; no automatic provider retry is installed.

## Image layer prepared for review

Build from repository root using the exact reviewed immutable current parent
image, including the native/vision/dashboard/logging modules needed by selection:

```sh
docker build --file backend/context/Dockerfile.context \
  --build-arg BASE_IMAGE=REVIEWED_PARENT_AT_SHA256 \
  --tag canesight-context:review .
docker run --rm --network none --entrypoint python canesight-context:review \
  -c 'from backend.context.deployment import create_deployment_app'
```

Replace the placeholder with a real `repository@sha256:...` reference. The recipe
refuses mutable parent tags. It copies only five runtime context modules, and its
Docker-specific ignore file excludes everything else from the context. No image,
model, private configuration, edge/audio implementation or deployment environment
is copied. Dependencies come from the reviewed parent. It retains UID 10001,
loopback port 18083, parent healthcheck and existing transport bounds. Build and
inspect/pin the resulting digest; verify the selected parent really contains the
required runtime, assets and optional DB adapter.

Docker is unavailable on this development host: no build/import/container smoke
or image digest is claimed here. Source-level factory/lifespan tests are separate
from those pending checks. The command above is a procedure, not an executed pass.

## Concrete deployment-owner changes to review

Proposed changes to the existing backend service (not applied by this PR):

```yaml
services:
  backend:
    image: REVIEWED_CONTEXT_IMAGE_AT_SHA256
    command: [python, -m, backend.context.deployment, --host, '127.0.0.1', --port, '18083', --forwarded-allow-ips, '127.0.0.1']
    environment:
      CANESIGHT_CONTEXT_BASE: SELECT_ACTUAL_EXISTING_BASE
      CANESIGHT_GEMINI_MODEL: SELECT_VERIFIED_MODEL
```

This is a partial overlay, not a replacement compose file. Preserve the existing
private env file/operator secret, weights/DB/CA mounts and paths, dashboard origin,
loopback bind, TLS proxy and trusted-forwarder mapping, resource limits, read-only
filesystem/tmpfs, UID, healthcheck, Caddy certificate volumes and native transport
settings. Inspect the actual private resolved composition before restart; do not
publish its environment output. A parent-only image update is insufficient if
compose still overrides the command with the old factory.

The accepted full Caddyfile proxies the origin to the loopback backend, including
context paths; its bootstrap-only health proxy does not. Confirm the actually
running configuration, without exposing debug/admin ports or disabling TLS.
No Caddy adjustment is prescribed without that inspection.

## Verification and restart sequence

1. On the deployment owner's trusted server environment, run the existing neutral
   generated-image model probe with the runtime key and chosen model:
   `python -m backend.context.probe --model SELECT_VERIFIED_MODEL`. No real scene
   is required. This checks current account/model availability, not accuracy.
2. Build/smoke the candidate, pin its image digest, and test its exact selected
   factory/model/assets/private mount paths. Verify the inherited `/readyz` remains
   native model readiness; context availability is a separate authenticated check.
3. Agree a restart window. Stop the old process gracefully, start the reviewed
   image/command, and enroll fresh phone/Pi sessions. In-memory sessions, viewers
   and logging consent are not preserved across this restart. Keep grants private.
4. Run accepted `backend.deploy.session_probe` and `vision_probe` against verified
   public HTTPS/WSS, with model expectations matching the candidate. Recheck
   dashboard login and logging consent/deletion receipts if those features were
   active. These are deployment-owner tests, not automatically run by this PR.
5. With a fresh Pi-role grant, verify `GET /v1/context/status`, rejection of missing/
   phone/viewer credentials and a consented generated-image POST. Use the exact
   enrolled session/source/boot/replay frame binding. The response must preserve
   original metadata, `capture_age_bounded:false` and only uncertain object labels.
   A successful context response must not change native vision/policy readiness.
6. Test provider denial/timeouts, cancellation, session revocation, old/mismatched
   frames and late results while native WSS/vision remains operational. Do not
   send real surroundings until explicit scene-sharing consent is obtained.
7. Finally perform the real consented Pi-camera/button -> backend/Gemini -> speaker
   test with the phone/freshness prerequisites and recorded audible cancellation.
   Deployment success alone is not hardware or model-accuracy acceptance.

Rollback selects the previous reviewed image AND command, preserving existing
mounts/proxy/resource configuration. Re-enroll after rollback as well. Disabling
context does not imply stored logging rows/provider-side data have been erased.
No automatic restart, deployment, credential transfer or background task is added.
