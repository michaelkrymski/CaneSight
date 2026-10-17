# CS-041 fixture dashboard - 2026-10-17

Owner: Gavin (`gmarcialcalleja`). Branch: `task/CS-041-session-health-dashboard`.
Base commit: `8c5af9c674635620c586d23accadc788f90e8cad` (accepted main after
Michael merged claim PR #24). Task requirements and dependency list unchanged.

## Result and scope

A local read-only dashboard presents source capture-age upper bounds separately
from transport health, unknown depth/signal/countdown, live/replay mode formatting,
and a persistent Research prototype - no crossing permission notice. The actual
preview always says Replay and Synthetic fixtures, with no live devices/backend
connected. It shows no green safe state or actuator/movement controls.

Six scenarios cover recent captures, unknown depth, delayed vision, heartbeats
without captures, clock uncertainty and disconnected sources. Pause stops fixture
packets while display time continues. Stale distances and object boxes disappear;
heartbeats never reset capture anchors. The right sector and pedestrian-signal
state remain explicitly unknown. Illustrative boxes are not camera images.

Changed files:

- dashboard/index.html, style.css, app.js, model.js and icon.svg: responsive,
  keyboard-accessible UI and isolated synthetic display model. Unknown/expired
  states are textual; screen-reader announcements follow state transitions.
- dashboard/package.json: private package and dependency-free Node test command.
- dashboard/README.md: runbook, semantics, fixture disclosure, integration gate,
  exact test commands and limitations.
- backend/telemetry/__init__.py and dashboard.py: dependency-free loopback-only
  static preview server. Explicit asset allowlist, no writes/query parameters,
  restricted Host values, no request logging, no-store, nosniff, no-referrer and
  CSP denying network connections, embedding and forms.
- tests/dashboard/model.test.mjs: meaningful display expiry/unknown/bounds tests.
- tests/dashboard/__init__.py and test_fixture_server.py: four real HTTP checks,
  included automatically in the existing shared Python suite.
- Own task runtime fields, new changelog fragment and generated changelog.

No backend app, sessions, deployment, model, protocol, protected automation,
master plan or teammate task was edited. No credentials or private images enter
this dashboard, its fixtures, logs, tests or repository.

## Tests actually run

- Node.js 24.21.0: `node --test tests/dashboard/model.test.mjs` and the equivalent
  `npm --prefix dashboard test`: **10 tests passed**. Covers separate exact age
  budgets, heartbeat-only expiry, pause/resume with advancing time, unknown and
  invalid/future bounds, missing depth, delayed vision, disconnects, heartbeat
  deadline, unknown source kind, bounded eight-event activity and mode formatting.
- Windows Python 3.14: `python -m unittest discover -s tests/dashboard -v`:
  **4 real HTTP tests passed**. Confirms loopback bind, actual static assets,
  security headers, traversal/private-file exclusion, no mutation endpoints,
  query/foreign-Host rejection, HEAD behavior and fixture notices.
- `python -m unittest discover -s tests -q`: **43 passed**, including those four
  dashboard HTTP tests plus the existing 39 shared repository/contract tests.
  Publisher-fixture CS-001-test messages refer to an isolated temporary Git repo.
- Repository structure and diff whitespace checks passed before publishing;
  checked publisher reruns shared tests and generated changelog validation.
- Real Chromium in-app browser: all six scenarios exercised. Heartbeats-only
  showed both observations Expired, capture sequences still #1, transport still
  Responding, distances removed and boxes hidden. Unknown and future-unbounded
  semantics are additionally covered in model tests.
- Browser pause: after transport timeout, both observations Unavailable and left
  distance removed. No real browser connection or credentials were used.
- Responsive widths 320, 390, 768, 1024 and 1440 checked; DOM document scroll width
  equaled viewport content width (no horizontal overflow). Desktop and mobile
  layouts visually inspected. Native labeled controls, skip link, visible focus
  and state-only live announcements included. No formal accessibility audit.
- Browser console: no warnings/errors. Final formatted stylesheet reloaded and
  rechecked without warnings/errors. Preview screenshots saved outside Git in
  Gavin's Codex visualization workspace (cs041-desktop.png / cs041-mobile.png).

Node tests are run separately; protected CI has not been edited to invoke Node.
The existing shared CI discovery includes the four new HTTP tests automatically.
These are software/fixture results, not model/device/haptic/electrical evidence.

## Run and review

From repository root: `python -m backend.telemetry.dashboard --port 8041`.
Open http://127.0.0.1:8041. No third-party installation is needed. The preview was
left running locally for review. It does not publish to Vultr or another host.

Status is **blocked**, with a draft implementation PR: the tested fixture preview
is available, but live integration awaits accepted CS-035 and a reviewed,
authenticated read-only dashboard data source. CS-029's native WSS currently
rejects browser Origins; do not bypass that or expose operator/device keys in the
browser. Changes outside allowed paths require PM authorization first. No shared
wire contract or live API is invented by this internal display model.

Next steps: Michael reviews the fixture UI; complete CS-035; agree the restricted
read-only integration and any necessary scope amendment; preserve session, boot,
frame and mode provenance and bounded/unknown ages in that integration. Michael
owns review/merge. Do not mark CS-041 Done from a fixture preview or CI pass.
