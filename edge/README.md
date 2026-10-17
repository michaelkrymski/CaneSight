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
  every policy cycle. This module does not yet implement WSS, clock probes,
  model inference, haptics or system readiness.
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
  lineage. Hardware evidence so far: Michael reported ten 416-square in-memory
  captures around 10.7KB. This implementation has not yet run on his Pi.

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
