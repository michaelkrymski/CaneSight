# CS-037 isolated scenario replay adapters

Base: `20d69c9f43a3a19a3aa102ca04933f9d0e379284`; branch `task/CS-037-signal-parser`. Accepted ownership is aditsangani on main. This follow-up implements the merged three-scenario amendment, retaining original task requirements and CS-036 dependency. Human authorized CS-037 software work; no real model training requested.

## Changed files

New backend/vision/scenario_adapters.py, signal_artifacts.py and SCENARIO_ADAPTERS.md; new tests/vision/test_scenario_adapters.py and test_signal_artifacts.py; new qa/vision/scenario-adapters-validation-20261018.json; own task runtime; this handoff; new changes/20261018-cs-037-scenario-adapters-aditsangani.json; generated CHANGELOG.md.

## Behavior

Explicit single-scenario selection bound to source/session/boot and local generation object. Old selections cannot observe or affect new state. Original ReplaySignalParser handles actual schematic pixels and nullable observed digits unchanged. Separate replay-only components process authored beacon on/off annotations and visible vehicle boxes/IDs. Bounded history, continuity/age/clock/sequence gates; target/ROI changes, hidden/lost tracks, sparse sampling and motion/night uncertainty never establish flashing/stationary/yielding traffic. Expiry/source failures require new explicit selection; clock failure requires a new instance. One source epoch per controller. Empty detections never grant clearance.

Custom-artifact inspector verifies trusted expected size/hash and required class/provenance metadata without importing an ML runtime, downloading/deserializing a model or claiming referenced evaluation/license review. All live capabilities stay false. It is a preparation boundary for future CS-036 artifacts, not a live YOLO adapter. No cross-process scenario fields or production wiring added.

## Tests actually run and evidence

Windows/Python 3.14.3: `python -m unittest discover -s tests/vision -q`: 80 passed, zero skips/failures, including 22 scenario and 5 artifact regressions. Existing replay parser/evaluation tests retained. New artifact tests use inert authored bytes. Normalized source hashes and coverage are in the new QA JSON. Checked publisher runs current shared tests plus repository/governance/rendered-log/whitespace checks before push; current-head remote CI inspected after publishing. Vision suite is separate from root discovery.

## Limits and next steps

Software checkpoint for independent Michael review; full CS-037 status Blocked, not Done. No custom training/data download, real recognition accuracy, actual detector/track association, validated flash rate, unsupported night, live capture-clock bound, Pi performance, phone/audio/button/motor or electrical acceptance. Camera motion/visibility and IDs are authored annotations, not a motion estimator. Need licensed independent scenes, reviewed custom models and held-out per-condition/temporal evidence under CS-036/038 before enabling actual adapters. Any later menu/job integration stays separately reviewed; shared wire changes need a CR. Publish a new PR for this follow-up; original PR #46 remains immutable merged history.
