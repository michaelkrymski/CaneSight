# CS-013 clock harness publication refresh

Owner Michael; claim/CS-013-michaelkrymski; PR #97. Local clock prep commit 601bd58
passed 250 shared tests but its push was rejected as non-fast-forward: a concurrent
PM refresh moved the same remote branch to92da714. Read/fetched and preserved both
histories with a normal merge; no source conflict, reset or force push. Backend
bond/deployment changes are accepted main integration, not new work here.

Add explicit CANESIGHT_OPERATOR_LOCK_TEST=1 runner opt-in to the assisted UI test
so normal full suites do not wait for a human. Actual lock result predates only
this selection guard; original source hash retained. Existing test body and host
lifecycle recorder unchanged. Compile/selection verification separate from actual
three passed physical UI cases. Original append-only prep fragment unchanged.
Fresh checked publication must inspect current PR head/CI before actual pair run.
