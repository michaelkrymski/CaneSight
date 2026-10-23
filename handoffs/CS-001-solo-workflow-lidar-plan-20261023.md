# Solo workflow and calibrated LiDAR plan

Base a253bf6; branch solo-workflow-and-lidar-plan. Michael explicitly authorized
solo operation and removal of claim, task ownership and extra reviewer blockers.
No task ownership was silently transferred; old allocation fields remain history.

Changes: trusted-main solo-owner governance exemption, owner publishing without
task ID/task branch patterns, no required Trello/owner/scope metadata for new solo
task records, current instructions plus historical notices, and no CODEOWNERS
review requests. Technical checks and runtime device/motor behavior remain.
The plan/prompt define sighted-helper calibration after mount angle changes,
existing Mac yellow region, frame-aligned fused gravity attitude, physical ROI/
floor/height validity, and obstacle-side cues with user-selected movement.

Four new solo regression tests passed. Full root suite ran 244 tests on Windows:
one existing tests/ios/test_pi_phone_probe.py mode-600 credential test cannot
pass on this Windows filesystem; 14 skips. Its runtime protection was not changed.
The other root tests, including team-mode governance and publisher behavior,
passed. Repository structure, generated log and whitespace checks are required.
Linux GitHub CI remains the authoritative cross-platform publication check.

Remote audit: GitHub credential has admin permission. Before transition, main
required one review, governance/repository-checks with strict freshness, admin
enforcement and conversation resolution; no rulesets. Prior settings will be
backed up outside Git. Applied changes/publication recorded in a follow-up below.

Backend read-only audit: TLS verified with certificate expiring Oct 27 07:24:45 UTC,
healthz 200, readyz 503, bond route GET 405. Later readiness request timed out;
do not infer the exact readiness cause or physical connectivity. Mac has newer
work on claim/CS-013-michaelkrymski (c34520b); backend activation evidence is on
task/CS-033-bond-backend (9469d81, PR #98). No live service was restarted.

## Applied solo settings and portability follow-up

GitHub main protection was updated and read back: required reviews null,
admin enforcement false, conversation resolution false; only repository-checks
remains required in the review path. Strict status freshness, no force pushes
and no deletions retained. Previous settings are saved outside Git as
solo-main-protection-before-20261023.json. No rulesets exist.

The preexisting mode-600 fixture now has the same explicit POSIX-only test guard
as its adjacent permissions test. This changes only test platform applicability,
not the credential loader; Linux CI still executes the test. Root discovery was
repeated after that portability correction. Publication/CI results follow remotely.
