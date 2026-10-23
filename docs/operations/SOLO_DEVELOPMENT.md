# Solo workflow — October 23, 2026

Michael is now the sole maintainer. His explicit request replaces the original
multi-person claim/assignment and approval process. No claim, task ID, ownership
transfer, formal CR or second-person approval is needed for his work. He can edit
all paths and requirements, add tasks and merge his own changes.

`governance.json` sets `collaboration_mode: solo`. The trusted-main governance
check skips task/title/scope/claim/approval gates for `michaelkrymski` only. It
does not authorize other PR authors to change their own trusted policy. Reverting
the flag restores team-mode guard behavior for future PRs.

Task files are optional planning aids. Existing owners and statuses are retained
as history, not locks. New solo task records need a valid unique CS-NNN ID; they
do not need a Trello card, owner, allowed-path allocation or prerequisite claim.
JSON structure, IDs, valid statuses and dependency consistency are still checked.

Use any named branch. PRs remain useful for a diff/CI view, but are optional.
The optional checked publisher accepts no task ID in solo-owner mode:

```sh
python scripts/publish_task.py --message "Describe the change" --files path/to/file.py
```

It still avoids unrelated files, credentials, wrong remotes, unresolved conflicts
and destructive git operations; it runs checks before publishing. Use ordinary
git when a narrowly selected checkpoint or another workflow is more appropriate.
Same-account chats on Mac and Windows still need separate working branches or
worktrees; sole ownership does not prevent simultaneous edits from conflicting.

GitHub settings transition: remove mandatory pull-request reviews and conversation
resolution, stop enforcing protections against the repository administrator, keep
repository-checks configured for the review path, and retain no-force/no-delete
settings. Remove the old governance status as a required branch-protection check.
CI tests still run; admin authority allows the solo maintainer to proceed without
an unavailable second reviewer. Record actual applied settings in the handoff.

No credentials, collaborators, deployment configuration, runtime freshness or motor
controls are removed by this workflow change. Physical validation remains distinct
from software tests. Older team documents are historical where they conflict with
this page and AGENTS.md.
