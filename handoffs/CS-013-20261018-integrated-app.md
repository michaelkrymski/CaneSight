# CS-013 integrated iPhone app

Base: e24279f9f4f62bfb602e43333936c0ca51136fad. Prior host: 88e2a14cd6fc2e6a368368cf72118c829382b4a4.
PR #69, branch claim/CS-013-michaelkrymski. Michael explicitly requested as many
available iOS features as possible and authorized phone testing. Existing PM
assignment-only exception/initial claim remains unchanged. No teammate task,
requirements, master plan or contract was amended.

## Changes

One app now presents Camera, Status and Location tabs. Host capture plumbing
adapts our own CS-015 bench: actual portrait display transform, matching depth/
confidence pixel permutation/crop, bounded in-memory image, confidence reasons,
session-only target check and loss/orientation/background/expiry resets.
Captured CS-018 display tokens accompany frames before async processing. Status
invalidation clears stale values and cancels fixed status speech; host scene
activity remains independent of whether the optional presentation is mounted.
Camera authorization, unsupported and interrupted paths remain unavailable.

Unmodified CS-018 status/view is integrated. Own local AVSpeechSynthesizer adapter
speaks one explicit fixed app-status message, fences callbacks before cancel,
propagates a failed stop and never controls VoiceOver/system audio or queues a
reconnect replay. This is status speech, not Gemini/scene narration or CS-040
provider integration. No physical audible stop-delay measurement claimed.

Accepted CS-019 source supplies explicit local consent, foreground collection,
rounded in-memory policy, age/accuracy availability and opt-out purge. Coordinates
are not displayed, persisted, transmitted or logged. Actual one-time permission,
usable coarse fix and opt-out display cleanup were observed by phone UI tests.
Privacy manifest declares only on-device elapsed-time/timer use; future network
clock use requires another privacy/clock review.

Review inputs are exact/hash-checked: accepted current lifecycle and location;
separate depth #62, telemetry #64, status #73 and mapping #70 inputs. The manifest
preserves mapping's relative dependency layout so only one depth source folder is
resolved. Existing prepared inputs were preserved locally before rematerializing.
No teammate source was modified or copied into tracked host implementation.

## Validation actually run

Signed physical-iOS SDK build/install/launch passed. Latest actual iPhone 17 Pro
Max / iOS 26.6.2 suite: 5 passed, zero failures/skips. It covers largest text and
60pt controls; real depth/Stop-to-Unknown/restart/Home Screen/live recovery; local
GPS one-time consent/fix/opt-out; GPS off on launch; fixed speech/cancellation.
Simulator UI: 2 passed, zero failures/skips (maximum text and unsupported-depth
unavailable/disabled controls). Current accepted lifecycle: 14 iOS Simulator tests
passed, including two native bridge cases. Strict-concurrency/warnings-as-errors
Mac cases: lifecycle 12, coarse GPS 15, status 17, mapping 11, PreviewState 5 (60).
Machine summaries and exact tested source hashes are in the evidence JSON.
Local result paths there are not committed result bundles or private images.
Checked publisher runs current shared checks and generated-log validation.

Real UI testing found the normal-size read-status hit area was only ~40pt despite
an outer frame: moved the minimum frame into the button label; default/largest
checks then passed. Free-profile install cap was resolved by removing only our
obsolete disposable Mount Check test runner, preserving the bench app. Simulator
initially built the app for x86_64 while packages were arm64-only; Debug now uses
standard ONLY_ACTIVE_ARCH=YES. A wide SwiftUI switch test initially tapped its
label; targeting its actual switch end exercised normal one-time OS permission.
No confidence/freshness threshold or assertion was weakened to manufacture passes.

## Limits and next integration

Task Review, not Done. Dependency review/acceptance still required. The current
lifecycle native runtime evidence supersedes older-pin evidence only for that
recorded package; no unrelated task is marked complete. App transport remains
unavailable: no backend enrollment, credentials, network client or clock mapping
is instantiated. GPS network contract is separately pending. Local callback
recency is not capture age; physical target placement, nonzero background counter
reset, final cane/grip/motor mapping, range/error/latency measurement, VoiceOver
listening and audible output buffering remain separate evidence. Floor samples
remain included and unknown never means an empty path.

Changed files: project/scheme, six-input manifest/materializer, camera/controller,
app services/root/views, UI tests, privacy manifest, current README, task runtime,
this handoff, new evidence/changelog fragment and generated log. Main/remote host
QA merges were integrated by fast-forward without editing their files. Keep the
phone app/local consent usable while remaining reviews and transport gates close.
