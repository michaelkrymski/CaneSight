# CS-044: pinned crossing-menu failure campaign

This extends the accepted N01–N05 software campaign for the merged crossing
interaction requirements. It tests **unmodified review inputs**, not a live
crossing assistant. No Pi, SSH runner, camera, provider, network device, GPIO,
motor or audible speaker is used. Speech is an in-memory silent sink.

Review requests: CS-027 PR #58 at
`8f4d52100fa3e7bfe93cf4a8a2faedfd4495bc49` and CS-040 PR #41 at
`ca88cd20205bc76dc88a06d1cd194689f5f05f90`. These are unmerged snapshots;
the campaign does not accept or modify their code. The manifest records each
source file's exact Git commit and SHA-256 plus the closed 19-case list.

```powershell
python -m unittest tests.failures.test_crossing_report -v
python -m qa.crossing_failure_suite --output C:/private/crossing-software-report.json
```

The runner performs no network fetch. Have the exact review commits locally
before running (ordinary `git fetch origin` sufficed at this checkpoint). It
materializes only seven pinned Python files in a temporary directory, verifies
bytes, runs the fixed test file in a fresh subprocess and verifies bytes again.
It never falls back to current branch source. Missing/tampered inputs, unexpected
shadow modules, changed QA source, missing cases, skips, errors, failures or a
30-second child timeout prevent `all_software_passed=true`.

For a Git-free isolated run, export first:

```powershell
python -m qa.crossing_failure_suite --prepare C:/private/NEW-crossing-review-source
python -m qa.crossing_failure_suite --prepared C:/private/NEW-crossing-review-source
```

The destination must be new. Exports remain unmodified source, not a deployment.
The Linux checkpoint used a local `python:3.12-slim` Docker container with network
disabled and both repository and verified export mounted read-only. Reports
record Python/platform, every dependency pin, QA source hashes and named outcomes.
Raw child stdout/stderr, assertion/exception messages, images and credentials
are not serialized. Output contains synthetic aggregate test evidence only.

## Coverage and interpretation

| Cases | What is actually exercised |
|---|---|
| Thresholds/barriers | Real `MenuBench` + `CrossingMenu` + `FixedMenuAudio`: 2999/3000ms entry, 999/1000ms confirmation, release barriers and no double activation. |
| Selection/input | No default, three exact spoken labels and wrap, no-selection prompt, idle short-release compatibility, bounce and startup-held input. A context gesture is counted; no actual context request exists in this bench. |
| Cancel/expiry | Cancel on debounced down edge; held input cannot restart; 15s inactivity/30s residence; shutdown cannot reopen; failed clocks latch. |
| Loss/recovery | Inject audio/source/consent/priority loss and each local epoch component. Old speech/selection cannot resume; audio reconnect requires a new entry. These flags do not verify actual route/source monitors. |
| Delayed work | The actual narration controller rejects a cancelled worker ticket after a blocked fixture worker completes; fixed menu audio rejects older generation/epoch events; original optional context deadline and independent menu-speech expiry remain enforced. |

All 19 named cases passed on Windows Python 3.14.7 and local Linux Python 3.12.
Four source/report-integrity tests are also discoverable by normal repository CI.
The 19-case campaign is explicit because its dependencies are unmerged; normal CI
does not fetch or silently skip them. Inspect the committed reports for exact
tested bytes. Refresh pins and rerun after dependency changes; an earlier pass
does not validate a newer PR head.

## Not established by this checkpoint

- PR #58's production uploader still uses the prior context path. The new menu
  bench has no scenario analysis job or request/result bridge. Live old-result
  rejection after a scenario switch is therefore **not integration-tested**.
  Low-level ticket/generation tests are not a substitute for that missing bridge.
- Source/epoch/audio flags are injected, not authenticated phone/Pi telemetry or
  actual Bluetooth notifications. Real readiness, audibility, buffered cancellation
  latency and device reconnect checks remain controlled bench work.
- Optional descriptions keep their separate original-capture 8s deadline. That
  is not a depth/vision allowance: accepted 500ms depth and 1500ms vision gates
  remain unchanged and covered by the existing independent expiry campaign.
- No model accuracy, traffic interpretation, physical-off guarantee or road-use
  acceptance. Physical acceptance remains false in every report. Coordinate
  hardware availability and prerequisites before any later device run.
