// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "CaneSightPhonePairing", platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "CaneSightPhonePairing", targets: ["CaneSightPhonePairing"])],
    dependencies: [.package(path: "../CaneSightTelemetry")],
    targets: [.target(name: "CaneSightPhonePairing", dependencies: ["CaneSightTelemetry"]),
              .testTarget(name: "PhonePairingTests", dependencies: ["CaneSightPhonePairing"])])
