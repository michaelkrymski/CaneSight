# CS-033 final image and CI correction - 2026-10-17

Owner: Gavin (`gmarcialcalleja`). Branch: `task/CS-033-vultr-deployment`.
Base: `beda5ec0df50aa567f6b5137791019b45e10759b`.
Accepted main: `56cbd7aa5b14c7db011c98a994909421f2989825`.
PR: https://github.com/michaelkrymski/CaneSight/pull/11.

This supplements `CS-033-20261017-authenticated-deployment.md`; its acceptance,
configuration, laptop fallback evidence and limitations remain applicable.

## Final immutable image

The final committed snapshot was archived to the existing Vultr runtime folder,
preserving its private operator file, configuration and certificate storage.
The rebuilt image is:
`sha256:c374fd16ab6a57ba17c775cbf6c01c0a06443b35c2e7ef206bf6f3c2c3c77e14`.
This supersedes the previous image identity in the earlier handoff. A hash map
comparison verified identical packaged runtime Python sources in backend/ and
shared/ between the previously running container and the final image.

All **115 Linux backend/deployment tests passed again** with this exact image
and the pinned Caddy integration enabled. The final immutable image was selected
in the private host configuration and the backend recreated. The complete public
HTTPS/WSS/JPEG session probe passed afterward: role separation, matching frame
acknowledgment, duplicate/expired credential rejection, disconnect invalidation
and reconnect replay rejection. No credential value or private input was printed.
Health remains 200; readiness remains truthful 503 (model/worker unavailable).
Caddy and its trusted certificate were preserved. The laptop fallback had already
passed twice against identical runtime Python sources with production stopped,
then restored. Prior Windows/shared tests remain valid; no runtime source code
changed in this correction.

## CI correction and scope

The first publish passed repository checks and security scanning, but governance
identified an unintended task metadata change. Reading UTF-8 JSON using the
Windows default text encoding had corrupted the elapsed-window dash. The field
was restored from accepted main using explicit UTF-8. All non-runtime task fields
were compared to main and match. No requirement, protected file or guard changed.

Changed files: only CS-033 runtime evidence plus baseline metadata restoration,
this new handoff, a new append-only changelog fragment and generated changelog.
The checked publisher reruns repository/shared/changelog checks before pushing.
Current-head CI is inspected afterward. No merge, main push or force-push.

Review remains required. Actual YOLO/worker integration, real device enrollment,
full-host outage coverage and hardware acceptance are not claimed. Michael owns
review/merge. The final deployed digest above is the current runtime identity.
