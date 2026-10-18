# CS-027 merged-plan menu checkpoint — 2026-10-18

Branch task/CS-027-context-button; base 8078be162357c0970c12f37cc9fb230cdde69bb1
includes accepted main 5dbb6ad and PR #71 amendment. Accepted owner bondmila.
Read the merged master/brief and updated task acceptance; no baseline edits.

Changed edge/context_menu.py: deterministic, no callbacks/queues/jobs/outputs.
Exact hold/debounce thresholds, release-only context gesture, no default, label
cycle/wrap, confirmation barrier, active down-edge cancel, timeout/stuck guard,
source/consent/audio/epoch invalidation and clock-fault latch. Local generations
bind events; zero supported capabilities by default. Unsupported is unavailable.

Changed edge/menu_bench.py: explicit synthetic interaction-only terminal/GPIO21
bench with CS-040 FixedMenuAudio; no requests/observations/camera/network/phone or
motor outputs. Simulated capability flags are explicit; source/audio/hazard state
is injected, not inferred. One worker and optional GPIO reader, latest state,
bounded counters; no event/log FIFO or analysis jobs. Private report/cleanup,
initial physical level before timers, 100ms input-age gating. Normal stdout/input
blocking cannot retain optional audio eligibility. Synthetic state never becomes
live traffic evidence. Audio-confirmed flag is operator assertion; no automatic
OS route monitor. Missing draft audio dependency fails without fallback.

Tests: tests/edge/test_context_menu.py and test_menu_bench.py. Exact virtual
2999/3000 and 999/1000 thresholds, startup held, bounce, barriers, wrap, inactivity/
absolute cap, unsupported/no-audio, source/epoch/consent/clock faults, immediate
cancel, synthetic composition, exact silent CLI and quit-without-entry. All 182 combined edge tests pass, including the final quit regression. Separate edge
root is not run by existing CI; draft #41 modules provided through external
file-based overlay, without copying code into this task branch. No hardware test.

Documentation in edge/CONTEXT_BUTTON.md, own runtime fields/new fragment/handoff
and generated log. The existing uploader one-shot path is unchanged. This is the
first rollout stage required by the plan, not completed task acceptance. Production
menu-to-existing-request bridge and trusted CS-018 route/source readiness remain
integration work. Other owners retain real vision/temporal models and fault
campaigns. No interprocess schema or protected baseline change. Keep #41/58 draft;
next run controlled synthetic GPIO21/audio menu bench, then integrate reviewed
production adapters. Never represent canned observations as live traffic.
