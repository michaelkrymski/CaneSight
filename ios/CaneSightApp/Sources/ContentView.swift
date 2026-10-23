import SwiftUI
import CaneSightStatusUI
import CaneSightPreviewState

struct ContentView: View {
    @ObservedObject var services: AppServices
    @State private var selectedTab = ProcessInfo.processInfo.arguments.contains("--depth-demo") ? 3 : 0
    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack { CameraView(camera: services.camera).navigationTitle("CaneSight") }
                .tabItem { Label("Camera",systemImage: "camera") }.tag(0)
            NavigationStack {
                StatusPage(services: services,camera: services.camera)
                    .navigationTitle("Status")
            }.tabItem { Label("Status",systemImage: "accessibility") }.tag(1)
            NavigationStack { LocationView(location: services.location).navigationTitle("Local location") }
                .tabItem { Label("Location",systemImage: "location") }.tag(2)
            NavigationStack { DepthDemoView(camera: services.camera).navigationTitle("Depth demo") }
                .tabItem { Label("Demo",systemImage: "waveform") }.tag(3)
        }
    }
}

struct CameraView: View {
    @ObservedObject var camera: CameraController
    private let names=["Left","Center","Right"]
    var body: some View {
        List {
            Section {
                Text("Research prototype · no crossing permission")
                Text("Hold portrait upright, rear cameras forward. Unknown readings do not mean an empty path.").font(.subheadline)
            }
            Section("Camera & LiDAR") {
                LabeledContent("Hardware support",value: camera.supported ? "Scene depth supported" : "Unavailable")
                    .accessibilityIdentifier("hardwareSupport")
                ZStack {
                    Color.black
                    if let image=camera.image { Image(decorative: image,scale: 1).resizable() }
                    HStack(spacing: 0) { ForEach(0..<3) { _ in Rectangle().stroke(.white,lineWidth: 1) } }
                }.frame(width: 180,height: 320).frame(maxWidth: .infinity)
                    .accessibilityLabel("Portrait camera preview; three vertical depth columns")
                Text(camera.status).accessibilityIdentifier("captureStatus")
                Button {
                    camera.requested ? camera.stop() : camera.start()
                } label: {
                    Text(camera.requested ? "Stop camera" : "Start camera")
                        .font(.title2.bold()).frame(maxWidth: .infinity,minHeight: 60)
                        .contentShape(Rectangle())
                }
                    .buttonStyle(.borderedProminent).disabled(!camera.supported && !camera.requested)
                    .accessibilityIdentifier("captureToggle")
                Button("Camera permission settings") { camera.openSettings() }
            }
            Section("Portrait depth columns") {
                ForEach(0..<3) { index in
                    VStack(alignment: .leading,spacing: 6) {
                        LabeledContent(names[index]) {
                            Text(camera.distances[index].map { String(format: "%.2f m",$0) } ?? "Unknown")
                                .monospacedDigit().accessibilityIdentifier("distance\(index)")
                        }
                        Text(camera.depthDetails[index]).font(.caption)
                            .accessibilityIdentifier("depthDetail\(index)")
                    }
                }
                Text("The floor can affect all three readings. This view does not classify floors or measure drop-offs.").font(.caption)
            }
            Section("Check physical sides") {
                Text("For this session only. Keep the phone fixed; place a broad object 0.5–1 m away on the requested side.").font(.caption)
                Text("Left \(camera.counts[0])/3 · Center \(camera.counts[1])/3 · Right \(camera.counts[2])/3")
                    .accessibilityIdentifier("mountCounts")
                if let target=camera.target {
                    Button("Record target on physical \(names[target].lowercased())") { camera.record() }
                        .frame(minHeight: 60).disabled(camera.image == nil)
                } else { Text("Portrait target check complete for this session") }
                Button("Reset side check") { camera.resetCheck() }.frame(minHeight: 60)
            }
            Section("Connection") {
                Text("Not paired · telemetry unavailable").accessibilityIdentifier("connectionStatus")
                Text("Capture-clock verification and paired enrollment are required before streaming. Local camera and location stay on this phone.").font(.caption)
            }
        }
    }
}

struct LocationView: View {
    @ObservedObject var location: LocalLocationController
    var body: some View {
        List {
            Section {
                Toggle("Use coarse location locally",isOn: Binding(get: { location.consent },set: { location.setConsent($0) }))
                    .frame(minHeight: 60).accessibilityIdentifier("locationConsent")
                Text("Off by default each launch. Only while this app is active. No location is sent or saved.")
                Text(location.message).accessibilityIdentifier("locationStatus")
            }
            if let fix=location.snapshot, fix.unavailable == nil {
                Section("Current fix quality") {
                    if let age=fix.fixAgeMilliseconds { LabeledContent("Fix age",value: String(format: "%.1f seconds",age/1000)) }
                    if let accuracy=fix.coarseAccuracyMeters { LabeledContent("Coarse uncertainty",value: String(format: "At least %.0f metres",accuracy)) }
                }
            }
            Section {
                Text("Coarse context only. No lane, signal or crossing association. Network location sharing awaits a separately approved contract.")
            }
        }
    }
}

struct StatusPage: View {
    let services: AppServices
    @ObservedObject var camera: CameraController
    var body: some View {
        VStack(spacing: 0) {
            Button { services.readStatus() } label: {
                Text("Read app status aloud").font(.title2.bold())
                    .frame(maxWidth: .infinity,minHeight: 60).contentShape(Rectangle())
            }
                .buttonStyle(.bordered).padding(.horizontal)
                .accessibilityIdentifier("readStatus")
            AccessibleStatusView(model: services.statusUI, capture: CaptureControls(
                requested: camera.requested, supported: camera.supported,
                start: { camera.start() }, stop: { camera.stop() }))
        }.onAppear { camera.synchronizeDisplay() }
    }
}


struct DepthDemoView: View {
    @ObservedObject var camera: CameraController
    private let names = ["Left", "Center", "Right"]
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Real LiDAR → simulated responses").font(.title2.bold())
                Text("Visual demo only · no motors or movement guidance")
                    .font(.headline).accessibilityIdentifier("demoScope")
                Text("Near = 1.2 m or closer. Hold portrait upright, rear cameras forward. Place a broad object in one image column at a time.")
                Text(camera.status).font(.caption).accessibilityIdentifier("demoCaptureStatus")
                Button(camera.requested ? "Stop depth demo" : "Start depth demo") {
                    camera.requested ? camera.stop() : camera.start()
                }.buttonStyle(.borderedProminent).font(.title2.bold())
                    .frame(minHeight: 60).disabled(!camera.supported && !camera.requested)
                    .accessibilityIdentifier("demoCaptureToggle")
                ForEach(0..<3) { index in
                    let distance = camera.distances[index]
                    let response = LocalDepthResponse(distanceMetres: distance)
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Image(systemName: response == .near ? "circle.inset.filled" : "circle")
                                .foregroundStyle(response == .near ? Color.orange : Color.secondary)
                                .accessibilityHidden(true)
                            Text(names[index]).font(.title2.bold())
                            Spacer()
                            Text(distance.map { String(format: "%.2f m", $0) } ?? "Unknown")
                                .monospacedDigit().accessibilityIdentifier("demoDistance\(index)")
                        }
                        Text(response.rawValue).font(.headline)
                            .accessibilityIdentifier("demoResponse\(index)")
                    }.padding().frame(maxWidth: .infinity, alignment: .leading)
                        .background(response == .near ? Color.orange.opacity(0.18) : Color.secondary.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                }
                Text("Unknown never means clear. These are image columns, not verified motor sides. The floor can activate multiple columns; no floor or drop-off classification.")
                    .font(.caption)
                Text("Runs locally. No backend, Pi or credential needed. Preview recency is checked; sensor capture-age calibration remains unverified.")
                    .font(.caption)
            }.padding()
        }
    }
}
