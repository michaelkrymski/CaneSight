# CaneSight team workspace

PM and lead developer: **Michael Krymski (`@michaelkrymski`)**.

This repository coordinates separate human-owned Codex/Work/ChatGPT sessions. Git `main` is the accepted project state. Chat history is not shared memory. Trello is a progress view, not the architecture authority.

- [Start here: team workflow](docs/TEAM_WORKFLOW.md)
- [Protected master plan](docs/master/MASTER_PLAN.md)
- [Master changelog](CHANGELOG.md)
- [Copyable teammate prompt](docs/TEAMMATE_PROMPT.md)
- [PM dashboard and launch checklist](docs/PM_RUNBOOK.md)
- [Trello board](https://trello.com/b/aH113bQW/canesight-20-hour-prototype)
- [Trello automation setup](docs/TRELLO_SYNC.md)

## First five minutes

1. Clone this repository and read `AGENTS.md` and the master plan.
2. Ask Michael for a task ID; inspect `tasks/CS-NNN.json` and its dependencies.
3. Submit a small claim PR setting that task's `owner` to your GitHub username and `status` to `in_progress`. Michael merges one claim. Start implementation only after your claim is on `main`.
4. Create `task/CS-NNN-yourname` from updated `main`. Keep one task per branch.
5. Implement within the task's allowed paths, write a handoff and one new changelog fragment, then open `[CS-NNN] Concrete outcome` as a PR.

See the runbook for the PM's direct assignment option. Teammate usernames are not yet known; tasks are initially unclaimed, not silently assigned to the PM.

## Checks

Python 3.11+; governance tools use the standard library only:

```sh
python scripts/validate_repo.py
python -m unittest discover -s tests -v
python scripts/render_changelog.py --check
```

The bootstrap contains coordination tools and app directories, not a working CaneSight application. No hardware or road-safety acceptance is claimed. Camera, power and LiDAR tests still require the actual devices.

## Protecting the plan

`AGENTS.md` guides assistants; it is not a security boundary. GitHub must enforce PRs, required checks, no force pushes and PM ownership of protected files. Private-repository enforcement depends on the GitHub plan. Read [protection setup](docs/PM_RUNBOOK.md) before treating the master plan as technically locked. Administrators with bypass access can still override protection; restrict that access.

Trello automation is installed as workflow source but remains inactive until its Secrets and enable variable are configured and an initial sync succeeds. It does not infer work completed inside an unreported private chat.
