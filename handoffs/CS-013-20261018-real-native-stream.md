# CS-013 actual native phone depth streaming — local only

Base c34520b60e85d6cd4b5efe18c94659ee236208c4;
claim/CS-013-michaelkrymski. Existing local changes retained. Michael explicitly
requested real ARKit streaming and a measured rate, with phone left foregrounded.
No fetch/pull/push, GitHub contact, PR, credential generation or motor command.

Reused the phone's original device-only Keychain bond. Signed app was rebuilt,
strict signature verified, installed and launched with --stream-saved-phone and
--phone-connection-probe. Source is the normal real CameraController ARKit portrait
summary, not a fixture or injected distance. This launch explicitly opts into
diagnostic depth and starts the camera. It disables iOS idle sleep only while
streaming is active; background/disconnect still clear the opt-in and restore
normal sleep. No background streaming or automatic motor arming was added.

The previous motors-disarmed checkbox was renamed to stationary diagnostic
transport consent. Michael authorized use of the connected motors, which is not
evidence of a disarmed GPIO/power state. Software now records consent accurately;
it does not assert, control or verify the Pi's physical motor state. Old handoff
records describe the previous label/guard and are historical.

Added nonsecret device-only diagnostics: elapsed sender interval, fresh capture
count/span, maximum original-capture-to-local-loop delta, clock-guard failure flag,
completed clock-reply count, and foreground/camera status. No credentials, unique
IDs, raw boot times, depth values, image, GPS or private frames are saved in Git.
PhoneSendFence counts clock replies only after native send completes successfully;
a new synthetic test covers that counting across invalidation. Nine strict
package cases pass; final Apple SDK build/strict signature passes, repository
structure and diff whitespace checks pass. No new UI test relaunched/stopped the
stream after measurement.

Two device probe snapshots showed:
- elapsed interval 56.053906 seconds;
- completed native depth sends increased 55 -> 322, delta 267;
- measured sender rate 4.763272 Hz;
- fresh source capture count increased 58 -> 324, delta 266;
- measured source rate over its original capture span 4.753794 Hz;
- live portrait view, camera requested, foreground active, diagnostic depth
  enabled and WSS connected at both snapshots;
- no observed local clock-guard failure;
- maximum observed original capture to local-loop delta 276.447667 ms;
- zero completed clock replies observed.

The existing camera preview is capped near five Hz; the unchanged sender's ten-Hz
limit is a cap, not the observed rate. Counts measure successful phone native-send
completions, not Pi acknowledgements. The first submitted source sample can be
rejected at a readiness boundary; buffered send completion can straddle a probe
snapshot. Thus capture and send count deltas need not match exactly at endpoints.

Local capture/clock diagnostics stayed within the inherited 500 ms local-delta and
100 ms media-vs-continuous elapsed guards. These short observations do not prove
ARKit physical capture-time calibration, a general drift bound or Pi capture-age
eligibility. The phone's unknown eligibility flag is explicitly a lack of receiver
evidence, not an independently read Pi status. Zero completed clock replies cannot
be reported as a successful receiver clock exchange. Await Pi receipt/rate and
clock/capture-age diagnostics for end-to-end confirmation. No physical guidance,
all-clear, floor classification, motor mapping or electrical acceptance claim.

Evidence: tests/ios/evidence/CS-013-local-native-stream-20261018.json.
Raw sanitized snapshots/derived measurement remain in /tmp/canesight-stream-*.json.
Leave the phone foregrounded and streaming per Michael; do not run lifecycle tests,
relaunch it or regenerate credentials merely to collect more evidence. Switching
away or manually stopping capture can still invalidate/stop depth as designed.

Final device check before reporting (stream left running): {"status": "Paired \u00b7 WSS connected \u00b7 depth sends: 752", "foreground_active": true, "diagnostic_depth_enabled": true, "depth_sends": 752, "clock_replies_sent": 0, "local_clock_guard_failed": false, "capture_age_eligibility": "unknown", "drift_bounds_verified": false, "camera_status": "Live portrait view; repeat target check after remounting."}
