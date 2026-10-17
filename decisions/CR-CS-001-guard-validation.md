# CR-CS-001-guard-validation: verify the protection blocks unapproved plan edits

Status: Test proposal; DO NOT MERGE.

This draft PR intentionally adds a harmless marker to the master plan to test server-side governance. It must fail without Michael's exact-head approval. The accepted plan is unchanged on main. Close this PR after recording the expected result; it does not implement CS-001.

Necessity: prove the protection is operational, rather than merely document it.
Alternative: unit tests only; insufficient to prove GitHub workflow/permission wiring.
Impact: no runtime code or wiring changes. Rollback: close unmerged draft PR.
Validation: repository checks should pass; governance should fail for missing exact-head PM authorization. No approval is requested.
