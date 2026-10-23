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
                MountCalibrationPreview(camera:camera,mount:camera.calibration)
                Text(camera.status).accessibilityIdentifier("captureStatus")
                Text(camera.floorStatus).font(.caption)

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
            Section("Calibrated obstacle sectors") {
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
                Text("Left obstacle → left vibration; center → both; right → right. You choose your movement. Unknown is not clear.").font(.caption)
            }
            MountCalibrationControls(camera:camera,mount:camera.calibration)
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

struct MountCalibrationPreview: View {
    @ObservedObject var camera: CameraController
    @ObservedObject var mount: MountCalibrationController
    var body: some View {
        ZStack {
            Color.black
            if let image=camera.image { Image(decorative:image,scale:1).resizable() }
            if !mount.polygons.isEmpty {
                ForEach(Array(mount.polygons.enumerated()),id:\.offset) { item in
                    Path { path in
                        let corners=item.element
                        if let first=corners.first {
                            path.move(to:CGPoint(x:CGFloat(first.x)*180,y:CGFloat(first.y)*320))
                            for p in corners.dropFirst() { path.addLine(to:CGPoint(x:CGFloat(p.x)*180,y:CGFloat(p.y)*320)) }
                            path.closeSubpath()
                        }
                    }.stroke(.yellow,lineWidth:1.5)
                }
            } else if mount.profile == nil && (mount.step == .position || !mount.wizard) {
                // Full-width band requested after inspecting the old 20x40 debug patch.
                HStack(spacing:0) {
                    ForEach(0..<3) { _ in Rectangle().stroke(.yellow,lineWidth:1.5) }
                }.frame(width:180,height:CGFloat(mount.region.height)*320)
                    .position(x:CGFloat(mount.region.x+MountRegion.width/2)*180,
                              y:CGFloat(mount.region.y+mount.region.height/2)*320)
            }
            if camera.inspectionEnabled {
                ForEach(Array(mount.exclusions.enumerated()),id:\.offset) { item in
                    Circle().fill(item.element[2] == 3 ? Color.green : item.element[2] == 2 ? Color.blue : Color.red).frame(width:2,height:2)
                        .position(x:CGFloat(item.element[0])*180,y:CGFloat(item.element[1])*320)
                }
            }
        }.frame(width:180,height:320).contentShape(Rectangle())
            .clipped()
            .gesture(SpatialTapGesture().onEnded { value in
                mount.moveRegion(y:Float(value.location.y/320))
            },including:mount.step == .position ? .all : .subviews)
            .accessibilityLabel("Yellow calibrated region; three obstacle sectors. Debug samples: green usable, red invalid or low confidence, blue excluded floor. Not object outlines.")
            .accessibilityIdentifier("mountRegionPreview")
            .frame(maxWidth:.infinity)
    }
}

struct MountCalibrationControls: View {
    @ObservedObject var camera: CameraController
    @ObservedObject var mount: MountCalibrationController
    @State private var confirmRemount=false
    var body: some View {
        Section("Mount calibration") {
            Text(mount.profileStatus).accessibilityIdentifier("mountProfileStatus")
            Text(mount.message).accessibilityIdentifier("mountCalibrationStatus")
            DisclosureGroup("Why a sector is Unknown") {
                ForEach(Array(mount.depthReasons.enumerated()),id:\.offset) { item in
                    Text(item.element).font(.caption)
                }
            }
            Button("Calibrate mount") { camera.beginMountCalibration() }
                .frame(minHeight:50).accessibilityIdentifier("calibrateMount")
            Button("Mount moved / recalibrate",role:.destructive) { confirmRemount=true }
                .frame(minHeight:50).accessibilityIdentifier("mountMoved")
                .alert("Has the phone moved in its mount?",isPresented:$confirmRemount) {
                    Button("Invalidate calibration and start again",role:.destructive) { camera.mountMoved() }
                    Button("Keep calibration",role:.cancel) {}
                } message: { Text("Normal cane motion does not need recalibration. Continue only after changing or doubting the phone's mounting angle.") }
            Toggle("Show depth sample diagnostics",isOn:$camera.inspectionEnabled)
            if camera.inspectionEnabled {
                Text("Green: usable depth samples. Red: invalid or low confidence. Blue: excluded floor. These are sampled depth points, not detected object outlines.").font(.caption)
            }
            if mount.wizard {
                Toggle("Sighted helper present; normal cane grip on level ground",isOn:$mount.helperPresent)
                    .accessibilityIdentifier("mountHelperPresent")
                Text("Adjust the phone mount angle, then tap the preview to position the full-width yellow band away from the floor, hand and cane. Adjust its height explicitly below. Keep the assembly still for capture. Optional sample diagnostics explain accepted depth and exclusions.").font(.caption)
                Text("Setup only · selected distances: \(mount.localDistances.map { $0.map { String(format:"%.2f m",$0) } ?? "Unknown" }.joined(separator:" / "))")
                    .accessibilityIdentifier("mountSetupDistances")
                if mount.step == .position {
                    Text("Detection band height: \(Int(mount.region.height*100))% of view")
                    Slider(value:Binding(get:{ Double(mount.region.height) },set:{ mount.resizeRegion(height:Float($0)) }),
                        in:Double(MountRegion.defaultHeight)...1)
                        .accessibilityLabel("Detection band height")
                    Button("Capture neutral mount") { mount.collect() }
                        .disabled(!mount.helperPresent).frame(minHeight:50).accessibilityIdentifier("captureNeutralMount")
                } else if mount.step == .stable {
                    Text("Stable frames: \(mount.progress) · at least 2.5 seconds")
                } else if mount.step == .confirm {
                    Button("Helper confirms · save calibration") { mount.save() }
                        .disabled(!mount.helperPresent).frame(minHeight:50).accessibilityIdentifier("saveMountCalibration")
                } else {
                    Text("Left \(mount.targetCounts[0])/3 · Center \(mount.targetCounts[1])/3 · Right \(mount.targetCounts[2])/3 · Low \(mount.lowCount)/3")
                        .accessibilityIdentifier("mountCounts")
                    Button("Helper confirms · record \(mount.step.rawValue) target") { mount.recordTarget() }
                        .disabled(!mount.helperPresent).frame(minHeight:50).accessibilityIdentifier("recordMountTarget")
                }
            }
            Text("Level ground only: ±15° pitch, ±10° roll, ±10 cm grip-height change from setup. Initial low-obstacle check: 8–20 cm high. Unsupported geometry stays unavailable. Mount slips cannot be distinguished automatically from cane motion.").font(.caption)
            Text("A saved profile survives ordinary restarts. Repeat setup after changing or doubting the mount. Floor exclusion is experimental; silence does not indicate a clear path.").font(.caption)
        }
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
