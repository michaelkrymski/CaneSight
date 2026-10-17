# CaneSight protocol v1 — CS-003

Status: **proposed freeze; accepted only after the protected-contract PR is reviewed and merged**. This implements master-plan section 6.5 without changing its age limits or safety invariants. Michael is the contract owner. Adit's CS-028, phone telemetry, Pi transport and vision adapters should use this version after acceptance. They may prepare mocks against this draft meanwhile, clearly identifying it as proposed.

## Start here

- `messages.schema.json`: JSON Schema Draft 2020-12, closed objects, bounded collections, required fields and explicit nullable values.
- `examples/`: six artificial **replay** packets. No live measurements or real device verification are implied. Do not silently change replay to live for demonstrations.
- `reference.py`: executable shape/semantic validation, sequence gate, conservative clock-age calculation and original-Pi-frame lineage check. This is a conformance reference, not a complete transport, authentication implementation, sensor policy or motor controller.
- Tests: install `tests/contracts/requirements.txt`, then run `python -m unittest discover -s tests -v`. CI runs the same contract cases on Python 3.12; the contract subdirectory is a discovery package.

## Message types and transport bindings

| Type | Producer/provenance | Transport | Consumer |
|---|---|---|---|
| `depth_observation` | Enrolled phone depth source | Phone → `/v1/telemetry`, relay unchanged → `/v1/events` | Pi policy; dashboard |
| `frame_metadata` | Enrolled Pi camera source | `/v1/frames` multipart fields `metadata` (UTF-8 JSON) and `image` (JPEG) | Backend |
| `vision_observation` | Backend result preserving the original camera provenance | Backend → `/v1/events` | Originating Pi; dashboard |
| `heartbeat` | Enrolled phone/Pi source | Its authenticated WebSocket; relayed where authorized | Session health |
| `clock_probe` / `clock_reply` | Receiver starts probe; identified source replies | Existing paired-session WebSockets, routed by backend | Probing receiver |

Use the master plan's `/v1/sessions` enrollment/authentication and HTTPS/WSS routes. Endpoint authentication, token issuance, rate limiting, model readiness, actual image decoding and backend implementation remain CS-028/029/032/vision work. The CS-003 schema must not be mistaken for completion of those tasks. No public device IDs or session IDs confer authorization.

For CS-028: parse metadata strictly; authenticate the source and role; enforce the enrolled session/mode/boot; check sequence; decode JPEG safely; require actual bytes and decoded dimensions to match metadata; record original capture metadata and frame ID before enqueueing latest-frame work. Return HTTP 202 JSON `{ "schema_version": 1, "frame_id": "<same frame_id>", "status": "accepted" }` only after those checks. This is ingestion acknowledgment, not an inference or freshness verdict. The later vision event preserves `frame_id`, source/boot, frame sequence, original timestamps, mode and image dimensions. Do not accept server-selected replacement capture times.

Recommended adapter rejections: 401 missing/invalid credentials; 403 wrong session/source/role; 413 oversize; 422 malformed fields/image metadata; 409 duplicate/old epoch/sequence/frame ID. Never reflect secrets or image bytes in errors. Backend may map WebSocket rejection to bounded error/close responses; error transport envelopes are not motor observations.

All JSON frames are at most **8192 UTF-8 bytes** (including whitespace); JPEG is a separate part, at most **1,000,000 bytes**, decoded width ≤1920 and height ≤1080. Endpoint must additionally cap total multipart body/overhead, decompression memory and parse depth before materializing arbitrary input. Targets: phone depth ≤10 Hz; Pi frame ≤1 Hz. Vision detections ≤32 and signal candidates ≤32. Schema bounds supplement these transport limits. Reject unknown fields/types/versions, duplicate JSON keys, NaN/Infinity/overflow and nonfinite numbers. UTC strings must be UTC `Z` format or `null`; UTC is diagnostic only.

## Common sensor envelope and identity

Every sensor/heartbeat packet requires `schema_version: 1`, `type`, `session_id`, `source_id`, `boot_id`, `seq`, `capture_monotonic_ms`, `capture_utc`, `mode`. IDs are opaque, case-sensitive ASCII letters/digits/underscore/hyphen, length 1–64. Production source/boot/frame/nonce IDs should be random UUID-style values, not user identities. Sequence is an integer 0…2^53−1, never a Boolean; rotate to an authorized new epoch before overflow. All times are nonnegative finite **milliseconds**, distances metres, fractions/confidence 0…1.

- `source_id` names an enrolled **sensor process stream**, not the sender's network connection. Do not use one source/boot ID for two independently restarted camera/depth processes.
- `boot_id` is a new random epoch on source process restart or capture-clock reset. It is not a reusable hardware ID. Backend authenticates the epoch binding through session enrollment. A packet cannot authorize its own new boot.
- Sequence increases independently for each `(session_id, source_id, boot_id, type)`. Gaps are permitted, duplicates/decreases rejected. A vision result's sequence equals its original frame's sequence; frame and vision are distinct types so the same number is intentional. A source has one writer per type. Reconnect with the same boot preserves sequence high-water marks.
- The backend is permitted to publish a vision result with the enrolled camera provenance only after matching a recorded accepted frame; a phone must not impersonate that role. Pi likewise verifies the authenticated backend connection and pending original frame.
- On authorized boot replacement, atomically clear that source's stored observations, pending jobs/results, capture ledger and clock mappings before readiness; retire its old boot and reset its type-specific sequence state. Late old-boot messages stay rejected. An ordinary observation/heartbeat must never implicitly reenroll a source.
- Closing/replacing a session invalidates all its mappings, identity/sequence state and observations. Live and replay are different enrolled sessions/modes; mixed packets are rejected. An old replay stream cannot become live by changing one packet field.

The reference SequenceGate bounds enrolled sources to 16 and retired epochs to 128 per session. At that bound create a new authorized session. Enrollment calls are trusted adapter actions, not wire messages. The gate checks ordering/shape only; callers must also enforce authorization, finite clock bounds, lineage and observation semantics before making data eligible for local policy.

## Values and unknown states

Depth requires all three source-camera sectors `left`, `center`, `right`, a `tracking` enum (`normal`, `limited`, `unavailable`) and sector `{distance_m, valid_fraction}`. Missing/invalid distance is **null**, never 0, a large sentinel or a carried-forward old distance. `valid_fraction` remains a measured fraction even when distance is null. A nonnull distance requires tracking normal and some valid samples. Low-sample/occlusion thresholds remain the sensor algorithm's responsibility; a schema-valid distance alone is not reliable obstacle evidence. Non-normal tracking requires null distances in all sectors. Sectors are source camera coordinates, not fused world geometry or motion commands.

Vision requires the original frame ID/image/capture metadata, nonempty model version, processing duration, detections and a `signal` object. Boxes are normalized source-image `[x_min,y_min,x_max,y_max]`, finite 0…1 with positive area. The inference adapter maps unsupported labels to `other`, never inventing classes. Empty detections mean **no reported detections in this frame**, not a clear path. `processing_ms` is backend diagnostics and never a substitute for full capture age.

`signal.symbol` is `unknown`, `walk` or `dont_walk`: observed appearance only. A known symbol requires exactly one candidate and numeric confidence. Zero/multiple/ambiguous/unreadable candidates require `unknown`, null confidence and null countdown. Countdown is nullable; if read, an integer 0…199. Confidence is model evidence, not a correctness guarantee. Even a high-confidence walk symbol never authorizes crossing or establishes the applicable intersection. Unknown results can report unavailable evidence but must not be treated as usable guidance merely because recently captured.

Schema contains no actuator command, direction, `go`, `clear`, `safe_to_cross` or crossing-permission field. Gemini narration, GPS and other P1 payload formats are outside this core freeze and must not be smuggled into depth/vision packets. Add separate reviewed contracts when required. Devices with different viewpoints stay separate; this protocol does not promise calibration or fusion.

## Capture age and expiry

| Data | Conservative capture-age upper bound | Separate requirement |
|---|---:|---|
| Phone depth | ≤500 ms | Approved source epoch, usable tracking/sector evidence and valid clock mapping |
| Remote vision | ≤1500 ms | Match original Pi frame; include upload, queue, inference and return delay |
| Heartbeat | ≤2500 ms | Current authorized source/epoch and bounded send age; connection health only |

These are prototype engineering starting limits from the accepted plan, not validated road-use guarantees. Clock half-width uncertainty is proposed at ≤100 ms for depth/heartbeat and ≤250 ms for vision, **in addition** to the full conservative age bound. If an age interval has negative lower bound (possibly future capture), upper bound over limit, reversed bounds, excessive uncertainty, or cannot be computed, it is ineligible. No clamping to zero. Schema validity alone is insufficient.

Each consumer uses its own monotonic clock for local expiry. At initial acceptance calculate upper age `u` and store local deadline `receive_local_ms + (budget-u)`. Recheck the deadline on every policy cycle, including while networking/inference is blocked. A relay may forward the original message but cannot reset capture time or recompute age from its latest receipt. A relay-local age estimate cannot be used by a different device without another bounded clock mapping. Unknown or stale data remain unknown; reconnect, model completion, retries and heartbeat receipt cannot extend an observation deadline.

Heartbeat state is `starting`, `ready` or `degraded`; it describes the producer's reported state only. A bounded fresh heartbeat may extend connection-health expiry to no later than its local receipt plus the remaining 2500 ms send-age budget. It cannot set sensor readiness, validate old results or renew depth/vision TTL. After a disconnect/expired health deadline, invalidate affected guidance; require newly captured valid observations after authorized reconnect. Heartbeats without a usable clock bound do not establish healthy guidance; clock negotiation may still proceed.

## Clock method A: originating Pi frame lineage (preferred for Pi vision)

Before upload the Pi records original metadata with `capture_monotonic_ms` from its own monotonic clock in a bounded pending ledger keyed by session/source/boot/frame ID/sequence. The backend copies this metadata unchanged into the result. On result receipt, Pi authenticates backend and session, matches every provenance field and image dimensions against its own ledger, then computes `now_pi_monotonic_ms − recorded_capture_monotonic_ms`. It includes all elapsed time; receiving a new result cannot reset it. Reject negative/over-1500 ms age and unknown/consumed/superseded ledger IDs. Clear ledger on source restart, Pi clock reset or session replacement. Keep at most two pending frames per camera; expire old entries and drop superseded queued work. No clock comparison with backend UTC/monotonic time is needed.

`local_vision_age` demonstrates matching/age only. Its caller still maintains the bounded ledger, atomic consumed/result sequence state and independent expiry timer. A missing ledger entry must stay unknown; never reconstruct it from the server's echoed metadata.

## Clock method B: bounded source↔consumer exchange (phone depth)

Use `clock_probe` and `clock_reply` from the schema over the authenticated paired session. Pi starts a random nonce, records its own `t1_ms`, receiver boot, target source boot and session/mode, then routes the probe to phone via the backend. The phone records `t2_ms` at receipt and `t3_ms` immediately before sending reply; backend relays the reply unchanged. Pi records **local** `t4` on receipt. No party may fill its timestamps from another device's clock. Probe/reply must match the one outstanding nonce and every bound identity/session/mode/t1 field, arrive on authorized roles, and complete within 1000 ms; consume nonce once. Drop unmatched, replayed or late replies. Backend/phone must rate-limit probes to ≤1 Hz per pair, and a consumer stores only one outstanding probe per source. This keeps relayed delays inside the measured exchange.

Define offset as **source monotonic minus consumer monotonic**. With nonnegative one-way delays and bounded relative clock drift, an offset interval comes from `[t3−t4, t2−t1]`, widened for drift during the exchange. Reject inconsistent/nonfinite/local-clock-reversing exchange times. This does not assume equal one-way latency. At later local time `now`, widen both ends again by `(now−t4) × configured_relative_drift_ppm / 1,000,000`; clock-map lifetime is at most 10,000 ms. The configured joint drift bound is an engineering assumption requiring device verification; start with a conservative budget such as 200 ppm only if justified, otherwise leave remote depth unavailable. Resync during operation and invalidate on interruption/suspension, clock reset, epoch/session change or inconsistent measurements; do not extend a bad map to hide network latency.

For a capture `c`, obtain age interval `[now−c+lower_offset−drift, now−c+upper_offset+drift]`. Only use captures that unambiguously occur **after** this calibration (`c−upper_offset−drift ≥ t4`); wait for a new sensor frame otherwise. Bind every map to source ID/source boot and consumer boot; never reuse a map after either process/clock restart. UTC is not a fallback. Do not combine independent device monotonic timestamps without this mapping. Failure to establish an acceptably narrow interval means unavailable phone-derived guidance, even on a connected socket.

The four-timestamp approach is informed by [RFC 5905, section 8](https://www.rfc-editor.org/rfc/rfc5905.html#section-8); this interval/expiry policy is a CaneSight design, not an NTP implementation or a claim that NTP synchronizes the devices. Schema follows [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-core). Neither source establishes the prototype's numerical safety limits.

## Acceptance, migration and change control

Before merging: PM reviews identity/sequence semantics, budgets, clock/control fields, examples and conformance tests; obtain collaborator review and exact-head authorization for protected `shared/` and CI edits. Task remains Review pending this acceptance. After merge Adit implements backend adapters against these exact files; iPhone/Pi owners port the same tests/fixtures into Swift and edge transport and exercise real failure injection. CS-003 tests do not establish measured clocks, network latency, electrical safety or end-to-end readiness.

No deployed protocol exists in accepted main at this baseline. Reject old/unknown shapes with a version error; do not silently translate or fill missing freshness metadata. Keep v1 immutable after freeze except through a new reviewed CR; incompatible changes require a new protocol version and coordinated consumers. Rollback through a reviewed revert and keep dependent implementations paused/explicitly mocked until a replacement contract is accepted. Leave the master plan and historical fragments untouched.
