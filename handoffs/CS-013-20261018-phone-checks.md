# CS-013 operator-confirmed phone checks

Main base: 5dd5fa37009402b7eb7c9dbed3d20eacd4346c90.
Phone source: 3e9e781cdb427cc7760cfcd47baeb74f8bc4cff7 plus local signing configuration.
Published signing config: cf64ad8d2c610f448d297375915384ccc29f26ec.
PR: https://github.com/michaelkrymski/CaneSight/pull/69.

Michael reported all three depth-image column values changing except for very
close objects. Asked separately whether Stop clears all values to Unknown and
whether lock/unlock or background/return clears old values and waits for new
captures, he answered "Both checks pass". Retain these as operator-reported phone
observations on iPhone 17 Pro Max / iOS 26.6.2. No video or measured timing trace
was supplied. Close-range behavior is not a certified sensor range or clearance.

Signed build, strict signature verification, installation and subsequent launch
were independently confirmed through Apple tools. Prior 64 Swift tests, four
backend conformance cases, four native SDK builds and simulator test-bundle builds
remain valid; this checkpoint changes evidence/status/docs only. Simulator tests
were not executed. Shared checks run through checked publishing.

The CS-013 local host is ready for independent review, not Done. Review and accept
the exact pinned draft package inputs and integration order before merging #69.
CS-001 inventory is unchanged; no full-system readiness is asserted. Source-clock
calibration, physical-side mapping, live WSS/paired Pi and the remaining CS-014,
016, 017 and 019 acceptance gates are separate. No teammate task/source changed.
