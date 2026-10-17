# CS-028: run the implemented backend in required CI

Status: proposed; exact-head PM authorization pending.

Michael requested verifying/completing CS-028 so Adit can continue CS-029 and
Gavin can integrate deployment. PR #9 already contains Adit's FastAPI endpoint,
bounded JPEG/metadata validation, truthful readiness and original frame lineage.
Independent local verification passed its 19 endpoint tests, 39 shared tests and
real loopback HTTP rehearsal. Its current CI failure was a missing generated-log
blank line; render the log rather than editing or deleting source fragments.

Gap: required CI installed only contract dependencies and skipped tests/backend.
Explicitly run that separate discovery root, install declared backend test
dependencies and run the existing loopback smoke in required
repository-checks. The workflow path is protected; implementation scope and task
requirements are otherwise unchanged. No other component implementation is added.

Alternative: keep manual-only backend verification. Rejected because a green
required check could miss endpoint regressions. Do not weaken checks or report
the default application's lack of a model/worker as ready. The smoke binds only
loopback, uses an ephemeral replay token/generated image, rejects a repeated
frame and terminates the subprocess without storing image/credentials.

Validation: 58 total tests across the two suites, structural validation, generated log verification,
whitespace check and real local HTTP replay. GitHub Ubuntu/Python 3.12 results
must be verified on the updated PR. No real phone/Pi, clock drift, image model,
TLS/WSS, Docker image or cloud deployment is claimed.

Migration: install backend/requirements-test.txt and run both local suites. After
reviewed merge, Adit extends this accepted app for CS-029, and Gavin packages its
single-worker ASGI entry point while waiting for CS-029/032 before full service
acceptance. Existing checks, master plan, contracts and task owners are preserved.
Rollback by a reviewed revert of CI additions; keep manual endpoint
checks required until replacement automated coverage exists. Michael's exact-head
authorization and a collaborator review are required under existing governance.
