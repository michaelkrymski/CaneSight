# CS-001: user-selected crossing observation workflow

Status: Proposed. Michael accepted the interaction design in chat and requested
the plan/task update; this file is not exact-head GitHub authorization.

## Reason and smallest change

The prior button requests one object description. Michael requested a 3-second
entry hold and three manually chosen scenarios: pedestrian walk/hand signal,
pedestrian-activated flashing yellow beacon, and unsignalized residential street.
He accepted short-press cycling, a new 1-second hold to confirm, immediate active
cancel, 15-second menu inactivity, and no silent activation without audio.
The accepted master plan and task acceptance do not yet specify this workflow.

Add only master-plan subsection 6.8 and an operations implementation brief.
Append acceptance requirements to CS-027, CS-036, CS-037, CS-038, CS-039,
CS-040 and CS-044; preserve their existing acceptance clauses, owners, statuses,
dependencies, scope, card links and historical evidence. Protected changes are
`docs/master/MASTER_PLAN.md` and those task static acceptance fields. No shared
schema, automation, governance or production module changes are included.

## Alternatives

- Keep one-shot context only: preserves simplicity but does not meet the agreed
  scenario-selection request. Retain it for idle short-release compatibility.
- Infer scenario automatically: adds scene/applicability uncertainty; rejected
  for this first implementation.
- Use double/triple clicks or multiple buttons: harder timing/counting and
  additional hardware; the spoken single-button menu was chosen.
- Ask the current Gemini object-list service whether cars stopped: unsupported;
  do not expand output permissions or make blanket stopped/yielding assurances.

## Impact, migration and rollback

Existing owners coordinate follow-up implementation after this amendment merges.
The operations brief specifies release barriers, fixed prompts, consent, no
automatic restart, audio/source failure and per-scenario capability gates.
Real YOLO signal recognition and beacon/vehicle temporal analysis require new
evaluated artifacts; current schematic fixtures and synthetic tests remain
limited to replay. No new wire fields or deployment is authorized by this CR.
Any interprocess scenario/track schema needs its own reviewed shared-contract CR.

Preserve P0 local depth/haptics and all original-age budgets. This workflow is
observations only, not road-use guidance or permission to cross. A yellow beacon
does not establish that cars yielded, and undetected traffic remains unknown.
Roll out synthetic menu/adapters before evaluated real observations. Rollback
selects the earlier app/feature configuration and clears all mode/job/audio state.
No old selection, armed state or queued observation resumes after rollback/reboot.

## Validation and approval

Required implementation tests and controlled bench gates are listed in
`docs/operations/CROSSING_ASSISTANCE.md`. This PR verifies document/task structure,
unchanged runtime fields, preserved original master text, generated log and
shared tests only. It contains no completed implementation or physical claim.

Michael must approve the final PR head through the existing GitHub review or
`PM-APPROVE-PLAN <full-current-head-sha>` mechanism. Reapproval is needed after
any further commit. The existing governance check must pass before merge.
