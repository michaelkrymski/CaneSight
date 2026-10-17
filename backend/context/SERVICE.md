# Gemini context service — CS-039

This optional single-process app composes the accepted paired-session backend.
It does not replace the existing factory or alter observation, signal, freshness,
readiness, inference or motor contracts. No service is deployed by this PR. The
current Docker allowlist does not package context; deployment packaging belongs
to its owner and requires a reviewed integration before enabling this in Vultr.

## Configuration and model check

Install the existing `backend/requirements-test.txt` for development, or
`backend/requirements.txt` for the server. No additional package is required.
Supply `GEMINI_API_KEY` through the server's private environment, never phone/Pi
configuration, a URL, source file, prompt, command-line argument or log. Use the
existing private operator-token configuration for `CANESIGHT_OPERATOR_TOKEN`.
Set `CANESIGHT_GEMINI_MODEL` to an explicit Gemini model ID.

`gemini-3.1-flash-lite` passed a real model metadata plus structured-image probe
on 2026-10-17 using a generated neutral 32-square JPEG. This is point-in-time
availability evidence, not an accuracy or latency certification. No real scene,
GPS trace, raw provider response or credential was retained. Availability/quota
can change. Probe the deployed account again:

```sh
python -m backend.context.probe --model gemini-3.1-flash-lite
```

The probe reads the server environment or uses a hidden terminal prompt. It
prints only the model ID, boolean outcome and optional numeric HTTP status.
Failure suppresses raw provider errors. Startup performs the same check within
eight seconds. Failed verification disables context while ordinary backend
health, enrollment and transport remain available. Restart after correcting
configuration. `/v1/context/status` reports startup verification, not guaranteed
future provider quota or current source health.

With the private environment configured, launch behind the reviewed TLS proxy:

```sh
python -m backend.context.server --host 127.0.0.1 --port 8000
```

This launcher reuses the accepted one-worker WebSocket, HTTP and trusted-proxy
bounds. Default factories and existing deployed containers remain unchanged.
For programmatic composition, `install_context(app, service)` requires the
accepted `app.state.sessions` manager; wrap the same app, never create a second
session authority for the same devices.

## Optional HTTP adapter

Only a valid Pi-role paired-session bearer credential over HTTPS can call
`POST /v1/context` or `GET /v1/context/status`. Phone credentials are rejected.
Context output is a private HTTP response; it is never injected into the shared
observation WebSocket or made available to another session.

POST uses the existing bounded multipart parser: one JPEG file part `image`,
one JSON text part `metadata`, at most 1,024,000 total bytes, at most 1,000,000
JPEG bytes, metadata at most 8192 UTF-8 bytes, JPEG dimensions at most 1920x1080.
Metadata contains exactly:

```json
{
  "request_id": "unique-request-id",
  "consent": true,
  "frame": {"...": "the original accepted v1 frame_metadata object"}
}
```

The `frame` example above is schematic: supply the complete existing frame
metadata contract, including unchanged capture time, session/source/boot IDs,
mode, sequence, frame ID, image dimensions and JPEG byte count. Source, epoch,
mode and session must match the authenticated Pi grant. Consent is an explicit
client assertion: the device integration must obtain the user's actual consent
before sending surroundings. Context does not enroll devices or grant consent.

Success returns request ID, original frame metadata, configured model ID,
`description: {"objects": [...], "uncertain": true}` and
`capture_age_bounded: false`, with `Cache-Control: no-store`. No raw provider
prose, signature, image or credential is returned. The consumer must correlate
the exact echoed request/frame, validate its current session/epoch, and bound
total capture age on its originating clock. Server receipt never makes a frame
fresh. A 200 response grants no speech, haptic, movement or crossing permission.

## Limits and cancellation

- One provider process at a time and one pending slot globally, including
  upload/validation. One outstanding request per session, ten-second cooldown,
  at most 32 distinct request IDs per pair. Reenroll at the ID-history bound.
  Capacity/cooldown returns 429, a reused request ID 409. Invalid requests also
  consume cooldown. Session removal purges the bounded cooldown/ID records.
- An eight-second starting server deadline includes body upload, validation,
  queue time, encoding and provider work. Late results are suppressed. Kill and
  process reaping may add up to 200 ms of cleanup; this is not physical timing
  certification. The receiving-device CS-040 deadline must also include original
  capture age and both network directions.
- Network calls and image reencoding run in an expendable spawned child,
  isolated from the inference worker. The parent kills a timed-out/cancelled
  child. No retry, unbounded worker queue, persistent raw image or result cache
  exists. JPEGs are reencoded with no EXIF, at most 640 pixels per side and
  200,000 outgoing bytes. Provider response reads cap at 32 KiB.
- HTTP disconnect cancels pending/provider work. Revocation/expiry is checked
  during generation and immediately before response; a 50 ms sweep also cancels
  work for removed sessions. Shutdown cancels and reaps active children. The
  client must abort the HTTP request on manual cancel, hazard, loss of health,
  backgrounding or session change, and suppress speech independently.
- The provider receives a fixed observation-only instruction and a closed-label
  JSON schema. Scene text is untrusted data. Provider text is parsed, checked
  again at the process boundary, and reduced to permitted object labels. An
  empty list means no supported description. A permitted label can still be
  hallucinated; no accuracy claim is made. CS-040 renders labels into short
  uncertain speech and owns local preemption. The server has no audio/motor API.

CS-018 accessible audio/manual cancel and CS-027 button integration still require
their assigned owners and real-device tests. CS-040's independent renderer is in
PR #41; this service does not depend on unmerged files from that PR.

## Verification

```sh
python -m unittest discover -s tests/context -v
python -m unittest discover -s tests/backend -v
```

Unit/HTTP tests use generated JPEGs, fake provider replies and fake credentials.
A real hung child test proves process termination, not electrical behavior.
The only real API probe uses the neutral generated image described above.

REST behavior follows Google's [model API](https://ai.google.dev/api/models),
[GenerateContent reference](https://ai.google.dev/api/generate-content),
[structured output guide](https://ai.google.dev/gemini-api/docs/structured-output)
and [thought-signature documentation](https://ai.google.dev/gemini-api/docs/generate-content/thought-signatures).
The optional opaque signature on final text is discarded. Thought/prose/tool
parts, multiple candidates, incomplete/safety-blocked results, extra output
properties and unsupported labels are never rendered as descriptions.
