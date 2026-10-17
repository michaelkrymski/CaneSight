# CS-001 publishing retry fix

PR: https://github.com/michaelkrymski/CaneSight/pull/4

Continues the checked-publishing amendment. Michael requested that fixable issues be corrected and remaining approval steps explained. Existing CR-CS-001-checked-publishing.md covers these protected helper/test changes. Exact-head authorization remains pending until the final updated commit is reviewed.

The review identified that failed checks leave generated CHANGELOG.md staged; the next identical command wrongly rejected that file as unrelated. The guard now permits only this generated file in addition to explicitly selected filenames. It is regenerated before scope validation and commit; unrelated files are still rejected.

The isolated integration regression first failed on the original helper, then passed after the fix while leaving files staged between attempts. It also verifies rejection/preservation of unrelated staged and untracked work, and confirms that only the task branch changes in a temporary local remote. All 21 tests, structural validation, rendered changelog check and whitespace check pass. No hardware or deployment acceptance is claimed.

Accepted main was integrated without rewriting branch history; CHANGELOG.md is regenerated from all immutable fragments, preserving the accepted CS-033 claim. Prior handoffs/fragments/master plan remain unchanged. The original handoff's validation describes its earlier checkpoint; this handoff records the correction.

Next: verify current-head CI; Michael posts exact-head PM authorization and a teammate submits an approving review. Merge only after all existing protection requirements pass. Teammates then pull accepted main and use the operations guide in their active sessions.
