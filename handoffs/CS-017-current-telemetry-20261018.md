# CS-017 preparation for current CS-016 integration

Task: CS-017. Owner: gmarcialcalleja.
Existing PR: https://github.com/michaelkrymski/CaneSight/pull/84.
Branch: task/CS-017-transport-fence. Starting head: 4c67bf82bf82951bb7947a19ac7c95b28f0cc873.
Accepted main integrated: a239e221b1d51d7673a78e8fb84e6df274b36e39.
Merge checkpoint: 460410e. No competing branch/session was started.

The human requested task-by-task integration preparation while CS-016 finishes.
The actual lifecycle coordinator already exists in this PR. This checkpoint
prevents its verification from staying tied only to Mila's historical telemetry
pin: the harness accepts --telemetry-ref, resolves an exact commit and archives
only that package without executing teammate scripts or changing the host pins.
It also supports CS-016's future accepted sibling layout after the duplicate
review pin is removed. Missing package is rejected before container execution.

Changed files: tests/ios/run_lifecycle_transport.py, new source-hashed evidence
tests/ios/evidence/CS-017-current-telemetry-20261018.json, host README, task runtime
evidence/blocker, this handoff/new changelog fragment and generated log. Accepted
main's other changes are inherited, not modifications to unrelated task scope.

Actually run: python tests/ios/run_lifecycle_transport.py --telemetry-ref 8a6c7b2
--output tests/ios/evidence/CS-017-current-telemetry-20261018.json: all 13 actual
production coordinator/actor tests passed under the pinned Swift 6.0.3 Linux
image, --network none, strict concurrency complete and warnings as errors. The
evidence resolves the full dependency commit and records actual source hashes.
Three Python Pi receiver lifecycle regressions passed. Merge checks passed
structure/log/whitespace and 222 shared tests, 11 Windows/platform skips.

No new actor/coordinator API changes were needed for that review head. The host
Apple SDK/ARKit body and real native paired phone/Pi behavior were not tested.
When CS-016 lands, retain its sibling telemetry package project reference and
remove the old duplicated review pin during reviewed integration; keep this PR's
LifecycleTelemetry and camera capture fence hooks. Current host construction
still needs authorized enrollment and verified source capture-clock mapping.
Do not infer that a newer review head or actual device is covered by these exact
source results. No source/task requirements, shared contract or hardware gates
were changed; no physical actuation or task completion is claimed.
