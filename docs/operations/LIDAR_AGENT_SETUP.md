# Calibrated LiDAR integration — implementation candidate, November 4, 2026

Michael requested implementation without automated tests, with combined manual
testing deferred to the end. No tests were added or run for this change; no Pi,
motor, server deployment or Xcode build was executed. Only source/parser and
git whitespace inspection is performed. Treat the new integration as unverified.

This branch includes the Mac's already published `codex/mac-lidar-calibration`
through de923be, preserving its profile/ROI/pose work. Michael later changed the
tiny yellow patch to a full-width left/middle/right detection band on the Mac;
this integration preserves that actual decision and does not recreate the ROI.

## What is implemented

`python -m edge.lidar_agent` is one exclusive Pi peer with an existing saved bond.
It reconnects and builds a fresh phone binding and capture-age gate from the
authenticated peer's boot/source IDs. It renews the transport lease independently
of camera capture. Depth-only mode needs neither a Pi camera nor YOLO/model readiness.
It receives original-time phone depth and clock replies, uses the existing local
policy/watchdog/scheduler/GPIO adapter, and prints current eligibility and sectors.

Left obstacle -> left BCM18; center -> both; right -> right BCM19. Never an
opposite-side recommendation. The user chooses movement with a conventional cane.
Default near/release thresholds remain 1.2/1.5 m, coverage .5, two fresh recovery
frames, pulse 100 ms. Agent limits tighten the existing scheduler to <=150 ms per
pulse, >=850 ms off and <=1000 ms on/channel/10 s. All are prototype settings.

`--with-camera` additionally captures/uploads Pi images through the SAME session,
sender ledger and native socket. It does not open a second Pi-role client. Camera
failure removes vision readiness; depth has no camera dependency. This does not
replace or retrain identification models or change the backend's model settings.
`--context-button --context-consent` optionally adds existing BCM21 scene request/
cancel, and `--context-audio` uses the existing current-user speaker route. No new
speaker pairing, route monitor bypass, provider configuration or crossing menu.

PhoneConnection now retries transient network/socket and session-rotation failures
while the phone remains foregrounded and the user still requested connection.
Old sockets and source clocks are discarded; explicit disconnect/background/clock
failure do not replay samples or silently reinstate sharing. Fatal authorization
rejection retains the bond but requires operator action. Swift changes require
a Mac build; they have NOT been compiled here.

## Existing prerequisites that remain explicit

* Use the existing phone/Pi bond files; do not provision a different registry.
  The Pi file is normally ~/.config/canesight/pi-bond.json, mode 0600.
* Phone must have a valid helper-confirmed mount profile and be foregrounded,
  camera running, connected and explicitly sharing the calibrated depth stream.
  Mount moved invalidates profile/stream. Unsupported geometry stays unknown.
* Production capture-age eligibility needs a justified supported-operation joint
  clock-drift bound. No such general bound was accepted in the old evidence.
  The Oct 18 candidate 1518.614 ppm was conditional on one run and must NOT be
  copied as a permanent verified bound. No zero/default drift is invented here.
* Without --relative-drift-ppm, monitoring/pairing/clock diagnostics work, but
  accepted depth/pulses remain unavailable. Status explicitly says
  clock_drift_budget_not_configured. --gpio requires a positive explicit bound.
  A new qualification/clock-characterization step remains part of final testing.
* There can be only ONE Pi-role bond poller/socket. Stop old uploader, clock probe,
  offline recorder and any duplicate agent before using this process. The new
  agent has a same-user instance lock, but old programs do not use that lock.
* This remains networked phone -> backend -> Pi. The offline video recorder was
  offline; this live feature needs reachable HTTPS/WSS and a valid certificate.

## Copy from Windows (no tests are run)

From a clean committed checkout of this integration branch:

```powershell
.\scripts\copy_lidar_to_pi.ps1 -PiAddress interfere@192.168.0.32 -Install
```

Use the Pi's current SSH address if DHCP changed. It prompts for your existing
SSH/sudo passwords, copies a versioned git archive, creates a Python environment
using system packages, installs pinned backend/client dependencies and installs
the service definition. It does not overwrite another checkout, copy credentials,
run tests, enable/start the service or claim any hardware result. The new runtime
uses no torch/YOLO installation on the Pi. For --with-camera or real GPIO, the Pi
OS must already have picamera2/gpiozero as in the earlier working setup.

Installer default config is simulation, no drift, no camera/audio. Existing
~/.config/canesight/lidar-agent.json is preserved on later installs. It references
the existing private bond file; installer does not create enrollment credentials.
The service name is canesight-lidar.service. Its working directory points to the
new versioned release. Installation alone has not started a hardware process.

## Final combined manual session — run when ready to test

On Mac: preserve local changes and incorporate this branch, then prepare pinned
dependencies using ios/CaneSightApp/prepare_review_dependencies.py and build the
existing CaneSight project/scheme with your existing signing. Do not overwrite
local profiles, Keychain enrollment or signing files. Confirm calibration/start/
connection and opt-in depth sharing in the app. This Windows code does not invent
or auto-confirm a mount profile on your behalf.

On Pi, first free exclusive ownership:

```bash
sudo systemctl disable --now canesight-recorder.service
pgrep -af 'edge.uploader|pi_bond_clock_probe|lidar_agent'
```

Stop those other peers using their own terminal/service; do not indiscriminately
kill every Python process. Change to the printed release directory. Pair/monitor:

```bash
~/.config/canesight/lidar-venv/bin/python -m edge.lidar_agent \
  --bond-file ~/.config/canesight/pi-bond.json \
  --status-file ~/.config/canesight/lidar-status.json
```

No GPIO is opened. Status separates raw arrivals from accepted/fresh observations.
last_raw_sectors are DEBUG ONLY, with receipt age; only sectors/age_interval_ms
from the current capture-age gate can reach the motor policy. Received depth alone
does not mean eligible depth. Unknown clock configuration is expected until the
clock bound is qualified. Always stop this foreground process before a service run.

After establishing the actual supported clock bound, replace MEASURED_PPM with
that numeric value, NOT a guessed/historical constant, to first inspect simulated
obstacle decisions and then physically enable motors:

```bash
~/.config/canesight/lidar-venv/bin/python -m edge.lidar_agent \
  --bond-file ~/.config/canesight/pi-bond.json \
  --relative-drift-ppm MEASURED_PPM --gpio
```

For combined vision, add --with-camera. Optional current scene-button/audio path:
--with-camera --context-button --context-consent --context-audio. This reuses the
existing restricted context implementation. It remains separately dependent on
provider settings, actual speaker routing and primary-source readiness.

Minimum one-session checks: neutral view, target left/center/right, low target,
supported tilt, Mount moved, Stop/background, temporary network loss/recovery,
power-bank load, and motor off after stop. End an output fault with the physical
power disconnect if necessary; software cannot force a frozen GPIO low.

## Saved service configuration and startup

Edit ~/.config/canesight/lidar-agent.json with ordinary JSON. It contains no token.
Set relative_drift_ppm only after clock qualification, then gpio=true to explicitly
request real motors. with_camera/context switches are optional and default false.
Relative bond_file/status_file paths resolve within the config folder. Keep
calibration on the phone; do not append new fields to closed sensor schemas.

```bash
sudo systemctl enable --now canesight-lidar.service
journalctl -u canesight-lidar.service -f
cat ~/.config/canesight/lidar-status.json
```

The service retries ordinary process failure at most three times in two minutes;
the agent independently recovers ordinary connection loss. Incomplete cleanup
stops rather than reopening hardware over an old worker. After correcting a fatal
configuration/output fault: sudo systemctl reset-failed canesight-lidar.service,
then sudo systemctl restart canesight-lidar.service.

The optional system-service speech route may need the user's audio session kept
running (loginctl enable-linger and appropriate user PipeWire session). Verify the
existing speaker setup; no audio-service/linger settings are changed by installer.
Haptic/depth-only operation does not need Bluetooth or a login audio session.

Rollback: sudo systemctl disable --now canesight-lidar.service, restore the prior
explicit runtime/service checkout, and re-pair automatically with the existing
saved credentials. Do not run both Pi peers simultaneously. No server image,
registry, certificate or current identification configuration was deployed here.
