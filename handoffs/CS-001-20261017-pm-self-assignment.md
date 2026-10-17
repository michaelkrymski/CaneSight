# CS-001 PM self-assignment policy amendment

Author: Michael Krymski (AI-assisted).
Branch: task/CS-001-pm-assignment-review-policy.
Base: 6a386675d24e88082fce9f3e063f101098c1e7bd.

## Result

The proposed policy permits Michael to authorize starting his own unclaimed task through a verified PM-authored assignment-only draft PR, then continue implementation in that same PR and obtain peer review before merge. Main's accepted task record lands with the reviewed implementation. Open pending PM assignments must be checked before competing for a task. The initial PR identity/diff/commit are recorded; closed-unmerged authorization ends.

Files: AGENTS.md; docs/operations/PM_ASSIGNMENTS.md; tests/test_governance.py; new CR and changelog fragment; generated CHANGELOG.md; this new handoff. Two tests preserve verified PM versus ordinary teammate authorization and scope/reassignment safeguards. No task JSON, master plan, guard script, workflow, CODEOWNERS, branch setting, runtime or device changed. No new agent or auto-merge mechanism.

## Verification

All 41 shared tests passed, including two PM/teammate/scope/reassignment boundary regressions. Repository validation, generated-changelog verification and whitespace checks passed. Publication also requires inspection of the complete staged diff using trusted-base governance; the PR records that result and its current head. Main branch settings were inspected read-only: required PR/one independent approval, stale dismissal, strict Actions-bound statuses, conversation resolution and admin enforcement remain enabled; force/deletion disabled.

## Acceptance

Current rules govern this amendment: Michael's exact-head command plus a teammate's independent review and all checks before merge. This is a policy exception for work start, not a conditional unreviewed merge exemption. If Michael instead needs assignment-only PRs merged without peer review, that requires a separate authorization design and explicit review; this amendment does not lower native protections. After merge, use the new runbook and keep actual implementation independently reviewed.
