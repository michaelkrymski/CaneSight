# CS-034: pretrained YOLOv8n baseline

Owner: aditsangani. Branch: task/CS-034-yolov8n-baseline.
Base: 8c5af9c674635620c586d23accadc788f90e8cad (accepted main).
Status: Review; PM acceptance/merge pending. Claim was accepted in PR #22.

## Changed files

- `backend/vision/`: optional pinned requirements, weight/runtime/class manifest,
  explicit download/hash-verified loader, synthetic smoke CLI and instructions.
- `tests/vision/test_baseline.py`: eleven offline standard-library tests.
- `qa/vision/yolov8n-smoke-20261017.json`: actual loaded model/runtime/classes,
  generated-input inference counts and timings.
- `qa/vision/runtime-packages-20261017.txt`: observed full CPU environment.
- Own task runtime, new changelog fragment, generated CHANGELOG and this handoff.

## What was verified

Downloaded publisher asset `ultralytics/assets` release v8.3.0, asset 195719301:
`yolov8n.pt`, 6,549,796 bytes, SHA-256
`f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`.
The hash is computed from downloaded release bytes, not an independently
published signature/digest. Weights are operator-controlled trusted checkpoints;
size/hash verification happens before PyTorch deserialization. No weights in Git.

Python 3.12.5 on Windows AMD64, CPU: Ultralytics 8.3.221, torch 2.7.1+cpu,
torchvision 0.22.1+cpu, NumPy 2.2.6, OpenCV 4.12.0.88, Pillow 12.1.1.
Actual loaded class IDs/names exactly matched all 80 manifest classes. Class 9
is generic `traffic light`; there is no pedestrian WALK/hand/countdown classifier.
Publisher model docs and pinned runtime LICENSE identify AGPL-3.0; the separate
Enterprise option has not been acquired or asserted. No project relicense.

Actual CPU smoke: one warmup plus 20 generated black 416x416 RGB predictions,
finite output with a 32-detection cap. All 20 returned zero detections; this is
not accuracy or absence-of-hazard evidence. Final local prediction wall time:
median 70.290 ms, nearest-rank p95 167.836 ms, max 171.200 ms. Model load including
imports was 5,117.275 ms in that run. These are laptop measurements only.

The first successful smoke exposed Ultralytics' fallback when its config parent
did not exist. The loader now creates the ignored parent before import; an
eleventh regression test and a repeated real smoke verified the fix. Initial
generated settings/report were preserved under ignored artifacts. Final settings
remain under backend/vision/artifacts/runtime, and offline/auto-install settings
are applied before the third-party import.

## Tests actually run

- `python -m unittest discover -s tests/vision -v`: 11 passed (standard library).
- `.venv/Scripts/python.exe -m unittest discover -s tests -q`: 39 passed.
- `.venv/Scripts/python.exe -m unittest discover -s tests/edge -q`: 13 passed.
- `.venv/Scripts/python.exe -m unittest discover -s tests/backend -q`: 115
  discovered, 107 passed, 8 environment-specific skips (platform/tooling/opt-in
  deployment integrations). No failed tests. 170 passed across these roots.
- `.venv/vision/Scripts/python.exe -m backend.vision.baseline`: actual weights
  loaded and actual class map inspected; repeated via final smoke after config fix.
- `.venv/vision/Scripts/python.exe -m backend.vision.smoke --samples 20 --report
  qa/vision/yolov8n-smoke-20261017.json`: actual model, final evidence recorded.
- `.venv/Scripts/python.exe -m backend.demo_replay`: health200, readiness503,
  upload202, duplicate409; generated replay only, stopped without saved images.
- Repository structural validation, compilation and whitespace checks passed.
  Checked publishing reruns shared tests and generated changelog validation.

## Limits and next step

No training or custom dataset. No real scene, signal-accuracy, deployed inference,
result-delivery, haptic or electrical verification. Empty detections do not mean
clear; pedestrian state stays unsupported/unknown and countdown unavailable.
The production factory, readiness and shared protocol are unchanged. No new
heavy dependency or model download is added to ordinary service/CI startup.

Michael reviews this PR. After acceptance, CS-035 needs its own merged assignment
and must adapt detections to observation-only results, preserve frame/source/boot
lineage and use the bounded worker/freshness path. Raw YOLO is not a drop-in
worker factory and must not be wired to movement/permission decisions.
