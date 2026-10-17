# CS-037: manual schematic replay parser

Owner: aditsangani. Branch: task/CS-037-signal-parser.
Task base: 1c22be9290b36458af7d644f2ba1beea644ce0bd (accepted claim PR #42).
Accepted main integrated before publish: 873fcb02e19c3a49531cc6cddf6c86340b01fd35.
Status: Review; Michael acceptance/merge pending.

## Changes

- `backend/vision/signal_parser.py`: isolated Pillow-only schematic-profile shape
  matching, segment-shape digit rules and bounded manual replay sequence state.
- `backend/vision/signal_parser_replay.py`: explicit offline 18-frame replay CLI.
- `backend/vision/SIGNAL_PARSER.md`: provenance, thresholds, API and limitations.
- `tests/vision/test_signal_parser.py`: 14 new rule/temporal regressions.
- `qa/vision/signal-parser-replay-20261017.json`: actual offline execution output.
- Own task runtime, new fragment/generated log and this handoff. Existing fixture
  assets, other task code, production factory/adapter, shared schema and workflows
  remain unchanged.

## Behavior and limits

The supported profile is `cs036-schematic-v1`, mode replay, one explicitly manual
ROI, and a bounded operator-selected target ID. Verified original CC0-1.0 walk
and hand fixture silhouettes are hand-selected prototypes, not trained weights.
Brightness segments masks; symbol identity additionally requires shape IoU >=.94
and a .30 margin. Two matching frames spanning >=100 ms confirm a schematic
symbol. Similarity is not a probability; confidence remains null.

Digit occupancy and full segment geometry reject partial/filled/unknown shapes.
Two observed valid readings must agree or decrement by one over 500..1500 ms.
Nothing extrapolates a countdown or compares it to walking speed. Hand/off/hand
alternation becomes flashing_or_uncertain with unknown symbol/null digits.

Target/shape change, loss, malformed selection or replay removes old evidence.
Sequence/frame-time high-water marks survive resets; history is capped at eight
entries/2000 ms. Independent replay polling expires observations after 1500 ms
without renewal. Invalid/backward poll clocks fail the instance closed. Replay
time is authored position, not live capture-age evidence or a device watchdog.

These prototypes are part of the exercised pack: this is a known-schematic
regression profile, not held-out evaluation or general OCR/pedestrian recognition.
It cannot accept live mode and is not a v1 observation or worker adapter. Existing
production pedestrian results remain unknown/null. No training, Pi, GPIO, network,
motor/electrical verification, deployment or crossing-permission output.

## Validation actually run

- `.venv/Scripts/python.exe -m unittest discover -s tests/vision -p
  test_signal_parser.py -v`: all 14 parser cases passed.
- `.venv/Scripts/python.exe -m unittest discover -s tests/vision -q`: all 45
  baseline/adapter/fixture/parser tests passed, no skips.
- `.venv/Scripts/python.exe -m backend.vision.signal_parser_replay --report
  qa/vision/signal-parser-replay-20261017.json`: 12 cases/18 frames processed;
  explicit regression checks passed. Final authored countdown was 11, flashing
  remained uncertain, and absent/generic/multiple/obscured/track-loss cases
  remained unknown. Single-frame positives remained unconfirmed.
- Structure and whitespace checks passed. Checked publishing reruns shared tests,
  structure, exact generated changelog and whitespace; inspect final-head CI.
- Protected CI does not discover `tests/vision`; the explicit local results above
  cover that root. No hardware or real-scene accuracy test was performed.

## Next

Michael reviews this scoped replay parser. CS-038 evaluation needs its own merged
assignment and independent evidence; no real accuracy is implied by matching the
prototype drawings. Real layouts/footage and any production integration need
separate source/license, geometry, temporal/freshness and applicability review.
