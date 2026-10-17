# Capture-age policy and event consumer — CS-030

`backend.freshness.CaptureAgeGate` implements the stateful receiving-side policy
for the accepted shared v1 messages. `backend.events_client.PairedEventsClient`
connects that policy to CS-029's certificate-verified native Pi WSS route. No
wire fields, schemas, master-plan budgets or server enrollment rules change.

## Which clock owns the decision

The gate must run on the **final consumer's local monotonic clock**. For the Pi
that is the process recording original camera capture metadata and receiving
results. A backend receipt timestamp is not a Pi capture timestamp. The session
server still relays the original messages unchanged and never stamps them fresh.
This implementation does not add a misleading server-to-Pi freshness assertion.

The convenience `CaptureAgeGate.for_pair(pair)` binds the Pi camera source and
receiver to the same enrolled process boot/clock. If capture and consumption are
split into independently restarting processes, integrate their lifecycle first;
do not share a reusable boot ID across them or assume this convenience binding
provides cross-process calibration. Any receiver clock reset requires a new
consumer/session epoch. An ordinary packet cannot enroll itself or reset a boot.

## Phone depth and health

Use the authenticated operator session response from `POST /v1/sessions` to
construct `PairedEventsClient(wss_origin, pair, relative_drift_ppm=verified_budget)`.
Do not log the response or credentials. WSS certificate and hostname validation
are required; URL credentials/queries, insecure WS and disabled TLS validation
are rejected. Proxy environment variables are not used by this native client.

`relative_drift_ppm` defaults to **None**. Until the actual joint source/consumer
clock-drift budget is justified, remote depth/health remain unavailable. Tests
use explicitly artificial zero/200 ppm assumptions; they do not measure a phone
or Pi oscillator. Do not silently substitute a guessed live drift budget.

Inside `async with client.connection()`, call `await client.probe(phone_source_id)`
and keep `await client.receive_once()` running in a receiving task. The Pi makes
its own random nonce and records its local t1; the phone returns its t2/t3 through
the existing session relay; `finish_probe` records local t4 and consumes the
matching pending nonce once. Maximum exchange duration is 1000 ms, maximum one
probe/second/source, maximum one outstanding/source. Identity, epoch, mode,
session, nonce and echoed t1 must match. Invalid/late correlated replies remove
the mapping and observations. No UTC or heartbeat fallback exists.

Clock offsets use `[t3-t4, t2-t1]`, widened for configured joint drift through the
exchange and every later age calculation. The mapping expires after 10 seconds.
Depth/health half-width must be <=100 ms; capture age must have a nonnegative
lower bound and conservative upper bound <=500 ms (depth) or <=2500 ms (health).
Captures must unambiguously postdate calibration and readiness/recovery. Wider,
future, stale, nonfinite, implausibly huge or unbounded values are unavailable;
the gate never clamps future age to zero.

`receive_once()` returns an `Observation` only when an actual sensor observation
is eligible; clock control, heartbeat, rejected or unknown-depth packets return
None. A fresh `ready` heartbeat establishes bounded connection health only. It
does not turn unknown sectors into distances or extend a depth/vision deadline.
Degraded, starting, missing and expired health cannot sustain stored guidance.
Recovery requires a ready heartbeat followed by newly captured valid data.

## Independent local expiry

An independent local policy tick must call `gate.expire()` and/or
`gate.current(source_id, kind)` even when receive/inference is blocked. Each
lookup checks the fixed original deadline and recomputes conservative age using
the observation's **original clock bound**, including additional drift. A new
clock synchronization cannot extend an existing observation. Refreshing heartbeat
cannot extend it either. No incoming packet is needed to expire a stored value.

None, `Unavailable`, or invalid tracking means unknown/unavailable, never clear
space. The gate contains no motor commands, safe-to-cross field or movement
permission. Consumers must not cache a returned snapshot past subsequent policy
ticks. Returned snapshots are copied; changing one cannot mutate internal state.

On transport interruption, `interrupt()` clears observations, clock mappings,
pending probes and pending frame records while retaining sequence and consumed
frame-ID history. A new calibration and new captures are required after recovery.
The WSS adapter calls it automatically on disconnect/context exit. On an invalid
or reversed receiver clock, the gate clears evidence and remains unavailable;
restoring the numeric clock does not recover the old receiver epoch.

## Originating-Pi vision lineage

Before uploading a frame, establish actual local-camera health with
`gate.set_local_ready(True)` and call `gate.record_frame(original_metadata)`.
This is a trusted camera adapter operation, not a response to a server heartbeat.
Default local readiness is False. The same metadata/capture time must be sent in
the CS-028 upload. The 202 frame acknowledgment is not a vision observation.

Record at most two pending originals; newer work evicts superseded requests.
Frame IDs and frame sequences cannot be reused within an epoch (history capped
at 4096 IDs; create a new authorized session at that bound). Missing, expired,
consumed and superseded ledger entries cannot be reconstructed from server echoes.

When an authenticated backend vision event arrives, `gate.receive(result)` must
match original frame ID, source/boot, sequence, session/mode, capture monotonic and
UTC values and image dimensions against the trusted ledger. Compute age from the
originating consumer's own capture clock to now, including upload, queue,
inference and return delay. The upper bound must be <=1500 ms. Processing duration
or receipt time cannot replace original capture time. Consume a matching request
once and retain a fixed expiry; a late result never becomes fresh on arrival.

Local-camera faults clear pending work/observations; recovery requires a new
local capture. Unknown signal/detection content stays unknown even when its age
is valid. Actual inference generation/publication remains CS-031/035 integration
work; this PR does not invent a live model response.

## Bounds, tests and integration limits

State is locked across consumers and bounded: shared SequenceGate identity/epoch
limits, one clock map/probe/health record per enrolled source, one observation
per source/type, two pending local frames and 4096 seen frame IDs. Session objects
are not transferable to a different session/receiver clock. Reconnect does not
erase high-water marks; trusted authorized source reboot purges mappings and
observations and retires the old boot.

Run `python -m unittest discover -s tests/backend -v` and the shared test root.
Freshness tests inject asymmetric offsets, excessive uncertainty, drifting/expired
maps, stale/future capture, replay/reorder/wrong identities, health recovery,
unknown depth, clock resets, altered frame provenance, superseded/consumed requests
and deadline boundaries. The existing real TLS test now also runs the actual WSS
consumer through probe/reply, ready heartbeat, fresh depth and stale rejection.

These are software fixtures and a loopback TLS rehearsal. Live drift measurements,
actual phone/Pi use, edge-policy/motor integration and hardware acceptance remain
unverified. CS-024 must integrate the gate's semantics into the final independent
edge policy loop; no file under edge/ is changed in this backend-scoped task.
