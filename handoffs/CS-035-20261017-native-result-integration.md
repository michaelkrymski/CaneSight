# CS-035 native result integration - 2026-10-17

Owner: Gavin (`gmarcialcalleja`). Branch: `task/CS-035-observation-results`.
Checkpoint base: `902d8f4f490a3c261d29aeedac5cfc3bd68d0522`.
Accepted scope base: `a4822f12a2860baf73e039fac4ba4d26b7e2bfc5` after Michael
merged PR #29. Merge checkpoint: 300f193. PR: #28, ready for review after checks.
The generated changelog conflict was resolved by rerendering both immutable
fragments. Expanded task paths and existing runtime progress were preserved.

## Changes

- backend/server.py: absolute CANESIGHT_VISION_WEIGHTS explicitly opts into the
  verified factory/worker. No-model default retained; no automatic downloads.
- backend/sessions.py: native current Pi socket polls at most one worker result.
  Validate schema, duplicate sequence, current grant/socket and exact latest-frame
  provenance. No new result relay queue: one retained worker result and one active
  send. Sends have a 1s deadline and 10ms rechecks; revoke/interrupt/supersede cancels
  blocked sends. Already-sent bytes cannot be recalled; receiver expiry still applies.
  Pi admission clears older generations. Phone/Pi interruption and queue overflow
  discard worker state. Late cleanup cannot discard a replacement socket's work.
  Preserve original expiry/revocation/peer close codes and native auth/Origin/query
  restrictions. No client is allowed to publish vision observations.
- backend/deploy/Dockerfile.vision and its explicit build allowlist: separate pinned
  CPU image with no weights, credentials or scene images in the build context.
- compose.vision.yaml and deployment examples/runbook: opt-in verified read-only
  host weights, bounded temporary settings, existing user/capabilities/resources,
  rollout validation and rollback to the ordinary no-model image/configuration.
- backend/deploy/vision_probe.py: generated replay input over verified HTTPS/WSS,
  original result lineage, phone/other-session isolation, forbidden roles/Origins/
  queries, expiry/revocation; bounded startup wait and optional explicit test CA.
- tests/backend/test_native_vision.py: 13 focused tests including actual configured
  model TLS (opt-in), missing-weight readiness, lifecycle/isolation, old cleanup,
  duplicates/supersession, slow-send cancellation/deadline, overflow and Compose.
- Vision integration docs, three new QA reports, own task runtime evidence,
  new append-only changelog fragment and this handoff. Earlier handoffs immutable.

## Verification actually run

- Windows pinned Python 3.12.14: 13 focused native tests passed, including actual
  model through certificate-verified HTTPS/WSS and missing-weight readiness 503
  despite enrolled ingestion. The full prior 125-test backend run passed with six
  environment-specific skips; subsequent new tests were run in the focused suite.
- Linux Python 3.12 on Vultr: final full backend suite 128 discovered, 122 passed,
  six environment/opt-in skips (including the host-side actual-ML opt-in test;
  the real model is separately tested inside the candidate container).
- Both hosts: 22 vision tests and all 39 shared tests passed. Existing deprecation
  warnings remain. The explicit vision root is not added to protected CI.
- Initial regression tests caught peer/revocation close-code mapping after result
  polling; corrected to preserve the existing connection close reason and reran
  full backend plus targeted TLS/lifecycle tests successfully.
- Private candidate image built on Vultr:
  `sha256:3f41d5a38f4cf04e344277623eed2be06e6798598058698785e47314ebcd975c`.
  Actual pinned CPU runtime/weights checked; five runtime source/manifest hashes
  match this checkout (QA provenance report). Bound to loopback TLS port 18443,
  UID10001, read-only root, all capabilities dropped, 1.5 CPU, 2GiB, 256 PIDs.
- Actual target candidate: 20 generated black 416-square JPEGs at approximately
  1Hz over verified HTTPS/WSS. Median122.358/p95 174.652/max197.754 ms from generated
  upload to received result. Phone and other session isolated; invalid Origin,
  query, absent/phone credentials rejected. Exact capture/frame/boot/mode lineage,
  unknown pedestrian signal, expiry and revocation passed.
- Candidate restart and one-sample re-enrollment/transport probe passed
  (195.351ms). A first immediate probe raced process startup; the probe now has a
  bounded verified-TLS liveness wait. No certificate validation was disabled.
- Observed idle memory 251.2MiB in one Docker sample; not peak-memory evidence.
  Resource caps were inspected. Short generated-input tests do not characterize
  all scenes or sustained worst-case loading.
- Candidate stopped/removed; its private operator environment and test TLS key
  removed. Source snapshot, public evidence and candidate image retained privately
  on the host. Actual public origin remains health200/readiness503; no image,
  proxy, secret or certificate-volume change was applied to the public service.

## Review, rollout and limits

Task is Review, not Done. Michael reviews/merges #28, then the runbook documents
how to promote the reviewed image/configuration and verify the public proxy path.
Record the previous immutable image/config privately for rollback, preserve
operator/certificates, and reenroll devices after restart. Candidate validation
is not a public deployment/promotion claim; production rollback was not exercised
because production was not changed. Existing no-model fallback remains available.

No physical Pi result receipt/camera timing, phone connectivity, inference
accuracy, signal recognition, cross-camera calibration, haptic or electrical
acceptance is claimed. Capture age is not replaced with server timing; the
originating Pi still needs its own frame ledger and capture-age gate. This task
adds no Pi client or authenticated browser feed. Dashboard integration remains
separate. No shared protocol, baseline or governance change was made.
