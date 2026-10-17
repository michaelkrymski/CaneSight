# CaneSight — Trello board overview

Updated 17 October 2026. Board status: **created and verified in Trello**. [Open CaneSight | 20-Hour Prototype](https://trello.com/b/aH113bQW/canesight-20-hour-prototype). Created through the signed-in browser because the installed Trello plugin did not expose callable tools to this chat. The board is private in the Personal workspace.

Verified in the board UI: 58 cards, 11 category lists, 58 descriptions, 40 red P0 labels, 12 orange P1 labels, and 6 blue P2 labels. Descriptions contain suggested owner roles, estimates, elapsed windows, dependencies and acceptance criteria. No Trello members were assigned and no dates were invented. The CSV is a backup/recreation package; do not import it into this board again unless you intend duplicates.

Motor revision: the intended supply is 5 V within the photographed 1–6 V range, subject to actual-part verification and measured current/thermal behavior. The rated 3 V data are not 5 V specifications. See implementation guide v1.1.

## Board structure and labels

Board name: **CaneSight | 20-Hour Prototype**. One list per category below has been created. Cards start in Backlog, recorded in their descriptions; no custom status field was created. Track later progress in the description or a custom field so category lists remain useful: Backlog → In progress → Blocked → Review → Done. Limit each contributor to one active critical card. Owner values are suggested roles, not assigned Trello members.

| Priority | Color | Meaning |
|---|---|---|
| P0 - Critical | Red | Required vertical slice, electrical protection, failure handling or release gate. |
| P1 - Important | Orange | Add after P0 integration; cut at hour 14 if incomplete. |
| P2 - Stretch | Blue | After-hackathon backlog; excluded from the 20-hour critical path. |

Priority prefixes in card titles preserve visibility even if an importer does not create colored labels. Category lists describe work domains; priority labels describe importance. Estimates are person-hours, while Window is elapsed time from kickoff. These are planning estimates, not measured execution times.

## Backup / recreation import instructions

Trello has no generic native CSV import tool. Use a compatible third-party CSV import Power-Up, the Trello API, or manually paste titles into lists. See [Atlassian import guidance](https://support.atlassian.com/trello/docs/importing-data-into-trello/). No paid importer or integration was installed for this delivery.

1. Create the named board and the category lists exactly as below.
2. Create the three priority labels with the colors above.
3. Open a trusted compatible CSV importer and select `CaneSight_Trello_Import.csv` (UTF-8, quoted fields, embedded newlines).
4. Map `Name` → card title, `Description` → description, `List` → destination list, `Labels` → label name. If the importer supports only one target list, filter/import each category separately.
5. Map remaining fields to custom fields only if supported. Owner roles are not email addresses or member IDs; do not map them automatically to assignees. Color, estimates and dependencies remain in descriptions/overview if custom fields are unavailable.
6. Test import with one or two rows first. Verify embedded newlines, lists and label names, then import the remaining rows once. Importers may duplicate cards on retry; use Task ID to reconcile.
7. Compare the resulting card count and per-list counts with the inventory below. Confirm all cards begin in Backlog, not Done.

Without an importer, paste the card-title bullets from each category into its Trello list, then copy descriptions/labels from the CSV. Dependencies are task IDs for humans; they do not automatically create Trello dependency links.

## Schedule and gates

Four concurrent workstreams are assumed; suggested owner roles may be combined across four people. At hour 2 verify real-phone build, networking and actual parts. By hour 5 establish protected power and data transport. By hour 8 demonstrate fresh phone depth → backend → Pi → motor. At hour 14 freeze optional work. Hours 14–17 are tests/fixes; 17–20 are rehearsal and handoff. A failed wiring, stale-data or permission-language gate requires a labeled recording/software-only fallback.

Critical chains:

- Hardware: CS-005 → CS-006 → CS-007/008/009 → CS-010 → CS-043.
- Depth: CS-013 → CS-014/015 → CS-016/017 → CS-025.
- Protocol: CS-003 → CS-028/029 → CS-030/031/032 → CS-044.
- Delivery: CS-045/046/047/048 → CS-051/052 → CS-053.

## Card inventory

### Planning & Safety (4 cards)

- **[P0] CS-001 Confirm build inventory and development tools** — Lead; 0.5 h; window 0–2. Dependencies: none. Acceptance: Record available/missing parts; verify Mac signing, phone depth support, network and Pi boot.
- **[P0] CS-002 Remove crossing-permission language** — QA; 0.5 h; window 0–2. Dependencies: none. Acceptance: Review planned UI, API, haptics and script; no go/all-clear/safe-to-cross state.
- **[P0] CS-003 Freeze schema and freshness rules** — Backend; 1 h; window 0–2. Dependencies: none. Acceptance: Agree source/boot/sequence IDs, capture-age bounds, unknown values and clock uncertainty.
- **[P0] CS-004 Define safe demo course and stop controls** — QA; 0.5 h; window 0–2. Dependencies: none. Acceptance: Indoor level course, soft objects, sighted spotter and reachable motor kill switch.

### Hardware & Power (8 cards)

- **[P0] CS-005 Verify motor range and characterize intended 5 V operation** — Hardware; 0.5 h; window 0–2. Dependencies: CS-001. Acceptance: Confirm actual part and stated 1–6 V range; characterize at 3 V, then measure 5 V startup/running current and heat at planned duty; retain 3 V fallback.
- **[P0] CS-006 Verify two HW-517 channels and logic compatibility** — Hardware; 1 h; window 0–2. Dependencies: CS-005. Acceptance: Confirm assembled-board topology, 3.3 V trigger behavior, 5 V isolation and default-off behavior; choose documented fallback if unresolved.
- **[P0] CS-007 Build protected 5 V motor branch with 3 V fallback** — Hardware; 1 h; window 2–5. Dependencies: CS-005;CS-006. Acceptance: Meter polarity and loaded 5 V branch; document fuse, cable limits, kill switch and common ground; use 3 V fallback if 5 V validation fails.
- **[P0] CS-008 Fit separate flyback diodes and secure wiring** — Hardware; 0.5 h; window 2–5. Dependencies: CS-007. Acceptance: One suitable diode per motor: cathode band to motor+, anode to switched motor-; insulate and strain-relieve.
- **[P0] CS-009 Bench-test driver off states and dummy load** — Hardware; 0.5 h; window 2–5. Dependencies: CS-006;CS-007. Acceptance: Check trigger high/low, GPIO voltage, leakage and module thermal behavior before Pi integration.
- **[P0] CS-010 Validate dual-motor power under camera load** — Hardware; 0.5 h; window 5–8. Dependencies: CS-008;CS-009;CS-021. Acceptance: At selected voltage, record startup/running current, rail minimum and temperature; confirm no Pi reboot or heat fault during both motor startups.
- **[P0] CS-011 Mount phone, camera and left/right motors** — Hardware; 0.5 h; window 11–14. Dependencies: CS-010. Acceptance: Secure reversible mounts; confirm grip mapping, cable relief and normal cane integrity.
- **[P1] CS-012 Evaluate optional ToF and IMU interfaces** — Hardware; 1 h; window 11–14. Dependencies: CS-010. Acceptance: Verify breakout levels/timing; MPU-6050 gesture is not absolute heading; omit unsafe or unverified sensors.

### iPhone LiDAR & GPS (8 cards)

- **[P0] CS-013 Build and sign app on physical LiDAR phone** — iOS; 1 h; window 0–2. Dependencies: CS-001. Acceptance: Run ARKit support check; unsupported hardware displays unavailable.
- **[P0] CS-014 Implement confidence-aware depth sectors** — iOS; 2 h; window 2–5. Dependencies: CS-013. Acceptance: Finite depth, confidence/coverage filtering, robust percentile, null unknown and source timestamp.
- **[P0] CS-015 Verify camera orientation and mount mapping** — iOS; 1 h; window 5–8. Dependencies: CS-014. Acceptance: Known targets map to physical left/center/right in supported orientations.
- **[P0] CS-016 Stream bounded timestamped telemetry** — iOS; 1 h; window 5–8. Dependencies: CS-003;CS-014;CS-029. Acceptance: Send 10 Hz starting summaries, session/boot/sequence IDs and reconnect without old queue replay.
- **[P0] CS-017 Handle AR interruption and app suspension** — iOS; 1 h; window 8–11. Dependencies: CS-016. Acceptance: No cached depth after interruption; Pi expires observations and recovery needs fresh data.
- **[P0] CS-018 Add accessible status and manual audio cancel** — iOS; 0.5 h; window 8–11. Dependencies: CS-017. Acceptance: VoiceOver labels, large controls, clear unknown/disconnected status.
- **[P1] CS-019 Add consented coarse GPS telemetry** — iOS; 1 h; window 11–14. Dependencies: CS-016. Acceptance: Include fix age and accuracy; denied/stale fix unavailable; no lane/signal association.
- **[P1] CS-020 Test challenging LiDAR surfaces** — QA; 0.5 h; window 11–14. Dependencies: CS-015;CS-017. Acceptance: Log glass, dark objects, glare and blocked-view behavior; no missing-depth all-clear.

### Pi Edge & Haptics (7 cards)

- **[P0] CS-021 Boot Pi and validate CSI capture** — Edge; 1 h; window 0–2. Dependencies: CS-001. Acceptance: Supported OS/Picamera2, correct Zero ribbon and in-memory capture work.
- **[P0] CS-022 Implement latest-only JPEG upload** — Edge; 1.5 h; window 2–5. Dependencies: CS-021;CS-028. Acceptance: Start 416-square quality-75 at 1 Hz; bound queues and preserve crop/letterbox mapping.
- **[P0] CS-023 Implement capped haptic scheduler** — Edge; 1 h; window 2–5. Dependencies: CS-003;CS-009. Acceptance: Two channels, bounded pulse duration/duty, outputs low at startup and cleanup.
- **[P0] CS-024 Implement local policy and source expiry** — Edge; 1.5 h; window 5–8. Dependencies: CS-003;CS-023;CS-030. Acceptance: Separate health from hazards; stale capture never becomes fresh at receipt.
- **[P0] CS-025 Integrate depth-to-motor vertical slice** — Edge; 1 h; window 5–8. Dependencies: CS-010;CS-015;CS-016;CS-024. Acceptance: Repeat left/right/center stimulus with real phone data and logged capture age.
- **[P0] CS-026 Add independent watchdog and restart behavior** — Edge; 1 h; window 8–11. Dependencies: CS-024. Acceptance: Network/camera cannot block expiry; boot/crash resets state; disclose frozen-GPIO limit.
- **[P1] CS-027 Add debounced context button** — Edge; 0.5 h; window 11–14. Dependencies: CS-023;CS-039. Acceptance: One outstanding request, cooldown, cancellation and rate limit.

### Backend & Transport (6 cards)

- **[P0] CS-028 Create FastAPI skeleton and frame endpoint** — Backend; 1 h; window 2–5. Dependencies: CS-003. Acceptance: Health/readiness separate; validate JPEG dimensions/body and return frame lineage.
- **[P0] CS-029 Create paired authenticated WSS sessions** — Backend; 1.5 h; window 2–5. Dependencies: CS-028. Acceptance: Phone/Pi roles, isolated session subscriptions, TLS route and scoped credentials.
- **[P0] CS-030 Implement age bounds and replay rejection** — Backend; 1.5 h; window 5–8. Dependencies: CS-029. Acceptance: Clock uncertainty or request lineage bounds capture age; reject duplicate/reordered/wrong-session messages.
- **[P0] CS-031 Add bounded inference worker and latest queue** — Backend; 1 h; window 5–8. Dependencies: CS-028. Acceptance: No event-loop blocking; one model load; per-source latest work; explicit drop metrics.
- **[P0] CS-032 Enforce message validation and rate limits** — Backend; 0.5 h; window 8–11. Dependencies: CS-029;CS-031. Acceptance: Reject NaN, oversize input and floods; memory and watchdog remain bounded.
- **[P1] CS-033 Deploy authenticated backend on Vultr** — Backend; 1 h; window 11–14. Dependencies: CS-029;CS-032. Acceptance: Test HTTPS/WSS, startup readiness and secret configuration; laptop remains rehearsed fallback.

### YOLO & Signal Vision (5 cards)

- **[P0] CS-034 Load pinned YOLO baseline and inspect classes** — CV; 1 h; window 2–5. Dependencies: CS-028. Acceptance: Record model hash/class list/license; distinguish generic traffic light from pedestrian signal.
- **[P0] CS-035 Return observation-only inference results** — CV; 1 h; window 5–8. Dependencies: CS-031;CS-034. Acceptance: Include model/frame/source/age, nullable signal fields and camera-space boxes; no permission output.
- **[P1] CS-036 Prepare signal fixtures or verified custom weights** — CV; 1 h; window 5–8. Dependencies: CS-034. Acceptance: Document source/license; label manual ROI and replay; no claim of automatic pedestrian recognition without evidence.
- **[P1] CS-037 Implement symbol and countdown parser** — CV; 2 h; window 8–11. Dependencies: CS-036. Acceptance: Shape/temporal checks, uncertain flashing and null ambiguous digits; HSV alone insufficient.
- **[P1] CS-038 Evaluate signal ambiguity and track loss** — QA; 1 h; window 11–14. Dependencies: CS-037. Acceptance: Multiple heads/glare/occlusion/track change yield unknown; record confusion and OCR accuracy.

### Gemini & Context (2 cards)

- **[P1] CS-039 Create isolated Gemini context service** — Backend; 1 h; window 11–14. Dependencies: CS-029;CS-035. Acceptance: Verify model availability; server-only key, compressed frame, separate queue, 8 s starting deadline.
- **[P1] CS-040 Restrict and preempt narration** — iOS; 0.5 h; window 11–14. Dependencies: CS-018;CS-027;CS-039. Acceptance: No movement/crossing advice; short uncertain descriptions, cancellation and hazard priority.

### Dashboard & Data (2 cards)

- **[P1] CS-041 Build session-health dashboard** — Frontend; 1 h; window 11–14. Dependencies: CS-029;CS-035. Acceptance: Show source ages, unknown, live/replay mode and prototype limitation; no green safe state.
- **[P2] CS-042 Add consented Tiger Data event logging** — Backend; 1 h; window After hackathon. Dependencies: CS-041. Acceptance: Coarse/minimal data, retention/deletion, parameterized writes; DB failure does not block policy.

### Safety & Testing (7 cards)

- **[P0] CS-043 Test power, boot, crash and motor kill** — QA; 1 h; window 8–11. Dependencies: CS-010;CS-023;CS-026. Acceptance: Execute E01–E03; retain measured evidence and fix failures before handling.
- **[P0] CS-044 Inject disconnect, delay and replay failures** — QA; 1.5 h; window 8–11. Dependencies: CS-025;CS-030;CS-032. Acceptance: Execute N01–N05; old observations never actuate as fresh; health cannot extend expiry.
- **[P0] CS-045 Measure end-to-end latency and depth error** — QA; 1 h; window 14–17. Dependencies: CS-025;CS-044. Acceptance: At least 20 latency samples, median/p95/max, clock uncertainty and distance test results.
- **[P0] CS-046 Run controlled obstacle and cue trials** — QA; 1 h; window 14–17. Dependencies: CS-004;CS-011;CS-043. Acceptance: Stationary then supervised level-course tests; verify mapping and cue distinguishability.
- **[P0] CS-047 Perform representative 15-minute power soak** — QA; 0.5 h; window 14–17. Dependencies: CS-010;CS-043. Acceptance: Log temperature, bank behavior and resets; no endurance claim beyond evidence.
- **[P0] CS-048 Audit all user-facing permission language** — QA; 0.5 h; window 14–17. Dependencies: CS-002;CS-035;CS-046. Acceptance: Review final code/UI/audio/script; no crossing authorization or no-detection-as-clear wording.
- **[P1] CS-049 Test GPS and Gemini denial/failure paths** — QA; 0.5 h; window 14–17. Dependencies: CS-019;CS-040. Acceptance: No location or description failure changes motor/permission policy; late context suppressed.

### Demo & Delivery (4 cards)

- **[P0] CS-050 Freeze optional features at hour 14** — Lead; 0.25 h; window 11–14. Dependencies: CS-025;CS-044. Acceptance: Cut unfinished P1/P2; retain P0 fixes only and document actual scope.
- **[P0] CS-051 Create honest fallback recording** — Lead; 0.75 h; window 14–17. Dependencies: CS-025;CS-050. Acceptance: Capture controlled demo with mode labels and unavailable behavior; no road crossing.
- **[P0] CS-052 Rehearse four-minute demonstration** — Lead; 0.75 h; window 17–20. Dependencies: CS-045;CS-046;CS-047;CS-048;CS-051. Acceptance: Explain observation role, show haptics and disconnect, report measured limitations.
- **[P0] CS-053 Package implementation evidence and runbook** — Lead; 0.75 h; window 17–20. Dependencies: CS-052. Acceptance: Include actual wiring photos/datasheets, versions/config, results, recovery steps and source attribution.

### Post-hackathon Backlog (5 cards)

- **[P2] CS-054 Collect and license representative signal dataset** — CV; 8 h; window After hackathon. Dependencies: CS-038. Acceptance: Split by scene/location; include negatives, diverse lighting and held-out evaluation.
- **[P2] CS-055 Design hardware timeout and robust enclosure** — Hardware; 6 h; window After hackathon. Dependencies: CS-043;CS-047. Acceptance: Document watchdog/load enable, fault states, protection and mechanical review.
- **[P2] CS-056 Evaluate calibrated multi-camera geometry** — CV; 8 h; window After hackathon. Dependencies: CS-045. Acceptance: Measured extrinsics/time alignment and uncertainty; no pixel-depth association before validation.
- **[P2] CS-057 Conduct specialist-led usability and risk review** — Lead; 8 h; window After hackathon. Dependencies: CS-053. Acceptance: Engage mobility specialists with consented controlled research; no deployment safety claims.
- **[P2] CS-058 Investigate independent local phone-to-Pi transport** — Edge; 4 h; window After hackathon. Dependencies: CS-044. Acceptance: Validate hotspot reachability, authentication and source freshness without cloud dependency.

## Reconciliation totals

58 cards total: 40 P0, 12 P1, 6 P2. Estimated total 82 person-hours, including after-hackathon work. In-window estimate: 47 person-hours. Allow remaining four-person capacity for integration, debugging and breaks; do not interpret estimates as a guarantee.

This board plans work; it does not assert that software, electrical tests or deployment have been completed. Use the implementation guide for full wiring conditions, thresholds, test IDs and risk controls.

