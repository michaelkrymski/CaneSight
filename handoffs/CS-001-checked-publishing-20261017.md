# CS-001 checked publishing amendment

Base: ac96e139a75e4ef61b2876c01c3d71dd6d508ea3. Branch: task/CS-001-publishing-workflow.

Michael requested communication to Gavin and future routine automatic task-branch publishing by each teammate's own instance. Feedback delivered on PR #2: https://github.com/michaelkrymski/CaneSight/pull/2#issuecomment-6230691235 . An idle local session cannot be woken by that comment.

Changed: AGENTS.md, scripts/publish_task.py, scripts/ci_feedback.py, scripts/render_changelog.py, protected regression tests, operations guide, new CR and change fragment, generated CHANGELOG.md and this handoff. No task record or master-plan edit. CS-001's inventory/hardware acceptance remains unverified and is not marked done.

Validation: repository structure; 21 unittest cases; generated log check; whitespace check. The integration test uses only temporary local repositories (including a bare remote), exercises failure before commit/push, rejects unrelated work without deleting it, and confirms task-branch publication leaves main unchanged. Remote guard is substituted only in that isolated test; production accepts only the intended GitHub origin. The portable-renderer test covers mixed-case fragment names; CI provides actual Ubuntu verification. No hardware, deployment, or real teammate-computer automation was run.

Limitations: helpers require Python 3.12+, Git, local credentials and an active authorized agent. They do not open a PR themselves, install a service, wake another chat or merge. The active agent creates/verifies a PR with available tools, then reads CI and PM feedback. Protected changes require existing amendment approval and collaborator review. Trello enablement and credentials are untouched.

Next: review CR-CS-001-checked-publishing.md, authorize the exact current head and obtain a collaborator review, then merge through existing rules. Teammates pull accepted main and use docs/operations/AUTO_PUBLISH.md in their own sessions. Gavin can independently correct the lowercase name of his unmerged fragment while waiting. Preserve historical fragments.
