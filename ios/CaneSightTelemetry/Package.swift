// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "CaneSightTelemetry", platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "CaneSightTelemetry", targets: ["CaneSightTelemetry"]),
               .executable(name: "TelemetryFixtures", targets: ["TelemetryFixtures"])],
    targets: [.target(name: "CaneSightTelemetry"),
              .executableTarget(name: "TelemetryFixtures", dependencies: ["CaneSightTelemetry"]),
              .testTarget(name: "CaneSightTelemetryTests", dependencies: ["CaneSightTelemetry"])])
