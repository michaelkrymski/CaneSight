# CS-034: pretrained YOLOv8n baseline

This is **inference setup, not model training**. No custom dataset is required.
The baseline is the publisher's COCO-pretrained `yolov8n.pt`, pinned to the
Ultralytics assets `v8.3.0` release. `baseline.json` records its exact byte size,
SHA-256, runtime versions, class list and upstream license references. It is
separate from the backend application: importing it does not activate inference
or change service readiness. The CS-035 worker adapter is documented below.

## Install and inspect

Use a separate **Python 3.12** environment on an x86-64 development machine.
For example, Windows PowerShell from the repository root:

```powershell
py -3.12 -m venv .venv/vision
.venv/vision/Scripts/python.exe -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cpu
.venv/vision/Scripts/python.exe -m pip install -r backend/vision/requirements.txt
.venv/vision/Scripts/python.exe -m backend.vision.baseline --download
.venv/vision/Scripts/python.exe -m backend.vision.smoke
```

On Linux x86-64, create the environment with `python3.12 -m venv .venv/vision`
and substitute `.venv/vision/bin/python` in the remaining commands. Native
PyTorch/OpenCV prerequisites must be present on that host. This is a laptop CPU
baseline, not a Pi installation or a change to the deployed container. The
existing backend and its test requirements stay separate from this environment.

Only `--download` fetches weights. Loading without that flag requires the local
artifact. Downloads are size bounded and installed atomically after SHA-256
verification. An existing corrupt/different file causes an error rather than
automatic replacement. Use `--weights PATH` to supply the same pinned bytes
from another operator-controlled location.

Weights and generated Ultralytics settings live under the ignored
`backend/vision/artifacts/` directory. No checkpoint, image or credential is
committed. The loader verifies the artifact before deserialization, checks the
six pinned runtime package versions, disables dependency auto-installation and
online integrations, loads on CPU, and compares every loaded class ID/name with
the manifest. A `.pt` file is a trusted Python checkpoint: do not substitute
user-uploaded models or bypass the hash check. The recorded digest was computed
from the official release download; the publisher's asset API did not provide
an independent digest or signature.

## Classes and interpretation

The expected 80 classes include `person`, `bicycle`, `car`, `motorcycle`, `bus`,
`truck`, and class **9: `traffic light`**. The complete ordered list is in
`baseline.json`; the actual loaded list is also recorded in the smoke evidence.

**A generic traffic-light detection does not identify a pedestrian-signal head,
WALK figure, raised hand, flashing phase, countdown, or the applicable crossing.**
This model supplies none of those classifiers. Future observation output must
keep pedestrian-signal state unknown and countdown null unless a separately
validated component supplies evidence. An empty detection list never means the
scene is clear. No output provides movement or crossing permission.

## License and provenance

The publisher identifies YOLOv8 models/software under **AGPL-3.0**, with a
separate Enterprise option. This task records the AGPL baseline and does not
claim that an Enterprise license has been obtained. Relevant upstream sources:

- [YOLOv8 pretrained models and licensing](https://docs.ultralytics.com/models/yolov8/)
- [Pinned runtime license text](https://github.com/ultralytics/ultralytics/blob/v8.3.221/LICENSE)
- [Publisher licensing terms](https://www.ultralytics.com/license)
- [Weight release](https://github.com/ultralytics/assets/releases/tag/v8.3.0)
- [Runtime source class reference](https://github.com/ultralytics/ultralytics/blob/v8.3.221/ultralytics/cfg/datasets/coco.yaml)

These records identify the selected upstream terms; they do not relicense
CaneSight or establish separate license compatibility/enterprise approval.

## Verification and limits

```powershell
python -m unittest discover -s tests/vision -v
.venv/vision/Scripts/python.exe -m backend.vision.smoke --samples 20
```

The eleven fast tests require only the standard library and use mocked downloads.
Adapter tests additionally require `backend/requirements-test.txt`, but no ML
packages or downloaded model. Run this explicit root: repository CI does not discover it or
install the optional ML runtime. No workflow/protected-file change is included.

The smoke command executes the real model on a generated all-black 416-square
RGB image, checks output shape/class IDs and finite bounded output, and runs
one warmup plus 20 timed predictions. It saves no images or prediction files.
An optional `--report NEW_PATH` creates a new JSON evidence file without
overwriting an existing report. Synthetic pixels test execution only; timings
cover local prediction, not capture/upload/queue/result transport or a freshness
guarantee. No detection-accuracy, pedestrian-signal or hardware claim follows.

Recorded run: [actual model smoke evidence](../../qa/vision/yolov8n-smoke-20261017.json)
and [observed environment](../../qa/vision/runtime-packages-20261017.txt).

## CS-035 observation adapter

`backend.vision.observations.YoloFactory(weights_path)` is a picklable factory for
`backend.inference_worker.InferenceWorker`. It invokes the existing verified
baseline loader once in the spawned process. Importing/constructing the factory
does not load weights, install dependencies or activate a service. The explicit
operator download step above remains required. Install backend test requirements
into the isolated vision environment for worker/adapter testing.

The adapter decodes a bounded JPEG in memory, checks dimensions against original
metadata, and runs the pinned CPU predictor with at most 32 detections. Original
uploaded axes are retained; EXIF rotation and cross-camera calibration are not
inferred. YOLO's original-image pixel boxes are normalized by original width and
height, preserving letterbox mapping back to the uploaded image. Invalid shape,
nonfinite output, class drift, invalid confidence or boxes outside the original
image fail closed rather than being silently clamped.

Only the accepted object labels are returned; other COCO classes map to `other`.
Generic `traffic light` maps to `traffic_light`. No pedestrian-head classifier is
available, so `candidate_count` is zero, `symbol` unknown and confidence/countdown
null even with generic traffic-light boxes. Zero candidates/objects do not prove
absence or clear space. No movement instruction or permission field is generated.

The existing worker adds measured processing duration and a model version with
the full artifact hash, while preserving the untouched session/source/boot/frame,
mode, sequence, image dimensions and capture timestamps. Receipt or processing
time never replaces capture time. Capture age remains unknown without the
originating-device ledger and accepted receiver-side gate. Synthetic integration
tests feed actual worker results to that gate and verify original-deadline expiry.

Optional actual-model execution, using generated black JPEGs only:

```powershell
.venv/vision/Scripts/python.exe -m pip install -r backend/requirements-test.txt
.venv/vision/Scripts/python.exe -m backend.vision.observation_smoke --samples 20
```

`--report NEW_PATH` writes new JSON evidence without overwriting. This smoke uses
the real spawned worker, default deadlines, one model load, original lineage and
the accepted schema. It stores no images or credentials. Local timing excludes
physical capture, network and Pi receipt and proves neither detection accuracy
nor deployed readiness. Public result delivery and deployment are not enabled
by importing the adapter. The approved opt-in service/runtime integration is
documented in [the integration notes](INTEGRATION.md) and `backend/deploy/README.md`.
