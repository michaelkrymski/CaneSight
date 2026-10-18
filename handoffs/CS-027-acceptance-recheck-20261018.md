# CS-027 acceptance recheck — 18 October 2026

Owner: bondmila. Branch: task/CS-027-production-menu.
Starting head: 150ecf10d18c296e30eb7db1020afa914c7489da.
Accepted base/tested implementation: dddbd4be0ba06a78a6f43b2806d2656d7b9abb03.
Fast-forwarded the clean task worktree to accepted main; no conflicts.
GitHub API verified PR #78 merged, with Michael approving its exact 150ecf1 head.
No implementation, protected baseline, contract or other task changed.
Only own runtime evidence/blocker, this handoff, new fragment and generated log.

## Actual verification

Initial system-Python runs failed: missing trustme and mismatched multipart
runtime dependencies caused import errors/422 responses. These failures are not
counted as passes and required no implementation edits. Created isolated
/tmp/canesight-cs027-acceptance-venv and installed backend/requirements-test.txt.
With that Python 3.13 interpreter:

- python -m unittest discover -s tests/edge -q: 205 passed, no skips.
- python -m unittest discover -s tests/context -q: 83 passed, no skips.
- python -m unittest discover -s tests -q: 195 passed.
- python scripts/validate_repo.py: valid.
- python scripts/render_changelog.py --check: passed before this new record;
  publisher regenerates and checks it again.

Fixture suites include simulated speech/input and real local TLS/process tests;
they do not establish physical button, audio buffering or paired-phone acceptance.
Dependency deprecation warnings were emitted; pinned versions were retained.

## Remaining acceptance

User explicitly selected running Pi checks personally. Supplied a separate
current-main clone and existing edge.menu_bench command with --speak,
--audio-confirmed, --consent, --synthetic-adapters and --gpio21, writing its private
report outside the checkout. Requested release/3s entry, all labels and wrap,
new 1s confirmation, next-press cancel and 15s inactivity, plus human clarity and
audible-tail observations. No report or new physical pass has been received.
The bench does not use camera/phone/backend/Gemini or motor GPIO and enables only
synthetic interaction capabilities. Its audio confirmation is manual.

CS-040 PR #80 implements automatic Bluetooth monitoring separately; API inspection
found it open and ready, not merged or approved. Do not copy its source, claim its
physical validation or mark its dependency accepted. Scenario detector/evaluation
adapters belong to CS-037/038; do not implement or enable them in this task.
The full task remains blocked. Record actual operator payload/provenance before
review, retain failures and unknowns, and let Michael accept physical evidence.
Never mark Done simply because PR #78 merged or software suites pass.

Publish this evidence checkpoint through scripts/publish_task.py, create a draft
follow-up PR, and inspect exact-head CI. No merge or ownership reassignment.
