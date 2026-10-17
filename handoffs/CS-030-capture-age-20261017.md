# CS-030 — capture age and replay rejection

- Human: Adit / `aditsangani`.
- Initial base: `b3bb016b9ce97f197ad643a5cbe1bdb83d151377`; branch `task/CS-030-capture-age`.
- Claim accepted via PR #17, prerequisite sessions accepted via PR #14.
- Scope: `backend/freshness.py`, `backend/events_client.py`, `backend/FRESHNESS.md`, backend README/session-guide links; `tests/backend/test_freshness.py`, existing TLS test extension; own task runtime fields; new change fragment and generated log.

## Acceptance addressed

The final consumer owns monotonic age decisions. Backend relay receipt is never substituted for the originating Pi clock. The new gate completes its own bounded, nonce-correlated source clock probes, uses only explicitly configured justified drift, rechecks 500/1500/2500 ms capture-age bounds and uncertainty, and maintains fixed per-observation deadlines. A newly synchronized clock or heartbeat does not extend an old deadline. Missing/unknown timing remains unavailable.

Original Pi capture metadata is stored before upload in a two-entry trusted ledger. Vision must match original source/boot/session/mode/frame/sequence/capture times/dimensions and consume its request once, counting upload through inference/return delay. The result cannot reconstruct a missing ledger entry or become fresh by being received now. Capture-ID history is bounded to 4096 per epoch.

Stateful sequence gates reject replay/reorder/wrong session/source/boot/mode. Trusted source epoch changes retire old boot IDs and clear evidence/maps; ordinary messages cannot reenroll. Interruptions clear pending evidence and probes while retaining replay high-water marks. Receiver clock reversal is sticky unavailable and requires a new consumer/session epoch. Health, unknown depth and recovery have separate semantics; no movement or crossing permission is introduced.

## Actual validation

- `.venv/Scripts/python.exe -m unittest discover -s tests/backend -v`: **57 passed** on Windows Python 3.14.3 (36 accepted backend tests plus 21 freshness cases). Coverage includes missing drift, asymmetric offsets, uncertainty, late/replayed/mismatched nonce, expired/drifting maps, stale/future/precalibration capture, health loss/recovery, heartbeat/resync nonrenewal, replay/reorder/wrong identities, receiver clock resets, retired boots, provenance tampering, superseded/consumed frames, exact expiry boundaries, huge integer clocks and TLS-client validation.
- Existing real certificate-verified HTTPS/WSS test now also uses `PairedEventsClient`: local Pi probe through server to synthetic phone (+200 ms clock offset), correlated reply, bounded ready heartbeat, fresh depth accepted and later old depth rejected. This uses an explicit synthetic zero-drift assumption, not actual device oscillator evidence. The existing authorization/isolation/upload/revocation checks remain.
- `.venv/Scripts/python.exe -m backend.demo_replay`: liveness 200, readiness 503, generated JPEG upload 202, duplicate 409, temporary server stopped.
- Shared repository/contract tests, structural validation, scope/ownership, generated changelog and whitespace checks run through checked publishing. Current-head CI results are reported in the PR; no prefilled acceptance is claimed.

## Integration and limits

Read `backend/FRESHNESS.md`. Consumer defaults to unknown joint drift and local-camera readiness False. Actual Pi/phone drift needs evidence before remote depth is eligible. Run receiving and independent policy ticks concurrently: `gate.current()`/`expire()` must be called even if network/model work stalls. Returned snapshots are copied and must not be cached past those checks. Gate location in backend/ is a repository component boundary, not permission to use a server clock for a Pi consumer.

The session relay intentionally keeps original wire observations unchanged. The verified native WSS client integrates this consumer at the receiving process. CS-024 still integrates the final edge policy/motor behavior; no edge/ edits or hardware verification were authorized/claimed in this backend task. CS-031/035 provide actual model results; no synthetic result is presented as live inference. Shared protocol, governance, protected workflows and master plan remain unchanged.

Also reviewed issue #20 during this session: paired enrollment is available in accepted CS-029, with operator steps in backend/SESSIONS.md. The issue still needs Gavin's verified deployed HTTPS origin/factory/version before a real Pi upload; no live URL or credential was invented or published. This task does not claim real-device upload acceptance.

Status: Review, not Done. Next: Michael reviews policy/clock/lineage evidence and merges through normal checks; final device drift and edge integration remain separate acceptance work. No self-merge.

## Accepted worker integration before publication

Integrated accepted main `dd7c46830d869b24b0d76f490cd086c9ec5b118f` (CS-031 worker PR #19) without history rewriting or dropping accepted records. Ran the combined backend suite again: **72 tests passed**, including all worker/session-lifecycle cases, the 21 freshness cases and real TLS consumer integration. Legacy replay and rendered-log/whitespace checks passed again. The earlier 57-case result records the pre-worker checkpoint; the final combined result is 72. Worker files and accepted shared contracts are unchanged relative to current main.
