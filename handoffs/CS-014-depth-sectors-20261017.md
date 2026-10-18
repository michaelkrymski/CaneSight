# CS-014 depth-sector source preparation

- Author: aditsangani (AI-assisted)
- Branch: task/CS-014-depth-sectors
- Starting base: 0a1a1cf9c15b8c7b126fe7b4e8c51870ef454545
- Integrated accepted main before publishing: 1dcead2 (CS-016 assignment only).
- Assignment: claim PR #60 merged, CS-014 owned by aditsangani.
- Human explicitly requested code now and Xcode/device verification later. CS-013 remains an unchanged dependency.

## Changed files

- ios/DepthSectors/Package.swift, .gitignore: standalone Swift 5.9 local package; separate depth and Apple adapter products, with no third-party Swift dependencies.
- Sources/CaneSightDepth/DepthSectors.swift and DepthBytes.swift: finite/positive and confidence filtering, independent coverage/sample gates, nearest-rank percentile, per-image-column unknowns, explicit mode/source time, bounded geometry/strided planes and stateless behavior.
- Sources/CaneSightDepthARKit/ARKitDepthAdapter.swift: conditional Apple buffer reader and iOS raw sceneDepth adapter with support/tracking/map/format/dimension/lock checks and owned samples.
- Tests/CaneSightDepthTests/: fifteen authored XCTest methods and seven original synthetic CC0 replay fixtures. No XCTest execution occurred.
- ios/DepthSectors/README.md, tests/ios/README.md: integration boundaries and deferred Mac/device verification procedure.
- tests/ios/validate_depth_fixtures.py, requirements-audit.txt, cs014-source-audit-20261017.json: actual Windows structure/grammar audit, exact tool versions and normalized source hashes.
- Task CS-014 runtime fields, new fragment, this handoff and rendered CHANGELOG.md.

## Actual checks

Ran `.venv/Scripts/python.exe tests/ios/validate_depth_fixtures.py --syntax --report tests/ios/cs014-source-audit-20261017.json`: seven fixture structures passed; seven Swift files parsed with no grammar errors using Tree-sitter 0.26.0 and Swift grammar 0.7.4. The report counts fifteen authored XCTest methods, not fifteen passing tests.

The fixture auditor does not reimplement the Swift algorithm or compare its numerical outputs. Expected fixture outputs are authored test requirements. Source grammar parsing cannot type-check Swift, validate SDK APIs, link code or exercise runtime behavior. The optional audit tools were installed only into ignored .venv, not backend runtime requirements.

The checked publisher runs existing root repository tests, validation, log consistency and whitespace checks before commit/push. Those Python checks do not run XCTest or compile iOS. Actual publisher/CI outcomes are reported with the draft PR.

## Limits and remaining work

No Swift compiler, Xcode/iOS SDK, simulator or physical LiDAR phone was available. No build, signing, runtime memory safety, depth accuracy, performance/thermal timing or electrical result is asserted. CS-013 remains pending. Status is Blocked for actual build/device acceptance, with source preparation complete; keep the implementation PR draft.

Every summary is labeled depth_image_columns with physicalMappingVerified=false. CS-015 must establish real orientation/mount/left-right mapping. Default high confidence, 25% coverage, 32 samples and 10th percentile are unvalidated engineering choices; cropping and quantiles can discard true hazards. Unknown never becomes zero/far distance or clearance. No crossing permission, haptic output, GPS or telemetry is produced. Consumer expiry/lifecycle and source-clock protocol integration remain CS-016/017; a retained result/heartbeat cannot renew capture time.

On a Mac: run `swift test --package-path ios/DepthSectors` (including Apple-only CoreVideo tests), then separately build the iOS ARKit target/host in Xcode, fix reproducible compile/test failures, and obtain CS-013/015/017/020 real-device evidence before any physical guidance/accuracy claim. No other task ownership, shared schema, baseline or protected automation was modified.
