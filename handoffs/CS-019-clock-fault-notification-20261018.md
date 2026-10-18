# CS-019 final review follow-up

Branch `task/CS-019-coarse-location`, PR #67. Follow-up base:
`9e81ce6dd749e69b7b68b616ae811957b9f291ca`.

Final manual review found that repeated clock-fault reads could call the purge
hook again. A UI reading the unavailable snapshot synchronously inside its purge
callback could recurse. `LocationContext.readClock()` now returns unknown without
another purge once the clock-fault latch is set. The existing clock-fault test
checks that subsequent reads do not repeat the notification.

Changed only that Swift core file and its existing test plus these new records.
Reran all 13 Swift XCTest cases in the same isolated Swift 6.0.3 Linux container
with complete strict concurrency and warnings as errors: passed. Apple SDK source
still excluded, Xcode/device tests still pending. Shared checked publishing and
current-head CI are reported on the PR. Contract, integration and device blockers
from the initial handoff remain; no end-to-end or hardware acceptance claimed.
