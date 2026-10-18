// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "CaneSightPreviewState",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "CaneSightPreviewState", targets: ["CaneSightPreviewState"])],
    targets: [.target(name: "CaneSightPreviewState"),
              .testTarget(name: "PreviewStateTests", dependencies: ["CaneSightPreviewState"])])
