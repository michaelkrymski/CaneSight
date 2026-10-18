# CS-019 local software checkpoint

Owner: Gavin (`gmarcialcalleja`). Assignment #65 was merged by Michael before work.
Initial base: `ae449acb1bea251c360833a0863ec014d1f7feff`.
Before publication, fast-forwarded accepted main to `5dd5fa37009402b7eb7c9dbed3d20eacd4346c90`
(CS-018 assignment only); no teammate task edits.
Branch: `task/CS-019-coarse-location`.

## Task and scope

Acceptance unchanged: fix age/accuracy; denied/stale fix unavailable; no lane or
signal association. Dependency remains CS-016 (Mila's draft #64, not merged at
implementation time). Allowed implementation paths remain `ios/`, `tests/ios/`.
No protected schema, master plan, backend or other teammate task was edited.

## Changed files

- `ios/CoarseLocation/Package.swift`, `.gitignore`: independent Swift package.
- `Sources/CaneSightCoarseLocation/LocationContext.swift`: consent, OS permission
  and foreground gate; original UTC fix dating then monotonic ageing; conservative
  invalid/future/stale/poor-accuracy rejection; rounded 0.001 degree cache only;
  sensor accuracy plus separate quantization-inclusive radius; immediate cache
  purge hook on revocation/background/failure; at most 1 Hz local handoff.
- `Sources/CaneSightCoreLocation/CoreLocationSource.swift`: main-run-loop provider
  with When In Use authorization, explicit sharing consent, foreground-only
  collection, freshest batch input and synchronous delegate forwarding. No
  precise history/logging, background capability or temporary full accuracy request.
- `Tests/CoarseLocationTests/LocationContextTests.swift`: 13 portable XCTest cases
  using synthetic coordinates only, including consent race/recovery, permissions,
  original-age expiry, precision/uncertainty, boundaries, clock faults and rate cap.
- `ios/CoarseLocation/README.md`: concrete host integration, purpose string,
  separate transport requirement and pending physical-device matrix.
- `decisions/CR-CS-019-location-context-contract.md`: proposed reviewed GPS contract
  and consumer requirements; no baseline edits, no wire serializer or network sink.
- Own task runtime, new changelog fragment and generated changelog.

## Actual validation

Ran on the existing Vultr host in an isolated disposable compiler container with
network disabled, one CPU and 2 GiB memory limit. Production services untouched.
Official Swift 6.0.3 image digest:
`sha256:a159706c0c52c1025998a87bc2ab3ceba71416a00110b31cc2ab08d9184341c9`.

```text
swift test --jobs 1 -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
13 tests passed, no failures or compiler warnings.
```

Core Location/UIKit source body is conditionally excluded by Linux. A target name
in Linux compiler output is not proof that the Apple adapter was compiled. No
Xcode/iPhone/GPS integration or electrical verification was run. Checked publisher
runs structure/shared tests/generated log/whitespace; PR reports actual results.

## Pending review and integration

The accepted core v1 protocol explicitly excludes GPS and requires separate
reviewed contracts. Local context software is implemented, but no compatible GPS
wire format or consumer exists on this base. Do not inject location fields into
depth, heartbeat or vision packets. Michael must review the CR and assign/review
the eventual shared/backend scope; this proposal alone does not authorize it.

After CS-016 merge and GPS contract approval, integrate an authenticated separate
P1 publisher with transport-age validation, independent receiver expiry and
revocation/pending-send cancellation. Then build the Apple adapter on a Mac and
verify purpose/permission prompts, denied/reduced/full authorization, Settings
revocation, old cached first fixes, poor accuracy/indoor, background/lock/resume,
clock steps and 1 Hz delivery on an actual phone. Record metadata/counters, not
precise tracks. No lane/signal association or motor/crossing effect is permitted.

Task remains blocked with those exact gaps. No end-to-end telemetry, physical
readiness or completed CS-019 acceptance claimed. Stop at Michael's review.
