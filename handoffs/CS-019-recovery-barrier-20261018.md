# CS-019: finish local location recovery review

- Branch: `task/CS-019-coarse-location`; PR: https://github.com/michaelkrymski/CaneSight/pull/67.
- Starting head: `5d311229a183b35176c10bdf33b6553c0c52fbfd`.
- Accepted main: `5dbb6adc6f7c8984e1beb624fc7c8fe1a4cdfafa`.
- Main was merged without changing teammate files; generated log conflict resolved
  using the renderer. Existing work and immutable records preserved.

## Changes and verification

Provider failure now advances the original-fix capture barrier, rejecting a
previously unseen fix captured before the error. Permission/activity/consent
transitions establish that barrier before synchronous purge hooks run, preventing
reentrant cache restoration during recovery. Add two regressions; update guide,
task runtime and source-hashed evidence.

All 15 portable Swift XCTest cases passed in official Swift 6.0.3 Linux with
complete strict concurrency and warnings as errors, `--jobs 1`. Checked publisher
runs repository, root unittest, generated log and whitespace checks; verify CI on
the published head. Conditional Core Location/UIKit source is excluded on Linux.

## Native evidence and next steps

Michael's draft PR #69 at `af55732f8fbe0423b8f66a4f73e584c5906802f8`
reports 13 macOS tests, an iOS SDK package build and compiled simulator test bundles
for the starting GPS commit. This is attributed earlier-commit evidence. The
phone preview explicitly has GPS sharing off and does not establish authorization
or provider lifecycle acceptance. Current-head Apple build still required.

No GPS serializer, endpoint, remote receiver or precise location logging added.
The existing proposal `decisions/CR-CS-019-location-context-contract.md` describes
the missing reviewed shared/backend work; v1 explicitly excludes GPS. Michael
must arrange the separate contract/scope review before enabling GPS transport.
Merging this local package or its proposal does not approve a new wire contract.

After review: update the host dependency pin through CS-013, wire the local opt-in
and scene callbacks with CS-016, verify real-device default-off/denied/restricted/
reduced accuracy/Settings revocation/background/failure/resume behavior, then
validate an approved transport and receiver. Until then CS-019 remains blocked
for end-to-end acceptance. No Pi, camera, GPIO, motor or remote-runner access used.
