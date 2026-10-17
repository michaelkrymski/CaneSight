# CaneSight ingestion — CS-028

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

The backend suite is a separate explicit discovery root because accepted CI
installs only the contract dependency. Run both commands; root discovery alone
does not test the backend. Adding backend dependency installation/discovery to
shared CI requires a separate PM-approved workflow amendment. No existing checks
are disabled or replaced here.

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
