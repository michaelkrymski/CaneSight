# CS-036: original signal replay fixture pack

Owner: aditsangani. Branch: task/CS-036-signal-fixtures.
Task base: 73871efea83f889facf73fcc8732faee972f0ec4, accepted claim PR #36.
Accepted main integrated before publication: 78dc1e2ac8558078e7ecf72187401c2f951b654c.
Status: Review, not Done; Michael reviews/merges the implementation.

## Changed files

- `backend/vision/signal_fixtures.py`: explicit offline new-directory generator
  and hash/provenance/ROI/timeline verifier; Pillow only, no model/network.
- `qa/vision/signal-fixtures/`: 18 original RGB PNGs, manifest, source/license and
  usage notes. 12 cases: absent/generic/walk-like/hand-like, digits, flashing,
  conflicting heads, occlusion, glare, low detail, ambiguous digits, target loss.
- `tests/vision/test_signal_fixtures.py`: nine integrity/provenance/reproduction
  tests, without claiming classification or OCR validation.
- `qa/vision/signal-fixtures-validation-20261017.json`: actual validation facts.
- Own task runtime, new changelog fragment, rendered log and this handoff.

## Evidence

Windows Python 3.14.3, Pillow 12.1.1. Generated 18 RGB 416x416 PNGs, total 30,112
bytes. Manifest SHA-256:
`7d13851d3c66ce12012271dc20f0ac7f6ccbbf7ce246b09d0ddf2430f0188225`.
Every frame has file and decoded-pixel digests. All committed image hashes,
dimensions, manual ROI bounds/provenance and sequence order verified. Regeneration
in a temporary new directory reproduced all pixels and annotations; compressed
PNG bytes may vary across encoder builds. No existing destination is overwritten.

First frames of all 12 cases were visually inspected in a generated contact
sheet. Replay banners and manual/no-ROI labels are legible. Sequence assertions
cover hand/off alternation, 12-to-11 digits, target A disappearance and target B.
The preview contact sheet is ignored developer output; it is not an extra asset.

The asset/annotation source is the original procedural geometry/bitmap lettering
in the new module, created with AI assistance. No third-party image/font files,
photos, model weights, private data or municipal design were copied. Generated
PNGs and annotations carry an explicit CC0-1.0 dedication, scoped only to these
original assets; upstream terms are linked in the pack. Existing code/model
licenses are unchanged.

## Checks actually run

- `.venv/Scripts/python.exe -m backend.vision.signal_fixtures --generate
  qa/vision/signal-fixtures`: new pack created; 12 cases / 18 frames verified.
- `.venv/Scripts/python.exe -m unittest discover -s tests/vision -v` and final
  `-q` run: 31 tests passed, including the nine new fixture tests.
- Offline fixture verification produced the recorded JSON evidence.
- Repository structure and whitespace checks passed before publication; checked
  publishing reruns shared tests, structure, rendered log and whitespace checks.
- CI and current PR feedback are inspected after the final push. Protected CI
  does not discover `tests/vision`; its explicit local result is recorded above.

## Limits / next steps

Manual ROIs and drawn content are authored annotations, never detector outputs.
Relative replay time is not a live capture timestamp. Images visibly say REPLAY;
metadata stays replay-only. Unknown/null production expectations remain unchanged,
even for clear-looking schematic figures/digits. Zero verified candidates does
not prove absence or clearance. No automatic pedestrian recognition, training,
real-world accuracy, transport/deployment, GPIO, motor or electrical verification.

This prepares inputs for separately assigned CS-037 parser experiments and later
CS-038 ambiguity evaluation. It does not implement either task. Real imagery,
held-out evaluation, credible/applicable head association and source-specific
freshness still require independent evidence. Review/merge this task first.
