# CS-031: bounded inference worker

- Gavin / `gmarcialcalleja`; claim #16 merged before implementation.
- Base: `de3e6376b5774f28515e6b382549542b48e21d14`.
- Branch: `task/CS-031-bounded-worker`; implementation PR recorded in task JSON.
- Acceptance: no event-loop blocking; one model load; per-source latest work;
  explicit drop metrics. Scope: backend and backend tests, own runtime metadata,
  new immutable handoff/fragment and generated changelog.

## Changes

- `backend/inference_worker.py`: trusted picklable model factory; one spawned
  model process and supervisor thread; at most 16 source epochs, one active job,
  one pending JPEG and one bounded observation per source. FIFO source fairness,
  supersession, expiry/revocation hooks, schema/JSON result checks, fixed counters,
  truthful health and bounded model load/job deadlines with child termination.
- `backend/app.py`: optional worker injection; ASGI startup/shutdown; actual
  worker health; scheduling after accepted authenticated/validated ingestion.
- `backend/WORKER.md`: adapter contract, bounds, semantics and integration seams.
- `tests/backend/test_worker.py`: 11 real-process tests with synthetic models.
- Own task runtime record, new fragment and rendered log.

The model adapter loads exactly once per worker; no automatic reload/future
backlog. Prediction cannot block the ASGI event loop. Queued old work and older
in-flight results are dropped when superseded. The default service/replay still
have no model and readiness stays unavailable. Upload 202 remains ingestion only.
Original capture timestamps are preserved; queue receipt is not capture freshness.

## Tests actually run

Windows Python 3.14.7 and isolated Vultr Linux Python 3.12:

- `python -m unittest discover -s tests/backend -q`: **30 passed** (19 previous,
  11 worker tests).
- `python -m unittest discover -s tests -q`: **39 passed** (Windows also run by
  checked publishing; Linux run directly).
- `python -m backend.demo_replay`: health 200, readiness 503, upload 202 and
  duplicate 409; no model/hardware.
- 2,000 submissions during deliberately blocked prediction leave one pending
  frame; scheduled software task makes all 30 ticks. Another test rejects 1,000
  excess source identities while retaining one latest pending frame.
- One model load, latest result/lineage/schema, source isolation, failed/hung
  loading, prediction exception/deadline, invalid nonfinite output, expiry,
  revocation, ASGI lifecycle and shutdown are exercised with spawned processes.
- Repository checks/changelog/whitespace run through `publish_task.py`.

Initial shutdown fixture used a multiprocessing event; killing a waiting child
could leave its event lock stuck. Replaced test gates with temporary empty files
and reran the complete suite successfully. Test runners were stopped and no
fixture lock remains in the shipped worker design. No image is stored by gates.

The Linux tests ran in `/home/linuxuser/canesight-cs031-worker-validation` and did
not replace the running private CS-033 ingestion container.

## Limits and next steps

- CS-034 must supply reviewed/pinned YOLO weights, hash/classes/license and a
  real adapter. These tests prove scheduling with synthetic models, not model
  accuracy, resource sizing or inference throughput.
- CS-030 must establish source capture age/lineage eligibility before downstream
  use; no server queue timestamp makes a result fresh. No physical motor watchdog
  or capture-to-motor latency measurement is claimed.
- CS-029 #14 remains unmerged at this checkpoint. Integrate after acceptance:
  preserve `session_manager`, TLS/auth/roles and both frame-admission paths; call
  `discard_source` on session revocation/epoch reset. Do not edit Adit's task.
- CS-032 #15 must preserve `traffic_limits` alongside `inference_worker` and test
  actual authenticated traffic while inference is slow. CS-033 image must include
  this module and a reviewed adapter before reporting deployed inference.
- Michael reviews and merges; this checkpoint is Review, not Done. No main push,
  PR merge, master-plan/protocol/governance amendment or live credential change.
