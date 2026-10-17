# CS-041 authenticated read-only viewer checkpoint

Task: CS-041. Branch: task/CS-041-session-health-dashboard.
Accepted main base: 89e15adab322ea299915f193cb6c9c6626d20739.
Main merged normally into this task at 7eed0e8bceaa199ba9dab3a5b20df619327815a8.
Before publication, also merged updated main 73871ef (CS-036 assignment only)
without conflicts; no CS-036 ownership or implementation changes made.

## Changed files and behavior

- backend/telemetry/live.py: separate opt-in factory with bounded metadata
  projection, operator-issued session-only viewers, hashed token bindings,
  Secure/HttpOnly/SameSite=Strict host-only cookie, exact TLS Origin checks,
  four reads/second limit, 16 viewers, native expiry/revocation cleanup.
- backend/telemetry/viewer.py: verified TLS operator CLI writes only a separate
  viewer file outside the checkout, exclusively, private Linux mode, no secrets
  printed. The existing Pi enrollment file format is untouched.
- backend/telemetry/Dockerfile.dashboard and adjacent allowlist ignore file:
  optional reviewed base extension, static assets and new factory only. Internal
  readiness port is 18083. Existing deployment/proxy files are unchanged.
- dashboard/model.js, app.js, index.html, style.css, README.md: retain eight
  local synthetic scenarios; separate authenticated metadata UI preserves actual
  mode and lineage, clears credentials after login and state after failures/logout.
  Packet activity is separate from capture age. No real images, GPS, detections,
  distances or crossing verdict are projected. Capture ages stay unknown because
  cross-device clock bounds are not established. Offered vision is not Pi receipt.
- tests/dashboard/model.test.mjs, test_live.py, test_viewer_file.py and updated
  fixture footer assertion: scoped auth, native route isolation, verified HTTPS,
  native browser-Origin denial, bounded bodies/polling/state and private output.
- decisions/CR-CS-041-dashboard-viewer-interface.md proposes Michael review of
  this interface before public activation; protected/shared/native files unchanged.
- tasks/CS-041.json changes runtime status/evidence/blocker only.

## Tests actually run

- Node built-in runner: 16 passed.
- Dashboard Python: 18 passed (5 fixture HTTP, 9 auth/projection/TLS, 4 issuer).
- Shared/dashboard discovery: 59 passed on Windows Python 3.14 and Linux 3.12.
- Backend regression discovery: 128 cases. Windows 121 passed, 7 skipped; Linux
  122 passed, 6 skipped. Optional dependency/platform skips reported as skips.
- Linux tests ran in a separate source directory on Vultr using the existing
  pinned test environment. No production service/environment was changed.
- Optional container build passed from locally verified reviewed runtime image
  sha256:8a7bcf8fa9dbcfedea2ecef6d0e5e94d766dc50c2505739229454a0ad851f3fa
  (local tag canesight:cs035-merged-2af3150). A raw image ID cannot be a Dockerfile
  FROM reference; verified the local tag ID before the successful build.
  Network-disabled/read-only/capabilities-dropped smoke confirmed factory import,
  static assets, snapshot route and readiness port using synthetic credentials.
- Browser checked final fixture and explicitly labeled SYNTHETIC UI HARNESS:
  login, actual replay mode, one backend-active source, both capture ages unknown,
  hidden boxes, missing distances, empty credential input, no desktop horizontal
  overflow; disconnect clears session/source/model/frame/events and availability.
  No real credentials or images were loaded. This is UI evidence, not public
  activation. Earlier handoffs retain their separate fixture/mobile evidence.
- Repository/changelog/whitespace validation runs through checked publishing;
  current-head GitHub checks are inspected after the push.

## Limits and next steps

Software ready for review, not Done. Michael reviews the proposed auth interface
and current PR head before any public activation. Follow dashboard/README.md for
reviewed container/proxy setup and separate private viewer issuance. Preserve
existing TLS/private upstream/resource controls. Restarts invalidate in-memory
sessions and require fresh enrollment. True capture ages need independently
reviewed clock bounds; the metadata view does not invent them. No phone
connectivity, Pi receipt, model accuracy, hardware, motor or GPIO validation is
claimed. No production restart or automated Pi runner was attempted.
