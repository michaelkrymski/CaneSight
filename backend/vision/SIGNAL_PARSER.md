# CS-037: manual schematic replay parser

`ReplaySignalParser` implements shape/temporal and seven-segment rules for the
**known CS-036 schematic profile only**. It uses manual replay ROIs, not an
automatic pedestrian-head detector. It does not change the existing production
YOLO adapter, its unknown/null pedestrian output, service readiness, transport,
shared protocol or motor policy. No training or Raspberry Pi is required.

## Scope and provenance

Two hand-selected silhouette prototypes come from CS-036's original CC0-1.0
`walk_like-00.png` and `hand_like-00.png`. All pack hashes/provenance are verified
before loading them. The canonical panel is 208x248 pixels. Profiles, ROI geometry
and digit-segment coordinates are explicit test-display conventions, not inferred
calibration or a claim that real pedestrian signals follow this layout.

Brightness isolates foreground; symbol selection requires silhouette intersection
over union >=0.94 and a >=0.30 lead over the competing shape. Color alone cannot
assign walk/hand. Neither threshold is a measured statistical confidence. Output
`confidence` is always null; `shape_iou` is only geometric similarity.

There is no fitting, optimization, training dataset or new weight file. The
prototype fixtures are also part of the exercised pack: results are regression
tests of these rules, **not independent accuracy or generalization evidence**.
CS-038 remains a separate evaluation task; real footage/support needs new source,
license, geometry, applicability and held-out validation work.

## Input / output

```python
from backend.vision.signal_parser import ReplaySignalParser

parser = ReplaySignalParser()
result = parser.observe(
    image,                       # decoded RGB 416x416 Pillow image
    mode="replay", sequence=1, replay_ms=0, target_id="operator-target-a",
    manual_rois=[{
        "kind": "schematic_panel",
        "provenance": "manual_fixture_annotation",
        "box_xyxy": [104, 96, 312, 344],  # right/bottom exclusive
    }],
)
status = parser.current(1600)     # independently expire a paused replay
```

The API rejects live mode. One manual schematic-panel ROI and a bounded explicit
target ID are required. Generic light annotations, multiple/no ROIs, unbounded
boxes and selections smaller than 64 pixels stay unknown. These manual inputs
do not establish that a real head is applicable to a crossing.

`ReplayResult` is a frozen internal record with `mode=replay`, profile name,
`automatic_pedestrian_recognition=false`, symbol, nullable countdown/confidence,
temporal state, reason and optional geometric similarity. It is **not** a v1
vision message or a drop-in production worker result. No source/session/capture
envelope or movement output is fabricated. `dont_walk` means a matched schematic
hand, not a road-use instruction. Consumers must retain the replay/profile labels.

## Temporal and digit behavior

- At least two matching frames spanning >=100 ms are needed for a schematic
  symbol. A shape, target ID or ROI geometry change immediately removes the prior result and
  starts confirmation again. Missing/ambiguous shapes never retain old evidence.
- An authored hand/off/hand or walk/off/walk sequence within the bounded history
  becomes `flashing_or_uncertain`; symbol/countdown remain unknown/null. This
  state persists for that target until a reset/gap/loss. No steady-phase claim.
- Two fixed seven-segment slots use occupancy **and segment-shape** checks.
  Broken, obscured, filled or unsupported patterns yield null. No general OCR,
  inferred missing digits or color-only digit decision is provided.
- A countdown needs two observed valid readings that agree or decrement by one
  over 500..1500 ms. Increases, large/fast jumps and ambiguous current digits
  stay null. Polls retain the last observed number only until expiry; they never
  decrement or extend it. It is never compared with walking speed/crossing time.
- Sequence and frame-time high-water marks survive invalid frames and target
  resets. Duplicate/reordered input removes evidence. The history has at most
  eight entries over 2000 ms; only scalar sequence state and two masks are kept.
- Results expire after 1500 ms of authored replay time, with re-confirmation
  after a long gap. Polls do not renew the observation. A backward/invalid poll
  clock fails the instance closed; start a new parser for a new replay timeline.

Replay time is caller-supplied authored position, **not a live capture-age bound**.
This module does not replace CS-030 or the independent device watchdog. There is
no heartbeat input. A blocked caller that never polls has no expiry guarantee;
the replay host must run `current()` independently of incoming frames.

## Run / evidence

Use the existing backend test environment (Pillow; no ML dependencies):

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests/vision -v
.venv/Scripts/python.exe -m backend.vision.signal_parser_replay
.venv/Scripts/python.exe -m backend.vision.signal_parser_replay --report backend/vision/artifacts/new-parser-report.json
```

Reports use new filenames only. The committed run is
`qa/vision/signal-parser-replay-20261017.json`. The CLI processes pixels and manual
selection/time metadata; it never supplies manifest `drawn_content`/`drawn_digits`
to the parser. Single-frame positive examples remain unconfirmed, the authored
countdown sequence returns its observed 11, and ambiguous/track-loss examples
remain unknown. These results do not constitute a real-scene confusion matrix.

Fifteen new tests cover confirmation, expiry, resets/retargeting, flashing, ROI provenance,
color-only negatives, all ten segment digits and malformed/plausibility cases.
Existing baseline, adapter and fixture tests are retained. Run `tests/vision`
explicitly; protected repository CI does not discover that root. No workflow or
existing task's implementation is changed.
