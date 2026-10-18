// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CaneSightDepthTelemetry",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "CaneSightDepthTelemetry", targets: ["CaneSightDepthTelemetry"])],
    dependencies: [.package(path: "../DepthSectors"), .package(path: "../CaneSightTelemetry")],
    targets: [
        .target(name: "CaneSightDepthTelemetry", dependencies: [
            .product(name: "CaneSightDepth", package: "DepthSectors"),
            .product(name: "CaneSightTelemetry", package: "CaneSightTelemetry")]),
        .testTarget(name: "DepthTelemetryTests", dependencies: ["CaneSightDepthTelemetry"])
    ])
