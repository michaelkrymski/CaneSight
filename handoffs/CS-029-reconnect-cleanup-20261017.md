# CS-029 — reconnect cleanup review fix

- Human: Adit / `aditsangani`; branch `task/CS-029-paired-sessions`.
- Reviewed base/head: `596de25589d56912193508dfffef15cae4bf96c7`.
- PR: https://github.com/michaelkrymski/CaneSight/pull/14 .
- Feedback verified as Michael (`michaelkrymski`): https://github.com/michaelkrymski/CaneSight/pull/14#issuecomment-6231378346 .

Michael reproduced old phone detach -> old Pi invalidated -> replacement phone attach -> old Pi late detach incorrectly closes replacement phone. Added this exact ordering to `tests/backend/test_sessions.py`. It failed with `1012 is not None` against the reviewed implementation, then passed after correction.

`backend/sessions.py`: detach always drains/removes its own registered connection, but propagates invalidation only for a connection that has not already been invalidated. Late cleanup does not clear replacement control state. Relay also requires the current registered connection object, so an old detached handler cannot publish through a replacement role. The overload path clears both marked connections' buffers and pending clock state immediately, rather than relying on repeated detach propagation.

Regression checks verify old buffers/control state clear, sequence high-water marks survive, duplicates stay rejected, fresh sequence 105 relays to the replacement Pi, stale objects cannot relay or disturb new registrations/probes, and a genuine replacement-phone disconnect still closes its peer. Existing queue-overload coverage now also checks immediate buffer/control invalidation.

Validation: targeted reconnect regression failed before correction, then passed. Full backend suite: **36 tests passed**, including real certificate-verified HTTPS/WSS. Legacy `backend.demo_replay` passed (200 liveness, 503 readiness, 202 upload, duplicate 409). Shared checks/structural/generated-log/whitespace and ownership/scope validation run through checked publishing; published-head CI is recorded on the PR. Local Windows Python 3.14.3; no phone/Pi, electrical/hardware or live deployment verification claimed.

Other changed files: own task runtime evidence/PR URL, new `changes/20261017-cs-029-reconnect-cleanup.json` and rendered changelog. Existing handoffs/fragments and protected files remain untouched. Task stays Review. Next: Michael re-reviews the new head after CI; no self-merge.
