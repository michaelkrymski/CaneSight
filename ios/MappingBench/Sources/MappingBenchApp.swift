import SwiftUI

@main struct MappingBenchApp: App {
    @StateObject private var bench = BenchController()
    @Environment(\.scenePhase) private var phase
    var body: some Scene {
        WindowGroup {
            BenchView(bench: bench)
                .onAppear { bench.setActive(phase == .active) }
                .onChange(of: phase) { bench.setActive($0 == .active) }
        }
    }
}

struct BenchView: View {
    @ObservedObject var bench: BenchController
    let names = ["Left", "Center", "Right"]
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("Research bench · no crossing permission")
                    Text("Portrait upright, rear cameras facing forward. Keep the phone fixed. Use a broad flat object about 0.5–1 m away, with a farther background. Sides mean your physical left/right while facing forward.")
                        .font(.caption)
                }
                Section("Portrait viewport") {
                    ZStack {
                        Color.black
                        if let image = bench.image {
                            Image(decorative: image, scale: 1).resizable()
                        }
                        HStack(spacing: 0) {
                            ForEach(0..<3) { _ in Rectangle().stroke(.white, lineWidth: 1) }
                        }
                    }.frame(width: 180,height: 320).frame(maxWidth: .infinity)
                    Text(bench.status).accessibilityIdentifier("mappingStatus")
                    ForEach(0..<3) { index in
                        VStack(alignment: .leading, spacing: 3) {
                            LabeledContent("View \(names[index].lowercased())",
                                value: bench.distances[index].map { String(format: "%.2f m", $0) } ?? "Unknown")
                            Text(bench.depthDetails[index]).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    Button(bench.requested ? "Stop camera" : "Start portrait check") {
                        bench.requested ? bench.stop() : bench.start()
                    }.buttonStyle(.borderedProminent).disabled(!bench.supported)
                }
                Section("Known-target check") {
                    Text("Move the object to the requested physical side. Keep it there and record three distinct frames, roughly one second apart. Move only the target, not the phone.")
                        .font(.caption)
                    Text("Left \(bench.counts[0])/3 · Center \(bench.counts[1])/3 · Right \(bench.counts[2])/3")
                        .monospacedDigit()
                    if let target = bench.target {
                        Button("Record target on physical \(names[target].lowercased())") { bench.record() }
                            .buttonStyle(.borderedProminent)
                            .disabled(bench.image == nil || !bench.requested)
                    } else {
                        Label("Portrait target check complete for this session", systemImage: "checkmark.circle")
                    }
                    Button("Reset mount check") { bench.resetCheck() }
                }
                Section {
                    Text("Orientation changes, stale frames, interruption or backgrounding reset the check. Repeat after remounting. No telemetry, GPS, motor or narration control. This test does not measure depth accuracy or capture-clock bounds.")
                        .font(.caption)
                }
            }.navigationTitle("Mount Check")
        }
    }
}
