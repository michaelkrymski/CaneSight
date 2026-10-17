# CS-035 observation adapter - 2026-10-17

Owner: Gavin (`gmarcialcalleja`). Branch: `task/CS-035-observation-results`.
Base: `0758598b8befed1e338536166c1e40d8c03e23ed` (accepted main).
Michael merged claim PR #27 before implementation. CS-031 #19 and CS-034 #26
are merged. Isolated checkout preserves the separate CS-041 branch and preview.

## Changes and behavior

- backend/vision/observations.py: picklable YoloFactory loads only the existing
  hash/runtime/class-verified baseline in the spawned child. Bounded in-memory
  JPEG decode and original-image shape checks precede prediction. Convert pixel
  boxes to normalized uploaded-image coordinates with at most 32 detections.
  Reject invalid geometry/confidence/class IDs, nonfinite output and class drift.
- Unsupported COCO classes map to other, generic traffic light to traffic_light.
  No pedestrian-head detector is implemented: candidate_count zero, symbol unknown,
  confidence/countdown null. Empty detections never establish clear space.
- Existing worker retains original session/source/boot/frame/mode/sequence/capture
  and image metadata, adding measured processing duration and model hash version.
  No new age field or replacement capture timestamp is introduced.
- backend/vision/observation_smoke.py: optional actual-model generated-JPEG smoke
  through the real spawned worker with default load/job deadlines, strict result
  schema and original lineage checks. Report creation refuses to overwrite.
- tests/vision/test_observations.py: synthetic detector mapping, real JPEG decode,
  spawned-process integration, live/replay preservation, maximum result size,
  original-deadline capture expiry, missing weights and invalid-output failure.
- backend/vision/README.md and INTEGRATION.md: usage, limits and concrete proposed
  scope expansion. qa/vision/observation-worker-smoke-20261017.json: actual evidence.
- Own task runtime fields, new changelog fragment, generated log and this handoff.

## Tests actually run

- Isolated Windows AMD64 Python 3.12.14: 22 vision tests passed (11 existing
  baseline plus 11 adapter/worker tests); all 39 shared Python tests passed.
- Python 3.14 backend regression suite: 115 tests discovered, 109 passed, six
  environment-specific skips. No failures. Existing deprecation warnings remain.
- Replay smoke in isolated environment: health200/readiness503, upload202 and
  duplicate409; no raw image/token saved and loopback server stopped.
- Actual pinned YOLOv8n CPU model: weights SHA-256 verified, pinned six-package
  runtime checked, one worker/model load (3578 ms), 21 completed schema-valid
  results including warmup. Twenty measured generated black 416-square JPEGs:
  local result median47/p95max63 ms; no failures, timeouts or expired work.
  Original lineage retained; pedestrian signal unknown for every result.
- Repository validation and whitespace checks passed; checked publishing runs
  shared tests and generated changelog checks. Vision tests run explicitly because
  existing protected CI does not discover the separate vision test root.

Ignored .venv/vision and backend/vision/artifacts contain local runtime/weights
and generated settings only; no model binary, image or credential enters Git.
Measurements cover local generated JPEG submission through worker result retrieval.
Windows clock resolution and local machine load apply. These are not recognition
accuracy, public capture/network/Pi latency, deployed readiness, real phone/Pi
connectivity, haptic/electrical or crossing-permission evidence.

## Bottleneck and next steps

Status: blocked for full integration, draft checkpoint for model-adapter review.
The current public service still uses its accepted no-model factory. Native event
sockets do not yet relay server-generated worker results. Those changes require
backend/server.py, backend/sessions.py, tests/backend/ and deployment edits beyond
CS-035 allowed paths. No session internals or alternate public API were used to
bypass task scope, authentication or native browser-Origin restrictions.

Michael must review the concrete scope proposal in backend/vision/INTEGRATION.md,
then explicitly authorize/assign the transport/runtime integration. Protected
contract changes, if needed, retain the exact-head amendment process. Alternative:
accept this adapter separately and assign the remaining integration to another
reviewed task. Browser dashboard read-only authorization remains separate.

No baseline/protocol/governance/deployment or teammate task changed. Michael owns
review/merge; this draft, test success and generated model results do not mark Done.
