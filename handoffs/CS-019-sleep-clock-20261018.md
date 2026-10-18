# CS-019 sleep/recovery fix

Owner: Gavin (`gmarcialcalleja`), merged claim #65.
Branch: `task/CS-019-sleep-clock`.
Initial test base: `46b65c3cb539717301bc9b5c1502405d3ef6286e`.
Publication base: `a7b0214dd0c28316b61449d72c81215753b94993`
(accepted CS-016 ownership transfer only; GPS source unchanged).

## Problem and change

The production provider paired UTC with ProcessInfo.systemUptime, which measures
awake time. During device sleep UTC advances but awake uptime does not; the
context's deliberate UTC-step detector consequently latched a terminal clockFault
on ordinary resume. The prior read-only audit reproduced initial availability,
clockFault on simulated resume, and rejection of a fresh subsequent fix.

`LocationSystemClock.swift` now pairs UTC with elapsed Swift ContinuousClock time,
including sleep. Its origin is local to the reader and is never an ARFrame/source
boot clock or implicit remote calibration. The existing policy still clears old
fixes on inactive/consent/provider changes and requires a new post-recovery fix.
Genuine UTC steps, nonfinite/reversed clocks and stale fixes remain unavailable.

Changed files: own package manifest (explicit macOS13/iOS16 support), clock reader,
Core Location provider, new clock XCTest file, package README, own task runtime,
new evidence/changelog/handoff and generated log. A following host dependency pin
update will select the actual committed GPS package; other package pins stay put.

## Validation actually run

Local official Swift6.0.3 Docker image
`sha256:f19aea3f9a889df5884e1186e60be74869613477d99656b598c115a4b91af8a1`,
network disabled, 1CPU/2GiB, read-only repository mount and temporary build output.

```text
swift test --package-path /code/ios/CoarseLocation --scratch-path /tmp/cs019-tests --jobs 1 -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
20 tests passed, zero failures/compiler warnings.
```

Five new tests cover conversion, system-reader monotonicity, thirty-second virtual
sleep/recovery, original-age expiry even without a host inactive callback, and an
actual UTC step during sleep remaining fail-closed. Fifteen existing consent,
accuracy/privacy/rate/recovery cases passed. Evidence JSON records tested hashes.
Virtual sleep tests follow ContinuousClock's documented contract; no physical
sleep or Apple SDK execution is asserted. Linux excludes conditional SDK source.

Checked publishing additionally runs shared tests/structure/generated-log and
whitespace checks; actual outcomes belong in this PR. No server or hardware access.

## Remaining acceptance gates

`decisions/CR-CS-019-location-context-contract.md` remains proposed. Main has no
accepted GPS wire schema or receiver; no GPS fields may be inserted into existing
v1 packets. Michael's earlier merge accepted local software only, not future
protected contracts/backend scope. Required next step is explicit contract review
and assignment, then CS-016 integration and current-head Apple build plus actual
permission, reduced-accuracy, stale-cache and sleep/lock/resume phone tests. Keep
sharing default-off; no precise tracks or credentials in evidence.

Task remains blocked by those external gates. This fix does not claim end-to-end
telemetry, completed CS-019 acceptance, motor readiness or crossing permission.
