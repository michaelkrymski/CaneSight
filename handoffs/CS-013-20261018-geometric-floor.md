# CS-013 — experimental ARKit geometric floor exclusion

Branch `claim/CS-013-michaelkrymski`; base
`c34520b60e85d6cd4b5efe18c94659ee236208c4`.
Michael authorized this local fix after confirming the measured near bottom strip
was floor. Master plan section 6.1 item 6 permits justified floor exclusion while
recognizing lost low obstacles. No baseline/contracts or pinned dependencies edited.
No GitHub contact, credential generation or motor controls.

## Implementation

PreviewState/FloorSurfaceMask.swift unprojects original depth pixels into an
AR-camera coordinate system (-Z forward, +Y up) and then current floor-plane local
coordinates. CameraController enables horizontal planes and supplies only current
ARKit floor classifications, near-horizontal normal (cos > .996) and camera >25 cm
above anchor. High-confidence points inside the observed polygon with 5 cm inset,
within 2 cm of plane, become NaN before the unchanged mapped sector processor.
Original confidence requirement, percentile, ROI, sample count and valid coverage
fraction remain. Floor-only and insufficient remaining coverage stay Unknown.

This is an experimental 2 cm geometric tolerance, not a verified accuracy bound.
Low objects within that slab can be lost; UI/README say so. No stored floor model
survives lifecycle reset. Missing/unclassified geometry retains raw depth with
explicit Floor not mapped status. Overflow (>8 floor anchors), invalid geometry
and polygon boundaries do not mask. Processing failure after masking yields Unknown.

Local probe exposes raw and filtered sector distances, mask-applied flag, floor
anchor count, excluded high-confidence pixel count and mask runtime. Raw patch
inspection is preserved so exclusion can be audited. Floor evidence clears with
source invalidation. Phone wire uses the filtered summary; no protocol field or
receiver policy changed, and production capture-age eligibility remains unknown.

## Actual checks

- PreviewState 14 cases passed (4 new masking cases + 10 existing).
- Temporary production processor harness: 3 passed (1 new floor/raised-obstacle
  integration, 2 previous chair cases). Retained source tests/ios/FloorProcessorTests.swift.
- Signed iPhone Debug build and strict signature passed, installed with saved bond.
- First deployment paired/WSS connected but fresh valid tracking unavailable after
  initial 10 sends; zero numeric sends. Local capture guard did not fail; maximum
  local delta 184.102750 ms. Requested 5–10 s slow room/floor sweep to initialize
  the reset AR session. Do not call this physical floor rejection verified.
- Final device status/evidence will be recorded separately after observation.

Changed files: CameraController.swift, ContentView.swift, PhoneConnection.swift,
PreviewState/Sources/CaneSightPreviewState/FloorSurfaceMask.swift and its tests,
tests/ios/FloorProcessorTests.swift, README, task runtime evidence, this handoff,
new changelog fragment, generated CHANGELOG. Earlier local work preserved.

Remaining gate: measure current floor anchors/mask count and before/after sectors
with room-facing normal tracking. If no floor is classified, request a brief scan;
never remove an arbitrary image band or claim ground detection from no detection.
