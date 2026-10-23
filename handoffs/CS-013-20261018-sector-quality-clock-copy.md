# CS-013 sector quality investigation and Pi source copy

Base c34520b60e85d6cd4b5efe18c94659ee236208c4;
claim/CS-013-michaelkrymski. Existing local work retained. No GitHub contact,
fetch/pull/push or PR. No saved enrollment regenerated or motor control changed.

Michael reported an earlier completed Pi receiver run: 71 depth packets / reported
4.77 Hz, 15 heartbeats, all tracking normal and captures increasing, one packet
with all three numeric sectors. Capture-age false, drift unknown and no motors
activated. That run ended before the Pi reboot. Its null-packet coverage fields
were not retained, so its precise rejection cause cannot be reconstructed.

The phone was reconnected using its existing device-only Keychain bond to the
newly polling Pi process. Read-only diagnostics were added to normal app capture,
connection probe and send wrapper: exact portrait ROI confidence histograms,
sector rejection tallies and successful native-send numeric/null counters.
No confidence threshold, coverage minimum, sample threshold, percentile, mapping
or wire schema was changed. Raw depth values/images and identifiers are not
recorded in this evidence. No calibrated age/clock readiness is asserted.

A new live interval reproduced left Unknown: 131/204 processed captures failed
coverage, zero failed the 32-sample minimum. Example left valid high confidence
2862/12032 = 23.8%, below 25%; raw depth samples were positive/finite and confidence
bytes valid. Center/right remained numeric. The actual completed wire packets
agreed: 71/202 numeric left/all-three, 202/202 numeric center/right. Thus measured
nulls in this interval follow the unchanged confidence gate rather than being
lost during conversion/serialization. Existing pinned processor/mapping inputs
were not modified. This does not prove the cause of the prior unlogged 71-packet
run or identify whether bedding material, distance, angle or another scene factor
caused low ARKit confidence.

Michael said the phone had been on the bed, then held it portrait upright with
rear cameras facing across the room. In a fresh 36.700268-second window:
175/175 completed outbound packets had numeric distances in all three sectors,
rate 4.768358 Hz, with zero coverage/sample/unavailable rejections. Mean valid
high-confidence coverage was left 80.5159%, center 88.6029%, right 67.6873%.
No threshold changed. This supports placement/view-dependent confidence as the
explanation for the observed current nulls; no general sensor accuracy claim.

Local elapsed clock observations in this new phone process reached 39,613,
maximum media/continuous elapsed discrepancy 0.158333 ms, no guard failure,
maximum observed original-capture-to-local-loop delta 259.489375 ms. These are
local observations, not a cross-device drift bound or hardware capture-time proof.
Zero completed clock replies were observed. Old recorded eight-exchange Pi RTT
median 41.049 / max 145.109 ms belongs to the earlier boot/test and was not reused
as a new bound. Freshness eligibility remains unverified.

Added tests/ios/pi_bond_clock_probe.py using the existing saved Pi bond and the
existing affine characterization/reference parser. It performs bounded matched
exchanges with separate calibration/holdout, renews only that existing bond,
discards models on session/peer changes and never uses camera/GPIO or configures
production drift. A new process epoch is not new enrollment. The existing Pi
poller must be paused to avoid two competing Pi identities. Procedure is
PI_BOND_CLOCK_BENCH.md. Actual Pi execution is pending and MUST NOT be reported as
measured evidence. Any future feasible rate interval is conditional on the finite
run's affine assumption, not a general oscillator/sleep drift guarantee.

Checks: signed Apple SDK build and strict signature/install/launch passed. Ten
strict pairing/send-counter cases passed. Initial system-Python clock test lacked
anyio; rerunning with the existing local project environment passed all seven
clock-model/binding cases. Archive extraction/import check and shell syntax check
passed; structural validation/diff whitespace passed. No fake clock or source
case is described as physical clock evidence.

Michael then explicitly requested copying the procedure and dependencies to
/home/interfere/canesight-local-demo/clock-bench/ without starting the test or
copying credentials. Direct passwordless SSH was rejected (publickey,password);
computer-use access to macOS Terminal was blocked by tool safety rules. No bypass
was attempted. A source-only archive and one-command SSH transfer script were
prepared. Michael ran it in his own Terminal and confirmed "Copy verified". The
script extracts only allowlisted source/docs/schema and checks a code SHA-256
manifest on the Pi; it contains no test-start command or credentials. Thus remote
copy verification is operator-confirmed, not a separate agent SSH inspection.

Destination root: /home/interfere/canesight-local-demo/clock-bench/
- tests/ios/PI_BOND_CLOCK_BENCH.md
- tests/ios/pi_bond_clock_probe.py
- tests/ios/pi_clock_characterization.py
- tests/ios/clock_characterization.py
- tests/ios/pi_phone_depth_probe.py
- tests/ios/pi_phone_transport_probe.py
- supporting backend/*.py, edge/*.py, shared/protocol/v1/reference.py and schema
- code-manifest.sha256 (36 source/document/schema files plus this hash manifest)

No test was started, no credential was copied, and no Pi service or motor state
was changed by the transfer script. Phone is left foregrounded and diagnostic
streaming enabled; do not relaunch merely to inspect more counters. Actual Pi
receiver/matched clock results await separate execution authorization/readiness.

Final check found native WSS rejected; relaunched the saved-bond stream (not a Pi test). Latest device state: {"status": "Paired \u00b7 WSS connected \u00b7 depth sends: 57", "foreground_active": true, "diagnostic_depth_enabled": true, "depth_sends": 57, "clock_replies_sent": 9, "local_clock_guard_failed": false}
