# CR-CS-035-native-result-integration-scope: permit bounded native result integration

Status: Proposed; exact-head PM GitHub authorization required before merge.

- Task and author: CS-035; Michael Krymski (PM, AI-assisted). Gavin (`gmarcialcalleja`) remains the implementation owner.
- Base: `0758598b8befed1e338536166c1e40d8c03e23ed`.

## Evidence and necessity

Draft PR #28 at `902d8f4f490a3c261d29aeedac5cfc3bd68d0522` implements the pinned-model observation adapter and internal bounded-worker results. Its `backend/vision/INTEGRATION.md` records the missing service configuration, native Pi result delivery and deployment boundary. The accepted service factory configures no model; the native event socket does not retrieve worker results. The current CS-035 allowed paths contain only `backend/vision/`, `tests/vision/` and `qa/vision/`. Ordinary in-scope implementation cannot complete authenticated result delivery without editing the existing service boundary.

## Smallest proposed amendment

Append exactly four entries to `tasks/CS-035.json` → `allowed_paths`:

| Added path | Authorized purpose |
|---|---|
| `backend/server.py` | Explicit opt-in configuration of the existing bounded worker and pinned, verified model; preserve the no-model default. |
| `backend/sessions.py` | Server-generated observation delivery on the existing authenticated native Pi event socket, bound to the current grant and connection. |
| `tests/backend/` | Focused service/session/HTTPS/WSS lifecycle and result-delivery regression coverage. |
| `backend/deploy/` | Package and configure the reviewed CPU runtime and verified operator-controlled weights, with deployment validation and rollback instructions. |

These paths are for CS-035 integration only, not unrelated backend refactoring. Do not add a blanket `backend/` scope. Acceptance, dependencies, owner, status and all other task fields remain unchanged. The master plan, shared contracts, governance and protected workflows are not edited. Changing `allowed_paths` is a protected static-field amendment under the existing governance policy; that policy remains intact.

## Required behavior and validation for implementation

- Deliver only server-generated schema-valid observations to the current authenticated Pi role. Preserve original session/source/boot/frame/mode/sequence, image and capture lineage; no retiming at inference or receipt.
- Revalidate grant lifetime and connection identity before delivery. Test expiry/revocation, cross-session and phone-role isolation, disconnect/reconnect, late cleanup, superseded frames, bounded queues/slow consumers and shutdown. Clients still cannot publish vision or enroll from observations.
- Keep header authentication, verified TLS, native browser-Origin/query rejection, quotas and existing worker/process bounds. Never expose device/operator credentials in a dashboard.
- Model selection is explicit and operator-controlled. No implicit downloads, synthetic readiness or fallback to an unverified checkpoint. Bad/missing weights or runtime/worker failures keep model readiness unavailable.
- Test an actual configured worker through authenticated result transport; separately validate target-host CPU/memory/deadlines, image/runtime provenance and rollback before claiming deployed inference. Do not claim device freshness or end-to-end acceptance from local worker timing or HTTP 202 alone.
- Pedestrian signal stays unknown and countdown null without a separately validated recognizer. Empty detections do not establish clear space. No motor commands, crossing permission, browser-dashboard authorization or Pi client implementation is added by this scope approval.

## Alternatives and impact

An alternative is to accept the adapter checkpoint and assign transport/deployment to another task. Keeping the existing CS-035 owner and allowing these four boundaries avoids a needless handoff while retaining separate review of implementation. Broad backend scope, new unauthenticated result endpoints, changes to governance, and bypassing native Origin checks are unnecessary and rejected. Coordinate with other backend work before touching the listed paths; teammate task ownership is unchanged.

## Migration and rollback

Merge this scope-only amendment first. Then update PR #28 from accepted main, preserving the expanded path list and Gavin's runtime progress. Governance reads allowed paths from the base branch, so editing them only within PR #28 would not authorize extra implementation files in that PR. Resolve any generated changelog conflict by rerendering; preserve append-only fragments. This amendment changes no running service. Reverting it removes future edit scope; deployed code/runtime rollback remains separately reviewed implementation work.

## Validation and approval

For this metadata amendment, run repository structure, shared/governance tests, generated changelog and whitespace checks, and confirm that `allowed_paths` is the only changed task field. A trusted-base governance inspection should have no structural/scope errors and should require exact-head PM authorization. Future implementation must meet the validation above.

Approval: pending Michael's exact-head approving GitHub review or `PM-APPROVE-PLAN <full-current-head-sha>` comment, followed by green checks and normal PR review/merge. This document does not itself grant approval or mark CS-035 complete.
