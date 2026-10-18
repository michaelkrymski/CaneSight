// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CaneSightLifecycle",
    platforms: [.iOS(.v16)],
    products: [
        .library(name: "CaneSightLifecycle", targets: ["CaneSightLifecycle"]),
        .library(name: "CaneSightARLifecycle", targets: ["CaneSightARLifecycle"])
    ],
    targets: [
        .target(name: "CaneSightLifecycle"),
        .target(name: "CaneSightARLifecycle", dependencies: ["CaneSightLifecycle"]),
        .testTarget(name: "CaneSightLifecycleTests", dependencies: ["CaneSightLifecycle"]),
        .testTarget(name: "CaneSightARLifecycleTests", dependencies: ["CaneSightARLifecycle", "CaneSightLifecycle"])
    ]
)
