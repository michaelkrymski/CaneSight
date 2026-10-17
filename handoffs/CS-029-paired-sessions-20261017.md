# CS-029 — paired authenticated sessions

- Human: Adit / `aditsangani`.
- Base: `49a1332f5bbe35fb1ce709575318ae9a85894684`; branch `task/CS-029-paired-sessions`.
- Ownership accepted via PR #10; prerequisite CS-028 implementation accepted via PR #9.
- Acceptance addressed: distinct phone/Pi roles, session-isolated subscriptions, HTTPS/WSS route enforcement and scoped short-lived credentials. New endpoint/control details are documented in `backend/SESSIONS.md`; existing shared v1 message schemas remain unchanged.
- Changed: `backend/sessions.py`, `backend/server.py`, `backend/app.py` integration seam, runtime/test requirements, backend README and session guide; `tests/backend/test_sessions.py` and `test_sessions_tls.py`; own task runtime fields; new changelog fragment and generated log.

## Tests actually run

- `.venv/Scripts/python.exe -m unittest discover -s tests/backend -v`: **35 passed** (19 accepted CS-028 cases, 15 session cases, 1 real TLS integration case), Windows Python 3.14.3. Fixed a cancellation-cleanup issue found by the first run and a test ordering race before the final passing run. No failed result is presented as passing.
- Real HTTPS/WSS test starts a loopback Uvicorn server with a temporary generated CA/server certificate outside Git, requires certificate/hostname verification, creates two replay pairs, rejects missing/invalid WS tokens, relays a synthetic depth packet only to its paired Pi, uploads a generated JPEG, and closes both endpoints on operator revocation. A client without the temporary CA rejects the certificate. Server and temporary keys are cleaned up.
- Unit cases cover transport scheme/forwarded-header rejection, operator authorization, session shape and bounds, scoped roles and identities, live/replay separation, duplicate sockets, preserved sequence marks on reconnect, expiry of idle sockets, explicit revocation, in-flight frame rejection after revoke, peer disconnect invalidation, bounded queues, strict/oversize JSON and clock nonce/rate/deadline correlation.
- `.venv/Scripts/python.exe -m backend.demo_replay`: accepted legacy replay behavior passed: liveness 200, readiness 503, upload 202, duplicate 409; local server stopped.
- Shared repository tests, structure, rendered changelog, scope and whitespace checks are run by checked publishing; exact published-head CI outcome is recorded in the PR. Accepted CI already installs backend test requirements and explicitly discovers the component suite, so this PR needs no protected CI edit.

## Integration and limitations

Start the new factory `backend.server:create_session_app`, with private `CANESIGHT_OPERATOR_TOKEN` configuration, one worker and either direct TLS or a private upstream behind an exactly trusted TLS proxy. Keep certificate verification enabled. Do not use wildcard proxy trust or expose the unencrypted upstream. See `backend/SESSIONS.md` for API, paths, role headers, boot bindings, shutdown and logging instructions. The default CS-028 app/replay factories keep their existing behavior and do not silently turn on session issuance.

Session POST is operator-only. Device tokens last at most 600 seconds. One socket per role, eight sessions, eight queued messages per consumer. Revocation/expiry clears buffers, frame ledger, sequence/control state and credentials. Reconnect with the same authorized boot keeps sequence marks and replays no buffered data. On source reboot, revoke the old pair and create a new session with a new boot binding; no packet can reenroll itself. Process restart invalidates all sessions.

No replay/live conversion, capture retiming, movement permission or model readiness is added. Relayed messages are shape/role/identity/ordering checked **observations**, not freshness-eligible motor input. CS-030 must wire clock bounds, source health and independent capture expiry into consumers; keep remote haptics unavailable until that integration is verified. CS-032 owns broader quotas and CS-035 backend-generated vision relay/lineage. Dashboard browser auth remains CS-041 work; this native-header path intentionally denies Origin-bearing browsers and all WS URL parameters.

Single-process in-memory demo only: do not deploy multiple workers without shared session/sequence/queue state. No actual phone/Pi, hardware/electrical, real drift/latency, trained inference, public certificate/domain, reverse-proxy or Vultr verification is claimed. Local TLS tests prove the implemented encrypted transport under test, not CS-033 live deployment. Starlette's non-failing httpx TestClient deprecation warning remains.

Next: Michael reviews the session API/lifecycle and TLS integration evidence; Gavin can align his CS-033 factory/proxy/header configuration using the guide. Proposed task status: Review, not Done. No self-merge.
