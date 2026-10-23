# Mac → Windows: calibrated cane depth, October 23

Branch: `codex/mac-lidar-calibration`.
Fetched accepted main: `33aee60` (solo workflow + calibrated cane plan).
Original Mac base: `c34520b60e85d6cd4b5efe18c94659ee236208c4`.
Preservation commit: `2f6285d`; reconciled merge base: `7c4083d`.
Backup of modified/nonignored untracked files and staged/unstaged patches:
`/Users/michaelkrymski/.codex/backups/CaneSight-20261023-131159`.
Signing, private Keychain bond and ignored local dependencies remain local.
No force/reset/main push or older Windows draft applied over the phone integration.

## Geometry decision made with Michael

Located actual yellow debug source in ContentView.swift: 20×40 pixels on a
180×320 preview, corresponding to CameraController.swift's 9×8 inspection grid.
The actual RGB transform is PortraitPreviewTransform.swift and ARKit's current
portrait 9:16 display transform; the depth path uses exact mapping permutations.

Initially preserved that patch's size, but during physical neutral/side setup
Michael explicitly clarified it was too tiny and the regions should correspond
to preview LEFT / MIDDLE / RIGHT thirds. The implementation therefore **now uses
a full-width detection band**, three equal thirds, default height still 40 pixels
(1/8 view). Helper explicitly adjusts vertical position and height (1/8–1 view).
This is a user-authorized geometry correction, not an inferred equivalence between
the old diagnostic patch and production ROI. Incomplete narrow-profile evidence
was not saved/used to authorize the new band. New profile format is version 2.

## iPhone implementation

- PreviewState/MountCalibration.swift: versioned profile, normalized intrinsics
  and display transform, ray backprojection, gravity-level/yaw-following camera
  frame, projected physical ray region, visibility, pixel selection and stable
  neutral window. Each selected pixel appears at most once, all from one ARFrame.
- MountCalibrationController.swift: current ARKit frame adapter, classified floor
  selection, geometric masking, packed unchanged depth processor, helper wizard
  and private profile storage. No Core Motion clock or separate gyro integration.
- CameraController.swift: current-frame preview/result, source epoch fencing,
  synchronous clear on calibration/remount, saved-profile gate and transient
  resets. ARKit uses explicit gravity alignment; no stored world anchor reused.
- ContentView.swift: actual projected yellow band/sector outlines, explicit height
  slider, tap-to-position, exclusion markers and helper controls. Scroll no longer
  drags the region. Setup distances are local; Status/Demo/stream remain unknown
  before confirmation. Product text states obstacle side, no turn recommendation.
- PhoneConnection.swift: existing private phone bond, native WSS/clock transport,
  source fence, current schema; local calibration diagnostic added to the private
  journal (not wire). No credential generation or Mac helper.

Calibration: helper-present checkbox; valid level floor/normal tracking; 12+ fresh
frames spanning 2.5 s, <=2° neutral pose and <=3 cm height variation; 3 separate
fresh records per physical side with >=15 cm dominance over other measured thirds; 3 low-obstacle
records with >=32 retained points 8–20 cm above floor; explicit helper save.
Unknown or poor samples never satisfy physical acceptance. Helper target identity
is an operator assertion, not automatic object recognition.

Saved Application Support `mount-profile-v2.json`: version, local profile ID,
confirmation date, helper/side/low flags, private this-device/camera binding,
image/depth dimensions, normalized intrinsics/display transform, band geometry,
neutral camera-to-level matrix, coordinate convention, neutral height, angle/
height/range limits and engineering floor uncertainty. No raw video, location,
world origin/anchor or credential. Loaded automatically on normal restarts when
compatible; fresh pose/floor/depth still required. Mount moved invalidates storage
and local source immediately; unfinished wizard evidence resets on lifecycle loss.
The IMU cannot distinguish a slipped mount from normal cane motion.

Initial supported envelope: level ground within 3°; camera height 0.3–2 m,
change <=10 cm from neutral; pitch <=15°, roll <=10°; slant range 0.25–4 m.
Yaw follows cane/camera direction; a world turn does not exchange sides. A partly
off-screen sector is entirely Unknown; fully visible sectors can still measure.
No extrapolation into unseen pixels. At least one visible sector required for
geometry support; otherwise source is degraded.

Floor mask: only high-confidence points within ±2 cm of a current classified floor
plane, >=5 cm inside its observed boundary. Ambiguous floor heights (>5 cm spread)
or missing floor/unsupported pose are unavailable; no fallback that marks raw
uncalibrated depth ready. Profile floor uncertainty 3 cm is an engineering margin,
not a measured hardware bound. Very small obstacles, ramps, stairs and arbitrary
height/ground changes are not validated. Initial low obstacle check is 8–20 cm.

The existing processor still uses high confidence, minimum 32, 25% coverage and
p10. Actual selected samples are packed into 3 columns with NaN padding up to the
largest per-sector sample count rounded up to a bounded 2D tile row. This conservatively underestimates coverage in
smaller sectors; no fake distance/duplicate sample is inserted. Original capture
time is retained; only geometry changes the sampled ROI and range calculation.

## Windows coordination / unchanged contract

**No packet fields, schema, receiver code or backend code changed.** Do not add
calibration metadata to existing closed v1 messages. Calibration is gated locally;
uncalibrated/unsupported geometry leaves existing producer starting/degraded,
without publishing a calibrated depth sample. Valid input uses existing original-
age left/center/right summaries, nulls and sequence rules. Distances are measured
3D slant ranges for selected points; no raw point cloud or RGB is uploaded.

Use existing Pi bond and phone bond. Do not reissue credentials. Independent
receiver capture-age/clock/drift gates remain mandatory; the October 18 conditional
measurement candidate was not configured. This new profile does not prove drift.
On calibration/remount/source loss the phone synchronously clears local data and
cancels the fenced socket. Bytes already in the OS and existing Pi pulses cannot
be recalled by a local fence: verify receiver clear-on-close/degraded/expiry and
capped watchdog behavior before claiming physical pulse clearance.

Obstacle on left → left motor (BCM18); center → both, priority; right → right
(BCM19). User chooses movement. No opposite-side avoidance, steering, continuous
unknown buzz or all-clear. This Mac change contains no GPIO/motor command and
makes no physical disarm claim. Windows owns actual channel/pulse/power evidence.

Public backend health was HTTP 200 with normal verified HTTPS during this run.
That is not readiness, successful authenticated pairing, WSS receipt or model
acceptance. Phone connection status/physical calibration results are recorded in
local evidence and the final checkpoint; do not infer completed pairing from health.

## Checks and physical limits

31 PreviewState tests (17 new mount cases plus 14 existing) pass: full-width band,
explicit height, independent portrait pixel oracle, positive/negative pitch/roll,
yaw invariance, off-screen unknowns, floor/10 cm low target, invalid ranges/NaNs,
profile reuse/version/device checks and stale/unstable window rejection.
10 pairing/wire-fence tests pass. Root repository 257 checks pass after selecting
full Xcode DEVELOPER_DIR (the first pass used CLT and could not import XCTest).
Backend 145 tests pass (6 skips); local replay passes. No private credential was
used in these tests. Root publisher tests print mocked temp-repo publication text;
that text is not an actual branch push.

Signed physical iPhone Debug builds/strict signature/install/launch ran. First
uncalibrated device snapshot confirmed eligible=false and zero depth sends even
with usable selected input. Operator reported reaching LEFT after neutral capture
for the obsolete narrow patch. Full-band version installed and physical setup
restarted; no acceptance credit transferred between those geometries. Full-band
side/low/save/relaunch/tilt observations remain pending unless separately recorded
in the final evidence. Build/unit success is not physical calibration acceptance.

Two Simulator UI cases cover missing real measurements preventing save and Mount
moved remaining required through background/relaunch. Final results and publication
SHA will be recorded in a followup checkpoint. Initial UI failures identified an
always-active preview drag intercepting scroll and a test reading an off-screen
label; both were corrected without adding fake sensor/profile eligibility.

## Followup during this implementation

Michael reported apparent invalid depth beyond ~2 m. Code has no 2 m cutoff:
selected slant range gate is 0.25–4 m, confidence stays high, coverage stays 25%/32.
Added per-selected-sector raw/high-confidence >2 m counts and explicit floor/range/
visibility reasons in a local disclosure. Separate calibration restriction fixed:
known placed target can be checked when background thirds are Unknown; those
unknowns are not compared as infinitely distant and never become known/clear.
Any other measured third must still be >=15 cm farther. Each side still requires
three operator-identified, fresh measured target captures. Stable neutral needs
96 retained samples and at least one measured sector, followed by all side checks.
No confidence relaxation or synthetic range introduced. New stale/future capture
window test added. Do not claim the actual reported >2 m failure diagnosed without
a supported live wall sample; device temporarily disconnected, then was reconnected
with camera stopped/unsupported pose. Phone authenticated waiting for Pi on latest
observed status. Existing Pi peer is needed for paired WSS receipt.

Unconfirmed band UI settings are now saved separately in Documents/mount-setup-region-v2.json;
this preserves Michael's chosen y~0.237211 / height~0.556829 across install/restart,
without helper verification or eligibility. It does not replace the confirmed
Application Support profile. No raw video/depth or credential is in that UI file.

## Live discovery: tall-band input dimensions

The distant-wall sample had 6,728–7,007 selected samples per sector with 6,554–6,998
usable high-confidence samples. Left sector had 2,933–3,529 high-confidence raw
samples beyond 2 m across four snapshots. Yet summary distances were null. The
new band's initial packer used 3 columns × max sector sample count rows; that
exceeded the unchanged DepthLimits maximumDimension=2048 for a tall band. This
was a bug in the new Mac packing, not a need to relax confidence. Reproduced the
old 3×6864 input returning invalidDimensions in a synthetic processor regression.

Fix: pack each sector into a width-32 tile, combine three tiles horizontally,
choose bounded height ceil(maxSamples/32), fill unused slots NaN/zero confidence.
Every selected source pixel still appears once. Max dimensions/pixel budget are
checked before allocation; overflow stays unavailable. Denominator is the largest
selected count rounded up to the next tile row, conservatively. Four real-processor
synthetic cases and 31 core tests pass, including numeric 2.7 m and original capture
time. Added a permanent Mac-only unittest wrapper to make the processor regression
reproducible in root checks; Linux skips it rather than claiming an iOS run.

Fixed app installed; fresh post-reset scan requested for actual phone numeric
confirmation. These raw counts show useful sensor depth beyond 2 m in this run;
they do not independently calibrate the wall distance or diagnose all October 18
confidence losses. No normal production eligibility until helper profile is saved.

## Post-fix physical range confirmation

After the requested fresh floor/furniture sweep, four real phone snapshots all
reported processedFrame, packed dimensions 96×215 or 96×219, and numeric selected
left/center/right distances approximately 2.33 / 2.34 / 2.49 m. Each sector had
6,864–7,007 high-confidence raw samples beyond 2 m. This verifies the packing fix
on the installed app without lowering confidence. It does not independently
verify absolute wall distance or all earlier confidence losses. No confirmed
profile yet; depth sends remained zero. Phone authenticated waiting for Pi.
Full-band helper neutral/side/low/save/restart acceptance remains pending.
Permanent processor regression wrapper rerun passed after adding the explicit
legacy invalidDimensions assertion.
