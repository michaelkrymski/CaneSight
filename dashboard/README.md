# CS-041 session-health dashboard

Local, read-only **synthetic replay preview**. This is not a connection to the
deployed backend, phone, Pi, model or motors. No device/operator credentials are
accepted. Live integration remains dependent on CS-035 and a reviewed,
authenticated read-only source of dashboard data.

## Run

From repository root, with Python 3.11+:

```sh
python -m backend.telemetry.dashboard --port 8041
```

Open **http://127.0.0.1:8041**. Stop the server with Ctrl+C. It binds only to
127.0.0.1 and has no option to expose it publicly. No third-party Python or
JavaScript packages, build, network fonts, API keys or model download are needed.
The server serves an explicit static-file allowlist; request logs are disabled.
It rejects writes, query parameters, unknown assets and untrusted Host headers.
The content security policy disallows outbound connections and embedding.

## Replay controls

The persistent Replay/Synthetic labels apply to every scenario. Scenario changes
start new local fixture state; no production session or device state is changed.
The page displays no live-mode selector because no live data source is attached.
The display formatter recognizes live/replay/unknown for future reviewed adapters;
the existing preview supplies replay only.

| Scenario | Expected display |
|---|---|
| Recent observations | Independent synthetic depth and vision captures; responding simulated transport; uncovered right sector unknown. |
| Unknown depth | Recent captures and responding transport do not turn missing depth into a distance. |
| Delayed vision | Vision age exceeds 1,500 ms; boxes removed while independent depth remains within budget. |
| Heartbeats only | Transport keeps responding; capture ages grow, observations expire, distances/boxes disappear. |
| Clock uncertainty | Unbounded capture ages stay unknown; receipt time never substitutes for capture time. |
| Sources disconnected | Both source observations unavailable immediately. |

Pause replay stops simulated captures and heartbeats while the local display
clock continues. Depth/vision expire at their own budgets; transport eventually
becomes unavailable. Resume generates new synthetic captures with increasing
sequences; it does not renew old captures through heartbeat updates. Activity is
bounded to eight entries. Screen-reader announcements report state transitions
without announcing every age tick. The layout supports phone and desktop widths,
visible keyboard focus, a skip link and native labeled controls.

## Age and unknown semantics

`model.js` is an internal fixture display model, **not a shared wire contract or
device policy**. `ageAtReceipt` is an explicitly supplied synthetic upper bound;
`receivedAt` and the current local `performance.now()` use the same display clock.
The displayed upper bound adds local elapsed time. Missing, nonfinite, negative
or future-clock bounds stay unknown. The preview never subtracts monotonic
timestamps from different devices or infers age from receipt time alone.

Depth and vision use the baseline 500 ms and 1,500 ms budgets. Last heartbeat has
a separate 2,500 ms transport deadline. A responding heartbeat never changes an
observation's capture-age anchor. Disconnected/unavailable sources suppress their
distances and boxes even when a previous capture was recent. An unknown sector,
signal or countdown never becomes zero, clear, or a crossing decision. The
persistent notice is **Research prototype — no crossing permission**.

These are display tests against fixture bounds, not real-device clock calibration,
inference accuracy, end-to-end latency, haptic eligibility or hardware evidence.
The page keeps pedestrian-signal state and countdown unknown in every scenario.
The illustrated camera-space boxes are not real camera images.

## Live integration gate

CS-029 is merged; CS-035 remains pending. The deployed native device WebSockets
reject browser Origins and use role-scoped credentials. Do not bypass those
restrictions, put the operator/Pi token into this page, or expose this preview
server to obtain a live dashboard. A future reviewed integration must provide a
restricted read-only projection, preserve session/source/boot/frame lineage and
the actual mode, and propagate bounded/unknown capture ages. Any required edits
outside CS-041's allowed paths need PM authorization first. No backend application,
protocol, deployment or authentication behavior is changed by this preview.

## Verification

Python HTTP checks are dependency-free and included in the existing shared test
discovery. JavaScript model tests require Node.js 20+ and use its built-in runner;
no npm installation is needed.

```sh
node --test tests/dashboard/model.test.mjs
python -m unittest discover -s tests/dashboard -v
python -m unittest discover -s tests -v
python scripts/validate_repo.py
python scripts/render_changelog.py --check
git diff --check
```

Alternatively, `npm --prefix dashboard test` runs the same JavaScript tests.
The shared Python suite does not invoke Node; run the JavaScript command
separately when changing display semantics. Existing protected CI is unchanged.

Browser checks: exercise all six scenarios, pause until transport expires, and
confirm that obsolete distances/boxes disappear. Check widths 320, 390, 768,
1024 and 1440 for horizontal overflow. Do not present a fixture screenshot as
live hardware or inference evidence. See the task handoff for actual results.
