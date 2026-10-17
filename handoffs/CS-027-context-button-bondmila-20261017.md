# CS-027 context button software checkpoint — 2026-10-17

Owner: bondmila. Assignment PR #49 verified merged.
Initial base: 5ccd4828783ae19bec850a6bb85e02a88f272521.
Integrated accepted base: 0ba7c1ef6a0f65a2529d3f111681b3fb47847ae0.
Branch: task/CS-027-context-button. Software ready for review; task remains blocked
on real button and application integration, not Done.

## Changed files

edge/buttons.py, edge/context_client.py, edge/CONTEXT_BUTTON.md;
tests/edge/test_buttons.py, tests/edge/test_context_client.py;
CS-027 runtime fields, new changelog fragment, this handoff and generated log.
No protected path, shared contract, other task or existing uploader/policy change.

The coordinator takes bool level events and an original latest-frame supplier.
30ms debounce, initial release-to-arm, no hold repeats, one outstanding job;
second press/manual/health/consent/hazard cancellation. Ten-second minimum request
interval survives failures/cancellation/rearming. An independent timer rejects
expired input and results using original capture+8s; callbacks/poll/reap time do
not renew age. Clock fault/reversal or failed cancellation latches unavailable.
Network work stays in a killable child, separate from camera and motor policy.

HTTP client composes accepted CS-039 multipart contract, Pi-only grant, exact
session/source/boot/mode/frame/request correlation, HTTPS and hostname/certificate
verification, no redirect/proxy/retry, bounded reply and closed uncertain labels.
No raw model prose or motor/speech policy interface. Gemini/operator keys are
never required on Pi or in this implementation. No credentials/private images
were saved; test JPEGs and grant strings are generated/synthetic.

## Tests actually run

- Pinned isolated Python 3.13 test environment (backend/requirements-test.txt).
- New coordinator/client roots: 28 tests passed (19 button, nine client).
- python -m unittest discover -s tests/edge -q — 116 passed after accepted-main
  integration, including existing uploader/receiver/policy/watchdog regression.
- python -m unittest discover -s tests -q — 82 passed. Publisher reruns root tests,
  repository validation, generated changelog and whitespace checks before push.
- git diff --check passed.
- Actual spawned child delivery and hung-child kill/reap tested. Independent
  expiry tested without further input/capture calls. In-process HTTPS-scheme
  adapter sent real multipart through accepted sessions/context routes, using a
  synthetic provider; phone credential rejected and readiness remained 503.
- TLS configuration verifies mandatory cert/hostname checks; not a new real TLS
  deployment test. No real camera/GPIO/button, cloud Gemini, physical audio,
  electrical or latency certification. No PM acceptance inferred from unit tests.

## Limits and next actions

Review the software checkpoint independently. Configure the deployed opt-in
context factory through its deployment owner before real requests; existing
production packaging is not changed. Coordinate same-process latest-frame and
input adapter integration with CS-025 owner, preserving source/boot/BOOTTIME and
capture metadata. Physical pin/pull-up/wiring and debounce verification requires
actual hardware and prerequisites; no GPIO driver/activation was introduced.
CS-040 remains draft PR #41; CS-018/040 own accessible audio and local preemption.
Stop local audio independently before waiting for network cancellation.

Current required CI discovers root/backend tests but not the separate edge root.
The edge suite above was explicitly run locally. Adding a required edge CI job
would be a protected workflow amendment; none was made or bypassed here.
