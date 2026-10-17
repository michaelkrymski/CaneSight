# CS-001: checked task publishing and portable changelog

Requested by Michael: communicate Gavin's review and make future routine pushing automatic in the teammate's own instance. Gavin's Windows-generated changelog also exposed platform-dependent Path sorting in Linux CI.

Scope: AGENTS.md publishing instructions, new publishing/feedback scripts, a portable string sort in the existing renderer, protected regression tests, operations guidance, and new append-only records. The master plan, protocol, ownership rules, required checks and branch protection are unchanged.

Necessity: active teammates should finish routine checks/commit/push without delegating Git typing back to a human; explicit-file staging and existing scope/claim enforcement keep the result reviewable. Stable case-folded string sorting reproduces the original Windows ordering across platforms without editing historical fragments.

Alternatives: prose-only manual Git (no consistent guard), a background daemon/webhook controlling teammates' agents (new authentication and lifecycle complexity), or automatic merges (unrequested and conflicts with review governance). Choose an active-session helper with no new service or secrets. Git auth still uses each teammate's local authorization.

Migration: merge only after Michael authorizes the current head and a collaborator supplies required review; teammates fetch accepted main, reconcile task branches and read updated AGENTS.md in their own active instance. Nothing remotely installs or wakes an agent. Gavin can fix his currently unmerged fragment with the posted lowercase rename independently.

Validation: shared validation/unit tests, deterministic mixed-case fragment ordering, latest CI reruns, branch/remote/path rejection, and isolated local Git publish tests; record actual final results in the handoff. Hardware and app deployment are outside scope.

Rollback: revert helper/instruction changes through a reviewed PR; ordinary task-branch publishing remains available. Preserve append-only records. No credential/config migration is needed.

Authorization: pending exact-current-head PM authorization required by AGENTS.md and governance.json. This proposal is not approval or a merge instruction.
