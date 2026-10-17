# CS-036 synthetic signal replay fixtures

**18 original schematic PNG frames in 12 cases. Replay only. Manual ROIs.**
These are software test inputs, not real signal photographs, trained weights,
automatic detections or a representative accuracy benchmark. No road use or
crossing permission is implied. Every image visibly says REPLAY and MANUAL ROI
(or NO ROI), including off/obscured sequence frames.

## Source and license

Source: `backend/vision/signal_fixtures.py`, written for CaneSight by aditsangani
with AI assistance. Panel geometry, symbols, seven-segment digits and bitmap
lettering are procedurally authored here. No external images, font files,
municipal logos, datasets, model weights, private photos or GPS are included.

The generated PNGs and authored annotations in `manifest.json` are dedicated
under **CC0-1.0**, to the extent rights can be waived. See [LICENSE.txt](LICENSE.txt)
and the [CC0 legal code](https://creativecommons.org/publicdomain/zero/1.0/legalcode).
This covers these original fixture assets, not the project's existing software,
Ultralytics weights or third-party dependencies. Source/license metadata applies
to every listed frame. No transport-agency design compliance or endorsement is
claimed; these are simplified artistic forms.

## Contents

| Case | Frames | Authored input / testing purpose |
|---|---:|---|
| no_signal | 1 | Empty scene; no detection must not become clear/permission. |
| generic_traffic_light | 1 | Vehicle-style light; not pedestrian-head evidence. |
| walk_like | 1 | Schematic walking figure, not a verified real signal. |
| hand_like | 1 | Schematic hand, not a verified real signal. |
| countdown | 2 | Hand with drawn 12 then 11, 1000 ms apart; no time extrapolation. |
| flashing | 4 | Hand/off/hand/off, 500 ms apart; needs sequence context. |
| multiple_heads | 1 | Conflicting figures; which head applies remains unknown. |
| occluded | 1 | Opaque mask over a schematic hand. |
| glare | 1 | White wash over a schematic figure; not realistic lighting validation. |
| low_resolution | 1 | Panel reduced to 12x14 pixels and enlarged. |
| ambiguous_digits | 1 | Obscured segments with null intended digit annotation. |
| track_loss | 3 | Target A, no target, target B; do not inherit old state. |

## Annotation contract

`manifest.json` is an **offline fixture manifest**, not the shared v1 protocol.
Each frame records its file SHA-256, decoded RGB SHA-256, authored content,
relative replay time, manually selected ROIs and optional authored target ID.
All images are RGB PNGs, 416x416. Coordinates use original image pixels:
`[left, top, right, bottom]`, right/bottom exclusive. A box selects the drawn
panel; it does not establish a credible/applicable real-world pedestrian head.
`generic_traffic_light` ROIs explicitly identify a generic schematic light.

- `manual_rois[].provenance` is always `manual_fixture_annotation`.
- `drawn_content`/`drawn_digits` describe what the generator drew; they are not
  detector predictions or validated pedestrian/OCR ground truth.
- `relative_replay_ms` is sequence position, not a source monotonic timestamp,
  UTC time or capture-age bound. No session, boot, sequence or live frame envelope
  is generated. Future transport replay must remain explicitly `mode=replay`.
- `authored_target_id` is a test annotation, not a computed tracker identity.
- `production_signal` is the unchanged unsupported-baseline expectation:
  zero verified candidates, unknown symbol and null confidence/countdown. Even
  the clear-looking drawings do not upgrade the production model's capabilities.
  Candidate count zero is not proof that no pedestrian heads are present.

## Verify or reproduce

Use the repository backend test environment (Pillow 12.1.1; no ML runtime or
network needed), from the repository root:

```powershell
.venv/Scripts/python.exe -m backend.vision.signal_fixtures
.venv/Scripts/python.exe -m unittest discover -s tests/vision -v
.venv/Scripts/python.exe -m backend.vision.signal_fixtures --generate backend/vision/artifacts/signal-fixtures-copy
```

The generator only creates a **new** directory and refuses to overwrite one.
Use a new destination for later runs. Linux uses the corresponding environment's
`bin/python`. The verifier checks image/file hashes, dimensions, replay/provenance
boundaries, bounded manual ROIs and increasing relative sequence times.
Reproduction tests compare all decoded pixels and annotations; PNG compression
bytes can differ between zlib builds, so encoded-file hashes identify a particular
generated artifact rather than promise universal encoder-byte identity.

Nine new fixture tests cover integrity/provenance and reproducibility; existing
baseline/adapter tests are retained. Run `tests/vision` explicitly: protected CI
does not discover this test root. This PR changes no workflows or shared contract.

## Next task and limits

CS-037 may use these inputs for isolated parser experiments once assigned.
CS-038 needs its own ambiguity/track-loss evaluation. Neither task gains real
accuracy evidence from passing schematic tests. Real footage, source/license
review, held-out evaluation and applicability remain separate requirements.
There is no fixture classifier, signal parser, automatic ROI selection, model
training, production integration, phone/Pi calibration or hardware test here.
