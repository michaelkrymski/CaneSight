# CS-044 N01–N05 software failure campaign

Task: CS-044. Branch: task/CS-044-failure-injection.
Base: 0ba7c1ef6a0f65a2529d3f111681b3fb47847ae0 (assignment merged in #50).
No Pi, actual camera, GPIO, physical motors or deployed backend accessed.

## Changes

- qa/failure_suite.py: fixed 25-case N01–N05 campaign with per-gate outcome,
  exact case IDs, test execution durations, numeric metric allowlist and source
  SHA-256 manifest. Failures/errors/skips/missing tests/source changes cannot pass.
  New private report outside checkout, Linux mode 0600; no exception bodies,
  payloads, credentials, GPS, images or device/operator environments serialized.
- tests/failures/test_fault_campaign.py: five new multi-stage attacks against
  accepted final-consumer gate, local policy, simulated scheduler and watchdog.
  Silent source health versus capture expiry, transport/boot reset recovery,
  delayed-capture barrage with healthy heartbeats, replay/mode/identity/future/
  reorder after expiry and malformed wire traffic cannot renew or sustain pulses.
- tests/failures/test_failure_report.py plus package __init__: five reporter
  checks (fixed groups/unique cases, error/skip classification, no private error
  content, numeric metrics/manifest and honest exported-archive provenance).
  Ten fast tests are included by existing shared discovery, no workflow changes.
- qa/failures/README.md and sanitized Windows/Linux JSON reports: fixed case
  matrix, reproduction, original tested hashes and explicit physical limits.
- Own task runtime, new immutable fragment and this handoff. No production,
  protected baseline, shared contracts, credential or teammate-ownership edits.

## Tests actually run

- Full campaign on Windows Python 3.14 and Linux Python 3.12: 25 selected cases
  passed per platform, all N01–N05 groups software_pass, zero failures/errors/skips.
- Shared discovery on both platforms: all 92 tests passed (ten new fast cases).
- Actual local certificate-verified HTTPS/WSS receiver expiry/revocation and phone
  interruption; spawned synthetic inference under authenticated flood/heap/queue
  checks; real policy-lock stall with independent watchdog; accepted gate clock,
  nonce, sequence/epoch, image/body/quota and isolation tests reused by name.
- Reports explicitly software-only with physical_acceptance=false. Windows run
  identifies base HEAD with worktree_dirty=true; Linux exported source has null
  commit/dirty metadata, git_metadata_available=false. Source SHA-256 manifests
  identify the tested bytes and were unchanged during each run. No exact PR-head
  claim is made from a precommit report; report source hashes are reviewable.
- Reporter was corrected to support exported source without inventing Git state;
  final campaigns on both platforms passed after that change. Early synthetic
  test adjusted to catch the accepted jsonschema ValidationError rejection type;
  no production bug or implementation change was needed.
- Linux ran in a dedicated Vultr source directory with pinned test environment;
  no production container/service/environment changed. No rejected Pi runner retried.
- Checked publishing runs repository/shared/changelog/whitespace validation;
  current-head PR checks inspected after push. Full campaign remains an explicit
  command; protected CI unchanged.

## Limits and remaining acceptance

Ready for software review, not Done. Real Wi-Fi interruption, actual phone clocks,
physical motor voltage/onset/off behavior, GPIO freeze and electrical/thermal
acceptance are not covered. Test case elapsed time and allowed scheduling metrics
are software measurements, not capture-to-motor latency or hard-real-time bounds.
CS-025 real-phone/mount/power prerequisites remain pending; Michael owns physical
review and acceptance. Coordinate camera availability before any Pi test and use
manual fresh 600s enrollment with private Pi-only mode-0600 JSON; don't retry the
rejected automated SSH runner. Retain physical kill/hardware timeout requirements.
Unknown data and absent detections never grant clear/crossing permission.
