# CS-023 capped scheduler software checkpoint

Base: 89e15adab322ea299915f193cb6c9c6626d20739.
Branch: task/CS-023-capped-haptic-scheduler.
Owner: gmarcialcalleja; Michael approved and merged assignment PR #34.

## Changed files
edge/haptics.py: pure-standard-library, two-channel local pulse scheduler.
Default simulated output only; no GPIO packages, network commands or pin mapping.
500 ms maximum pulse, at least 200 ms off, conservative simulation rolling budget
2000 ms per 10 seconds per channel, nominal 10 ms independent worker tick.
The 20% duty setting is an implementation simulation starting point, not a
manufacturer rating or change to the master plan. Configuration can tighten caps.
There is no pulse backlog or active pulse extension. Both channels must qualify
before pair admission. Requests expire at the ORIGINAL local eligibility deadline.
Readiness is false at startup. Disarm/cancel preserve elapsed duty and cooldown.
Startup/cleanup attempt both off requests independently. Invalid/reversing clock,
output faults and observed maximum-pulse overruns latch unavailable. Failed off
writes report unknown. Closing is terminal and joins the worker.
edge/HAPTICS.md documents the CS-024 policy boundary, commands and limitations;
edge/README.md links it. tests/edge/test_haptics.py adds meaningful scheduler tests.
Own task runtime fields, immutable changelog fragment and sanitized simulation
report complete the checkpoint; existing task static fields remain unchanged.

## Tests actually run
Windows pinned Python 3.12: all 38 edge tests passed (25 scheduler, 13 uploader).
Linux Python 3.12 in an isolated Vultr source directory: all 38 passed.
python -m edge.haptics --simulate succeeded on both systems, accepted two pulses,
closed both outputs off, and reported gpio_used false.
30,000 deterministic adversarial 10 ms steps (five simulated minutes) verified
no overlapping channel pulses, minimum off times, <=500 ms observed virtual pulse
length and <=2000 ms rolling usage. Recent history and event trace remain bounded.
Other cases cover exact boundaries, partial-window duty clipping, pair admission,
expired eligibility, readiness toggling, late ticks/cancellation, output faults,
unknown off writes, invalid clocks, context exception cleanup and independent
expiry while the caller blocks. No images, credentials or hardware outputs used.
Checked publisher runs all 41 shared tests plus structure/changelog/whitespace
checks before commit. Protected CI does not discover tests/edge automatically;
these edge tests were run explicitly. No unrun hardware/CI step is pre-asserted.

## Limits and next steps
This is simulated software, not proof of physical pulse duration or pin voltage.
Python/OS scheduling or a blocking/frozen process/adapter can delay off requests;
a fault cannot undo an elapsed overrun. Physical kill/power/driver/diode conditions
and CS-026 independent watchdog remain necessary. No physical adapter is provided.
CS-009 is still backlog: Michael must accept its driver off-state, logic-voltage,
leakage and thermal evidence and power prerequisites before physical integration.
The scheduler does not select hazard cues or grant crossing permission. CS-024
must integrate trusted readiness, evidence expiry and cue precedence using the
same BOOTTIME clock; no cloud timestamp or heartbeat may authorize movement.
Review the software checkpoint, then integrate/validate the physical adapter
after CS-009. Task stays blocked on that dependency and is not marked Done.
