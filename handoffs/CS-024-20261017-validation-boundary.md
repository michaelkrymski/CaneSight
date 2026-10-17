# CS-024 validation boundary

Base: 6a386675d24e88082fce9f3e063f101098c1e7bd.
Branch: task/CS-024-pi-receiver-expiry; draft PR #32.
Implementation checkpoint: deca0e47fe5647d2d2d0a67b787fa57875bc7679.
Runtime PR linkage: f0b0ce43234a56d17fc03092a8d5bfeb6758efc5.

The receiver checkpoint and its runbook are published. All 26 edge tests passed
on Windows and Linux Python 3.12, including real local certificate-verified
HTTPS/WSS with explicitly synthetic observations, expiry with blocked receive,
and invalidation of fresh evidence on revocation. Windows backend regression
discovered 128 tests: 121 passed, seven environment/opt-in skips. All 39 shared
tests and repository/changelog/whitespace checks passed before publishing.

The next proposed validation was an isolated clone/venv on Michael's Pi, leaving
his existing CS-022 checkout untouched, with private SSH password entry and
automatic Pi-only credential transfer. Automatic approval review rejected the
command that would prepare and launch that runner, giving only 'blocked by policy'.
That command did not execute. No alternative route or approval bypass was used.
No receiver run on the actual Pi is claimed.

Task status is blocked at this validation/integration boundary. Real Pi receiver
execution remains pending; the full local hazard/motor policy still depends on
outstanding CS-023. Michael may review the software checkpoint in draft PR #32.
No phone connectivity, electrical or motor acceptance is established.
This handoff adds evidence only; it changes no runtime implementation or scope.
