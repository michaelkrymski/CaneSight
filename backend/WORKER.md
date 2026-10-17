# CS-031: bounded inference scheduling

`InferenceWorker(factory)` loads a trusted model adapter once in a spawned
process. The factory must be importable/picklable for Python spawn, return an
object with a bounded `version` string, and implement `predict(AcceptedFrame)`.
Prediction returns exactly `detections` and `signal` from the accepted vision
schema. The adapter receives a separate deep copy of metadata; observation
provenance comes exclusively from an untouched original, including nested image
dimensions. Adapter preprocessing cannot rewrite the source capture lineage.
The worker preserves frame/session/source/boot/mode/sequence/capture
metadata and image dimensions, adds measured processing duration/model version,
and validates the complete observation in the model process. Nonfinite,
oversized or invalid output fails closed. No YOLO package, weights, model hash
or signal classifier is supplied by this scheduling task; CS-034 owns that adapter.

Inject a worker into `create_app(ingress=..., inference_worker=worker)`. ASGI
lifespan starts its supervisor thread and stops it off the event loop. A supplied
worker's actual health overrides a synthetic `dependency_health` callback.
The default app and replay factory still have no model and return readiness 503.
Use exactly one ASGI service process: this scheduler is process-local.

## Bounds and overload

- One model process and one active inference job, with no automatic reload or
  retry. `start()` is idempotent; a failed worker requires service restart.
- At most 16 source epochs, each with one pending JPEG (maximum 1,000,000 bytes),
  bounded validated metadata and one result of at most 8192 bytes. One extra
  active JPEG plus IPC/model working copies exist. Actual model memory is an
  adapter/deployment sizing requirement, not proved by these scheduling tests.
- A new pending frame supersedes its source's prior pending frame. Source order
  is FIFO; replacing pending work does not move another source behind a flood.
  A full source table rejects new epochs instead of evicting active identities.
- A newer submission invalidates a retained result and suppresses an older
  in-flight result. Expired/revoked source work cannot publish. Counters include
  submitted/completed, superseded pending/results, source capacity, unavailable,
  expired, revoked, failures, deadlines, shutdown drops and successful model loads.
  Gauges expose source/pending/result/active counts without credentials or images.
- Default load deadline 30 seconds; job budget 1.5 seconds from server queue
  admission, including queue wait. Expired queued work is dropped. A hung load
  or prediction terminates the model process, clears buffers and makes readiness
  unavailable. No backlog of timed-out executor futures accumulates.
- Upload 202 continues to mean validated ingestion only, including when inference
  scheduling is unavailable. Rejected scheduling is counted, and readiness
  reports the unavailable worker. No new public inference/result API is invented.

These time budgets are engineering defaults. Server queue time is not device
capture age. A result's original capture timestamps are never refreshed, and the
worker provides no freshness verdict. `take_result(authenticated_grant)` is an
internal adapter only; CS-030 must bound capture age/lineage before downstream
use, and CS-029 must reauthenticate consumers and isolate sessions. No result is
permission to cross or a direct motor command. Unknown signals stay unknown.

## Integration boundaries

`submit(grant, metadata, jpeg)` requires prior trusted authentication, typed
metadata validation, JPEG validation and replay/sequence admission. It performs
no model work on the calling event loop. Session revocation/epoch reset should
call `discard_source(grant)`; a removed in-flight generation cannot publish.

The accepted CS-029 session path retains both `session_manager` and
`inference_worker` keywords and existing TLS/role checks. Session admission and
worker submission share the session lock so revocation cannot interleave between
them. Session disposal calls `discard_source` before removing grants. Session
expiry sweeping and revocation wrap the app/worker lifespan; session cleanup runs
before worker shutdown. The legacy fixed-grant frame path still submits directly
after ingestion admission. For CS-032 #15, retain
`traffic_limits`; apply quotas before body reads and test real authenticated
session traffic together with a slow worker after those changes are accepted.
For CS-033, include this module and the selected reviewed CS-034 adapter in the
image; do not claim the existing deployed ingestion image runs inference.

## Verification

Run `python -m unittest discover -s tests/backend -v` and the separate shared
suite `python -m unittest discover -s tests -v`. Worker tests spawn real Python
processes with explicitly synthetic adapters. They check one load, latest work,
bounded floods, preserved lineage/schema, software task progress while prediction
waits, failed/hung loads, prediction deadline, invalid output, expiry/revocation
and ASGI lifecycle/readiness. Test gates use temporary empty files so terminating
a child cannot leave a multiprocessing event lock held.

Software task progress is not a physical motor-watchdog measurement, end-to-end
capture latency, YOLO throughput or model accuracy evidence. No raw input/output
image is written to disk by this component.
