# Copy into the Mac chat

```text
Continue CaneSight on this Mac. Michael is now the sole maintainer. Fetch current
GitHub main, read AGENTS.md and docs/operations/SOLO_DEVELOPMENT.md. Task claims,
old ownership locks, path-allocation gates, formal CR approval and extra reviewers
must not block his work. Preserve uncommitted changes and use a separate branch
if the Windows chat is editing concurrently. Do not reset the Mac's newer work.

Read docs/operations/LIDAR_CANE_CALIBRATION_PLAN.md in full, then implement its
Mac/iPhone stages using this Mac's existing yellow debug region. First locate
the actual region code and coordinate transforms; report the relevant files.
The user says that region is already the right size. Do not invent or silently
replace its geometry. Use current app/telemetry/clock code, not the older Windows
persistent-bond draft. Inspect current branches and reconcile changes carefully.

Product: supplementary to a conventional white cane. Obstacle on left -> left
motor, center -> both, right -> right. Users choose their own movement. No turn
recommendation or route planning. Unknown stays unknown and does not become a
normal obstacle cue or an all-clear.

Add a sighted-helper mount calibration option. First calibration is required;
repeat it whenever the phone mount angle changes. Position the agreed region
at the user's normal cane holding angle to avoid floor/cane/hand interference,
verify physical sides, then save a versioned mount profile. Provide Mount moved /
recalibrate; invalidate old observations atomically. Do not require recalibration
for ordinary cane tilting. Reuse a valid profile automatically on later runs;
reported uncertain or changed mounting requires the helper again. Do not claim the phone
IMU alone can automatically distinguish a slipped mount from a moving cane.

Use gravity-referenced fused attitude synchronized to depth frames for pitch/roll
compensation; gyro integration alone is insufficient. Work with actual intrinsics,
depth/display transforms and camera axes. A projected physical detection region
plus a supported floor/height model is stronger than only moving a screen box.
Document the angle/ground/height envelope and preserve low-obstacle detection.
Keep left/right relative to the cane/user, not fixed world yaw. Off-screen or
unsupported geometry is unavailable. Do not add synthetic depths or relax
confidence merely to obtain readings.

Perform ROI/geometry processing on the phone. Send original-age left/center/right
summaries through the existing native transport. Coordinate any necessary wire
change with the Windows chat; existing v1 schemas reject extra fields. Missing
calibration can gate locally and use existing unknown/degraded states. Do not
share raw depth/video unnecessarily. Build with Xcode, run focused geometry and
lifecycle tests, install on the physical phone and report actual observations.

Windows handles Pi/server/bond connectivity, native receiver freshness/clock
integration, capped GPIO obstacle cues and power checks. Backend base URL:
https://64.177.50.116. Keep existing identification working. Publish your branch,
commit and concise handoff so Windows can integrate. Do not claim a passing build
or physical result without running it. Preserve credentials and signing locally.
```
