// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CaneSightAccessibleStatus",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "CaneSightStatus", targets: ["CaneSightStatus"]),
        .library(name: "CaneSightStatusUI", targets: ["CaneSightStatusUI"])
    ],
    targets: [
        .target(name: "CaneSightStatus"),
        .target(name: "CaneSightStatusUI", dependencies: ["CaneSightStatus"]),
        .testTarget(name: "CaneSightStatusTests", dependencies: ["CaneSightStatus"])
    ]
)
