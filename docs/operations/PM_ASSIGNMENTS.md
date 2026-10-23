> Historical team workflow. Superseded on October 23, 2026 by AGENTS.md and docs/operations/SOLO_DEVELOPMENT.md. Claim, ownership and extra-review requirements below do not apply to Michael in solo mode.

# PM self-assignment and independent implementation review

Michael Krymski (`michaelkrymski`) controls task assignments, including his own.
Deciding who starts a task does not require a second person's approval. Merging
implementation into accepted main still requires an independent approving review
and all existing checks. No branch-protection setting is changed by this policy.

## Start an unclaimed task as PM

1. Fetch main and inspect its `tasks/CS-NNN.json`. Confirm owner is null and check
   all open PRs for that exact task ID, including pending PM assignments. Do not
   compete with another active claim or implementation; resolve allocation first.
2. Create `claim/CS-NNN-michaelkrymski` from current main. Set only assignment
   runtime fields: owner to `michaelkrymski`, status to `in_progress`, branch to
   this branch, and optionally pr_url after the PR exists. Preserve every other
   task field, including evidence, blocker, requirements and scope.
3. Add a uniquely named changelog fragment describing the assignment and a new
   task handoff. Regenerate CHANGELOG.md, run shared repository checks, commit,
   push, and open `[CS-NNN] Assign <task> to Michael` as a draft PR.
4. Verify the real GitHub PR author is `michaelkrymski`; a name in a file or PR
   body is insufficient. Record the PR URL, initial claim commit and accepted
   main base in the handoff/session. Verify that initial commit's PR diff contains
   only the assignment runtime fields, its new changelog/handoff records and the
   generated log. Check task structure and main/open-PR ownership again.
5. The verified PM assignment now authorizes Michael to start implementation.
   Continue in that same PR and branch; do not open a competing implementation
   PR for the same task. Update the title/description to describe the resulting
   implementation and append its own changelog fragment/handoff checkpoint.
6. Run task-specific and repository checks. Mark the PR ready when implemented.
   Another teammate with write access reviews the current head. Merge only after
   that approval and normal required checks/conversation resolution pass. The
   implementation and assignment record then land together on main.

The first assignment-only commit remains reviewable in the PR history. Later
implementation commits do not erase the original work authorization, but they
must receive normal code review. Refresh/reconcile the branch when main changes.
If the PR is closed unmerged, the pending authorization ends; coordinate release
or a replacement assignment before anyone else begins.

## What changes and what stays enforced

- A PM self-assignment can start before its PR merges. Until merge, open PM
  assignment PRs are a provisional allocation record; accepted main is unchanged.
  Task dashboards may show an open claim as in progress while main's owner field
  is still unclaimed. Consult the actual PR to determine pending ownership.
- Other teammates' claim PRs still wait for Michael's approval/merged assignment.
  As their reviewer, Michael can manage those assignments under the normal flow.
- Reassigning an occupied task, modifying requirements/allowed paths/dependencies,
  changing governance or protected files, and marking Done are not covered. They
  retain their current evidence, change-request and exact-head approval rules.
- PM assignment authorization never supplies a code approval. A different
  reviewer is still needed for Michael's implementation. No automatic merge,
  admin bypass, review-setting change, credential or remote agent is introduced.

## Existing technical enforcement

`scripts/governance.py` already exempts the verified PM PR author from the
pre-merged teammate-claim restriction. Ordinary authors remain subject to it.
The existing main branch rule still requires a pull request, one approving
review, dismissal of stale approvals, GitHub Actions-bound `governance` and
`repository-checks`, an up-to-date branch and conversation resolution. It applies
to administrators, with force pushes and deletion disabled.

This policy removes a work-start bottleneck without changing those settings.
It does **not** make assignment-only PRs mergeable without a peer approval. That
different behavior would need a separately reviewed authorization design; do not
disable native required approvals or replace them with an ordinary forgeable
workflow status as an incidental setup step.
