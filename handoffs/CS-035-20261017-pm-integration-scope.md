# CS-035 PM scope amendment — 2026-10-17

Author: Michael Krymski (AI-assisted). Implementation owner remains Gavin (`gmarcialcalleja`).
Branch: `task/CS-035-integration-scope`.
Base: `0758598b8befed1e338536166c1e40d8c03e23ed`.

## Change

Only CS-035's allowed_paths is amended: append backend/server.py, backend/sessions.py, tests/backend/ and backend/deploy/. New change request records purpose, bounded native Pi delivery, authentication/lifecycle/freshness/readiness conditions, target-host deployment tests and rollback. Add one immutable changelog fragment and regenerate CHANGELOG.md. No application code, master plan, shared protocol, governance, ownership, task status or acceptance changes.

## Validation

Repository validation passed; all 39 shared/governance tests passed. Generated changelog and whitespace checks passed. A UTF-8-aware JSON comparison confirmed that allowed_paths is the only changed task field and the exact four paths are appended. Trusted-base staged-diff governance inspection found no structural/scope errors and correctly required exact-head PM authorization. No deployment or new device tests apply to this metadata-only amendment.

## Integration

This is a scope-only PR, separate from Gavin's draft #28. Merge after exact-head PM authorization and required checks. Gavin then updates #28 from main, retaining the expanded allowed_paths together with his runtime progress; rerender any changelog conflict. His implementation remains separately reviewed and tested. Neither this PR nor its merge marks CS-035 Done, deploys a model, grants dashboard access or proves Pi result receipt.
