// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CaneSightCoarseLocation",
    platforms: [.iOS(.v16)],
    products: [
        .library(name: "CaneSightCoarseLocation", targets: ["CaneSightCoarseLocation"]),
        .library(name: "CaneSightCoreLocation", targets: ["CaneSightCoreLocation"])
    ],
    targets: [
        .target(name: "CaneSightCoarseLocation"),
        .target(name: "CaneSightCoreLocation", dependencies: ["CaneSightCoarseLocation"]),
        .testTarget(name: "CoarseLocationTests", dependencies: ["CaneSightCoarseLocation"])
    ]
)
