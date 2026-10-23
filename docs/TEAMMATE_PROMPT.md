> Historical team workflow. Superseded on October 23, 2026 by AGENTS.md and docs/operations/SOLO_DEVELOPMENT.md. Claim, ownership and extra-review requirements below do not apply to Michael in solo mode.

# Copy into each teammate's own AI session

Replace the bracketed values before starting. If this chat cannot access the repository, attach the listed files and a current source snapshot.

```text
You are helping me implement CaneSight task [CS-NNN]. I am [human name / GitHub username].
Repository: [repo URL]. Base commit: [full main SHA]. Task branch: [task/CS-NNN-username].

Read AGENTS.md, docs/TEAM_WORKFLOW.md, docs/master/MASTER_PLAN.md,
tasks/[CS-NNN].json, relevant shared contracts, and the latest handoff for this task.
Confirm my claim is merged and summarize the acceptance criteria before editing.

Work only within the task's allowed paths. Preserve the master plan, governance,
other teammates' files, shared contracts, and changelog history. If a necessary plan
change is found, create a separate CR proposal with evidence for Michael; do not
silently rewrite the plan or expand scope.

Implement and run meaningful tests. Tell me exactly which tests were run and what
was not tested. Update only this task's runtime fields; add a new handoff and
changelog fragment and regenerate CHANGELOG.md. Open a PR titled [CS-NNN] <outcome>.
Do not merge or push to main. Report blockers explicitly. A draft/ready PR means
In progress/Review; Done requires accepted evidence on main.

If you cannot write to GitHub, return a patch, test instructions and handoff so I
can apply them. Do not claim you changed Trello or the repository without verifying it.
Never provide crossing permission or treat missing detections as a clear path.
```
