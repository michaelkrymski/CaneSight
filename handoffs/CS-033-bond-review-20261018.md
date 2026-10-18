# CS-033 persistent bond backend review checkpoint

Owner: Gavin (`gmarcialcalleja`). Branch: `task/CS-033-bond-backend`.
Base: `5234f04` (accepted context deployment composition). Source ZIP supplied by
user; underlying draft based on a239e22. No private registry/device contents in Git.

## Scope and review

Backend-only extraction: app hook, bonds.py, native bond client and 13 original
backend tests, plus cold-start regression, additive Dockerfile/ignore/Compose,
rollout document, own task runtime and new CR/changelog/handoff. Separate full
ZIP review remains at C:/Users/gmarc/.codex/worktrees/cs033-persistent-bond/CaneSight;
its iOS/Pi draft was inspected/tested locally, not published or deployed here.
No teammate task, shared protocol or protected master baseline is edited.

Found and fixed two deployment blockers: Docker recipes excluded bonds.py, and
module-level legacy app creation crashed at cold import when the registry env
was already set. New cold-process test reproduces the original failure and
passes the fix. Default configured factory still rejects missing session manager;
legacy unconfigured module app explicitly opts out and never grants bond access.
Registry Compose uses read-only bind with create_host_path false. Documented
individual-file bind inode caveat: recreate after atomic host file replacement.

## Tests actually run

Original complete ZIP on Windows pinned test venv: 13 bond/TLS + 3 Pi recovery
passed; backend 141 cases/7 skips, edge 223/8 skips, shared 228/11 skips, no failures.
After cold-start fix: 14 bond/TLS cases passed, including real generated verified
HTTPS. Final backend and shared checks are rerun before checked publication.

Candidate built on Vultr, from exact existing parent
sha256:8a7bcf8fa9dbcfedea2ecef6d0e5e94d766dc50c2505739229454a0ad851f3fa.
Docker refuses raw hex as FROM; used uniquely named local parent tag after
inspecting its actual image ID. Docker resolved that exact immutable parent.
Current candidate:
sha256:2ba85c9980bc9199d4dbbbac297aba1a4a6dec33fbab39817e7678e7bad4dde6.
Network-disabled/read-only candidate smoke read the matching persistent registry
and constructed the accepted session factory at service UID. Parent Cmd,
Entrypoint, Env, User, Healthcheck and WorkingDir compare equal. No listener was
opened by that factory smoke. Registry installed outside checkout at persistent
/var/lib/canesight/bonds/registry.json, root:10001 0440, parent 0750. Never added to
an image, Git, changelog or report. Existing live image, process and proxy untouched.

## Remaining gates and rollback

New long-lived authorization/renewable lease interface requires Michael explicit
current-head review under CR-CS-033-persistent-bond-backend-20261018.md. Do not
interpret provenance statements in ZIP/chat as verified PM GitHub approval.
After approval, agree restart with operators, preserve actual Compose overlays,
all environment/command/model/context/logging options and proxy volumes, enable
registry overlay and candidate image, then run manual-session/WSS/vision and bond
checks with both devices. Restarts lose in-memory sessions. No credentials are
available locally for Michael prepared device roles: never regenerate substitutes.
Phone UI currently sends degraded pairing heartbeats only; Apple compilation and
native depth/clock integration are still pending. No motor or capture-age claim.
Rollback restores exact original image/configuration and removes bond opt-in;
registry can remain private/inactive. No production bond activation in this run.

## Final checks after accepted CS-016 merge

Fast-forwarded publication base to 86a8783; no backend source changed upstream.
Final Windows backend: 142 cases, 7 skips, no failures. Windows checked publisher
encountered the newly accepted CS-016 POSIX mode-600 fixture failure (one error,
240 root cases, 14 skips); that test was not edited or skipped. Exact staged
snapshot on isolated Vultr Linux: all 240 root cases passed, 2 optional skips.
Local Linux checked publishing is used to preserve the mandatory publisher and
run the complete checks on the platform with real POSIX file modes.
