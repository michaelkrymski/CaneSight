# CS-045: offline measurement-analysis preparation

- Accepted base: `5dbb6adc6f7c8984e1beb624fc7c8fe1a4cdfafa`.
- Publication base: `f85e833` (Michael merged CS-017 PR #63 during this work;
  branch fast-forwarded to accepted main without changing existing work).
- Branch: `task/CS-045-measurement-analysis`.
- Merged assignment: https://github.com/michaelkrymski/CaneSight/pull/54.
- Scope: `qa/`, `tests/`, own task runtime and new records only.

## Changed files

`qa/measurements/` adds an offline, standard-library analyzer, a collection and
normalization guide and a deliberately incomplete synthetic example.
`tests/measurements/` adds 15 regression tests. `tasks/CS-045.json` records progress
and physical evidence gates. New immutable changelog and this handoff describe
software preparation; generated `CHANGELOG.md` is rendered by the publisher.

The analyzer reports conservative original-capture-to-endpoint latency bounds,
sample count, median/nearest-rank p95/max and combined endpoint interval width.
Capture IDs/times must increase; impossible stage ordering, unknown fields,
duplicate JSON keys, malformed/oversize/nonfinite data and mixed endpoints fail
closed. It does not infer clock mappings. Command and physical onset cohorts stay
separate. Failed/cancelled/missing trials remain counted. Depth errors and
availability are grouped by sector and measured distance; null depth never becomes
zero or disappears from coverage. No accuracy pass threshold is invented.

## Tests actually run

- Windows Python: all 15 focused unit/CLI tests passed.
- Local Docker `python:3.12-slim`, network disabled, read-only source bind: all
  15 focused tests passed. Image digest:
  `sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`.
- CLI analyzed the included example: two attempted, one observed, one unavailable;
  latency interval 80–100 ms; fewer than 20 observed; depth coverage 1/2;
  `synthetic_only`. Those are fixture numbers, not device measurements.
- Checked publisher runs repository structure/governance, root unittest suite,
  generated changelog and whitespace checks before committing/pushing. Inspect
  current PR head CI for final results.

## Remaining limits and next steps

Software preparation is ready for independent review. CS-045 acceptance remains
blocked on real phone/Pi timing with independently evidenced capture-clock bounds,
at least 20 observations per measured endpoint/cohort, physical onset when claimed,
and controlled measured-distance depth results. CS-015/016/025 integration and
physical power/mount prerequisites remain relevant; this analyzer does not supply
them. Follow the README to collect/normalize one source boot/configuration per
private run, preserve failed trials and review provenance before publishing any
sanitized results. Bench declarations are not authenticated hardware evidence.

No Pi, camera, SSH runner, network device, GPIO or motor access. No production
activation or new protocol. Synthetic evidence cannot mark this task Done.
