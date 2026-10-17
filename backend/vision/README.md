# CS-034: pretrained YOLOv8n baseline

This is **inference setup, not model training**. No custom dataset is required.
The baseline is the publisher's COCO-pretrained `yolov8n.pt`, pinned to the
Ultralytics assets `v8.3.0` release. `baseline.json` records its exact byte size,
SHA-256, runtime versions, class list and upstream license references. It is
separate from the backend application: importing it does not activate inference
or change service readiness. Worker/result integration belongs to CS-035.

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
Run this explicit test root: existing repository CI does not discover it or
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
