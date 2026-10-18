// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "CaneSightMountMapping",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "CaneSightMountMapping", targets: ["CaneSightMountMapping"]),
               .library(name: "CaneSightMountMappingARKit", targets: ["CaneSightMountMappingARKit"])],
    dependencies: [.package(name: "CaneSightDepth", path: "../MappingBench/ReviewDependencies/DepthSectors")],
    targets: [
        .target(name: "CaneSightMountMapping", dependencies: [.product(name: "CaneSightDepth", package: "CaneSightDepth")]),
        .target(name: "CaneSightMountMappingARKit", dependencies: ["CaneSightMountMapping", .product(name: "CaneSightDepthARKit", package: "CaneSightDepth")]),
        .testTarget(name: "MountMappingTests", dependencies: ["CaneSightMountMapping", .product(name: "CaneSightDepth", package: "CaneSightDepth")])])
