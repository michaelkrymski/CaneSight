# CS-027 operator GPIO21 evidence — 2026-10-18

Branch task/CS-027-context-button; base 33b5a7d7ab8a71271b4cbeabcee531c7271c9480.
Accepted owner bondmila. PR #58 remains draft, dependency #41 remains draft.

Operator pasted input-only observer console output and completed JSON from Pi
combined checkout 6dfda420ff5fbf5b4377f3608bda8a22a25c5ea5. Report retained in
tests/edge/evidence/CS-027-gpio21-operator-report-20261018.json with attribution;
no SSH observation, host path, credentials or device identity recorded.

Initially LOW, seven HIGH/LOW pairs; JSON counts seven rising/seven falling raw
edges and 2965 samples, complete true/outcome finished. GPIO input used; no
context request, camera, backend, audio or motor GPIO. gpio_input_verified stays
false for PM review. This confirms reported operation of the raw adapter only:
it is not application debounce/cooldown/request cancellation or electrical proof.

Changed own task runtime, new evidence/handoff/changelog fragment and generated
log only. Verified JSON counts/flags and source commit's adapter presence. No code
changes or new local hardware test; previous software results remain separate
(164 combined edge and 71 context tests). Checked publisher runs shared checks.

Next: from this same Pi combined checkout, run speaker_bench --speak with
--bluetooth-recovery and a new private report. Full physical-button/context/audio
path still requires an eligible real phone/backend session; #68 says phone depth
not ready. Keep both PRs draft; PM independently reviews physical evidence.
