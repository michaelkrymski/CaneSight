# CR-CS-001-pm-self-assignment: distinguish allocation from merge approval

Status: Proposed; exact-head PM GitHub authorization and independent review required.
Author: Michael Krymski (AI-assisted). Task: CS-001.
Base: 6a386675d24e88082fce9f3e063f101098c1e7bd.

## Evidence and necessity

Michael is PM/lead developer and controls task allocation. The instructions require every claim to merge before implementation, while native main protection requires one independent review and rejects self-approval. Consequently Michael cannot begin his own unclaimed task without waiting for a teammate to approve the allocation decision. This delays work even though the existing trusted ownership guard already exempts the actual PM PR author from the teammate pre-merged-claim restriction.

## Smallest amendment

Update AGENTS.md to recognize a narrow provisional PM self-assignment: an assignment-only PR actually authored by michaelkrymski, claiming an unowned main task, authorizes Michael to start after the initial claim diff and identity are verified and its commit/PR recorded. Continue implementation in that same PR and obtain an independent review before merge. Add docs/operations/PM_ASSIGNMENTS.md with the exact procedure. Add two regression tests verifying the existing PM-author admission seam and retaining teammate-claim, reassignment and scope protections. No task is assigned by this amendment.

Initial claim changes are confined to owner/status/branch/pr_url in that task, a new assignment handoff/changelog fragment and generated log. Requirements, acceptance, dependencies, allowed paths, existing evidence and blockers remain unchanged. Check accepted main AND open PM assignment PRs before competing for a task. A closed-unmerged assignment ends the provisional authorization.

Protected files changed: AGENTS.md and tests/test_governance.py. The existing master plan, runtime guard code, workflows, CODEOWNERS, governance.json and all GitHub branch settings remain unchanged. Main remains accepted state; the pending assignment PR is an explicitly documented provisional allocation record until implementation and assignment merge together.

## Alternatives

1. Keep waiting for peer review of every PM allocation: unnecessary work-start bottleneck.
2. Exempt all PM merges/admin actions: too broad and not requested.
3. Replace native approvals with a conditional workflow status: requires a stronger independent authorization infrastructure because untrusted same-repository workflows share the GitHub Actions status identity. Do not lower native approval requirements as part of this change.
4. Add a separate assignment service/bot: unnecessary infrastructure for this hackathon.

The existing workflow/prompt files remain unchanged because they are outside this task scope; AGENTS.md states the explicit exception and links its operations runbook. The proposed documentation exception uses the existing verified PM-author seam and preserves native independent code review.

## Impact and limits

This authorizes work start, not an unreviewed assignment-only merge to main. Ordinary teammate claims keep their merged-ownership requirement. Occupied-task reassignment and protected/scope/contract changes keep existing CR and exact-head approval. Done status still requires accepted evidence. No automatic merge, direct main push, branch bypass, credential, code execution or motor/navigation behavior is introduced. Dashboards may show provisional progress while main owner remains unclaimed; teammates must check the actual PR.

## Migration and rollback

Review/merge this amendment through today's unchanged native protections. Once accepted, Michael can open and verify his own claim-only draft, begin work in that PR, and get an independent implementation review when ready. Existing teammate claims and assignments need no migration. To roll back the policy, restore the prior merged-claim prerequisite in a reviewed PR and coordinate any in-flight provisional allocation; do not reset other work or edit history.

## Validation and approval

Run the full shared suite (including the two authorization-boundary regressions), structural validation, generated changelog check and diff whitespace check. Inspect the staged diff with trusted-base governance: no structural/scope errors, protected exact-head PM approval required. Read-only inspection of main rule 84965762 confirmed required PR + one approval, dismissal of stale reviews, strict Actions-bound governance/repository-checks, conversation resolution and admin enforcement; force pushes/deletions disabled. Do not save any settings changes.

Approval: pending Michael's exact-head PM-APPROVE-PLAN comment and another teammate's approving review on this amendment. The file itself is not authorization, and this amendment cannot use its own proposed exception to bypass current rules.
