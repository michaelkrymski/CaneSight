# CS-027 uploader menu and one-shot request bridge

Owner: bondmila. Branch: task/CS-027-production-menu.
Base accepted main: d64dc5d0ca6cc8b4c5c16e12e48a1bc58de4ab66.

Scope: edge/context_runtime.py, uploader.py, context_report.py,
CONTEXT_BUTTON.md; tests/edge/test_menu_runtime.py and existing uploader harness
in test_context_runtime.py; own task runtime, new change fragment/rendered log.

The opt-in menu path uses the originating uploader’s frame/client/session/clock
and sole ContextNarration slot. Short release dispatches through the CS-040
completed-gesture API; long hold never requests. Menu speech/request speech have
bounded separate ownership over one sink, with no queue. Entry/cancel/source loss
preempt old requests and reject late results. Clock failure latches even if the
next read succeeds. Cleanup closes only owned audio/input resources. Report menu
state uses closed enums, with live observations explicitly false.

New flags require existing enrolled context input, explicit consent and primary
policy prerequisites plus --context-audio --context-menu
--context-menu-audio-confirmed. Confirmation is explicitly manual, not automatic
route monitoring. Missing dependency refuses startup. The audio_ready callback
must return promptly and strictly true; omission/error is unavailable. Terminal
audio-off latches loss until a new controller; recovery never replays.

All scenario capabilities remain empty. Unsupported confirmation announces
unavailable, cannot activate analysis, and cannot initiate a context request.
No scenario-specific provider job/correlation or new wire field is implemented.

Validation: 204 combined edge tests passed on macOS/Python 3.13 using an external
file-based overlay for the new CS-040 modules and edge/buttons.py, without copying
those files into this task branch. Generated frames/jobs and synthetic speech;
existing real local TLS/client regressions also run in the edge suite. New
virtual-time regressions cover release vs hold dispatch, cancellation/cooldown,
old replies after menu entry, expiry, consent, source/hazard/route changes,
clock reversal/single failure, held input and safe shutdown. Uploader harness
checks exact opt-in arguments/readiness/cleanup; argument validation occurs
before camera. Standalone dependency behavior is recorded below. Checked
publisher runs root tests, repo and generated log checks before push.

No real Gemini or device/network/audio acceptance is asserted. Requires the
separate CS-040 gesture-dispatch PR to be installed/merged for menu mode. Keep
this integration PR draft until that dependency is available and inspected.
Automatic route monitor, evaluated live adapters and real paired acceptance stay
open. No acceptance/baseline/contract changes and no motor GPIO.

Standalone accepted-main dependency run: 204 cases, 195 passed and nine explicitly
skipped for the unmerged CS-040 menu bridge dependency. No unsupported API
was copied into this branch. Combined source run: all 204 pass, no skips.
