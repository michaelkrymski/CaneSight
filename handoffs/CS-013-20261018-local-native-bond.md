# CS-013 local native phone bond integration

Base c34520b60e85d6cd4b5efe18c94659ee236208c4; branch
claim/CS-013-michaelkrymski; Michael authorized local iPhone integration.
No GitHub contact, fetch, pull, push, PR, merge or remote review was performed.
This is an uncommitted local checkpoint, not accepted main or task Done.

## What was found

The normal app was a local preview. Earlier real transport came from explicit
CaneSightTransport tests using USB-delivered, single-use phone session files:
TelemetryDeviceTests.testNativeStartingHeartbeatAndReconnect and
LiveDepthPairTests.testRealDepthPairPauseReconnect. Tests deleted those files;
there was no durable phone bond reader or confirmed persistent Mac helper.
Other local worktrees were inspected without changing them. The CS-017 worktree
contains staged Apple test/checkpoint changes, not newer persistent phone code.

Michael subsequently supplied the location of the existing phone-bond.json in
Downloads. Its role/origin/schema were inspected without printing credentials;
its Mac permissions were restricted to its owner. The original enrollment was
reused, USB-delivered to the app and consumed into device-only unlocked Keychain
storage. No credential was generated, exported into logs, or added to Git.
The original private Mac file remains available to its owner.

## Local changes

- ios/PhonePairing: existing-schema phone bond validation, redacted diagnostics,
  bounded TLS POST to /v1/bonds/connect with redirects disabled, source/boot/peer
  validation, diagnostic elapsed epoch, synchronous depth-send invalidation gate.
- ios/CaneSightApp/Sources/PhoneConnection.swift: secure import/USB staging,
  native polling, saved-bond Connect/Disconnect, explicit diagnostic depth opt-in,
  existing TelemetryClient and original portrait captures, stale/unknown/background
  invalidation. No helper or Pi/GPIO API. Launch/probe options documented in README.
- AppServices.swift, ContentView.swift and project.pbxproj: native controller,
  separate Connection tab, local package linkage, updated camera permission text.
- HostUITests.swift: missing-bond disabled-depth UI check; explicitly compiled
  opt-in native pairing/depth bench, separate from routine nonnetwork UI tests.
- README, this handoff, new local changelog and task runtime evidence.

## Checks actually run

- Signed physical-iOS SDK build passed, app installed/launched on the connected
  iPhone 17 Pro Max / iOS 26.6.2. Xcode project opened locally.
- Eight strict-concurrency PhonePairing package tests passed: credential role/
  origin/shape, private header/redaction, waiting vs paired, source/boot/peer,
  elapsed-age preservation, permanent jump/stale failure, permission/ended gate.
- Existing Telemetry package: 23 tests, zero failures, two native-loopback cases
  skipped by that package's existing configuration (21 cases passed).
- Actual signed phone missing-bond UI test passed without skips after moving the
  controls from a lazy off-screen section to their own Connection tab. First
  UI attempt failed because the test waited for an off-screen lazy row; that
  attempt is not a pass. /tmp/canesight-local-pairing-ui-v2.xcresult.
- Actual iPhone default-TLS /healthz test passed without skip.
- First sensor test failed: zero processed depth frames in each run. After Michael
  positioned the phone portrait with cameras facing a room, the unchanged native
  test passed without skip: 30 actual processed frames per run, two pause/restart
  runs. Observed candidate callback deltas remained below 46 ms in this short run;
  these are observations, not capture-age/drift bounds or physical accuracy.
  /tmp/canesight-local-sensor-positioned.xcresult.
- Native saved-bond UI attempt authenticated the phone and displayed exactly
  "Phone authenticated · waiting for Pi" for its 40-second window. The WSS
  expectation therefore failed; no successful paired WSS or depth delivery was
  inferred. /tmp/canesight-local-native-bond.xcresult.
- Structural validator and git diff --check passed. Additional latest status and
  checks, if any, are recorded below before ending the session.

## Limits and next step

Pairing alone is not depth readiness. The phone diagnostic epoch reuses prior
bench assumptions; sensor uncertainty, Pi capture-age bounds and drift remain
unverified. No receiver mapping or eligibility was enabled. The unchanged preview
producer is about five Hz, while the sender cap remains ten Hz; no hard ten-Hz
claim. Existing status speech/lifecycle display does not announce verified network
or guidance readiness from this connection.

Both clients must poll the same persistent bond within the backend's 20-second
presence window. Resume the Pi's existing persistent client using its original
Pi-only credential; do not generate enrollment. Verify WSS, real depth send counts
and separately Pi receipt. Confirm outputs are disarmed for the transport bench;
the app's checkbox is not a remote disarm command or evidence of GPIO state.
Michael reported working connected motors and likely disarmed, then permitted
using them; no physical disarm or running Pi policy state was independently
verified. Diagnostic depth was therefore left off while pairing was investigated.
No motor command, arming, crossing permission, all-clear or physical guidance
claim was made. Actual paired background/lock expiry remains unverified here.

## Latest local checkpoint

The final signed app build and strict signature verification passed and the app
was installed/launched normally with --connect-saved-phone and the sanitized
status probe. Existing Keychain enrollment survived rebuild/install and was
reused. A subsequent phone request reported network timeout -1001. Independent
Mac /healthz attempt could not connect to TCP 443 within three seconds (curl 28,
HTTP 000), after the earlier native phone health pass and accepted bond poll.
This is current backend reachability failure, not evidence of invalid credentials.
The native controller now retries transient network failures while foreground,
cancelling/suspending depth transport during that failure; it retains the bond
and all in-session sequence high-water marks. Default TLS verification is intact.
Package tests remain eight passed; repository validator and diff whitespace check
passed. No actual paired WSS or depth send was observed in this session.
The current device-only probe is read back below for the final status.

Final sanitized device status: {"status": "Backend unavailable (network code -1001) \u00b7 retrying", "wss_connected": false, "depth_sends": 0, "diagnostic_depth_enabled": false, "connection_requested": true, "capture_age_eligibility": "unknown", "drift_bounds_verified": false}

## Backend-restored phone retry

Michael reported backend restored and matching Pi actively polling. Relaunched
the installed app with its existing Keychain phone bond and no depth opt-in.
Two sanitized device status reads, separated by more than the ten-second bond
renewal interval, both reported paired WSS connected with zero depth sends.
No credential generation, GitHub contact, motor command or drift claim. Latest:
{"status": "Paired \u00b7 WSS connected \u00b7 depth sends: 0", "wss_connected": true, "depth_sends": 0, "diagnostic_depth_enabled": false, "connection_requested": true, "capture_age_eligibility": "unknown", "drift_bounds_verified": false}
