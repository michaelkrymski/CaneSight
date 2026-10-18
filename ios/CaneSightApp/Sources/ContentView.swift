import SwiftUI
import CaneSightDepth

struct ContentView: View {
    @ObservedObject var camera: CameraController

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Label("Research prototype", systemImage: "flask")
                    Text("No crossing permission. Use your established mobility techniques.")
                        .font(.subheadline)
                }
                Section("Camera & LiDAR") {
                    LabeledContent("Hardware support", value: camera.supported ? "Scene depth supported" : "Unavailable")
                    Text(camera.status).accessibilityIdentifier("captureStatus")
                    if let timestamp = camera.summary?.captureTimestampSeconds {
                        Text(String(format: "Original capture timestamp: %.3f s", timestamp))
                            .font(.caption).monospacedDigit()
                    }
                    Text("Local preview only. Capture-clock calibration is unverified.")
                        .font(.caption)
                    Button(camera.requested ? "Stop camera" : "Start camera") {
                        camera.requested ? camera.stop() : camera.start()
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!camera.supported)
                    .accessibilityIdentifier("captureToggle")
                    if camera.permissionDenied {
                        Button("Open camera permission settings") { camera.openSettings() }
                    }
                }
                Section("Depth image columns · uncalibrated") {
                    ForEach(Array(DepthImageSector.allCases.enumerated()), id: \.offset) { index, position in
                        let sector = camera.summary?.sectors.first { $0.position == position }
                        LabeledContent(["Image left", "Image center", "Image right"][index]) {
                            Text(sector?.distanceMetres.map { String(format: "%.2f m", $0) } ?? "Unknown")
                                .monospacedDigit()
                        }
                    }
                    Text("Image columns are not verified physical directions. Missing or interrupted data stays unknown.")
                        .font(.caption)
                }
                Section("Integration status") {
                    Label("Phone transport unavailable", systemImage: "wifi.slash")
                    Text("Pairing, capture-clock verification and physical mapping are required before telemetry. GPS sharing is off.")
                    Text("Review build: packages from draft PRs #62, #63, #64 and #67. No motor or narration control.")
                        .font(.caption)
                }
            }
            .navigationTitle("CaneSight")
        }
    }
}
