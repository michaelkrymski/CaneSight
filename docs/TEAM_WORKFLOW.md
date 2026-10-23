> Historical team workflow. Superseded on October 23, 2026 by AGENTS.md and docs/operations/SOLO_DEVELOPMENT.md. Claim, ownership and extra-review requirements below do not apply to Michael in solo mode.

# Team operating system

## Source of truth

| Artifact | What belongs here | Who changes it |
|---|---|---|
| `docs/master/MASTER_PLAN.md` | Accepted scope, architecture, hardware, safety and milestones | Michael approves exact changes; no model rewrites |
| `shared/` | Accepted interface/schema contracts | Contract owner proposes; Michael approves |
| `tasks/CS-NNN.json` | Task requirements plus owner/status/evidence | Assigned teammate updates runtime fields; PM changes scope |
| `changes/*.json` | One permanent record of each accepted change | Author adds a new fragment; previous fragments immutable |
| `CHANGELOG.md` | Readable generated master log | Renderer, included in each PR; resolve by regenerating |
| `handoffs/` | What a session actually did and what remains | New file per handoff; never overwrite another session |
| `decisions/CR-*.md` | Proposed and accepted plan amendments | Proposal by anyone; approval by Michael |
| Trello | Category/priority plus managed progress and PR links | One-way repository/PR sync; humans may add discussion |

Existing architecture under `docs/reference` is historical evidence and contains superseded crossing claims; it must not override the corrected master plan.

## Work allocation

Michael owns prioritization, integration, shared contracts, review and release claims. Suggested lanes are iPhone (`ios/`), Pi/haptics (`edge/`), hardware (`hardware/`), backend/vision (`backend/`), dashboard (`dashboard/`), and QA (`qa/`). People can own several lanes, but no two sessions should edit the same task concurrently.

Claim protocol: create a small `claim/CS-NNN-username` branch from current `main`; set owner and in_progress in the task JSON; add a changelog fragment; open a claim PR. Michael chooses and merges one claim. Another candidate rebases, sees the occupied owner and stops. Git conflicts plus the governance check reject ownership takeover unless Michael explicitly approves reassignment on the current head. Michael may batch-assign multiple tasks in a single reviewed setup PR.

Do not wait for all 58 tasks. Start the parallel lanes with CS-013 (real-phone build), CS-021 (Pi camera), and CS-003/028 (protocol/backend). Michael coordinates CS-001/002/004 and hardware feasibility CS-005/006. Shared contracts are agreed before integration. No code has been assigned or those tasks marked complete by this bootstrap.

## Every session

1. Fetch/pull latest `main`; inspect outstanding local edits before switching branches.
2. Read repository instructions, master plan, task JSON and dependencies. Summarize the assigned acceptance and identify relevant files.
3. Confirm your merged claim. Use a task branch or isolated worktree based on current `main`.
4. Implement a small reviewable change. Use mocks/fixtures when dependencies are unavailable and label them clearly.
5. Update task runtime fields and write a handoff. If blocked, state exact missing input and set blocked; keep the branch/evidence links.
6. Add a new JSON changelog fragment; regenerate the master log. Open a draft PR for ongoing work, ready PR for review.
7. Michael reviews acceptance and merges. Pull latest `main` before starting another task. Follow-up fixes need their own recorded change.

## Status semantics

- Backlog: unclaimed, no implementation claim.
- In progress: merged claim, or an open draft PR with the task ID.
- Blocked: task JSON contains an explicit blocker; this overrides PR-derived review status.
- Review: open ready PR references the task; it is not accepted yet.
- Done: task on `main` says done and includes evidence; Michael accepted the PR. Merge alone never silently marks hardware complete.

The sync reads all open PRs; title format `[CS-021] ...` is required. Multiple active PRs for one task are flagged as ambiguous/blocked in the progress view. A closed unmerged PR stops contributing status. Never use percentage complete without an explicit measurable basis.

## Plan amendments

Ordinary implementation updates do not change the master plan. A change is necessary when accepted requirements are impossible, technically wrong, unsafe, or materially inconsistent with verified evidence—not for wording preferences.

1. Add `decisions/CR-<task>-<unique>.md` using the template.
2. Include the smallest proposed diff to protected files, a changelog fragment and affected tests.
3. Michael reviews the exact head commit. To authorize, Michael posts `PM-APPROVE-PLAN <full-head-sha>` on the PR, or submits an approving review on that exact head. Authorization expires after any new commit. The governance workflow verifies identity through GitHub API metadata, never a username written in a file.
4. Re-run the governance workflow after a comment/review. Merge only after required checks pass. A PM-authored PR still needs the explicit command/review when protected files change.
5. Update the plan version only for the approved amendment; keep old history in Git and immutable change records. No destructive rewrite of the plan or changelog history.

GitHub protection and human review enforce this agreement. A README/AGENTS instruction alone cannot prevent a model or admin from overwriting a file.

## Across different ChatGPT/Codex accounts

Everyone uses their own account and authorized repository access; do not share account passwords. Codex uses the checkout and instructions. In a chat without a writable checkout, attach a snapshot containing AGENTS, master plan, assigned task, relevant contracts and handoff template. Have it return a patch plus evidence; a developer reviews/applies the patch on that task branch. Reattach updated files for a new session. Never assume hidden chat memory is current project state.

The team does not need a central AI conversation. The PM can use one chat for coordination, but accepted decisions must land in the repository. This workflow has no model API costs beyond each person's existing product usage; automation uses ordinary GitHub Actions and Trello APIs, subject to account limits.
