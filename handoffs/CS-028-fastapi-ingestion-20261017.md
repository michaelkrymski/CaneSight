# CS-028 — FastAPI ingestion and replay rehearsal

- Human: Adit / `aditsangani`.
- Base commit: `1ed21a63fbea4e50241dd975e728f4321b9410a6`.
- Branch: `task/CS-028-fastapi-ingestion`.
- Goal: separate liveness/readiness; validate JPEG dimensions/body; preserve original frame lineage and return its ID. CS-028 ownership and CS-003 protocol were merged before implementation. CS-003's task JSON still says Review; its contract is accepted via PR #8, not silently rewritten here.
- Changed: backend app/package, pinned requirements, replay factory, synthetic smoke and one-command demo, backend README; `tests/backend/test_app.py` and component requirements; own task runtime fields; new change fragment and generated changelog.

## Validation actually run

- `.venv/Scripts/python.exe -m unittest discover -s tests/backend -v`: 19 passing cases. Tests cover malformed/oversized body and JPEG, chunked request limit, decode validation, dimensions/length mismatch, strict JSON/depth limit, unauthorized identity/role/session/mode/epoch, duplicate/out-of-order sequence and frame IDs, bounded retention, atomic concurrent duplicate rejection, overload admission and body-read timeout, dependency readiness and credential expiry.
- `.venv/Scripts/python.exe -m unittest discover -s tests -v`: 39 shared repository/contract cases passed.
- Loopback HTTP replay with generated solid-color JPEG and an ephemeral token: liveness 200, readiness 503, original frame acknowledged 202, duplicate rejected 409. Server stopped after smoke. No raw images or credentials written to Git/disk/logs.
- Structural validation, generated changelog and whitespace checks are run by the checked publishing helper; final publication results are recorded in the PR.
- Runtime: Windows, Python 3.14.3, pinned backend requirements (jsonschema 4.23.0 in isolated `.venv`). Starlette reports a TestClient deprecation warning for httpx; tests still pass. No Python 3.12 backend or Linux backend run claimed.

## Limits and continuation

Run `python -m backend.demo_replay` after installing `backend/requirements-test.txt` for the complete software rehearsal. Default app has no grants; replay has a five-minute fixture-only grant. Readiness stays unavailable until real enrollment/model/worker health is connected. A 202 acknowledges ingestion, not freshness, inference or movement permission. Raw source capture metadata is never retimed.

The component suite is an explicit test root. Existing shared CI installs only contract dependencies, so `discover -s tests` alone does not cover backend tests. PM should arrange a reviewed CI dependency/discovery amendment; this task does not edit protected workflows or silently expand its allowed paths. Locally both suites were run.

Trusted fixed grants are an injection seam, not CS-029's public pairing/enrollment service. Single process only; do not deploy multiple workers or reuse old live session/boot grants on restart. CS-029 must supply lifecycle/rotation/shared state, CS-031 the actual bounded inference worker, CS-032 rate quotas, CS-033 HTTPS/WSS deployment. Latest JPEG/two metadata records per source are held in memory, max 16 sources; frame-ID history capped at 4096 per source epoch; expired state purged on next auth/intake/readiness call. No unbounded image history or image files.

No phone/Pi, real camera, hardware/electrical, clock-drift, inference, network freshness or deployment verification performed. Next: Michael reviews this implementation and the documented integration seams; merge only after acceptance. Proposed status: Review.
