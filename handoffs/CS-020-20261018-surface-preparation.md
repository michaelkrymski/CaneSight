# CS-020 surface-check preparation and pause

Accepted base: 0925c3af5d83d7ca86c091643f8e6fd5b5b7d5c9.
Branch: claim/CS-020-michaelkrymski.
Assignment PR: https://github.com/michaelkrymski/CaneSight/pull/90
Initial assignment commit: ff4cfcf68781ac09648458c8bc6d21bf2268a747.

Before implementation, verified actual GitHub PR author michaelkrymski and the
initial diff: only owner/status/branch in CS-020 plus its new handoff, changelog
fragment and generated log. Main task unowned and only this pending CS-020 PR.
Static requirements/dependencies/allowed paths unchanged. PM self-assignment
exception applies; no reassignment or protected amendment.

Added separately selectable SurfaceUITests for glass, dark object, indoor glare
and blocked view. Tests use normal capture controls and five sequential UI reads
of distances/Unknown, coverage reasons and status; reject nonpositive/nonfinite
numeric readings and listed permissive phrases, then verify Stop-to-Unknown.
Material names are requested conditions, not automatic classification. UI snapshots
are not synchronized/independent captures, source-age, accuracy or latency evidence.
No production app or sensor thresholds changed. Added procedure and sanitized
preparation evidence with every physical condition explicitly not tested.

Actual verification: Xcode 27.1 signed physical-iOS build-for-testing passed;
no UI tests executed. 15 strict Mac depth XCTest cases and 11 strict Mac mapping
cases passed. Exact bench depth dependency remains pinned/unmodified at
5f73dbf33ba9b2395f27b429c22344d41fb6162a. Shared checks run by publisher. No
physical sensor result, imagery, unique device/signing ID or GPS in repository.

Michael reports glass, dark and glare materials available, but has not staged or
confirmed a case. At the glass-ready prompt, he explicitly paused: CS-016 is top
priority and another chat is using the phone. No surface test was launched. Do
not install, launch, capture or otherwise contend with that phone session.

Changed files: ios/MappingBench/UITests/BenchUITests.swift,
tests/ios/surface_checks/README.md,
tests/ios/evidence/CS-020-surface-preparation-20261018.json,
tasks/CS-020.json, this handoff, new changes fragment and generated log.

Resume: wait for Michael to release the phone and authorize resuming; stage and
name one material at a time, confirm portrait rear-forward position and approximate
or measured distance/illumination, run only its selected SurfaceUITests method,
and record actual sanitized JSON results/failures. Leave unavailable/unconfirmed
materials untested. Current local build: /tmp/canesight-cs020-build; compile log:
/tmp/canesight-cs020-final-build.log. Local signing config is ignored and not
published. If a test bundle is produced later, retain its private camera attachments
outside Git. The pending glass-ready prompt must not be treated as confirmation.

Task blocked and PR remains draft. CS-017 integrated recovery remains a full
acceptance dependency. No final-mount, range accuracy, capture-age, network/Pi,
motor/electrical, road-use or Done claim. Independent implementation review required.

Accepted main advanced with CS-037 during preparation. Merged unchanged accepted
main 0fa978dc2dc62ee697f900fd1c0b352514a95e0e before publishing; no phone/sensor/test source overlap.
