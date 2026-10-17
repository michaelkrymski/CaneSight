# CS-022 — latest-only Pi JPEG uploader

Owner: michaelkrymski. Branch: task/CS-022-latest-upload.
Base: 690ed12ac266952ac92e7da9cc6f1cbbc8c6f319.

## Change

Add edge/uploader.py and tests/edge/test_uploader.py; replace edge placeholder
README with bench instructions and enrollment/integration requirements. Capture
640x480, letterbox 416-square quality75, nominal 1Hz. One pending replacement
slot and one in-flight JPEG; two original metadata/mapping ledger entries.
Preserve conservative camera capture time in BOOTTIME, original IDs and exact
v1 wire shape. Live credentials only, HTTPS verification and redirect refusal.
Network failure drops without retries; auth/order/ACK problems stop the session.

## Evidence and limits

13 edge tests passed on Windows Python3.14, including synthetic JPEG through
actual backend multipart ingress, not a camera or live network. Shared/backend
checks recorded in the PR after execution. Existing CI does not automatically
discover tests/edge; run it explicitly. No protected paths changed.

Michael separately reported ten 416x416 quality75 JPEGs around 10.7KB on his
IMX708 wide NoIR Pi Zero2W. That supports capture feasibility, not execution of
this new uploader, timestamp validation, real upload or motor behavior.

Pending hardware verification: run README capture-only commands and inspect
all ten age-bound lines. Then enroll a live paired session after CS-029 service
acceptance/deployment and verify real HTTPS upload, offline recovery, token
expiry, overload and end-to-end age behavior. Sender socket timeout does not
bound DNS/trickle-response wall time; queue storage remains bounded.

No WSS, clock reply agent, inference or policy added. CS-023/024 must share this
process's identity, BOOTTIME clock and two-entry ledger and enforce expiry/lineage
even when network stalls. No ready, clear-route or crossing claims. CS-021
metadata remains untouched; PM must accept its independent hardware evidence.
