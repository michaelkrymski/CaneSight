# CS-037 scenario replay adapters

This local prototype implements the accepted three-scenario isolation rules.
`live_capabilities()` returns false for all scenarios. No YOLO model was trained,
downloaded or loaded. Production COCO observations, the schematic parser, menus,
transport, narration and motors are unchanged.

## Selection, identity and time

`ScenarioReplay.select()` requires exactly one of `pedestrian_signal`,
`pedestrian_yellow_beacon` or `unsignalized_street`, plus source/session/boot.
There is no default or inferred scene. Selection does not establish applicable
signal identity or presence/absence of a crossing. Pass the exact local selection
object to observe(). Switch/cancel discards old evidence; old selection objects
cannot populate, clear or advance the clock of the new selection.

`ReplayFrame` accepts only `mode='replay'` and
`provenance='authored_synthetic_replay'`. Beacon/vehicle annotations are authored
test inputs, not detected objects. Sequence/capture high-water marks survive
scenario switches. Each controller is bound to one source/session/boot; a new
epoch needs a new controller. Live frames, wrong epoch, invalid/old/future or
duplicate/reordered frames cancel. Camera motion, unknown/occluded visibility
and lighting other than day also cancel. Recovery requires explicit selection.

All times use one integer authored timeline. Call `current(replay_ms)`
independently during paused replay. Results expire after 1500 ms; polls do not
renew original capture time. Backward/invalid poll clocks latch the instance
closed. This caller-driven prototype has no background watchdog and establishes
no live capture age or clock mapping. Synthetic weather variants and metadata
labels do not establish real night support.

## Scenario outputs

- Pedestrian signal delegates actual pixels/manual fixture ROI to the existing
  `ReplaySignalParser`. Shape/temporal confirmation and nullable observed digits
  remain unchanged. Other scenario payloads are rejected. No general OCR or
  automatic live pedestrian recognition is added.
- Yellow beacon consumes one `BeaconSample` with target, normalized region,
  kind and illuminated/off annotation. Vehicle-yellow-light kinds and missing
  or invalid samples remain unknown and reset history. Changed target/region
  resets continuity. At most 16 samples within 2000 ms are kept; gaps above
  200 ms reset. At least four transitions spaced 200..600 ms apart yield only
  `alternating_replay_evidence`. These are engineering replay thresholds, not
  evaluated flash-rate bounds. One frame, 1 Hz sampling and rapid flicker stay
  unknown. There is no physical flashing-frequency or yielding verdict.
- Unsignalized street consumes up to 16 uniquely identified `VehicleSample`
  annotations. Beacon mode can use this separate vehicle component too. Visible
  adjacent boxes within 200 ms with center displacement .01..0.20 normalized units
  produce `image_displacement_observed` and observed `(dx, dy)`. Unchanged boxes,
  large jumps, first sightings, hidden/lost tracks and sparse samples stay
  unknown. Missing IDs are dropped immediately and need fresh continuity on
  reappearance. One previous box per visible ID is kept. This is not automatic
  association, calibrated speed, approach, stationary or yielding recognition.
  Empty detections do not establish absence of traffic.

Frozen local results carry replay mode and live_supported=false. There is no
Gemini verdict input, crossing-permission field, automatic source recovery or
wire representation. CS-027/040 integration needs separate reviewed work;
cross-process scenario fields require a shared-contract CR.

## Example

```python
from backend.vision.scenario_adapters import ScenarioReplay, ReplayFrame, VehicleSample

replay = ScenarioReplay()
selection = replay.select('unsignalized_street', source_id='fixture',
                          session_id='session', boot_id='boot')
for sequence, ms, x in [(1, 0, .1), (2, 100, .13)]:
    frame = ReplayFrame('fixture', 'session', 'boot', sequence, ms)
    result = replay.observe(selection, frame, replay_ms=ms,
        vehicles=(VehicleSample('car-a', (x, .2, x+.1, .4)),))
# result.vehicles[0].state == 'image_displacement_observed'; live_supported=False
replay.current(1601)  # expires original capture; cannot auto-resume
```

## Custom-signal artifact inspection

`signal_artifacts.inspect_signal_artifact(path, SignalArtifactRecord(...))`
checks bounded operator-owned bytes against a separately trusted expected size
and SHA-256. Required metadata includes unique ordered classes with `walk` and
`dont_walk`, source, license, scene-split/evaluation references and conditions.
Generic COCO traffic-light labels do not satisfy that custom class contract.

This verifies identity with the supplied record only. Text references are
metadata, not audited licenses or validated held-out results. The inspector
does not discover actual model class IDs, deserialize checkpoints, import an ML
runtime or enable live inference, even if metadata lists night. No custom weights
or current custom artifact manifest are supplied. CS-036 trusted provenance,
runtime class verification and CS-038 held-out evaluation remain prerequisites
for a separately reviewed real loader/adapter. A caller-supplied matching hash
does not establish model trust or accuracy.

## Validation and limits

Run `.venv/Scripts/python.exe -m unittest discover -s tests/vision -v` explicitly;
repository root CI does not discover the vision root. New tests cover isolation,
actual schematic pixels/countdown, epoch/sequence/age/clock faults, late tokens,
beacon ambiguity/undersampling, motion/occlusion/night, hidden/lost/unchanged
vehicles and bounded state. Artifact tests use inert bytes, never a model.
Evidence: `qa/vision/scenario-adapters-validation-20261018.json`.

The software checkpoint is reviewable; full CS-037 still needs licensed real
data, custom weights, evaluated live/temporal adapters, verified source clocks
and controlled integration. No real-world accuracy, night support, Pi benchmark,
physical cancellation or road-use acceptance is established.
