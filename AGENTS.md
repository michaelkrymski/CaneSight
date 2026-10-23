# CaneSight — solo development

Michael Krymski (`michaelkrymski`) is now the sole maintainer. He explicitly
authorized this workflow on October 23, 2026. This file and
`docs/operations/SOLO_DEVELOPMENT.md` supersede older team-claim, PM-approval,
task-scope and second-reviewer instructions elsewhere in the repository.

## Work autonomously

- Do not require a task ID, claim PR, merged assignment, ownership transfer,
  path-scope approval, formal CR, exact-head approval comment or another reviewer.
- Michael may add tasks, edit requirements/contracts/plans, use ordinary branches,
  commit, push and merge his own changes. Existing task owners describe history;
  they do not block him from continuing any work. Do not mass-rewrite that history.
- Task records, handoffs and PRs are context, not permission gates. A PR is optional.
  Sensor contract changes still need coordinated client/backend validation; there
  is no separate administrative approval ceremony.
- Inspect git status and fetch main. Preserve uncommitted work. Use a separate
  branch/worktree if another chat on either computer is editing the same files.
- Run meaningful checks, commit/push authorized work and inspect CI. Never report
  unrun tests or simulated/bench checks as physical acceptance. Keep secrets and
  private footage/checkpoints out of Git.
- Prefer small recoverable commits and fast-forward/squash merges. No force push,
  destructive reset or history rewrite is needed for routine solo work.
- `scripts/publish_task.py --message "..." --files ...` is an optional checked
  publisher. In solo-owner mode task ID is optional; any named branch works,
  including main. Normal git operations are also allowed. A missing optional
  task/handoff/fragment is not grounds to stop an authorized change.

## Technical behavior

Solo workflow changes are separate from runtime device behavior. Keep stale or
unknown observations unknown, bounded motor pulses, explicit stop/disarm behavior,
clock/capture provenance, private per-device credentials and verified TLS.
No all-clear or crossing-permission claim. Vibration identifies obstacle location;
the user chooses their own movement with the conventional cane.

Follow Michael's current product requirements. Calibration must be repeated
after the phone mount angle changes. Read the latest Mac/Windows LiDAR handoff
before implementing it. Do not infer the Mac-only yellow debug region's source.
