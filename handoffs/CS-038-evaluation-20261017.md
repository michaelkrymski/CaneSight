# CS-038 signal evaluation handoff

- Author: aditsangani (AI-assisted)
- Task branch: task/CS-038-signal-evaluation
- Starting base commit: 712ae1b7a8b20a097f222ddc1662a74a9546a702
- Integrated accepted main before publishing: 0ba7c1ef6a0f65a2529d3f111681b3fb47847ae0 (CS-025 PR #48 and CS-044 claim PR #50); no overlap with CS-038 changes.
- Assignment: claim PR #47 merged; accepted task owner is aditsangani.
- Dependency: CS-037 implementation PR #46 merged.

## Changed files

- backend/vision/signal_evaluation.py: fixed scenario inputs, pixel/selection replay, complete observation ledger, per-condition confusion and numeric OCR accounting, exclusive report output and failure exit.
- tests/vision/test_signal_evaluation.py: seven tests covering correct metric denominators, zero/readable/null values, no-sample metrics, annotation separation, cold/warm negative coverage, complete real-parser evaluation, deliberately wrong parser detection and durable CLI failure evidence.
- qa/vision/signal-evaluation-20261017.json: actual run, source/spec/pixel hashes and all observations.
- qa/vision/CS-038-EVALUATION.md: reproduction, interpretation, counts, correlated-input and real-world limits.
- tasks/CS-038.json: runtime status Review, task branch and evidence.
- New changelog fragment plus script-generated CHANGELOG.md.

## Tests actually run

- `.venv/Scripts/python.exe -m unittest discover -s tests/vision -v`: 53 tests passed, including seven new evaluator tests. Existing 46 vision tests retained.
- `.venv/Scripts/python.exe -m backend.vision.signal_evaluation --report qa/vision/signal-evaluation-20261017.json`: 127 scenarios, 309 checks (303 frames and six polls), zero required-output mismatches.
- The checked publisher runs repository validation, shared unit tests, generated-log consistency and whitespace checks before committing/pushing; its actual result is reported with the PR.

## Evidence and limits

Cold and previously-confirmed multiple heads, glare, occlusion, low resolution, generic lights and no signal returned unknown. Target-ID/ROI changes required new confirmation; expiry polling did not renew prior evidence. All 205 checks requiring null countdown remained null.

The observable-reference symbol matrix retains 23 walk and 110 hand abstentions. Numeric OCR exact-match across readable frames was 103/212 (48.58%), including 109 abstentions, with zero wrong emitted values; emitted-value exact-match was 103/103. The 100 two-slot controls contribute 200 correlated readable frames. Full per-condition counts and failures are preserved, not treated as independent scenes.

There are zero held-out/real scenes; templates and synthetic evaluation share the CS-036 generator. This is a manual schematic profile regression evaluation, not automatic pedestrian recognition, applicability, real-scene/OCR accuracy, live timing, electrical verification or crossing permission. Existing parser, production adapter, readiness, shared contracts, model weights and hardware logic are unchanged.

## Next steps

Michael reviews the software evidence, limits and current PR head. Review does not mean Done; acceptance remains his decision. Real-scene claims require independently licensed footage and scene-separated evaluation. No training or hardware work is started by this PR.
