# CS-040 narration clock follow-up — 2026-10-17

Owner: bondmila. Branch: task/CS-040-restricted-narration.
Review base: 070ed0321a0da0c45068cfe1b927930dad7e2ad8.
Integrated accepted main: bb00b82 (including CS-039 service; no conflicts).
PR: https://github.com/michaelkrymski/CaneSight/pull/41 — keep draft.

Changed: backend/context/narration.py, backend/context/README.md,
tests/context/test_narration.py, task runtime evidence/PR URL/blocker, this new
handoff, new changelog fragment and generated CHANGELOG.md. No protected changes.

The supplied clock previously allowed a request begun at 100 to speak at 90.
New tests first reproduced three failing reversal assertions and clock-failure
errors against the original code. A single guarded clock reader now retains the
high-water mark across operations and cancellation, stops audio, and invalidates
pending tickets on reversal, exceptions or invalid/nonfinite/overflowing values.
A new request requires a valid clock reading at least as high as the prior mark;
clock recovery never restores an old ticket. Equal readings remain valid.

Actually run before main integration: context discovery — all 20 narration tests
passed after the fix; git diff --check passed. Five new test methods cover
reversal at delivery, reversal after a later reading during speech, history
across begins/cancellation, exceptions in each clock-consuming operation and
invalid/nonfinite readings. After main integration the context root also includes
the accepted service tests; rerun it before publishing. The checked publisher
reruns root tests, repository validation, generated changelog consistency and
whitespace checks before pushing. No checks bypassed or weakened.

Limits: synthetic speech adapter only. Actual audio/button/provider integration
is unfinished, even though the isolated provider service is now accepted on main.
This timing fix supplies no device, electrical or physical audio acceptance.
Keep task blocked and PR draft pending integration and human review. No API key
or private scene was needed for this change.
