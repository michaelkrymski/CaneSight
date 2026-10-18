// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CaneSightDepth",
    platforms: [.iOS(.v14), .macOS(.v12)],
    products: [
        .library(name: "CaneSightDepth", targets: ["CaneSightDepth"]),
        .library(name: "CaneSightDepthARKit", targets: ["CaneSightDepthARKit"])
    ],
    targets: [
        .target(name: "CaneSightDepth"),
        .target(name: "CaneSightDepthARKit", dependencies: ["CaneSightDepth"]),
        .testTarget(name: "CaneSightDepthTests",
                    dependencies: ["CaneSightDepth", "CaneSightDepthARKit"],
                    resources: [.copy("Fixtures")])
    ]
)
