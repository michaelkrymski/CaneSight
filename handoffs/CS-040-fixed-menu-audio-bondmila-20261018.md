# CS-040 fixed menu speech — 2026-10-18

Branch task/CS-040-restricted-narration; base 32d7b122fff04dd1311cb8c85bafbff02436ecd3
includes accepted main 5dbb6ad and merged PR #71. Accepted owner bondmila.
Read merged master/brief/task; unchanged baseline and requirements thereafter.

New backend/context/menu_audio.py: closed fixed entry/three labels/confirmation/
cancel/unavailable phrases. Explicit trusted audio/priority/epoch gate, monotonic
generation fence, no replay after output/epoch loss, clock/engine fault latch,
one sink/no queue and independent 15s optional-speech expiry. Existing object
narration remains separate. pi_speech.py permits only these exact extra fixed
phrases; no free-form provider text. README and own runtime/fragment/handoff/log.

Tests/context/test_menu_audio.py: five new silent tests for vocabulary, no silent
confirmation, lost/recovered audio and old event rejection, priority/epoch,
expiry/clock/engine faults and preemptive fixed cancellation. All 78 context tests
pass. No actual speaker or hardware used locally. Publisher reruns shared checks.

CS-027 synthetic menu bench consumes these APIs; it requires explicit simulation
or confirmed real speech and consent. Synthetic supported capabilities emit no
traffic observations/model jobs; live/default capabilities remain unavailable.
Engine process health is not an OS route monitor. Production menu/request bridge
and CS-018 trusted route readiness are pending. New Pi menu speech/gesture, clarity,
preemption/buffering observations are still needed; earlier reports apply to old
builds. No crossing advice, new wire fields, live model accuracy or road testing.
Keep #41/58 draft and preserve other task owners. No task Done/physical acceptance.
