# Automatic Trello progress

Board: https://trello.com/b/aH113bQW/canesight-20-hour-prototype

The repository already maps all 58 task IDs to existing cards. No duplicated board or cards are required. Category lists and priority labels remain intact.

## What updates automatically once enabled

- Push to `main`: accepted owner/status/evidence updates.
- PR opened or converted to draft: In progress.
- PR made ready or opened ready: Review.
- Multiple open PRs referencing one task: Blocked pending PM reconciliation.
- PR closed without merge: returns to canonical task state.
- Merged PR: task state on `main`; Done only if explicitly accepted with evidence.
- A manual Actions run reconciles all cards and repairs a missed/failed trigger.

GitHub Actions adds one `Status: ...` label and replaces only the `CANESIGHT-REPO-SYNC` description block. It never erases the original acceptance criteria, moves categories, removes unrelated labels, posts repetitive comments, or silently marks a task complete. It cannot observe unreported chat activity. Humans continue to add discussion outside the managed block.

## One-time credential setup by the PM

1. Obtain a Trello API key and a token from Trello's official developer flow, authorized for the account that can access this board. The installed ChatGPT connector's token is not available to GitHub Actions and must not be extracted.
2. In GitHub repository Settings → Secrets and variables → Actions, add encrypted repository Secrets **TRELLO_API_KEY** and **TRELLO_TOKEN**. Enter them directly there; never paste tokens into this chat, Git, a task, or PR.
3. Add repository variable **TRELLO_SYNC_ENABLED** = `true` after the Secrets are saved.
4. In Actions → Trello progress sync → Run workflow, run on `main`.
5. Verify one card shows its repo status/owner/task link and exactly one status label, while its priority label and original description remain. Verify the run reports 58 cards before declaring sync active.
6. If access, rate limits or credentials fail, the run fails visibly. Fix credentials/access and re-run; do not treat a skipped workflow as successful sync. Disable the variable to stop writes without deleting project history.

Use least-privilege credentials available for this board; ordinary Trello user tokens may grant broader account-level read/write than one board. Prefer a dedicated automation account restricted to this board where practical, short expiry, and revoke the token after the event. No new Trello account or paid subscription was created here.

The sync uses a serialized workflow, bounded retries for safe operations, exact card mappings and marker checks. Trello description updates have no compare-and-swap guarantee: avoid editing a managed block while a sync runs. After a human concurrently edits a card, reconcile if needed. Newly added status labels are created once; if a network failure makes a create ambiguous, inspect labels before retrying.

## Offline verification

```sh
python scripts/trello_sync.py --dry-run
python -m unittest discover -s tests -v
```

Offline dry run makes no writes and does not fetch PR state. It does not prove live auth or Trello connectivity.

References: [Trello REST cards](https://developer.atlassian.com/cloud/trello/rest/api-group-cards/) and [GitHub Actions encrypted secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions).
