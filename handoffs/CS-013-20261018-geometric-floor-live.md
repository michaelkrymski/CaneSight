# CS-013 — final floor filter live observation

Branch `claim/CS-013-michaelkrymski`; base
`c34520b60e85d6cd4b5efe18c94659ee236208c4`. Local only.

Final build succeeded and strict signature passed; installed and launched using
saved Keychain phone bond. Operator confirmed slow floor/furniture sweep complete.
Initial live snapshot: one current ARKit classified floor; 7342 high-confidence
pixels excluded; mask runtime 52.885750 ms. Raw L/C/R 3.345703/2.097656/1.304688 m
became 3.345703/3.009766/1.620117 m. First 24 sends all numeric. Floor rejection
executed on real frame data; this does not independently calibrate classification
or obstacle range and does not establish guidance eligibility.

Five followup snapshots: paired/WSS/live portrait; sends 75->116 across 8.636902 s
(~4.747 Hz). Scene now reports left/centre ~0.15 m and right Unknown in both raw
and filtered summary. One floor model retained but no pixels near it were removed;
no substitute distances invented. Scene identity/phone covering not independently
verified. Local guard passing, maximum capture delta 333.788292 ms. Mask runtime
6.056–6.526 ms in the followup scene. Latest send count 116, 25 all-three numeric
cumulative; do not claim latest scene all numeric or chair correctly detected.

14 PreviewState tests and 3 production-processor harness cases passed during this
implementation. Local repository validation passed. Physical near-floor/low-obstacle
accuracy and full L/C/R target demonstration remain open. No production drift,
receiver clock acceptance, motor operation or GitHub contact. App left foregrounded
and native streaming using existing private bond, no helper/test runner required.
