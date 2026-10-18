# CS-049 software denial/failure campaign

Requires Python test dependencies and, for the separate portable location run,
Swift 5.9+ (tested with Swift 6.0.3). No demo phone, Xcode, live Gemini key,
network service, Pi or motors are used. Do not change deployed services.

```sh
python -m qa.denial_failure_suite --output NEW-cs049-software.json
swift test --package-path ios/CoarseLocation --jobs 2 -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
```

Use a new report path for each Python attempt. Reports include actual test IDs,
failures/skips and normalized source hashes, never image bytes, coordinates,
credentials or exception text. A skipped or failed campaign is not a pass.
Swift is deliberately separate: the Python command never claims it ran Swift.

| Acceptance aspect | Actual component checks | Boundary |
|---|---|---|
| GPS denied/restricted/no consent/inactive/stale/invalid/provider failure | Existing portable CoarseLocation XCTest suite, including queued-fix barriers and cache purge | Real Swift core with synthetic fixes/clocks; Core Location bridge and OS prompts excluded on Linux |
| Optional location cannot affect motor/permission policy | New unsupported-field rejection cases through accepted CaptureAgeGate and LocalPolicy, plus GPS core suite | No accepted GPS wire contract exists; this is isolation evidence, not GPS network integration |
| Gemini authorization/provider errors/timeout/cancellation | Accepted provider, service, HTTP and consumer tests | Synthetic provider opener/runner and TestClient; no live API/quota or real TLS claim |
| Context cannot refresh depth or change pulses | New real LocalPolicy/HapticScheduler + ContextNarration composition | Same synthetic clock, calibrated zero-drift fixture, simulated outputs |
| Late context suppressed | New depth-expiry, original-context-deadline, cancel/consent-recovery and hazard-preemption cases | Synthetic pending client; existing service tests separately exercise timeout/child cleanup |

The positive control first delivers a valid fixed description while depth is
fresh, then proves that original depth expiry cancels it. The hazard test first
starts a context request, then accepts real policy obstacle evidence, checks
that optional narration cannot cancel its simulated motor pulse, and checks the
original pulse deadline. Invalid GPS/description/permission fields are rejected
before policy input changes; no new GPS protocol is invented.

Historical CS-019/040 evidence remains unchanged. Full acceptance still needs
their native permission/provider/lifecycle and actual phone/Pi/audio integration
checks, reviewed GPS transport if introduced, and physical timing where claimed.
Software reports do not establish audible silence, motor off-state or crossing
permission. Michael decides acceptance; this checkpoint is not task Done.
