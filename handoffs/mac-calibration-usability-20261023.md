# Calibration usability and preview — October 23, 2026

Branch codex/mac-lidar-calibration; base 89489ef; fetched main remains 33aee60.
Existing untracked ChatGPT PNG and private device/signing files are untouched.

## Diagnosis and changes

Operator screenshot shows Mount changed/invalidated and red points near a hand
edge. Red points were exclusions, not object detections. Old first-120 raster
markers biased the display toward edges. New optional uniform 8-pixel-grid samples
show green accepted high confidence, red invalid/low confidence/range/visibility,
and blue excluded floor; legend explicitly says these are not object outlines.

Found destructive path: confirmed profile plus camera compatibility failure called
moved(), which deleted saved calibration and required helper setup. Previous
compatibility included 3% intrinsics and .001 display-affine limits. Those are not
physical mount measurements. Current geometry already uses actual frame k/display
against saved neutral rays; remove those parameter-delta rejection rules. Keep
valid camera geometry, same private device and image/depth dimensions. Any
remaining incompatibility gates readings temporarily without deleting the saved
profile. Explicit Mount moved now requires a cancelable alert. Actual origin of
the screenshot event is not retrospectively established (could also be an explicit
action); do not claim measured autofocus caused it. The latest phone probe had
no loaded profile, so there is no recovered confirmed calibration to assert.

Fresh RGB rendering is now independent of PortraitDepth validity. Depth/tracking
loss still invalidates measurements immediately; fresh RGB continues if available.
Both use the current source epoch and 500 ms callback-recency checks. Preview has
its own expiry and clears on Stop/background/interruption. This addresses a known
black-preview code path, not proof that all reported flashes were caused by depth.
Local-only camera_capture counters include session runs, valid/missing/delayed
frames and OS thermalState. No hardware temperature measured. Disabled expensive
raw histogram in ordinary launches; projection validity cached once per selection
rather than per raw pixel. No measured power/performance improvement yet.

Floor, original capture timestamps, clocks, range/confidence/coverage gates,
pitch/roll/height envelope and v1 wire schema remain. Unsupported motion may
make readings temporarily Unknown; it does not itself invalidate calibration.
No receiver, motor or production drift changes. No private screenshot copied to Git.

## Checks and deployment

35 geometry/state tests pass (focus/crop variation above prior 3% threshold,
current-frame projection, retained source measurements, uniform accepted/rejected
markers); four real processor integration cases pass. 10 native transport/fence
tests and 257 repository checks pass. Initial new test fixtures were corrected:
8% narrowed FOV properly exceeded the 90% visibility envelope; initial mixed
confidence fixture covered only low-confidence pixels in the narrow band. Final
fixtures independently exercise the intended retained and mixed observations.

Signed physical build, strict signature and final install pass. Earlier launch
attempt was denied because phone locked; final build installed without automatic
camera restart. User asked to open the cooled phone with camera stopped first.
Simulator explicit invalidation through background/relaunch passed. Initial
confirmationDialog lacked an accessible named cancel control; changed to alert
and reran cancellation test (append final result below). No physical preview,
thermal recovery, recalibration reuse or haptic acceptance claim. The user may
need helper setup again because the previously deleted profile cannot be inferred
from a screenshot or recreated as confirmed evidence.

Final cancellation alert Simulator rerun: TEST SUCCEEDED. Both cancellation
and explicit invalidation/background/relaunch have passing executed results.
Final signed build installed successfully; camera was not started automatically.
