# Pi camera upload — CS-022

CS-023's separate software-only pulse scheduler and simulation are documented in
[HAPTICS.md](HAPTICS.md). It does not activate GPIO or integrate motor policy into
this uploader.

`python3 -m edge.uploader` captures the configured 640x480 RGB stream,
letterboxes to 416x416 (416x312 image, 52 black pixels top/bottom), encodes
quality-75 JPEG in RAM and schedules captures at a nominal 1 Hz. Slow capture
reduces the rate; it never schedules catch-up bursts. No images are written to disk.

## First run on the Pi (no backend credentials needed)

Use Raspberry Pi OS's Python, which can import the apt-installed Picamera2:

```sh
sudo apt update
sudo apt install -y git python3-picamera2 python3-pil
git clone --branch task/CS-022-latest-upload --single-branch https://github.com/michaelkrymski/CaneSight.git ~/CaneSight-CS022
cd ~/CaneSight-CS022
python3 -m edge.uploader --capture-only --frames 10
```

This branch is proposed work, pending review. If that destination already exists,
inspect its working tree before updating it. Do not overwrite an existing checkout.
Stop other camera programs before running. A venv without `--system-site-packages`
cannot normally see the apt-provided Picamera2/libcamera bindings.

Expect ten dimension/size/age lines. Missing/future capture timing or age above
1500ms produces an explicit dropped-frame line, never a fabricated timestamp.
Retain console evidence without credentials or private photographs. These logs
still do not prove live cloud latency or usable inference.

## Authenticated upload, after the session service is accepted and deployed

The accepted CS-028 skeleton alone has no operator enrollment API. CS-029 supplies
short-lived paired sessions. Do not disable backend authentication for integration.

1. On the Pi run:

   ```sh
   python3 -m edge.uploader --session-file ~/.canesight-session.json --frames 0
   ```

2. The process prints its nonsecret `source_id` and fresh `boot_id`, then waits up
   to 300 seconds. From a trusted operator machine enroll that exact Pi identity
   in a **live** paired session using CS-029. Keep the operator credential on that
   machine. Obtain the Pi's limited upload credential from the response.
3. Transfer only the following private configuration onto the Pi, outside Git:

   ```json
   {
     "base_url": "https://YOUR-BACKEND-HOST",
     "session_id": "SESSION-FROM-ENROLLMENT",
     "source_id": "pi-camera",
     "boot_id": "BOOT-PRINTED-BY-THIS-PROCESS",
     "mode": "live",
     "token": "PI-CREDENTIAL-FROM-ENROLLMENT"
   }
   ```

   Write through a private temporary file (`umask 077`) and atomically rename it
   to `~/.canesight-session.json`; permissions must be `600`. Never put credentials
   in chat, command-line arguments, PRs or screenshots. Do not include the phone
   or operator token. `base_url` is the HTTPS origin only, with no path/query.
4. The waiting process reads the matching file and starts uploads. Ctrl+C stops.
   Restart creates a new boot: revoke/replace the old session and reenroll. It
   deliberately will not reuse a previous process's credential/sequence epoch.
   An expired/revoked grant, sequence conflict, redirect or invalid ACK stops the
   sender and requires operator investigation. Ordinary network failures drop
   that frame permanently. For a private test CA use `--ca-file /path/to/ca.pem`;
   certificate verification stays enabled. No insecure HTTP mode is provided.

## Bounds and integration seams

- One pending JPEG replaced by newer captures; one sender holding at most one
  in-flight frame. No retry queue. Socket operations have a 2s timeout; DNS and
  a peer delivering tiny chunks can take longer. This is **not** a hard wall-clock
  network deadline. Capture continues with bounded queue storage. Exit discards
  pending work; a daemon sender is not a durable delivery mechanism.
- Drop pending frames older than 1500ms or apparently from the future before
  starting upload. A frame can expire during transport/inference. HTTP 202 means
  ingestion accepted, never fresh inference, readiness or crossing permission.
- `Sender.ledger` retains at most two `(original_metadata, Mapping)` records, no
  JPEGs. It is process-local and guarded by `Sender.lock`. CS-023/024 must consume
  it in the same process, match result lineage and enforce capture expiry on
  every policy cycle. The opt-in CS-024 receiver below integrates vision WSS
  and local capture expiry. Phone clock probes, haptics and overall system
  readiness remain unavailable.
- Uploaded metadata has the exact accepted v1 fields; capture time is not
  replaced with queue, encode, send or server time. `capture_utc` is unknown/null.
  Crop mapping stays local to avoid an unreviewed schema change.
- All camera/age timestamps use Linux **CLOCK_BOOTTIME**, including any future
  Pi clock replies. Do not mix them with `time.monotonic()` readings. The latter
  only schedules local sleeps here. `SensorTimestamp` is nanoseconds since boot;
  `ExposureTime` is microseconds. We subtract one exposure as a conservative
  older capture bound for driver variations. Validate the real device metadata
  before hardware acceptance. Reference: [libcamera controls](https://docs.libcamera.org/master/internal-api/namespacelibcamera_1_1controls.html).
- `Mapping.stream_box()` clips 416-pixel boxes to nonpadding content and reverses
  scale/offset into configured 640x480 stream pixels. `sensor_crop` preserves
  optional `ScalerCrop` metadata separately. This does not establish native sensor
  coverage, lens calibration, bearing, distance or phone/Pi alignment.
- Session identity/clock/ledger must be shared by the eventual single Pi agent;
  starting another process with the same source ID does not share its boot or
  lineage. Hardware evidence: the original handoff records Michael's ten in-memory
  captures. Subsequent manual Pi tests acknowledged 20/20 uploads and then
  accepted 20/20 matched vision results; see the CS-024 evidence below.

## Developer verification

Use backend test requirements (Pillow, FastAPI TestClient, schema validator):

```sh
python -m pip install -r backend/requirements-test.txt
python -m unittest discover -s tests/edge -v
```

Thirteen tests cover JPEG/mapping, sensor timing rejection, latest-only delivery
under a blocked sender, stale/future drops, no retry, auth stop, epoch binding,
HTTPS origin validation, redirect refusal, ACK identity and actual multipart
ingestion. Transport tests use mocks/in-process HTTP, not real TLS or camera.
Run this explicit test root: existing CI discovers shared/backend tests only.
Adding a required CI step is a separately reviewed protected workflow amendment.

## CS-024 receiver checkpoint: observation availability only

Install the accepted freshness-gate dependencies in a dedicated environment that
can see Raspberry Pi OS's Picamera2/libcamera packages. Do not install the ML
runtime on the Pi:

```sh
python3 -m venv --system-site-packages ~/.venvs/canesight-receiver
~/.venvs/canesight-receiver/bin/python -m pip install -r edge/requirements-receiver.txt
~/.venvs/canesight-receiver/bin/python -m edge.uploader --receive-vision --frames 20 --session-file ~/.canesight-session.json
```

Coordinate camera availability with Michael first. Preserve his existing checkout
and use a separate reviewed checkout for this checkpoint. The process prints a
new boot ID and waits 300 seconds. Enroll that exact active process with the
operator, transfer only the six-field Pi JSON privately and atomically, and verify
that `~/.canesight-session.json` belongs to the Pi user with mode `600`. Session
creation still requires a phone binding; an explicitly unconnected bench phone
counterpart is sufficient for a vision-only test. Never copy its credential or
the operator credential to the Pi. Old boot credentials cannot be reused.

The WSS connection must succeed before camera capture starts. The existing sender
records original capture metadata in its two-entry ledger and the accepted
`CaptureAgeGate` before HTTP upload. Both use CLOCK_BOOTTIME. Results must match
the original session/source/boot/mode/frame/sequence/timestamps/image dimensions;
unknown, consumed, evicted, future, replayed or stale lineage is unavailable.
The gate counts capture through upload/inference/return, with a 1500ms vision
budget. A separate loop calls expiry at a nominal 50ms interval even while socket
receive blocks. Python scheduling is not a certified real-time deadline.

`VisionReceiver.current()` returns a fresh copied observation and its original
stream mapping, or `None`; a consumer must call it again on every policy tick
rather than retain a snapshot. Only local-camera readiness is trusted here.
Phone data remains unavailable: the Pi-only file supplies no phone identity and
no measured phone clock drift/mapping. Empty detections and `signal: unknown`
never imply an obstacle-free route or crossing permission.

There is one socket, one bounded receive queue and no reconnect backlog. TLS and
hostname verification are required, credentials use a header, proxy discovery is
disabled for WSS, and redirects are refused. Disconnect, revocation, camera
failure, shutdown or clock reversal clears evidence. Restart and enroll a new
boot after WSS interruption. Cleanup closes the camera and invalidates the gate;
the existing bounded sender socket limitation remains as documented above.

The final line reports vision accepted/rejected/expired counts and unavailable
on exit without printing result contents or credentials. These are receiver
metrics, not motor readiness. Capture-only and ordinary upload commands retain
their existing behavior; `--receive-vision` is explicit and cannot combine with
`--capture-only`.

Tests: run `python -m unittest discover -s tests/edge -v` in the backend test
environment. Receiver tests include real certificate-verified local HTTPS/WSS
with synthetic backend observations, idle expiry and revocation of a fresh
result. They do not establish actual Pi timing, real detector performance,
phone connectivity or motor behavior. CS-023 scheduler/local hazard policy
integration remains outstanding. A manual Pi run at commit
17441cee512bb29ae6ad5bd327706a45c0a8f107 reported 20 acknowledged uploads
and 20 accepted vision results, with zero rejections, stale drops, failures or
queue replacements. See tests/edge/evidence/pr32-pi-receiver-20261017.json and
handoffs/CS-024-20261017-manual-pi-receiver-pass.md for evidence and limits.
Zero expirations in continuous fresh input does not independently validate idle expiry.

## CS-024 local policy

See [POLICY.md](POLICY.md) for the opt-in simulated policy, explicit trusted
phone binding, clock uncertainty gate, expiry tests and remaining physical gates.
`--simulate-policy` never uses GPIO; existing receiver-only behavior is preserved.

## CS-026 watchdog and restart

See [WATCHDOG.md](WATCHDOG.md) for the independent policy lease, local failure
demonstration, fresh enrollment after restart and uninstalled service example.
Software supervision cannot force a frozen GPIO or failed driver low.
