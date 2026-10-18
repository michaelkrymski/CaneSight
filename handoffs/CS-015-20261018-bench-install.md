# CS-015 signed portrait bench installation

Accepted main: 5dd5fa37009402b7eb7c9dbed3d20eacd4346c90.
Tested implementation: bd99b6cf043122d2d4548f4e97bfa70bbf868409.
PR: https://github.com/michaelkrymski/CaneSight/pull/70.

Personal Team iPhone build passed. Strict deep codesign verification passed.
Apple devicectl installed and launched the separate Mount Check bundle on iPhone
17 Pro Max / iOS 26.6.2. The existing #69 host was neither edited nor replaced.
Signing selection remains in ignored local configuration. No credentials, images
or unique device IDs are included in evidence.

Required CI was green on the tested implementation. The 11 strict Mac XCTest
cases and iOS SDK build evidence are in the earlier handoff; application code is
unchanged by this checkpoint. Checked publishing reruns shared checks.

The operator was asked to place a broad target on each physical side while the
phone stays portrait/rear-forward, record three distinct frames per side and
then test rotation/Stop/background reset. Those observations remain pending.
No physical mapping result, final cane mount, motor side, calibrated source
clock or live telemetry acceptance is inferred from installation or tests.
