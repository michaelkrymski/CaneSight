# CS-040 menu readiness follow-up — 2026-10-18

Base ef2e4314f284063e16c1b57eea82c3e6e583c275, task/CS-040-restricted-narration,
accepted owner bondmila, existing draft #41. During final inspection, identified
that a clock exception in update's internal tick latched failure but returned the
previously computed ready boolean. Change backend/context/menu_audio.py to return
false immediately in that case. Speech itself already checked the fault latch.

Tests/context/test_menu_audio.py adds the exact between-reads exception regression;
all 79 context tests pass. Own runtime/new immutable fragment/new handoff/log.
Shared publisher checks run before push. No new device/audio test. Existing draft,
physical evidence, production integration and trusted-route/adapter gates unchanged.
