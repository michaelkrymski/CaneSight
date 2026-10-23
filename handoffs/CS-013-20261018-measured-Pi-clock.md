# CS-013 measured real Pi clock checkpoint

Base c34520b60e85d6cd4b5efe18c94659ee236208c4;
claim/CS-013-michaelkrymski. Local evidence update only; no GitHub contact,
fetch/pull/push, PR, production configuration or motor control changes.

Michael reported the completed saved-bond Pi measurement. Initial partial attempt
was discarded on peer/session change; the final 75.17-second run used one stable
connection and was uninterrupted. No evidence/model combines those attempts or
an earlier Pi boot. The raw timestamp exchanges were not supplied, so the Pi
aggregate fit/acceptance remains operator-reported, not independently recomputed.
The signed phone's device-only probe independently reported 61 successful native
clock-reply sends, matching the reported 61 exchanges.

Reported final result:
- 355 real depth packets, 75 heartbeats; source 4.752 Hz, receiver 4.758 Hz.
- Strict sequence order and strictly increasing captures true.
- RTT median/max 40.973/142.738 ms; exchange width median/max 35.323/135.338 ms.
- Twenty calibration exchanges over 23.014 s, then 41 holdouts; consistency true.
- Observed feasible affine rate interval [-1518.614, 1355.032] ppm; candidate
  absolute drift 1518.614 ppm, conditional on constant affine rate during this run.
- Isolated measurement receiver accepted 70 depth observations; minimum age lower
  endpoint 105.832 ms, maximum upper endpoint 358.728 ms across its observations.
- Transport close cleared those isolated receiver observations.
- Conditional age diagnostics: 202 packets within 500 ms age and 100 ms halfwidth,
  153 rejected or unmapped. The two counters partition 355; they do not mean all
  153 were physically stale. Isolated acceptance 70 is a separate later-stage
  counter and is not interchangeable with conditional-budget count 202.
- Hardware drift limit verified false, production drift configured false,
  receiver guidance eligible false, production capture-age eligibility unknown.

This is useful controlled cross-device timing evidence. It does not justify
installing the observed candidate as a general hardware/production drift bound.
The feasible interval includes network/exchange uncertainty; RTT is not one-way
sensor latency. No heartbeat renews capture age and no old depth becomes eligible
because the transport or Gemini service is available. Original capture-time
calibration and a justified supported-operation drift envelope remain unresolved.

Normal Pi polling was reported restored/paired. Device inspection then found the
old measured phone socket rejected, with 417 depth sends and 61 replies retained
in its diagnostic counts; this was not reported as a still-running stream.
Relaunched normal foreground streaming with the existing Keychain phone bond,
--stream-saved-phone --phone-connection-probe --sector-quality-probe. No enrollment
was generated. New device status showed WSS connected, 115 positive depth sends,
foreground/diagnostic depth true and no local clock failure. New session counters
are distinct and do not extend the previous measured model or bound.

Evidence: tests/ios/evidence/CS-013-Pi-clock-measured-20261018.json. Checked aggregate
count and candidate-magnitude consistency. Repository structure/diff whitespace
checks passed. No code change or unchanged software-test repetition was needed.
No production drift, hardware accuracy, motor/electrical, or guidance acceptance.
Keep the normal phone foregrounded and streaming, with outputs untouched.

Final normal-stream device check: {"status": "Paired \u00b7 WSS connected \u00b7 depth sends: 415", "depth_sends": 415, "foreground_active": true, "diagnostic_depth_enabled": true, "local_clock_guard_failed": false}
