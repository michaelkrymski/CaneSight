# CS-040 — reported Pi speaker bench results

Owner: bondmila (AI-assisted). Date: 2026-10-17.
Branch: task/CS-040-restricted-narration.
Base: f162c34126db756fa23a692b4849e49345a35427.
Tested combined checkout: 9607f76c9fb6f250c133848d611eae56910c4be1.
PR #41 stays draft; #58 remains dependent/draft. No merge requested/performed.

The human operator pasted two JSON files from the Pi. Preserve both in
`tests/context/evidence/CS-040-pi-speaker-operator-report-20261017.json`:

- First attempt: incomplete, generic bench-unavailable error, cause unrecorded.
  This attempt is not passing evidence and is not diagnosed retrospectively.
- Subsequent run: complete, three rounds of manual cancellation, synthetic
  hazard, synthetic unavailable, capture expiry and late-result suppression.
  All 15 software checks and all 15 operator observations are true; no timer
  fault. Bluetooth speaker/eSpeak playback had previously been operator reported.

Software stop-call duration across nine stop cases: 3.547..3.878 ms. Timer expiry
overshoot: 2.647, 9.499 and 4.728 ms. Neither measures audible speaker latency or
Bluetooth buffering. No numeric audible-tail measurement was supplied. The
agent's SSH attempt was denied; the agent did not observe the device/audio.

Input priority and capture remain synthetic; phone/backend/Gemini/GPIO false.
Physical acceptance and Bluetooth disconnect/reconnect verification remain false
as reported. The completed bench supports those specific reported cancellation,
priority/expiry observations, not full integration or general device acceptance.

Changed files: new evidence JSON, own task runtime evidence/blocker, new immutable
change fragment, this handoff and generated CHANGELOG.md. No implementation,
protected baseline, old fragment or task requirement edits. JSON structure was
parsed; verified 15 unique repetition/case pairs and three instances of every
expected case, with all software/operator fields true. Shared repository/root,
generated log/governance/whitespace checks are rerun by checked publisher.

Remaining: Michael reviews this operator-reported evidence; Bluetooth speaker
physical disconnect/reconnect and stale-buffer/no-replay observations remain
unverified. Full live phone/backend integration and CS-018 accessible controls
remain open. Keep PRs draft and task blocked until that review/remaining scope is
resolved; no physical audio acceptance or Done status inferred from script exit.
No credentials, device identifiers, images, recordings or precise location saved.
