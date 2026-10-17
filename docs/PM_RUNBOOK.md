# Michael's PM / lead developer runbook

## Start the team

1. Confirm the remote repository URL and that all initial files are pushed.
2. Add only the named teammates as collaborators using their own GitHub accounts. No invitations are sent until usernames are provided.
3. Configure `main` protection/ruleset: require PRs, require `governance` and `repository-checks`, require up-to-date branches, block force pushes/deletions, require code-owner review where supported, and apply to administrators where available. Restrict bypass to an explicit emergency process. Do not claim this is active merely because CODEOWNERS exists.
4. Set code owner `@michaelkrymski`. A code owner's account must have write access. Private-repo enforcement may require a paid plan; if unavailable, use PM-only merge/push permissions and a human review policy, while acknowledging the weaker guarantee. Do not make the repository public to gain features without a deliberate decision.
5. Validate the controls with a draft PR attempting a small protected-plan edit: governance must fail without exact-head PM approval, then pass only after the PM command and a valid CR/changelog. Do not merge the test change.
6. Assign tasks with claim PRs or one PM assignment PR. Every task initially has `owner: null`. Record owner, status and branch; do not assign missing people by guess.
7. Configure Trello sync following `TRELLO_SYNC.md`. Run it manually once and confirm the visible status block and labels before declaring automatic reporting live.

## Standup every 1–2 hours during the hackathon

Ask each human for task, working branch/PR, verified result, blocker and next checkpoint. Use repository handoffs/PRs as evidence. Choose one integration checkpoint and freeze optional features at elapsed hour 14. AI instances cannot report progress they have not been given.

Review open PRs by P0 dependency order. Keep accepted interface changes narrow. Check tested hardware evidence separately from unit tests. A PR is not a safety certification. An AI-authored “Done” is a proposal until merged acceptance.

## Merging

Check task owner, acceptance, meaningful tests, handoff and new changelog fragment. If two PRs touch the generated log, rebase then regenerate it—never delete another person's entry to resolve a conflict. A changed protected file needs a new CR and exact-head PM authorization. Require author updates when the PR grows new scope.

Merge claim PRs before implementation; merge implementation only when evidence supports status done. To accept partial work keep status in_progress/blocked with specific remaining work. Do not auto-merge just because CI is green. A revert is a new PR plus new changelog entry; don't erase history.

## Emergency correction

For a verified safety/technical error, prepare a focused amendment, record why it is urgent, approve the current head explicitly, run checks and merge. If an admin bypass is unavoidable, record exact actor, commit, reason, skipped checks and follow-up in a new immutable change entry. Do not turn a temporary exception into permanent disabled checks.

## Initial implementation priorities

The hardware and camera tasks remain unverified. The current practical step is Pi Wi-Fi recovery and CSI test capture (CS-021), alongside real-device iPhone signing/LiDAR (CS-013), source schemas/freshness (CS-003), and backend skeleton (CS-028). Motors/diodes ordered from Amazon can be represented by logged mock haptic commands until delivery and bench verification.

## References and product behavior

- [Codex AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md): persistent checkout instructions; other chat products should be explicitly given the files.
- [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches): actual server-side enforcement, subject to plan/permissions.
- [GitHub CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners): review ownership only becomes a merge restriction when required by protection.
- [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use): never execute untrusted PR code with privileged secrets.
