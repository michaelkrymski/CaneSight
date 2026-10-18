# CS-018 accessible status — 18 October 2026

Owner: aditsangani. Branch: task/CS-018-accessible-status.
Merged assignment: PR #66. Initial base: 5dbb6adc6f7c8984e1beb624fc7c8fe1a4cdfafa.
Publication base: 94ccaaf14a88b990cc468433e55622b0b1e6681f.

## Change and scope

Standalone `ios/AccessibleStatus` package with portable typed status/cancellation
controller and conditional SwiftUI model/view. Explicit unknown/degraded depth,
connection and audio states, sanitized nullable distances, image-column labels,
VoiceOver labels/values/hints, wrapping Dynamic Type fonts, large full-width camera
and Cancel controls, and accessibility Escape. No duplicate UI value cache; read
controller snapshot after reentrant changes. One depth epoch and audio ticket,
local display expiry, clock-fault latch, offline manual cancellation, late callback
fencing and visible failed/unwired cancellation. Software success means request
accepted, not verified audible silence. No automatic announcements or speech.

Gavin's CS-017/019 merged during work. Fast-forwarded to accepted main and changed
the integration fixture to use accepted `ios/Lifecycle` directly. No teammate source,
protected contract/baseline/workflow, camera host, speech engine, GPIO or service
was changed. The accepted scenario-menu amendment is preserved; CS-027/040 stay
with Mila. CS-018 exposes the common cancellation seam rather than implementing
her state machines. No secrets, image assets or location data added.

## Changed files

- ios/AccessibleStatus/.gitignore
- ios/AccessibleStatus/Package.swift
- ios/AccessibleStatus/Sources/CaneSightStatus/StatusController.swift
- ios/AccessibleStatus/Sources/CaneSightStatusUI/AccessibleStatusView.swift
- ios/AccessibleStatus/Tests/CaneSightStatusTests/StatusControllerTests.swift
- ios/AccessibleStatus/README.md
- tests/ios/cs018_lifecycle_integration/.gitignore
- tests/ios/cs018_lifecycle_integration/Package.swift
- tests/ios/cs018_lifecycle_integration/Tests/CS018LifecycleIntegrationTests/LifecycleIntegrationTests.swift
- tests/ios/evidence/CS-018-status-20261018.json
- tasks/CS-018.json (runtime fields only)
- changes/20261018-cs-018-accessible-status.json
- this handoff and renderer-generated CHANGELOG.md

## Actual verification

Official Swift 6.0.3 Ubuntu 24.04 toolchain, local WSL x86_64. Extracted libncurses6
into task-local WSL cache, no system/root dependency installation. No Swift or Apple
SDK on Windows was claimed. Commands:

```
swift test --package-path ios/AccessibleStatus --jobs 2 -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
swift test --package-path tests/ios/cs018_lifecycle_integration --jobs 2 -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
```

17 portable controller tests passed; 2 tests using the actual accepted CS-017 guard
passed. Cases include missing/nonfinite depths, 500ms expiry, heartbeat not renewing
capture age, clock faults, background/interruption/epoch fencing, offline cancel,
failed cancellation, one bounded audio slot, late/reentrant audio completion and
observer/cleanup reentry. The two integration tests demonstrate real lifecycle-hook
purging and cleanup reentry, not a Python copy of the algorithm.

Tree-sitter 0.26.0 / Swift grammar 0.7.4 parsed all six owned Swift files without
syntax errors. This checks the conditional UI syntax, not Apple API type checking.
Evidence JSON contains exact UTF-8/LF source hashes and accepted lifecycle hash.
Shared Python/repository/changelog/whitespace checks run in checked publishing;
Swift tests are separately reported and are not root CI discovery.

## Limits and next steps

Keep draft and task blocked. Linux excludes the SwiftUI body. Native UI has NOT
been built, installed or exercised by this session; no VoiceOver, Dynamic Type,
real phone/Pi/speech path or audible Bluetooth timing was tested. This package is
not yet linked into Michael's still-separate CS-013 app. Nil/unwired cancellation
stays visibly unavailable; a no-op hook must never masquerade as a working cancel.
Local callback-recency preview is not calibrated capture age. UI ticking is not
a hard real-time safety watchdog. Physical image-to-body mapping remains CS-015.

Review package/source; add products to PR #69 host after reviewed integration,
forward native lifecycle hooks synchronously, capture display tokens before worker
processing, and preserve original worker receipt/source clock bounds. Integrate the
real local CS-040 generation invalidation/stop action without a network wait or
invented wire message. Follow the package README's host snippets and pending Apple/
VoiceOver/layout/audio matrix. Verify against current native dependency heads.
Record exact commit, build/device, failures and audible buffering separately before
asserting acceptance. Independent Michael review/merge required; no self-merge.
