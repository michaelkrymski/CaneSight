# CS-016 ownership transfer to Michael

Status: Proposed. Chat authorization/request is not exact-head GitHub approval.

Task: CS-016. Proposed by michaelkrymski (AI-assisted).
Accepted base: dddbd4be0ba06a78a6f43b2806d2656d7b9abb03.

## Necessity and evidence

Michael explicitly said “I was transferred cs16, do it.” GitHub API confirms
bondmila authored the PR #64 handoff/reassignment request and stopped local
implementation work. The connected LiDAR phone and Xcode are on Michael's Mac.
Accepted main still assigns bondmila, so the occupied-task transfer must use the
existing PM/CR review process. The unclaimed-task PM exception cannot apply.
Existing implementation PR: https://github.com/michaelkrymski/CaneSight/pull/64
Existing tested source: 0433fc94af1a1e3edfe2d2bb28925cb3be6df1ee.

## Smallest proposed change

Change only CS-016 runtime owner to michaelkrymski, status to blocked, future
implementation branch to task/CS-016-michaelkrymski, and append transfer evidence/
blocker. Preserve acceptance, dependencies, allowed_paths and every static field.
Add this CR, a handoff/changelog fragment and generated log. No implementation,
shared protocol, master-plan or automation/governance change is included.
The ownership change itself is guarded under scripts/governance.py.

## Alternatives

- Keep Mila assigned and have Michael supply device evidence only: does not
  implement the requested ownership transfer and leaves integration responsibility
  split after Mila's explicit stop/handoff.
- Treat it as an unclaimed PM claim: invalid; main already has an owner.
- Bypass checks or overwrite ownership in an implementation PR: rejected.

## Impact and migration

After this transfer merges normally, create a PM-authored continuation branch
from the existing #64 source, integrate accepted main, preserve Mila's commits
and immutable records, and add only task-scoped integration/evidence changes.
The existing PR author cannot be changed: retaining bondmila's PR with Michael as
accepted owner would fail ordinary-author ownership enforcement. Link the new
PM-authored continuation before closing superseded #64; do not open competing
writable implementation sessions or force-push/rewrite shared source history.
No Pi/phone enrollment, credentials, capture-clock calibration, sensor readiness,
GPS contract or motor permission follows from reassignment. Existing technical
acceptance remains required. No full-task completion is asserted.

## Rollback and validation

Before merge, close this transfer proposal to retain accepted ownership. After
merge, reassignment back requires the same reviewed runtime/CR procedure; never
reset accepted records or erase Mila's work. Verify exact initial diff is runtime
assignment/evidence only plus these new records and rendered log. Run repository
checks and a non-mutating verification of existing CS-016 software. Guarded
ownership authorization must be recorded by Michael against the final PR head.
Independent review and normal branch checks remain required; no automatic merge.
