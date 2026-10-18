# CS-016 real-depth paired bench

Use only after publishing this harness and preparing the signed CaneSightTransport
scheme. No timed credentials are needed for build or local capture tests.
This is additional transport evidence, not guidance acceptance.

The phone selects only LiveDepthPairTests/testRealDepthPairPauseReconnect.
USB-deliver the existing nested phone-role JSON format documented in
PHONE_PI_TRANSPORT.md to Documents/cs016-depth-pair.json. It is consumed once.
A fresh reserved phone process source/boot and the actual running Pi process
source/boot must be enrolled in one live session (ttl_seconds=600). Deliver only
the relevant role grant to each operator. No credentials in chat, arguments,
environment, source control or output. Keep the operator key on the server.

On the Pi in this published review checkout, using its existing receiver venv:

```sh
~/.venvs/canesight-pr32/bin/python tests/ios/pi_phone_depth_probe.py \
  --session-file "$HOME/.canesight-depth-pair.json" \
  --phone-source-id RESERVED_PHONE_SOURCE \
  --phone-boot-id RESERVED_PHONE_BOOT
```

The command prints fresh process IDs and waits up to 300 seconds for a user-owned
mode-600 regular Pi-only six-field JSON, in the format in PHONE_PI_TRANSPORT.md.
Enroll those exact IDs; write the role file atomically. Restart/timeout requires
new process identity and fresh enrollment. Connect Pi first, then start the phone
test. Allow up to 90 seconds; on success paste only its final diagnostic summary.
Do not change existing camera/menu/haptic worktrees. No automated SSH runner.

Phone captures real ARKit frames, converts with the existing adapter, and
subtracts one fixed private media-clock origin from captures and clock readings.
Only elapsed intervals from test start leave the phone; original frame time is
never replaced by callback/send time. The local ContinuousClock comparison and
frame-to-callback bounds are runtime checks, not proof of oscillator drift or
sleep behavior. Test-only implementation; normal app streaming stays off.
Local producer ready requires a newly processed actual frame. Forty depth sends
per pass are requested. Pause stops capture/submission, suspends the client,
checks an empty pending slot and no new completed depth sends for 1.2 seconds;
resume requires fresh frames. Sequence/capture state survives same-client reconnect.
Native send completion alone is not receiver delivery.

Pi retains independent per-kind sequence and original-capture high-water marks
across reconnect. It reports source capture rate separately from receiver arrival
rate. Packets before a ready heartbeat are counted as transport diagnostics only.
At most four connection attempts; success requires two completed connections
with at least thirty depth packets each and at least two actual matched clock
replies. One random correlated probe at most every 1.1 seconds, one outstanding;
invalid/late/replayed replies fail. Report RTT and exchange interval width only.
No clock map is created and no zero/guessed drift is supplied to an eligibility
gate. Capture age remains unknown. No Pi camera, GPIO, policy or motor code runs.

Success does not establish exact 10 Hz delivery, capture-age eligibility, actual
lock/sleep behavior, forced delayed-network backlog disposal or physical mapping.
Keep those gates explicit. Revoke the pair and remove both private files after
testing. Record directly observed phone and operator-reported Pi evidence separately.
