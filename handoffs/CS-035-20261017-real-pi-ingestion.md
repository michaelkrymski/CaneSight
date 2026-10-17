# CS-035 real Pi ingestion evidence — 2026-10-17

Base: 2af3150dfaeb0efa5ce37f26d66e552fe8147f15.
Branch: task/CS-035-public-rollout; PR #30.
Michael authorized access/camera tests through the human operator.
No code, branch, ownership or task requirements changed on Michael's Pi.

## Inspection and tests actually run
Pi checkout /home/interfere/CaneSight-CS022 was clean on
task/CS-022-latest-upload at 66627a64314388e182cce7895c59041016c1f6ce.
Read repository instructions, master plan, CS-021/022 tasks and uploader handoff.
No camera/uploader processes were found before tests.
Python 3.13.5; Picamera2/Pillow present.

Capture-only: ten 416-square JPEGs, 12245–12336 bytes, reported ages 120–277 ms;
exit 0. Then a new uploader process was enrolled for 600 seconds and only its
Pi credential transferred over SSH stdin into an atomic, user-owned mode-600
~/.canesight-session.json. Operator credential remained in private Vultr config;
the bench phone counterpart was unconnected. No credentials are in this evidence.

Real HTTPS upload: 20 captures, Accepted=20, stale=0, failed=0, replaced=0;
uploader and SSH exited 0. Checkout remained clean after both tests.
Sanitized aggregate evidence: qa/vision/pi-camera-upload-20261017.json.
Only console metrics were retained; no image files were saved by the tests.

## Limits and next steps
libcamera warns that sensor static properties/delays are unavailable and uses
unverified defaults. Reported age bounds therefore do not establish calibrated
physical capture timing. HTTP ingestion ACKs do not establish fresh inference.
This uploader does not implement native WSS reception. A reviewed Pi receiver
sharing this process identity/clock/ledger is needed for real inference receipt
and receiving-side expiry tests. Phone, haptics and electrical behavior untested.
No task ownership takeover or Done claim; Michael accepts hardware evidence.
