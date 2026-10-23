import SwiftUI
import CaneSightStatusUI
import CaneSightPreviewState
import UniformTypeIdentifiers

struct ContentView: View {
    @ObservedObject var services: AppServices
    @State private var selectedTab = ProcessInfo.processInfo.arguments.contains("--target-inspection") ? 0 : ProcessInfo.processInfo.arguments.contains("--connect-saved-phone") || ProcessInfo.processInfo.arguments.contains("--stream-saved-phone") ? 4 : (ProcessInfo.processInfo.arguments.contains("--depth-demo") ? 3 : 0)
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
            NavigationStack { ConnectionView(connection: services.connection).navigationTitle("Connection") }
                .tabItem { Label("Connection", systemImage: "network") }.tag(4)
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
                    if camera.inspectionEnabled {
                        Rectangle().stroke(.yellow,lineWidth:2).frame(width:20,height:40)
                            .position(x:CGFloat(camera.inspectionColumn)*20+10,y:CGFloat(camera.inspectionRow)*40+20)
                    }
                }.frame(width: 180,height: 320)
                    .accessibilityLabel("Portrait camera preview; three vertical depth columns")
                    .contentShape(Rectangle())
                    .gesture(DragGesture(minimumDistance:0).onChanged { value in
                        guard camera.inspectionEnabled else { return }
                        camera.inspectionColumn=max(0,min(8,Int(value.location.x/20)))
                        camera.inspectionRow=max(0,min(7,Int(value.location.y/40)))
                    })
                    .frame(maxWidth:.infinity)
                Toggle("Inspect target patch",isOn:$camera.inspectionEnabled)
                if camera.inspectionEnabled {
                    Text("Tap the target in the preview. Yellow patch is diagnostic only; it does not change the transmitted columns.").font(.caption)
                    let patch=camera.inspectionSnapshot
                    if let total=patch["total_samples"] as? Int, let high=patch["positive_finite_high"] as? Int {
                        Text("Patch high confidence: \(high)/\(total) pixels")
                        if let all=patch["all_confidence"] as? [String:Any], let filtered=patch["high_only"] as? [String:Any] {
                            Text("Patch 10th percentile · all confidence: \(metres(all["p10_m"])) · high only: \(metres(filtered["p10_m"]))").font(.caption)
                        }
                    }
                }
                Text(camera.status).accessibilityIdentifier("captureStatus")
                Text(camera.floorStatus).font(.caption)
                Text("Floor exclusion is experimental; very low obstacles can be missed. Unknown does not mean clear.").font(.caption)
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
                Text("Open the Connection tab for phone pairing and diagnostic transport.")
            }
        }
    }
    private func metres(_ value: Any?) -> String {
        guard let distance=value as? Double else { return "Unknown" }
        return String(format:"%.2f m",distance)
    }

}

struct ConnectionView: View {
    @ObservedObject var connection: PhoneConnection
    @State private var importingBond = false
    var body: some View {
        List {
            Section("Connection") {
                Text(connection.message).accessibilityIdentifier("connectionStatus")
                Button("Import existing phone bond") { importingBond = true }
                    .frame(minHeight: 60).accessibilityIdentifier("importPhoneBond")
                Button(connection.requested ? "Disconnect" : "Connect") {
                    connection.requested ? connection.disconnect() : connection.connect()
                }.frame(minHeight: 60).accessibilityIdentifier("phoneConnect")
                Toggle("Allow stationary diagnostic transport", isOn: $connection.diagnosticConsent)
                    .accessibilityIdentifier("diagnosticConsentConfirmation")
                Toggle("Send diagnostic depth", isOn: Binding(get: { connection.diagnosticDepth },
                    set: { connection.setDiagnosticDepth($0) }))
                    .disabled(!connection.requested || !connection.diagnosticConsent)
                    .accessibilityIdentifier("diagnosticDepth")
                Text("Start the camera separately. Sends depth summaries only; no images or location. Capture-age and drift bounds remain unverified. Diagnostic transport is not guidance readiness. This does not arm, disarm or verify Pi motor outputs.")
                    .font(.caption)
                Text("Pairing runs on this phone. No Mac helper required. Backgrounding stops depth; enable it again after returning.").font(.caption)
            }
        }.fileImporter(isPresented: $importingBond, allowedContentTypes: [.json]) { result in
            if case .success(let url) = result { connection.importFile(url) }
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
