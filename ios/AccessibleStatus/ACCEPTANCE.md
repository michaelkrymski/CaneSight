# CS-018 acceptance follow-up

PR #73 is ready for software-checkpoint review. Michael's review on 18 October 2026 confirms that merged
host #69 uses the exact status source and asks that completed Apple checks be
distinguished from remaining physical checks. This follow-up changes no runtime
Swift, host, speech engine, contract or task requirement.

## Source-verified attributed evidence

`ios/CaneSightApp/ReviewDependencies.json` pins AccessibleStatus to
`6ddb7fc4166eda69db5153025d29ceea164b315e`. All four Swift files in that package
match the pin, byte-normalized to UTF-8/LF. The nine host files recorded in
`tests/ios/evidence/CS-013-integrated-app-20261018.json` also match their recorded
hashes on accepted main `185aa3afaca1bdd6ba5380ba0e7113917f86b2df`.

The accepted CS-013 evidence reports five phone UI tests and two Simulator UI
tests passing with no failures/skips, signed iOS build/install/launch, 17 status
Mac tests and 14 current lifecycle Simulator tests. Relevant checks include
largest text/reachable 60pt controls, Stop/Unknown/restart/background recovery,
unsupported camera unavailable, fixed local status speech and the actual local
cancel hook. These are attributed repository results, not Apple tests run by this
Windows session. Their original device/model and source hashes remain in that
evidence. No private screenshots or test bundles are copied.

Current AppServices owns the controller and real LocalStatusSpeech adapter;
CameraController passes display tokens before asynchronous capture processing.
The sink fences callbacks before stopSpeaking and propagates a failed stop.
This is fixed app-status speech, not Gemini narration, remote Pi speech or a
physical silence measurement. The host has no active network/enrollment client.

The local WSL Swift 6.0.3 rerun passed 17 status tests and two integration tests
against the actual accepted ios/Lifecycle, with complete strict concurrency and
warnings as errors. Linux excludes SwiftUI; its successful UI-target build is
not Apple API type checking. No source changes invalidate the earlier Apple pin.

## Human observation on an unidentified installed build

The human confirmed Camera/Status/Location tabs and Read status/Cancel audio
controls. They then corrected an earlier no-audio response: speech is audible
and cancels using Cancel audio. Record the corrected observation only as
operator-reported behavior. Device model, OS, installed commit, output route and
stop-delay measurement were not supplied. Visible feature matches do not prove
the installed commit. This does not establish Bluetooth behavior, VoiceOver,
exact-head acceptance or physical silence across routes.

The human subsequently reported meaningful VoiceOver labels, spoken Unknown
values and an accessible/activatable Cancel audio control. This is a positive
manual listening/control observation on the same unidentified installed build.
The Escape gesture, full layout matrix and output routes were not tested by
that answer. Do not label the reported VoiceOver check unrun, or extend its scope.

## Remaining manual/device checks

Use a known installed build and record its exact tested host commit, device/OS,
output route and operator privately. Do not record images, surroundings, GPS,
credentials or unrelated spoken notifications. Preserve a failed/untested result;
do not substitute an automated accessibility identifier check for listening.

1. **VoiceOver names/values/focus:** with camera stopped, inspect the Status page
   using VoiceOver. Confirm meaningful Depth, Connection and Narration labels,
   spoken Unknown sector values, a predictable focus order and reachable camera/
   Cancel controls. Activate with a double-tap. Check hints and the accessibility
   Escape action separately; app Cancel must not disable VoiceOver/system audio.
2. **Layout:** test small screen, portrait/landscape, light/dark and largest
   Accessibility Dynamic Type. Record clipping, overlap, scroll reachability or
   lost focus. Existing largest-text UI evidence covers only its tested devices.
3. **Local cancellation routes:** request fixed app speech, cancel while audible,
   then wait for any late restart. Repeat for the intended speaker/headphone/
   Bluetooth route, offline, repeated taps and lifecycle loss. Record app status
   separately from what is heard; VoiceOver may continue intentionally.
4. **Buffering:** measure audible start/stop against the user action using an
   agreed private recording/timing method. Software stop-call or UI-status timing
   is not an audible latency measurement. No unvalidated pass threshold is added.
5. **CS-040/Pi integration:** coordinate with its owner; verify the real request
   generation, pending-job cancellation, priority/consent/expiry and reconnect
   non-replay. The existing fixed phone speech sink does not complete this gate.

Partial observations can inform debugging, but Michael accepts the exact evidence
and remaining task boundaries. Merging the software checkpoint does not close
those gates; keep the task blocked. No Done, paired-transport, movement-permission
or physical-readiness claim.

Apple's [VoiceOver practice guide](https://support.apple.com/guide/iphone/turn-on-and-practice-voiceover-iph3e2e415f/ios)
explains selection/activation gestures; use normal device controls to restore
the user's prior accessibility configuration after testing.
