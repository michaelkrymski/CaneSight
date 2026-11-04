# Pi calibrated LiDAR implementation candidate

Michael requested implementing as much as possible without automated tests,
deferring manual combined tests. Base main 33aee60; this branch fast-forwards to
the Mac's published de923be before the new integration. No Mac calibration work
was reset or reimplemented; the later full-width detection band is preserved.

New edge.lidar_agent provides one saved-bond Pi session/receiver, explicit clock
binding, independent freshness/watchdog/capped obstacle-side GPIO, raw-vs-eligible
status, optional same-session camera uploads and existing context button/speech.
Unknown clock bounds stay unavailable. Parameters in DepthPolicySettings preserve
old policy defaults; new runtime motor envelope is tighter. The same clock callable
is passed to gate/sender/scheduler/policy/watchdog, not just numerically similar clocks.

Phone transient network/session failures can now rejoin with a new epoch after
old socket cleanup. Explicit stop and clock/auth failures do not silently resume.
New service config/installer and PowerShell versioned release transfer preserve
existing credentials and working checkouts. Installer does not start hardware by
default. Setup/combined manual run is in docs/operations/LIDAR_AGENT_SETUP.md.

No unit/integration/functional tests were added or run. No Pi or server connection,
service activation, physical GPIO/motor operation, live provider calls or Xcode
build performed. Syntax/parser inspection and diff review only. Existing Mac
evidence remains historical; it does not validate these new integration changes.
Current drift qualification is still required; the old 1518.614 ppm candidate is
not installed or represented as a verified permanent hardware bound.

Publish as an untested integration candidate based on Mac calibration, with tests
deferred at user request. No weakening of stale-data or motor-stop protections,
new wire fields, model replacement, credential regeneration or live deployment.
