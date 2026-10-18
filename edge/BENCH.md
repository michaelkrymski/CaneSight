# CS-025 depth integration and private capture-age evidence

This checkpoint prepares repeatable **software** integration. It does not satisfy
CS-025's real-phone/physical-motor acceptance: outputs are simulated and actual
phone data, mount mapping and power verification remain pending.

## Local synthetic runner

Create a private parent directory first (0700 on Linux or user-only ACL on Windows).
Choose a new output file outside the checkout; existing files are never overwritten.

```sh
python -m edge.bench --simulate --repetitions 3 --output /PRIVATE/new-bench.jsonl
```

The runner needs no Pi, camera, network, credentials or GPIO. It uses an explicitly
synthetic replay session, same-clock fixture calibration and virtual time. Three
rounds repeat left, center and right stimuli through the accepted capture gate,
policy, scheduler and watchdog. Each sector recovers from distinct covered frames,
accepted channels are checked, and idle capture expiry cannot retrigger pulses.
The JSON summary always identifies synthetic input, simulated output and false
physical acceptance. Zero drift and virtual timing are fixture choices, not phone
measurements. Values must never be represented as measured physical latency.

## Private session trace (future coordinated Pi run)

After Michael confirms camera availability and the hardware/phone prerequisites,
use a separate reviewed checkout/environment and the manual enrollment procedure
from POLICY.md. Obtain a new uploader boot ID, create a fresh 600-second session,
and privately install matching Pi-only JSON with user ownership and permissions
0600. Do not retry the rejected automated SSH runner. The uploader waits only
300 seconds, so coordinate the private transfer before starting it.

Add these flags to the existing receiver/policy command:

```sh
python -m edge.uploader --receive-vision --simulate-policy --frames 20 \
  --session-file ~/.canesight-session.json \
  --phone-binding-file /PRIVATE/phone-binding.json \
  --policy-trace /PRIVATE/new-policy.jsonl
```

This still uses **simulated outputs**. The trusted phone source/boot must match
operator enrollment, and the joint drift budget needs measured support. Null drift
keeps ages unknown/unavailable; do not set zero merely to make a test pass. The
phone app must answer native clock probes and stream valid bounded depth/heartbeat
messages. No phone/operator token belongs on the Pi or in the trace. No such run
was performed for this checkpoint, and no Pi/camera was accessed.

Each admitted fresh depth sequence logs only whitelisted metadata: session/source/
boot/sequence/mode, original capture time, original receipt time and deadline,
software command-observation time, capture-age interval, sector classification,
requested channels, accepted/rejected result and reason. Source UTC, GPS, raw
images, distances, detection bodies, URLs and credentials are not logged. Enrolled
session input and simulated output have separate labels; `live` mode does not
mean a real motor moved or that a physical sensor was verified.

`software_command_observed_ms` is read **after** the software pulse decision; its
capture-age interval retains the original calibrated capture mapping and includes
elapsed processing. It is not physical motor onset or independently measured
end-to-end latency. Original receipt/deadline fields allow old-at-receipt data to
be distinguished from fresh evidence. Rejected/malformed packets are not written
as admitted depth; the receiver's counters remain the separate rejection evidence.
Health packets/ticks never create additional decision records for a saved sequence.

The writer has a 64-record queue, at most 1,024 submitted records, <=2,048 UTF-8
bytes per record (<=2 MiB payload per run). It runs separately from policy/scheduler
workers. Queue saturation drops records; disk errors mark the trace incomplete.
Shutdown drains for up to two seconds. The sanitized summary must show complete
true, dropped zero, error false and submitted=written before treating it as a
complete capture. No-record, dropped, failed or unfinished writes are incomplete.
Logging cannot renew data, grant motor readiness or block expiry. Output mode is
0600 on Linux; verify the private parent ACL on Windows. Keep files out of Git,
chat and issue trackers. Share only sanitized counts/results as needed.

## Remaining acceptance evidence from Michael

- CS-016 real-phone depth/heartbeat and native clock-response support, with actual
  source/boot enrollment and measured joint drift/calibration uncertainty.
- CS-015 verified phone orientation/mount and physical left/center/right mapping.
- CS-010 selected-rail current, voltage/thermal and camera-load evidence, plus
  required driver/diode/kill verification. The opt-in CS-023 GPIO adapter and
  CS-025 policy wiring are described in POLICY.md; no physical run is claimed.
- Coordinated real-phone/Pi test on the exact new commit; record repeated stimuli,
  capture-age intervals, failures and actual output mode. Physical onset requires
  separate measured evidence, not these software decision timestamps.

Do not energize motors or mark real-phone acceptance complete from synthetic logs.
Silence and absence of detections never mean clear or permission to cross. The
watchdog's frozen-GPIO/OS/driver limitations remain; see WATCHDOG.md.

## Verification

```sh
python -m unittest discover -s tests/edge -v
python -m unittest discover -s tests -v
```

Tests cover repeated mapping, original age bounds and expiry, private/new output,
closed fields, invalid numbers, bounded blocked-disk behavior and write failure.
The native TLS synthetic-phone relay test also verifies capture-age tracing and
credential exclusion. This is automated software evidence, not real-phone data.

## CS-025 configured GPIO path

The same uploader now has an explicit `--gpio-policy` alternative to
`--simulate-policy`. It connects the existing native receiver, final-consumer
capture-age gate, local policy, independent watchdog and GPIO adapter in one
process. Session/source/boot/sequence and the phone wire contract are unchanged;
CS-016 does not need a separate backend protocol for this output path.

Follow POLICY.md for the reviewed pin/binding configuration. GPIO trace records
and summaries say `output_mode: gpio`, while existing synthetic runs retain
`output_mode: simulation`. Both record software command decisions rather than
measured motor onset. A GPIO label identifies the configured adapter, not proof
of actual voltage, motion, calibration or electrical readiness. The new automated
GPIO tests inject fake pin devices and synthetic phone messages; none opens GPIO.
