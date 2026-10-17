# CS-040 restricted narration checkpoint — 2026-10-17

Owner: bondmila. Base: 8394b17f9f6443f2ff7d3b57b3d8587c3570ed45.
Branch: task/CS-040-restricted-narration. Assignment accepted through PR #39.

Changed: backend/context/{__init__.py,narration.py,README.md},
tests/context/{__init__.py,test_narration.py}, task runtime fields, new fragment,
this handoff and generated changelog. No protected baseline edits.

Actually run: python3 -m unittest discover -s tests/context -v — 15 passed;
git diff --check — passed. Publisher also runs shared tests, repository structure
and changelog consistency before committing. Speech sink is synthetic. No real
Gemini key/model call, device speech, electrical or hardware verification.

Provider prose is never spoken. Strict object labels feed <=20-word uncertain AI
phrasing. Single-use correlation, capture-derived deadline, independent expiry
hook, manual cancellation and hazard/unavailable preemption fail closed. A
consumer must drive policy/tick on its own local loop, and implement immediate
speech stop. Model accuracy is not established by language restrictions.

Remaining: CS-039 provider and CS-018/027 phone/button integrations. Task is
blocked rather than Done; PR is a reviewable component checkpoint. CS-039 claim
PR #38 was still open at inspection; no CS-039 implementation was undertaken.
No credentials, private images or GPS were saved. Next: review this component,
merge the provider assignment, wire the adapters, test real device preemption.
