# CS-025 depth integration software preparation

Branch: task/CS-025-depth-integration.
Base: bb00b82c86591f161fa877e2c484acc5a9b220da (accepted main).
Assignment merged in #44. Requirements/dependencies/allowed paths unchanged.
Task remains blocked for real-phone/physical-motor acceptance. No Pi/camera access.

## Changes

- edge/bench.py: bounded 1..20-repeat synthetic left/center/right runner using
  accepted CaptureAgeGate, LocalPolicy, HapticScheduler and PolicyWatchdog.
  Virtual same-clock calibration, explicit replay/synthetic input and simulated
  output; actual channels checked, idle expiry checked, physical_acceptance=false.
- edge/trace.py: new-file/private/outside-checkout metadata JSONL writer, independent
  disk thread, nonblocking 64-record producer queue, 1024 submitted record bound,
  2048-byte record limit, closed field allowlist and finite JSON serialization.
  Drops, disk failure and unfinished shutdown are explicitly incomplete evidence.
- edge/policy.py: optional decision tracing for distinct admitted depth sequences;
  original capture, receipt, expiry and calibrated age interval recomputed after
  software pulse decision. No heartbeat renewal or tick duplicate; classifications,
  channels and acceptance/rejection reason only. No raw distances/images/GPS/UTC,
  URLs or credentials. File I/O never occurs in the policy worker.
- edge/uploader.py: --policy-trace requires --simulate-policy, closes/drains logger
  with bounded wait and prints only sanitized summary. Pi credential format unchanged.
- edge/BENCH.md and README: local runner, future coordinated manual session
  trace procedure, evidence interpretation and exact remaining hardware inputs.
- tests/edge/test_bench.py plus existing native TLS policy transport test: repeated
  mapping, original age bounds, private closed output, bounded blocked-disk queue,
  write failure/incomplete reporting and native age trace/credential exclusion.
- Own task runtime, new immutable fragment and this handoff only. No protected
  paths, backend, shared contracts, real service or teammate ownership changed.

## Tests actually run

- Linux Python 3.12: all 88 edge cases passed. Windows Python 3.14: 87 passed,
  POSIX SIGTERM test skipped. Existing receiver/policy/watchdog tests retained.
- Linux shared discovery: all 82 cases passed (current accepted dashboard/narration
  cases included). Checked publishing repeats repository/shared/changelog/whitespace
  checks; current-head CI inspected after pushing. Edge tests run explicitly.
- Local Windows synthetic runner: three rounds, left=3/center=3/right=3 accepted,
  18 records submitted/written, zero drops/errors, complete=true, final outputs off,
  gpio_used=false and physical_acceptance=false. Trace stays in private local folder.
- Synthetic native certificate-verified HTTPS/WSS phone relay test logs actual
  final-consumer calibrated age bounds <=500ms and excludes both device tokens.
  Enrolled-session/live labels are separate from simulated output; this test is
  not actual phone data. No real motor onset measurement is claimed.
- Logging tests retain original capture deadline and 30ms synthetic age, never
  receipt-age substitution. Queue saturation and disk error become incomplete,
  bounded records; existing file and checkout path are refused.
- Linux tests used isolated Vultr source directory/runtime; no deployed backend
  service/environment was changed and no automated Pi SSH runner was retried.

## Remaining acceptance and next steps

Michael reviews software preparation, then coordinates real-phone/Pi testing only
when camera is available. Need CS-016 phone telemetry and native clock-response
support, actual enrolled source/boot and a measured joint drift budget. Need CS-015
physical orientation/mount mapping and CS-010 power/current/thermal/driver/diode/kill
verification. No GPIO adapter or motor energization is provided by this checkpoint.
Use a fresh uploader boot, 600s paired session and privately transferred Pi-only
0600 JSON; prepare transfer before starting the uploader's 300s wait. Retain
unknown ages if calibration/drift cannot be bounded. No guessed zero drift.

Trace software-command timestamps are sampled after the decision, not physical
onset or independent end-to-end latency. Synthetic virtual times are not measured
phone performance. Incomplete/no-record/dropped traces cannot establish acceptance.
Keep traces out of Git/chat/issues; share sanitized counts only. Silence is never
clear or crossing permission; existing watchdog/frozen-GPIO limitations remain.
Task is blocked, not Done; PM verifies physical evidence.
