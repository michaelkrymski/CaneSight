# CaneSight backend — CS-028 / CS-029

The FastAPI skeleton implements `GET /healthz`, `GET /readyz` and `POST /v1/frames`
against the accepted `shared/protocol/v1` contract. It does not run inference or
produce guidance. No hardware is needed for the software tests or replay smoke.

## Install and test (Python 3.12+)

From the repository root, preferably in a virtual environment:

```text
python -m pip install -r backend/requirements-test.txt
python -m unittest discover -s tests/backend -v
python -m unittest discover -s tests -v
```

The required repository CI installs backend test dependencies, explicitly runs
both suites, and rehearses a real loopback HTTP
upload/duplicate rejection using `backend.demo_replay`. Run both commands locally;
root discovery alone does not cover backend tests. The separate roots avoid the
tests/backend package shadowing the application backend package. This CI amendment
is covered by `decisions/CR-CS-028-backend-ci.md`; no checks are disabled.

## Default server

```text
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

Liveness returns 200. Readiness returns 503 until enrollment, selected model
availability and worker health are supplied. The default server has no credentials
and rejects uploads. It does not infer readiness from a healthy process or from an
accepted upload. Use one worker: enrollment, replay guards and intake are in memory.

## Explicit software-only replay

The simplest rehearsal generates an ephemeral token, starts a loopback server,
uploads one generated JPEG, verifies duplicate rejection, then stops the server:

```text
python -m backend.demo_replay
```

To keep a replay target running for manual integration instead:

In PowerShell, generate a temporary token and start the replay factory:

```powershell
$env:CANESIGHT_REPLAY_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
python -m uvicorn backend.replay:create_replay_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

In another shell with the same private environment token, run
`python -m backend.smoke_replay`. Alternatively run the smoke as a child of the
same shell while the server runs in another terminal inheriting that environment.
Never paste the token into a prompt, commit or log. The grant expires after five
minutes. The target accepts only the fixture's `demo-session` / `pi-camera-1` /
`pi-boot-1` identity in **replay** mode. Readiness deliberately stays 503 because
there is no model or inference worker. A valid generated JPEG receives 202 with
its original frame ID. A second identical upload receives 409.

## Ingestion behavior and adapter boundary

Send multipart parts `metadata` (JSON text, <=8192 UTF-8 bytes) and `image`
(JPEG file). The endpoint limits the entire request to 1,024,000 bytes, including
overhead, whether or not Content-Length is supplied. JPEG bytes are limited to
1,000,000; decoded dimensions to 1920x1080, checked before full raster decode.
Both byte count and dimensions must match metadata. JSON nesting is limited to
12; duplicate keys, nonfinite values, unknown fields and unsupported versions
are rejected. Four upload slots and a five-second body-read deadline bound
concurrent intake. Decoding runs off the event loop.

`SourceGrant`/`FrameIngress` are trusted injection points for CS-029 enrollment,
not a public enrollment endpoint. Fixed short-lived grants bind role, session,
source, boot and live/replay mode. Uploads cannot authorize a new epoch. Rejected
images never advance sequence state. Accepted frames preserve every capture field
unchanged: the 202 acknowledgment means ingestion only, not fresh or inferred.
No raw device timestamps are compared to server monotonic time.

The intake retains at most one JPEG and two original metadata records per source
in memory (at most 16 sources), without writing images to disk. Frame-ID history
is capped at 4096 per source epoch; at that bound create a new authorized session.
Expired grants are purged when intake/auth/readiness next runs. Metadata and image
retention are temporary; restart the process to clear all buffers. Do not mutate
grants or reuse the same session/boot after restart in a live integration: CS-029
must provide new authorized epochs and shared lifecycle/rotation before live use.

CS-031 replaces the intake seam with a bounded inference worker, while retaining
original lineage. `dependency_health` must report actual `model_available` and
`worker_healthy` booleans from those components. Tests inject synthetic health;
the shipped replay server never declares a model ready. TLS termination, paired
session issuance, quotas and distributed state remain CS-029/032/033 work. This
component is a loopback software scaffold, not a deployed or complete live system.

## Paired HTTPS/WSS sessions — CS-029

See [paired sessions](SESSIONS.md) for the operator-created session API, scoped
phone/Pi bearer credentials, WebSocket transport, teardown rules and TLS setup.
The new factory is `backend.server:create_session_app`. The legacy CS-028 default
and explicit replay factory retain their existing behavior; they do not silently
enable paired sessions. No inference/model readiness is enabled by pairing.

## Handoff to CS-029 and CS-033

After PR #9 is reviewed and merged, pull accepted main before starting the
CS-029 branch. Its ownership is already assigned to Adit. Extend `create_app`,
inject/replace `FrameIngress` through its `authenticate`/`accept`/`configured`
boundary, and provide a real `dependency_health` callback. Preserve all CS-028
endpoint tests. Add paired session issuance, credential expiry/rotation, source
epoch lifecycle and isolated phone/Pi WebSocket routes as CS-029 work; the fixed
replay grant is not that implementation. Do not start a second incompatible app.

For Gavin's CS-033 package: this is the real ASGI entry point
`backend.app:app`, Python 3.12+, one worker, port 8000. In a container use
`python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --workers 1`.
Install `backend/requirements.txt` and include the repository's `shared/` tree
in the application image. Keep the host port private behind the reviewed proxy.
The default app returns `/healthz` 200, `/readyz` 503 and upload 401; those are
intentional fail-closed states before trusted enrollment/model/worker integration.
Never change readiness to a constant 200 to satisfy deployment health checks.
Image build/digest, real TLS/WSS and server deployment remain Gavin's task;
authenticated service acceptance still depends on CS-029 and CS-032. No host
changes, live credentials, Docker image or cloud deployment were created here.

## CS-033 deployment

See [deploy/README.md](deploy/README.md) for image packaging, private host tests,
HTTPS/WSS configuration and remaining deployment acceptance.
