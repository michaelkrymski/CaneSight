# CS-018: accessible status and manual audio cancel

Standalone local Swift package, owned by CS-018. Products: `CaneSightStatus`
(portable presentation controller) and `CaneSightStatusUI` (conditional SwiftUI
view/model). No third-party packages. iOS 16+, macOS 13+ for native review.

This is source preparation plus portable software evidence. It is **not yet
installed in Michael's draft host app**, and does not replace CS-017 lifecycle,
CS-016 transport, CS-019 consent/location or CS-040 speech policy. The current
accepted main contains the lifecycle and coarse-location packages but no host app. App integration needs
review of those separate PR inputs. No other teammate's source was modified.

## Behavior

- Explicit labelled depth, connection and narration rows; missing/nonpositive/
  nonfinite distances are `Unknown`, never zero or a far-distance default.
- Depth rows always say **Image left/center/right**, not verified physical sides.
  Connection success never means sensor or whole-system readiness. Healthy local
  preview can remain visible while the backend is disconnected.
- Local preview is explicitly labelled capture-timing unverified. Its 500ms
  deadline is **callback recency only**. A separate bounded-capture input requires
  conservative verified source-clock bounds; it expires from the earliest capture
  bound, not the receive time. Neither path authorizes transport or motors.
- One current depth epoch, one audio display ticket, no retained frames or queue.
  Lifecycle loss clears sectors and rotates the UI epoch. Old worker/playback
  callbacks cannot restore old state. Resume alone restores no depth or audio.
- The view ticks every 100ms independently of incoming data. It clears expired
  display values; the host/CS-017/Pi must enforce their own expiry even when the UI
  thread stalls. No heartbeat API renews a depth deadline. A nonfinite, negative,
  excessive or backwards local clock latches unknown until a new controller.
- Cancel stays visible and can call the **local** adapter while offline. It
  invalidates the audio display ticket before invoking the synchronous cancellation
  hook, including on reentrant/late callbacks. The host must cancel pending work
  and stop/request stop on its local sink without waiting for a network response.
- Success says `Audio cancellation requested; output silence unverified`, never
  claims physical Bluetooth silence. Failure is visible and blocks new audio
  display admissions until the controller/adapter is deliberately replaced.
  Manual retry stays available. No adapter means a disabled button and explicit
  `Audio control unavailable`; no fake success or no-op production callback.
- Source invalidation, depth expiry, inactive scene and lost connection cancel
  a pending/active audio display. Reconnection does not automatically resume it.
  The host still owns consent, priority/preemption, job identity and speech expiry.

The SwiftUI view uses vertical rows and wrapping system fonts for Dynamic Type,
explicit VoiceOver labels/values/hints, stable accessibility identifiers, a large
full-width Cancel control and optional Start/Stop camera controls. All buttons have
a minimum 60-point label height plus padding. Stop remains enabled if support
disappears while camera capture was requested. Cancellation also has an accessibility
Escape action. No automatic 10Hz status announcements interrupt VoiceOver. The
button cancels **app narration**, not VoiceOver, motors or the physical kill switch.

## Host integration (Michael's PR #69 / accepted CS-017)

Review the exact host package inputs before integrating. CS-017 and CS-019 merged
during this session; their physical acceptance is still pending. This package
requires no unmerged dependency at runtime. Add `ios/AccessibleStatus` as a local Xcode package
and link `CaneSightStatus` and `CaneSightStatusUI` in the host app. Do not copy
teammate implementations into this package. PR #69's current local camera preview
does not have a narration/remote cancel path, so **keep its adapter nil until there
is a real connected implementation**.

1. Own one `StatusController` and one `AccessibleStatusModel` per camera scene,
   on MainActor. Use a finite nondecreasing local monotonic clock in milliseconds.
   An example for presentation is `{ CACurrentMediaTime() * 1000 }` with QuartzCore;
   this does not establish that ARFrame's clock is mapped to that clock.

   ```swift
   import CaneSightStatus
   import CaneSightStatusUI
   import QuartzCore

   // In the host's MainActor owner. Nil is intentional for the preview-only host.
   let status = StatusController(nowMilliseconds: { CACurrentMediaTime() * 1000 })
   let statusUI = AccessibleStatusModel(controller: status)
   ```

2. Embed the view in the existing host. The following body fragment uses PR #69's
   actual `CameraController` interface. Ownership/state-object initialization belongs
   in the host; do not recreate the model/controller during every body evaluation.

   ```swift
   AccessibleStatusView(model: statusUI, capture: CaptureControls(
       requested: camera.requested, supported: camera.supported,
       start: { camera.start() }, stop: { camera.stop() }))
   ```

3. Forward lifecycle invalidation **synchronously** on MainActor. Compose the
   existing CS-017 hooks; preserve their transport/cache/clock invalidation work.
   In `depthBecameUnknown`, clear the existing host summary AND call
   `status.invalidateDepth(.unknown)` (or a typed interrupted/inactive reason).
   Do not parse freeform `camera.status` strings to infer readiness. A host's
   inactive/stop/permission-denied/unsupported/failure path must invalidate this
   display too. Forward `setSceneActive` from the camera's actual scene even if
   the view is not mounted. The view's own scene/disappear hooks are additional
   display cleanup, not a replacement for the native capture/lifecycle barrier.

4. Attach `status.depthToken` to each newly admitted capture/worker event **before
   asynchronous processing**. Keep CS-013/017's epoch and capture guards intact.
   At successful local preview delivery, map CS-014's owned value sectors:

   ```swift
   let sectors = DisplaySectors(
       imageLeft: result.sectors.first { $0.position == .imageLeft }?.distanceMetres,
       imageCenter: result.sectors.first { $0.position == .imageCenter }?.distanceMetres,
       imageRight: result.sectors.first { $0.position == .imageRight }?.distanceMetres)
   status.showLocalPreview(sectors,
       sourceMilliseconds: originalCaptureSeconds * 1000,
       receiptMilliseconds: originalWorkerReceiptSeconds * 1000,
       token: tokenCapturedBeforeWorker)
   ```

   Do not mint a new token or substitute `now` for the old receipt at UI delivery.
   Clear the UI when the host's existing preview guard expires/rejects a result.
   For actual telemetry-ready observations, only after CS-017 admission and a
   verified clock mapping, call `showBoundedCapture` with the original source time
   and local earliest/latest bounds. It repeats a display check; it does not prove
   calibration, select sides or send data. Mapping expiry must invalidate it.

5. Forward CS-016's actual connection states to `setConnection`. A socket handshake
   only displays connection status. Remote session identity, calibrated clocks and
   source health remain their existing separate gates. Do not add a remote cancel
   message without an approved shared contract; none is invented in CS-018.

6. When a real local CS-040 adapter is available, construct the controller with
   `cancelAudioNow` capturing that host weakly. On the same actor, invalidate that
   adapter's current/pending request generation and call its bounded local stop
   path before returning `.requested`; return `.failed` on failure. Do not enqueue
   cancellation behind narration, await network, or pass an empty closure that
   returns success. Local sink teardown and remote job cancellation must preserve
   existing cooldown/consent/priority and never restart after reconnect. Physical
   speaker buffering needs separate measured/audible checks.

   Before an already-authorized host job is queued, retain a `beginAudioDisplay()`
   token with it. This is UI tracking, not speech authorization. Use it for
   `audioStarted` and `audioFinished`; old callbacks after cancellation are ignored.
   A display ticket cannot substitute for CS-040's expiry/priority/consent ticket.
   New speech still requires a new explicit authorized host request. Stop/inactive/
   session/consent teardown must also call the real host cancellation independently
   of whether a view is observing a display ticket.

7. Compose the new scenario-menu controller's existing cancellation action through
   that same host path after Mila's implementation is reviewed. This package adds
   no gesture menu, scenario activation, narration engine, Gemini output or motor
   action. Do not put CS-027/040 state machines in the UI package.

## Tests

Portable tests (Swift 6.0.3 tested with complete concurrency, warnings as errors):

```sh
swift test --package-path ios/AccessibleStatus --jobs 2 \
  -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
```

The **actual CS-017 hook integration** fixture uses the accepted local
`ios/Lifecycle` package directly. It was verified after the merge at accepted main
`94ccaaf14a88b990cc468433e55622b0b1e6681f`; its lifecycle implementation is identical
to CS-017 `0a2e161ed399c7a850cd8ffcf6ed211ce4f2cbca`. No teammate code is copied.

```sh
swift test --package-path tests/ios/cs018_lifecycle_integration --jobs 2 \
  -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
```

Linux **excludes the SwiftUI body**. A log saying it compiled the UI target on
Linux is not a SwiftUI type check. No native SwiftUI/VoiceOver/physical audibility
claim follows from portable tests. Root Python CI also does not run Swift tests.
See `tests/ios/evidence/CS-018-status-20261018.json` for actual commands, results,
source hashes and unrun checks. A UI observer must only consume snapshots; it must
not feed callbacks back as new sensor readiness. Reentrant notification delivery
is suppressed and is not a general event bus.

## Mac/phone acceptance — all pending for this new UI

| Check | Evidence required |
| --- | --- |
| Build | macOS package plus physical-iOS SDK build of the SwiftUI body and host; build/run the current CS-017 dependency head, not an older pin. |
| VoiceOver | Depth/connection/narration names and values; Unknown spoken; predictable focus; button/hint and Escape cancellation reach the real adapter. |
| Layout | Small phone portrait/landscape, light/dark and largest Accessibility Dynamic Type; wrapping, no clipped labels, scrollable/reachable 60pt controls. |
| Failure display | Camera denied/unsupported; lock/background/interruption; worker delayed across epoch; missing/expired depth; connected heartbeat with stale depth. |
| Local cancellation | While offline, pending request, long speech, failure and repeated taps; no late callback/reconnect replay. Verify real sink and request generation. |
| Audio | Record observed speaker stop/buffering delay; distinguish app narration from VoiceOver; never label software stop-call timing as audible latency. |
| Whole host | Real PR #69 camera, reviewed CS-017/016 wiring, live phone/Pi and original-age evidence. Physical mapping remains CS-015. |

Until native/host/device results exist, keep the PR draft and task blocked rather
than asserting Done. The original task acceptance/dependencies remain unchanged.

Apple references: [SwiftUI accessibility modifiers](https://developer.apple.com/documentation/swiftui/view-accessibility),
[accessibility labels](https://developer.apple.com/documentation/swiftui/view/accessibilitylabel(_:)-1d7jv).
