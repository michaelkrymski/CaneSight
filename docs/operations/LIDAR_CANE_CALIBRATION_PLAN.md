# Calibrated cane LiDAR: Mac and Windows handoff

October 23, 2026. Planning only: no LiDAR, ROI or motor behavior is implemented
by this document. Michael is now working solo; use AGENTS.md and SOLO_DEVELOPMENT.md,
not the original claim/ownership/reviewer process. Coordinate Mac/Windows branches
to preserve simultaneous work even though both are Michael's account.

## Agreed product behavior

This complements a conventional white cane. The user chooses their own movement.
Vibration identifies the **obstacle's side**, never a recommended direction.
Left obstacle -> left motor; right -> right; center -> both, with short capped
pulses and center priority. A greater side distance can be shown as diagnostic
information, but must not invert a cue into an instruction to turn. There is no
route planner, automatic steering, crossing decision or clear-path heartbeat.

Use the existing yellow debug region in the Mac implementation as the initial
size/shape. Michael says it is the right size. Locate its actual rendering and
processing code, including uncommitted Mac work; do not invent a replacement or
assume it is already in accepted main. The displayed region must correspond to
the depth samples actually used. Partition that selected region into three
consistent left/center/right sectors and measure all three from the same frame.
No sequential "look left/right" camera motion or additional sensors are needed.

Unknown/poorly observed sectors stay unknown, with no obstacle pulse generated
from missing data. Ordinary cane technique supplies the complementary tactile
information; silence must not be labelled as a clear path. Do not add continuous
unknown buzzing. Local status can show sensor/calibration unavailability.

## Calibration — helper-assisted and required after remounting

Expose a **Calibrate mount** option plus a prominent **Mount moved / recalibrate**
action. The first setup requires a sighted friend. Hold the assembled cane with
the user's usual grip/height/forward angle while the helper sees the live preview.

1. Stop LiDAR motor eligibility and clear pending observations/pulses on entry.
2. Keep the yellow region's agreed dimensions as the default. Let the helper
   position/align it so the usable detection region excludes the visible floor,
   hand and cane at the neutral holding angle. Any optional size edit must be
   explicit; do not silently shrink the supplied region.
3. Collect a short stable window of valid depth and gravity-referenced pose.
   Show which pixels/3D points are included, low-confidence exclusions and
   resulting left/center/right distances. Reject unstable or insufficient samples.
4. Use level floor and broad known targets to verify physical left/center/right.
   Verify a low obstacle is not removed merely because the floor is rejected.
5. The helper explicitly confirms the mount calibration. Save a versioned local
   profile: device/camera/orientation, ROI and coordinate conventions, neutral
   orientation, any floor/height model and its uncertainty, validity ranges,
   confirmation time and profile ID. Do not save raw video or exact location.
6. Changing the mount's angle requires repeating this wizard. Mark the profile
   invalid immediately when **Mount moved** is selected; old queues cannot rearm it.

A valid mount profile persists across ordinary app restarts and reloads automatically
when the mount is unchanged. Show its status and the Mount moved action; do not
require a routine confirmation or helper visit on every launch. When the user
reports changed/uncertain mounting, require the helper wizard. Camera/device/
orientation/profile incompatibility also invalidates it.
Do not require recalibration for every normal cane tilt or swing.

Important limitation: the phone cannot distinguish a phone slipping in its mount
from the user moving the whole cane using only its own IMU. Do not claim automatic
detection of every mount change. A mechanical index/secure mount and the explicit
recalibration action address that requirement. A separate cane IMU would be a
future option, not a prerequisite for this addition.

## Tilt compensation and floor exclusion

Use a gravity-referenced fused orientation, not integrated gyro alone. Prefer the
ARKit camera pose associated with the exact depth frame where it supplies the
needed gravity/world reference. If Core Motion is needed, synchronize its attitude
to frame timestamps and document the camera-to-device axis transform. Avoid two
independently drifting pose conventions or assuming receipt time equals capture.

Back-project selected depth pixels with the matching camera intrinsics, accounting
for depth resolution, portrait transform, cropping and mirroring. Apply the
calibrated neutral-to-current pitch/roll transform and select a consistent physical
detection region. Preserve left/right in the mounted cane/user frame; yaw must
not make cues point toward a fixed compass/world direction when the user turns.

Do not only slide a rectangle vertically as a universal floor correction. Use
the calibrated geometric selection and a supported floor/height rejection model
where available. A gyro measures rotation, not camera height; cane translation,
uneven ground and changed grip height need an uncertainty/validity envelope.
Begin with level-ground pitch/roll compensation. State that operating envelope
before attempting ramps, steps or arbitrary slopes. Keep low obstacles visible.

Draw the projection of the actual selected 3D region on the preview so the helper
can inspect it. At steeper/shallower tilt, out-of-view, inadequate pose/depth or
unsupported geometry means unavailable, not filled-in space. Never extrapolate
obstacles into the camera's unseen field. Do not lower confidence thresholds
simply to obtain a distance.

## Mac/iPhone work — do this first

1. Preserve local edits, fetch main and inspect the current Mac branch. At this
   audit, main was a253bf6; newer phone work was on
   origin/claim/CS-013-michaelkrymski at c34520b (PR #97). Do not reset that branch
   or revive the older Windows persistent-bond patch over the newer implementation.
2. Locate the actual yellow region and list its source files/transforms before
   changing it. Record the camera/depth geometry and existing stream/clock state.
3. Implement profile storage, wizard, invalidation and static calibrated ROI.
   Verify that calibration changes atomically clear old displayed/streamed values.
4. Add gravity-based pitch/roll compensation and a documented floor/height model.
   Use synthetic geometry tests for neutral/positive/negative pitch, roll,
   portrait transforms, bounds and low-obstacle retention before physical checks.
5. Reuse the existing native depth/clock transport. The phone performs geometry
   filtering locally and sends compact left/center/right summaries; no raw point
   cloud upload is needed. Preserve original capture timestamps and null distances.
6. Existing v1 messages have closed schemas. Do not append calibration fields
   ad hoc. Gate invalid calibration locally and send unknown/degraded using the
   current contract. If remote calibration metadata is required, coordinate a
   versioned contract update with the Windows receiver before emitting it.
7. Build/test with Xcode on the real LiDAR phone. Exercise Stop, background,
   tracking reset, reconnect, sensor loss and remount invalidation. Rebuild any
   world-referenced geometry after ARKit relocalization/reset; never reuse an old
   world anchor as if unchanged. Persist the mount profile, not stale world state.
8. Publish source, focused tests and a short handoff listing the exact branch/SHA,
   packet changes (if any), profile format and physical observations. No claim PR
   or second reviewer is necessary. Keep local signing and device keys private.

## Windows / Pi / server work — in parallel

Windows owns integration/testing here, not Xcode or duplicating the phone ROI code.

* **Git:** reconcile current main and the Mac's actual branch before a combined
  run. Work in another branch/worktree. Older task owner fields are informational.
* **Backend:** origin is https://64.177.50.116. On this audit TLS verified, certificate
  expiry was October 27 07:24:45 UTC, /healthz returned 200, /readyz 503, and GET on
  /v1/bonds/connect returned 405 (POST route present). A later readiness read timed
  out. Inspect the readiness JSON/host logs; do not declare the model broken or
  remove checks from the HTTP status alone. Ingestion may simply lack an active
  pair. Preserve the working identification/model configuration and renew TLS
  before expiry. Never bypass certificate verification to keep a demo connected.
* **Bonding:** reuse the accepted/deployed bond implementation (main PR #96;
  activation evidence PR #98). Use the existing phone-only and Pi-only credentials.
  Confirm same pair, source/boot identities, role separation and auto reconnect.
  The registry contains hashes; do not paste device tokens into logs or Git.
* **Pi camera/button ownership:** offline recorder must be disabled before the
  main agent owns camera/GPIO21. Do not run multiple uploader/motor processes.
  Read service definitions and the actual checkout first; do not assume old paths.
* **Clock/data:** collect current real phone packets and measured clock exchanges;
  use existing receiver gates and the Mac's measured uncertainty/drift work. Do
  not replace original capture times with network arrival or invent zero drift.
* **Haptics:** keep obstacle-side semantics and center priority. BCM18/physical12
  is left; BCM19/physical35 is right; active-high button BCM21/physical40. Inspect
  actual physical labels before use. Reuse accepted GPIO adapter, pulse caps,
  hysteresis, freshness gate and watchdog. Do not implement direction advice.
* **Tests:** software replay should cover calibrated/uncalibrated unknowns, each
  sector alone, center-plus-side priority, low confidence, replay/delay and
  reconnect. On hardware confirm channel labels and short off-bounded pulses.
* **Power:** repeat a representative camera/network/both-motor run on the actual
  power bank/cable. Save throttle/temperature evidence; previous short good runs
  do not establish a new mount/phone/agent combination's acceptance.

The server relays summaries and handles existing identification; it need not do
the iPhone's orientation compensation or fuse phone pixels with Pi YOLO boxes.
Keep those sources independent unless actual cross-camera calibration is added.

## Minimum joint acceptance sequence

1. Before calibration: app says calibration required; no LiDAR-driven motor pulses.
2. Helper completes neutral calibration: actual ROI matches the yellow overlay.
3. Broad targets left/center/right produce corresponding measured sectors and
   left/both/right pulses. User chooses movement; no turn instruction appears.
4. Empty level-floor view does not persistently trigger center; a low target in
   the claimed detection region remains detectable.
5. Repeat within the stated pitch/roll range and at its limits. No floor alert
   is hidden by erasing all low obstacles. Unsupported geometry becomes unknown.
6. Select Mount moved: motor eligibility and old observations clear immediately;
   the helper must recalibrate. Normal supported cane tilt does not invalidate it.
7. Stop/background/disconnect/reconnect: no old pulse resumes. Fresh data and the
   appropriate valid mount profile restore eligibility without re-pairing.

Record observed results, distances, mount/grip conditions, angle range and limits.
Do not label unknowns as no obstacle or claim drop-off/floor/boundary detection.
This plan adds obstacle information to normal cane technique, not a replacement.
