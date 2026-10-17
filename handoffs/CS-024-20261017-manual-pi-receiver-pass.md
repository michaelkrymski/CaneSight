# CS-024 real Pi receiver checkpoint passed

Base: 6a386675d24e88082fce9f3e063f101098c1e7bd.
Branch: task/CS-024-pi-receiver-expiry; draft PR #32.
Exact manually tested code snapshot: 17441cee512bb29ae6ad5bd327706a45c0a8f107.

## Execution and evidence source
The human prepared a separate /home/interfere/CaneSight-PR32-test checkout
and dedicated system-site-packages venv, reported camera/receiver imports OK
and the exact snapshot SHA. Existing /home/interfere/CaneSight-CS022 was outside
the documented test commands. This was manual execution; the rejected automated
SSH runner was not retried. Michael authorized camera/receiver testing;
motor and GPIO testing stayed out of scope.

After the public backend recovered following a VM reboot, a fresh waiting boot
was enrolled for 600 seconds with the explicitly unconnected bench phone
counterpart. Only the Pi credential was delivered privately through the human's
SSH stdin transfer. The human reported owner/mode interfere:600.
Operator DELETE subsequently confirmed revocation of the completed test session.
No credentials, session/boot IDs, images or phone credentials are included here.

## Human-supplied final summaries
Vision accepted=20; rejected=0; expired=0; unavailable on exit
Accepted=20; stale=0; failed=0; replaced=0

All 20 uploads were acknowledged and all 20 corresponding vision results reached
the same Pi process and passed its original-frame lineage and capture-age gate.
Reported capture ages span 115-254 ms. Frame 1's pasted line was truncated;
frames 2-20 were 416-square JPEGs, 12228-12326 bytes. These are console metrics,
not saved images or a complete capture-to-result latency measurement.
The human supplied summaries, not an independently captured full log or shell
exit status; no additional exit code is asserted.
Backend inspection after the run confirmed the expected pinned image
sha256:8a7bcf8fa9dbcfedea2ecef6d0e5e94d766dc50c2505739229454a0ad851f3fa,
running/healthy and public health alive.

Sanitized report: tests/edge/evidence/pr32-pi-receiver-20261017.json.
This supersedes the network block for this receiver checkpoint.
Earlier handoffs remain immutable records of prior observations.

## Validation and remaining work
Runtime source is unchanged from the tested snapshot; this update adds evidence
and corrects current runbook/task status. Previously run: 26 edge tests passed on
Windows/Linux Python 3.12; Windows backend 128 discovered/121 passed/seven skips.
Checked publishing runs shared/repository/changelog/whitespace checks again.

Zero expirations during continuous fresh input is expected; this physical run
does not independently test blocked-read idle expiry or failure injection.
Those paths have separate synthetic certificate-verified TLS tests. libcamera
sensor delays remain unverified, and the nominal ticker is not hard real-time.
Phone bindings/clock drift/depth availability, hazard/motor policy,
detector accuracy and electrical validation remain unestablished.
CS-023 scheduler remains unassigned/backlog on accepted main. Full CS-024 policy
integration still depends on it; task stays blocked and PR remains a draft.
Michael may accept this receiver checkpoint without marking full CS-024 Done.
