# CS-040 — synthetic Pi speaker bench and combined test checkout

Owner: bondmila (AI-assisted), 2026-10-17.
Branch: task/CS-040-restricted-narration. Base b07e68ea6e08ba2bbf6bd261d22c8259bf3560cc.
Accepted main updated to 18884a5 (merge checkpoint 077522863094ba6df404a593192b82b498dfc237) before publishing.
PR #41 remains draft. Combine for testing with #58 head
4ac8c50ae2e0b6ec178ec64c3f90dc1480a60604, not an accepted-main integration.

Operator reports eSpeak/Bluetooth playback on the actual Pi as the intended
user. This is reported evidence only. Full phone/backend integration remains
unverified. Speaker identifiers and credentials are deliberately omitted.

Changed: backend/context/speaker_bench.py, backend/context/README.md,
tests/context/test_speaker_bench.py, own runtime task evidence/blocker, new
immutable fragment, this handoff and generated CHANGELOG.md. No protected changes.

Bench uses real EspeakSink/NarrationController but synthetic labels, readiness,
hazard/unavailable and capture age. Standard library only plus installed eSpeak.
No phone, camera, provider/API, network, GPIO, routing/volume changes or audio
recordings. Manual/hazard/unavailable interruption, independent expiry, stale
result suppression and non-replay are explicit cases. An independent 10ms timer
continues during human observation input. Human y/n/u observations are separate
from software checks; unknown cannot pass. Stop-call/timer timings are software
only, not physical speaker latency. Ctrl+C/EOF closes speech and records incomplete.
Reports include exact Git head, contain no device IDs and use new mode-0600 files
outside checkout under private parent. Physical acceptance stays false.

Tests actually run: all 67 context tests passed before main synchronization; the new seven-case suite covers scripted silent sink cases,
independent expiry, no/unknown answers, input interruption, explicit opt-in,
exclusive private reporting, and exact CLI through actual EspeakSink with a
silent disposable executable. No audio was played locally. Run the full context
suite and checked publisher shared checks before push. Combined checkout must
run its own context and edge tests before being advertised as prepared.

Test-only branch target: codex/cs-040-027-speaker-bench. It combines the updated
#41 with pinned #58 for Pi testing; not a PR/main merge or a completion claim.
A separate local worktree prevents changes to either task checkout. If the
combined generated changelog needs reconciliation, regenerate it with the
accepted renderer. Do not modify static task requirements or protected baseline.

Pi command (as normal audio user, with current Bluetooth output selected):

    bench_dir=$(mktemp -d "$HOME/canesight-speaker-bench.XXXXXX")
    python3 -m backend.context.speaker_bench --speak --repetitions 3 \
      --interrupt-after 1 --output "$bench_dir/results.json"

Keep #41 and #58 draft. Actual bench observations, audible buffered-tail behavior,
Bluetooth disconnect/reconnect, and full phone/backend integration remain open.
Independent PM review accepts evidence; software exit zero is not hardware proof.
