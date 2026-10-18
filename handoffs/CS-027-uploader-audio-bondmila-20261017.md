# CS-027 — optional manual uploader narration

Author: bondmila (AI-assisted), 2026-10-17.
Branch: task/CS-027-context-button.
Base: 5fbbed2f0143710ceba3849eb85e8e2d5914eb5b (accepted main).
Merged assignment: PR #49; prior checkpoints #52 and #55 are merged.
Dependency: draft PR #41 at b07e68ea6e08ba2bbf6bd261d22c8259bf3560cc.
Keep PR #41 draft. This follow-up is also draft until dependency acceptance.

## Behavior and changed files

- edge/uploader.py adds --context-audio, requiring consented --context-stdin and
  its existing policy/phone prerequisites. Text remains default; no audio import
  or speech activation without opt-in. Startup refuses missing narration/eSpeak
  components with a sanitized error, while normal teardown still runs.
- edge/context_runtime.py connects audio mode to the local ContextNarration
  adapter rather than constructing an extra ContextButton/request timer. Uses
  original same-process frame/session/capture clock; camera freshness, independent
  primary priority and explicit current consent feed narration. No retiming or
  model-controlled movement/health state.
- Terminal press/release drive the sole narration button. Cancel/off/EOF/input
  failure/camera loss/shutdown stop speech before remote cancellation. Independent
  narration worker checks camera stalls and capture-based audio expiry, even if
  capture/input are blocked. Cleanup closes owned bridge and speech sink; stop
  errors remain explicit sanitized faults and do not skip primary teardown.
- Snapshot distinguishes opt-in from audibility; audio_used is unknown in audio
  mode and delivery verification is false. No claim of actual speaker delivery.
- edge/CONTEXT_BUTTON.md documents invocation/dependency and limits. Tests in
  tests/edge/test_context_audio.py, test_context_runtime.py and
  test_context_runtime_tls.py cover wiring and the combined path. Own task runtime
  evidence/blocker, new fragment, this handoff and generated changelog included.
- No CS-040 implementation, protected baseline, shared protocol or task scope
  changes are copied into this branch. Imports are lazy because #41 is unmerged.

## Tests actually run

Python 3.13 /tmp/canesight-gemini-venv/bin/python with pinned backend test deps:

- unittest discover -s tests/edge -v: 145 ran, 140 passed and five explicit skips
  for unmerged narration dependency. These skips are not audio acceptance.
- Against exact draft #41 b07e68e modules: all 145 edge tests passed, no skips.
  A temporary external file-based runner added that worktree's backend/context
  path to backend.context.__path__, then discovered tests/edge under a main guard.
  It did not modify/copy dependency code into this branch. Use a file/main guard
  for multiprocessing spawn; stdin-only test launch cannot run spawned children.
- New tests cover one request engine, preserved original frame, default off,
  explicit CLI flag prerequisites, missing dependency without silent fallback,
  terminal EOF/off, owned cleanup including failed stop, failed startup unwinding
  receiver/policy/watchdog/scheduler, original audio expiry despite newer captures,
  manual cancel, hazard/recovery and independent stale-camera preemption.
- Combined generated local CA/JPEG replay fixture exercises terminal press ->
  actual spawned verified HTTPS Pi client -> accepted paired-session/context
  endpoint -> fake provider -> synthetic speech, then manual speech cancellation.
- Checked publisher reruns repository validation, root suite, generated changelog,
  governance and whitespace checks before commit/push; inspect current-head CI.
  Required CI does not discover the separate edge root; results are explicit.

## Remaining limits

Draft dependency #41 must be reviewed/accepted/installed before audio works from
an ordinary main checkout. Once it lands, rerun ordinary edge discovery with no
narration-dependency skips. This is software-only, with simulated haptics, no
GPIO switch, and no real eSpeak/Bluetooth audio or cloud/Gemini request.
Pi camera/phone enrollment and drift evidence, speaker pairing/default routing,
audibility, disconnect/reconnect and measured stop/priority/buffering remain
actual-device gates. Bluetooth/OS buffering can outlast process termination;
no instant silence or physical safety acceptance. CS-018 accessible controls and
accepted electrical prerequisites remain separate. No keys, private scenes,
Bluetooth identities or recordings committed. Independent PM review; no merge.
