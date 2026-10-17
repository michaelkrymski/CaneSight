# CS-038: signal ambiguity and track-loss evaluation

This evaluates the **CS-037 manual schematic replay profile**. It is a software
regression evaluation, with no model training, Raspberry Pi, camera footage or
production activation. Real-world signal recognition and OCR accuracy remain
unverified. The production adapter continues to emit unknown pedestrian state.

## Reproduce

From the repository root, using the backend environment with Pillow:

```powershell
.venv/Scripts/python.exe -m backend.vision.signal_evaluation
.venv/Scripts/python.exe -m backend.vision.signal_evaluation --report backend/vision/artifacts/new-cs038-report.json
.venv/Scripts/python.exe -m unittest discover -s tests/vision -v
```

The CLI prints metrics and returns nonzero on any required-output mismatch. With
`--report`, it writes the full observations **before** returning failure. Existing
evidence files cannot be overwritten. This task's committed execution record is
`qa/vision/signal-evaluation-20261017.json`.

## Inputs, provenance and scoring

`backend/vision/signal_evaluation.py` defines the fixed scenario inputs and
hand-authored output requirements. It reads the verified CS-036 CC0-1.0 pack,
repeats selected images at authored replay positions, translates one manual
panel, and uses the original generator for hand panels displaying `00` through
`99`. Original CS-036 assets and CS-037 parser/rules are unchanged. New generated
pixel derivatives inherit the original assets' CC0 dedication; no third-party
images or model weights are introduced.

The record includes every input, pixel hash, manual ROI, sequence, target ID,
replay position, output and mismatch, plus per-condition metrics. It records
Python/Pillow versions, the scenario specification hash, and SHA-256 of UTF-8
source text normalized to LF, so Windows checkout line endings do not change
source identity. Labels, digit references and required outputs never enter the
parser: inference receives only pixels and replay selection/time metadata.

There are **127 scenarios and 309 checks**: 303 frame observations and six expiry
polls. Inputs cover:

- Repeated walk/hand positive controls, including temporal warm-up.
- No signal, generic vehicle lights, multiple heads, occlusion, glare and low
  resolution, both on a fresh parser and after a confirmed walk, then recovery.
- Target disappearance, target-ID changes with the same/different symbol, ROI
  geometry changes with reused ID, and symbol changes with the same ID.
- Flashing after a confirmed hand, repeated evidence during uncertainty, exact
  expiry boundaries, continued polling without renewal, and long-frame-gap reset.
- Broken digits after readable digits, countdown increases/jumps/fast decrements,
  no interpolation between readings, and the 100 two-slot numeric layouts.

The symbol reference matrix uses the manually authored observable symbol:
`walk`, `dont_walk` (schematic hand), or `unknown` for ambiguous/absent inputs.
It includes warm-up frames as abstentions against their visible reference class.
A separate required-output matrix checks temporal policy, where a visible symbol
can correctly require unknown during warm-up/reset. Neither matrix estimates
real-scene classifier accuracy. Polls are scored as policy checks, not as new
image or OCR samples.

OCR numeric exact-match uses **all readable frame references**, including the
first observation, rejected temporal jumps and abstentions. It normalizes leading
zeros to an integer, matching the parser API, and is not a general text OCR score.
Coverage and correctness among emitted readable-frame values are reported
separately. Missing/broken digits, warm-up and uncertainty also have explicit
null-output requirements; violations are retained even when the input has no
readable digit reference. Zero denominators produce null, never perfect accuracy.

## Observed results

The recorded run matched **309/309 required-output checks**. Ambiguous inputs did
not retain a previous confirmed symbol; retargeting required confirmation again.
No countdown was emitted on the 205 checks requiring null. This includes polls
and initial/plausibility-rejected readings, not 205 independent negative images.

Frame reference confusion (rows are hand-authored reference; columns are output):

| Reference | unknown | walk | dont_walk |
|---|---:|---:|---:|
| unknown | 34 | 0 | 0 |
| walk | 23 | 23 | 0 |
| dont_walk | 110 | 0 | 113 |

All 133 abstentions on visible walk/hand references are retained in this matrix.
There were 167 unknown outputs total, including the 34 unknown references.
These missed/withheld readings are not removed to make the score look better.

| Digit measure | Result |
|---|---:|
| Exact numeric match, all readable frames | 103/212 (48.58%) |
| Readable-frame output coverage | 103/212 (48.58%) |
| Exact match among emitted readable-frame values | 103/103 |
| Abstentions on readable frames | 109 |
| Wrong emitted values on readable frames | 0 |
| Non-null outputs where null was required | 0/205 checks |

The 100 two-slot controls account for 200 of the readable frames: one warm-up
and one repeated value each. This correlation dominates the aggregate counts.
Use the report's per-condition breakdown and individual observations when
reviewing behavior; do not present the emitted-value score as overall accuracy.

## Limits and next steps

There are **zero independent real scenes and zero held-out scenes**. Silhouette
prototypes and evaluation images share the CS-036 generator. Repeated frames,
synthetic white wash/opaque masks and fixed glyph layout are diagnostic probes,
not lighting, occlusion or OCR generalization evidence. The operator supplies
candidate count and target identity; the parser cannot discover a hidden second
head, establish crossing applicability or resolve real tracking errors.

This evaluation found no mismatch against its declared replay contract; that
does not establish the contract is sufficient for live use. The parser remains
unsupported for real footage. Independently licensed real scenes, scene-level
separation, appropriate ROI/applicability evidence and condition-specific results
are needed before making real-world accuracy claims. No physical timing, live
capture-age guarantee, hardware acceptance or crossing permission is established.

Michael reviews this software evidence and its limitations before accepting
CS-038. Task status remains Review until that decision; no additional data
collection, training or production integration is started by this PR.
