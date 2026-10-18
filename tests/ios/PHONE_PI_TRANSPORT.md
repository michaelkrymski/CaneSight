# CS-016 manual phone/Pi transport test

Use the CS-016 review branch in a separate Pi worktree. Preserve existing camera,
receiver and menu checkouts. This test imports no GPIO driver and starts no camera,
model, policy or motor scheduler. Execute Pi commands manually; do not retry the
previously rejected automated SSH runner. Source/boot identifiers name this new
test process, not the machine's Linux boot.

On the Pi, using its existing receiver venv:

```sh
python tests/ios/pi_phone_transport_probe.py \
  --session-file "$HOME/.canesight-phone-pair.json" \
  --phone-source-id PHONE_SOURCE_FROM_OPERATOR \
  --phone-boot-id PHONE_BOOT_FROM_OPERATOR
```

The probe prints its new nonsecret source and boot IDs and waits up to 300 seconds.
Enroll those exact bindings with the phone's reserved new process epoch in a fresh
600-second live session. Do not use the earlier unconnected bench identity. Each
operator receives only its own role credential through a private file, never chat.

The Pi's user-owned, mode-600 file contains exactly:

```json
{
  "base_url": "https://64.177.50.116",
  "session_id": "SESSION_FROM_OPERATOR",
  "source_id": "SOURCE_PRINTED_BY_THIS_PI_PROCESS",
  "boot_id": "BOOT_PRINTED_BY_THIS_PI_PROCESS",
  "mode": "live",
  "token": "PI_ROLE_CREDENTIAL"
}
```

Write privately and atomically; no phone/operator token belongs on the Pi. If the
process exits or times out, obtain its new boot and reenroll instead of editing an
old boot into the file. The Pi follows default TLS verification and refuses
redirects. Only enrolled phone starting heartbeats with strictly increasing
sequences count; high-water state survives a same-process socket reconnect.
At most four connection attempts and 60 seconds of observation are allowed.
Output contains counters only, not frames, timestamps or credentials.

For the phone host, the private role file is:

```json
{
  "origin": "https://64.177.50.116",
  "session_id": "SAME_SESSION_FROM_OPERATOR",
  "mode": "live",
  "phone": {
    "source_id": "RESERVED_PHONE_SOURCE",
    "boot_id": "RESERVED_PHONE_BOOT",
    "token": "PHONE_ROLE_CREDENTIAL"
  },
  "pi": {
    "source_id": "ACTUAL_PI_PROBE_SOURCE",
    "boot_id": "ACTUAL_PI_PROBE_BOOT"
  }
}
```

Keep it under ignored `ios/CaneSightApp/secrets/cs016-phone-pair.json` on the Mac
with mode 600. Deliver to the signed app's Documents directory via the normal
developer USB file-copy API, not launch arguments/environment/logs. The device
test consumes/removes it before using it. Select only
`TelemetryDeviceTests.testNativeStartingHeartbeatAndReconnect` in the hosted
`CaneSightTransport` scheme; an unrelated full test run must not consume the grant.

The phone uses elapsed time since the test starts, never absolute system uptime,
and remains `starting`. It submits no ARKit sample and sends no depth packet.
Three completed heartbeat sends precede suspend/resume; two more exercise the
same process's retained sequence state. The Pi independently observes five
starting packets across reconnect. Closing/replacing either socket invalidates
the other; bounded retries are for this metadata-only test and never restore
source readiness. Revoke the pair after the run and remove private files.

Native send completion alone is not receiver delivery. Only the Pi's separate
counter output establishes receipt in this test. There is no clock map, justified
drift, capture-age eligibility, real sensor stream, camera inference, haptic or
electrical acceptance. `live` labels a real authenticated transport/session; it
does not label the source ready or authorize physical guidance.
