# CS-013 measured receiver harness

Owner Michael; claim/CS-013-michaelkrymski, PR #97; base c703c1ee2034344dac8fdda53796244256cd9f8b.
Add isolated unchanged CaptureAgeGate to Pi characterization observer only after
20 calibration +20 separate consistent holdout exchanges. Candidate derived from
causal affine slope interval, no guessed/zero live default. Gate requires fresh
own nonce/reply calibration, ready heartbeat, post-readiness capture; independent
expiry ticks and actual transport-close clearing are recorded. Six software tests
passed, including synthetic real-gate admission and close clearing. They do not
prove physical clocks. Actual hardware run pending current fresh-role enrollment.

No production receiver change, motor output, schema, master plan, CS-017/CS-030
source/task or ownership change. Normal app remains unpaired. Numeric bench age
results remain conditional on stable affine clock model in sampled environment;
no arbitrary future hardware drift guarantee. Detailed method/limits in
CLOCK_CHARACTERIZATION.md. This extends own host/verification task as explicitly
requested by Michael; current phone lifecycle evidence remains separately actual.
