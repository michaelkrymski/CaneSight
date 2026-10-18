// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "CS025PolicyFixture", dependencies: [
    .package(path: "../CaneSightTelemetry")
], targets: [
    .executableTarget(name: "CS025PolicyFixture", dependencies: [
        .product(name: "CaneSightTelemetry", package: "CaneSightTelemetry")
    ])
])
