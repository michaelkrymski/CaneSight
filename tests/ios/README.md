# CS-014 verification boundary

The executable Swift tests live with their local package under
`ios/DepthSectors/Tests/CaneSightDepthTests/`, so SwiftPM resources stay inside
the package. They are authored but have not run on this Windows host.

Run `python tests/ios/validate_depth_fixtures.py --syntax` after installing
`tests/ios/requirements-audit.txt` for a **source/fixture audit only**. It checks
seven original CC0 synthetic fixtures and optionally Swift grammar; it neither
compiles Swift nor evaluates the authored expected numerical outputs. A report
may be saved to a new filename with `--report`.

The root Python suite does not execute XCTest. On a Mac, run
`swift test --package-path ios/DepthSectors`, then separately build the iOS ARKit
target/host in Xcode. Physical support/signing, mount orientation, accuracy and
lifecycle checks remain pending CS-013/015/017/020. See the package README for
the exact source-time, unknown-value and coordinate-space contract.
