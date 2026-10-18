// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CS018LifecycleIntegration",
    platforms: [.iOS(.v16), .macOS(.v13)],
    dependencies: [
        .package(path: "../../../ios/AccessibleStatus"),
        .package(path: "../../../ios/Lifecycle")
    ],
    targets: [.testTarget(name: "CS018LifecycleIntegrationTests", dependencies: [
        .product(name: "CaneSightStatus", package: "AccessibleStatus"),
        .product(name: "CaneSightLifecycle", package: "Lifecycle")
    ])]
)
