import CaneSightStatus

// Linux can run the portable status tests but has no SwiftUI or VoiceOver.
#if canImport(SwiftUI)
import SwiftUI
import Foundation
import Combine

/// One view adapter per controller; the host delivers lifecycle/source events on
/// MainActor. No camera, network, credentials, speech engine or GPS access here.
@MainActor public final class AccessibleStatusModel: ObservableObject {
    public let objectWillChange = ObservableObjectPublisher()
    public let controller: StatusController
    // Read the authoritative controller snapshot. Never cache a second copy:
    // synchronous observers can invalidate a source while notification runs.
    public var snapshot: StatusSnapshot { controller.snapshot }

    public init(controller: StatusController) {
        self.controller = controller
        controller.onChange = { [weak self] _ in self?.objectWillChange.send() }
    }
}

/// Bind to the host's actual requested/support state. Stopping remains available
/// if support disappears while capture was requested. These closures control
/// capture only; they cannot arm motors or establish source readiness.
@MainActor public struct CaptureControls {
    public let requested: Bool
    public let supported: Bool
    public let start: () -> Void
    public let stop: () -> Void

    public init(requested: Bool, supported: Bool, start: @escaping () -> Void,
                stop: @escaping () -> Void) {
        self.requested = requested
        self.supported = supported
        self.start = start
        self.stop = stop
    }
}

/// Embed in the host's existing navigation. No automatic audio announcements:
/// VoiceOver can inspect stable labelled rows without 10Hz speech interruptions.
@MainActor public struct AccessibleStatusView: View {
    @ObservedObject private var model: AccessibleStatusModel
    @Environment(\.scenePhase) private var scenePhase
    private let capture: CaptureControls?

    public init(model: AccessibleStatusModel, capture: CaptureControls? = nil) {
        self.model = model
        self.capture = capture
    }

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text("CaneSight status")
                    .font(.largeTitle.bold())
                    .accessibilityAddTraits(.isHeader)
                Text("Research prototype. No crossing permission. Use your established mobility techniques.")
                    .font(.body)
                    .accessibilityIdentifier("cs018.researchNotice")

                statusRow("Depth", value: model.snapshot.depth.text, id: "cs018.depthStatus")
                statusRow("Connection", value: model.snapshot.connection.text, id: "cs018.connectionStatus")

                if let capture {
                    Button { capture.requested ? capture.stop() : capture.start() } label: {
                        Text(capture.requested ? "Stop camera" : "Start camera")
                            .font(.title2.bold())
                            .frame(maxWidth: .infinity, minHeight: 60)
                            .padding(.vertical, 8)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!capture.supported && !capture.requested)
                    .accessibilityLabel(capture.requested ? "Stop camera" : "Start camera")
                    .accessibilityHint("Controls the local camera and depth preview.")
                    .accessibilityIdentifier("cs018.captureToggle")
                }

                VStack(alignment: .leading, spacing: 16) {
                    Text("Depth image columns")
                        .font(.title2.bold()).accessibilityAddTraits(.isHeader)
                    ForEach(0..<3, id: \.self) { index in
                        statusRow(["Image left", "Image center", "Image right"][index],
                            value: distanceText(model.snapshot.sectors.distances[index]),
                            id: "cs018.sector.\(index)")
                    }
                    Text("Image columns are not verified physical directions. Unknown values do not mean an empty path.")
                        .font(.body)
                }

                statusRow("Narration", value: model.snapshot.audio.text, id: "cs018.audioStatus")
                Button(role: .destructive) { model.controller.cancelAudio() } label: {
                    Label("Cancel audio", systemImage: "speaker.slash.fill")
                        .font(.title2.bold())
                        .frame(maxWidth: .infinity, minHeight: 60)
                        .padding(.vertical, 8)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.borderedProminent)
                .disabled(!model.snapshot.canCancelAudio)
                .accessibilityLabel("Cancel audio")
                .accessibilityHint(model.snapshot.canCancelAudio
                    ? "Cancels requested app narration. Does not stop VoiceOver or turn off motors."
                    : "Audio cancellation is not connected in this build.")
                .accessibilityIdentifier("cs018.cancelAudio")
                Text("Cancellation requests stop app narration through the connected adapter. External speaker buffers may continue briefly.")
                    .font(.body)
            }
            .padding(24)
            // Fixed vertical layout, wrapping text, and system fonts support the
            // largest Dynamic Type sizes without horizontal rows or truncation.
            .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityAction(.escape) { model.controller.cancelAudio() }
        .onAppear { model.controller.setSceneActive(scenePhase == .active) }
        .onChange(of: scenePhase) { phase in model.controller.setSceneActive(phase == .active) }
        .onDisappear { model.controller.setSceneActive(false) }
        .task {
            while !Task.isCancelled {
                model.controller.tick()
                do { try await Task.sleep(nanoseconds: 100_000_000) }
                catch { break }
            }
        }
    }

    private func statusRow(_ label: String, value: String, id: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(.headline)
            Text(value).font(.body).monospacedDigit()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text(label))
        .accessibilityValue(Text(value))
        .accessibilityIdentifier(id)
    }

    private func distanceText(_ distance: Double?) -> String {
        guard let distance else { return "Unknown" }
        return String(format: "%.2f metres", distance)
    }
}
#endif
