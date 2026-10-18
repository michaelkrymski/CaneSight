# CS-040 — local narration bridge and Pi speech adapter

Author: bondmila (AI-assisted), 2026-10-17.
Branch: task/CS-040-restricted-narration.
Starting head: 03edc9ab90fe690980f98eaeffc7564f47fb6d6e.
Accepted main integrated: 5fbbed2; merge base for this checkpoint:
737134d966b8bfa65f5f1625f4eb17ae3ee12b66.
PR #55 confirmed merged at dfde4d181d18523ed51dfdd117c1b1904e4dc83b.
PR: https://github.com/michaelkrymski/CaneSight/pull/41 — stays draft.
Merged CS-040 ownership remains bondmila; no competing task taken over.

## Changed behavior/files

- backend/context/consumer.py composes accepted ContextButton/ContextClient and
  NarrationController. One independent local 10ms worker drives input debounce,
  request/results, priority and audio expiry. Trusted readiness/obstacle policy,
  consent, frame supplier and concrete sink are injected local adapters, not
  model-controlled state. Audio stops before network-child cancellation.
- narration.py adds begin_capture for original local capture time; expiry is
  capture +8s, avoiding renewal between adapter age calculation and begin.
  Existing conservative remote-age API remains unchanged. No cross-clock use.
- User selected Bluetooth speaker connected to Pi. pi_speech.py provides opt-in
  eSpeak NG output using OS-selected audio for the Pi user, not pairing/routing.
  Only fixed <=20-word uncertain template/unavailable text is accepted. Text is
  bounded stdin, no shell/argument interpolation/temporary recording. One owned
  process group, cancellation/replacement/close kill/reap, engine-health latch.
- README documents integration API, prerequisites and remaining actual-device
  gates. Task runtime evidence/blocker updated, plus new immutable fragment,
  this handoff and generated CHANGELOG.md. No shared/protected baseline edits;
  existing uploader/context runtime was not changed under CS-040 scope.

## Tests actually run

Python 3.13 using /tmp/canesight-gemini-venv/bin/python with pinned test deps:

- unittest discover -s tests/context -v: 60 tests passed.
- unittest discover -s tests/edge -v: all 132 tests passed.
- New consumer tests: original capture expiry across network delay, manual and
  second-press pending cancel, playing-audio cancel without cooldown bypass,
  no held-repeat cancellation, priority/consent/recovery, envelope retiming and
  instruction rejection, clock reversal, independent worker and engine health.
- Generated local CA/JPEG replay fixture: real paired session, actual spawned Pi
  HTTPS client, accepted context endpoint/fake provider, synthetic speech sink,
  then hazard preemption. Child cleanup verified; no cloud/Gemini request.
- Synthetic executable tests execute real owned speech processes, check bounded
  stdin/fixed args, replacement/kill/reap, engine failure latch, input rejection
  and missing executable. These produce no audio and do not run eSpeak NG.
- Checked publisher reruns repository validation, root tests, changelog check,
  governance and whitespace before commit/push. Inspect current-head CI after.

## Limits / next steps

PR #41 remains draft and task blocked. The bridge and Pi sink are adapter APIs,
not installed in uploader or phone. Actual Pi installation, default Bluetooth
routing, output audibility, disconnect/reconnect behavior, startup/off state,
manual/obstacle preemption and measured cancellation latency remain unverified.
Bluetooth/OS buffers may outlast process termination: no instant physical silence
claim. Confirm all adapters return promptly and do not reenter the consumer;
Python scheduling is not hard real time. Priority must include trusted camera
freshness and primary-source availability. CS-018 accessible controls and physical
acceptance are separate. Root discovery includes the context package; separate edge discovery is
still required and its result is explicit. The first publisher run caught a TLS
test helper import that worked only in direct context discovery. Fixed it to
support both package/root discovery and direct discovery before republishing. No credentials, real scenes, Bluetooth
addresses, recordings, electrical proof or release claim. Independent PM review
and actual-device evidence required; no merge performed.
