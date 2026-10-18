# CS-016 real phone/Pi transport checkpoint

Owner Michael; branch task/CS-016-michaelkrymski; draft PR #89.
Base/tested phone source: a5b666c1bfb8a195eeaef05efd335b6da8921e91.
Accepted main: a239e221b1d51d7673a78e8fb84e6df274b36e39.

Changed files: new sanitized native-paired evidence JSON, this handoff, a new
append-only changelog fragment, task runtime evidence/blocker, generated changelog.
No implementation or protected requirement changed in this checkpoint.

Actual physical iPhone test: xcodebuild test-without-building with the signed
CaneSightTransport device test product, selecting only
TelemetryDeviceTests/testNativeStartingHeartbeatAndReconnect. Direct Xcode result:
one passed, zero failed/skipped. Native transport recorded five starting
heartbeats, two connections and zero depth packets. Local result bundle:
/tmp/canesight-cs016-native-paired.xcresult (private local device metadata; not committed).

Michael manually ran the transport-only probe on his real Pi and reported its
final summary: starting_heartbeats_observed=5, connections=2,
strict_sequence_order=true, capture_age_eligibility=unknown, camera_used=false,
gpio_used=false, physical_guidance_verified=false. No automated Pi SSH was used;
Pi revision was not independently inspected. Phone-local writes alone do not
prove delivery; receiver evidence is the separately reported operator result.
See tests/ios/evidence/CS-016-native-paired-20261018.json for sanitized counters
and hashes of the unchanged phone test/probe source.

Default OS TLS and separate role credentials were used. The client remained
starting, used elapsed test time, and retained sequence state across same-process
reconnect. No ARKit depth was transmitted. This is no proof of real-depth 10 Hz
rate, depth backlog disposal, capture clock epoch/sleep behavior, justified
relative drift, fresh capture-age eligibility, haptic mapping or electrical safety.

Next steps: revoke the short-lived test pair through the backend operator;
remove private role files locally and on the Pi. The phone test consumed its own
credential file before starting. Do not reuse this process epoch in another run.
Keep PR draft/task blocked for the real-depth clock and freshness gates above.
Run checked publishing/shared repository checks for this evidence-only checkpoint;
inspect current-head CI after push. No physical test is rerun with consumed grants.
