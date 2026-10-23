import ARKit
import AVFoundation
import CoreImage
import QuartzCore
import SwiftUI
import CaneSightDepth
import CaneSightDepthARKit
import CaneSightPreviewState
import CaneSightMountMapping
import CaneSightMountMappingARKit
import CaneSightStatus
import CaneSightLifecycle
import CaneSightARLifecycle

@MainActor final class CameraController: ObservableObject, DepthLifecycleEvents {
    let accessible: StatusController
    let calibration=MountCalibrationController()
    @Published private(set) var summary: DepthSectorSummary?
    @Published private(set) var floorStatus = "Floor not mapped; using full depth columns."
    private(set) var floorDiagnostics: [String:Any] = [:]
    private(set) var inputQuality = [[String: Any]]()
    @Published var inspectionEnabled = ProcessInfo.processInfo.arguments.contains("--target-inspection") {
        didSet { capture.setDiagnostics(inspectionEnabled || ProcessInfo.processInfo.arguments.contains("--sector-quality-probe")) }
    }
    @Published var inspectionColumn = 7
    @Published var inspectionRow = 3
    var inspectionSnapshot: [String: Any] {
        guard let age=qualityAgeMS, age < 2000 else { return [:] }
        for sector in inputQuality {
            if let cells = sector["cells"] as? [[String: Any]],
               let cell = cells.first(where: { $0["column"] as? Int == inspectionColumn && $0["row"] as? Int == inspectionRow }) {
                return cell
            }
        }
        return [:]
    }
    private lazy var bridge = ARLifecycleBridge(lifecycle: self)
    @Published private(set) var status = "Camera stopped; mapping unverified."
    @Published private(set) var image: CGImage?
    @Published private(set) var distances: [Double?] = [nil,nil,nil]
    @Published private(set) var depthDetails = [String](repeating: "Waiting for a new depth frame.", count: 3)
    @Published private(set) var counts = [0,0,0]
    @Published private(set) var target: Int? = 0
    @Published private(set) var requested = false
    let supported = ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)
    private let session = ARSession()
    private var active = false
    private var portrait = false
    private var epoch = UUID()
    private var sample: CameraSample?
    private var check = MountCheck()
    private var lastLoss: UInt64 = 0
    private var lastSource: Double?
    private var timer: Timer?
    private var orientationObserver: NSObjectProtocol?
    private lazy var capture = CameraCapture(device:calibration.device,receive: { [weak self] event in self?.receive(event) },
        receiveQuality: { [weak self] quality in self?.receiveQuality(quality) })
    private var qualityCapture: Double?
    private var previewReceipt: Double?
    private var sessionRuns=0,validDepthFrames=0,unavailableDepthFrames=0,delayedDepthFrames=0
    var captureDiagnostics: [String:Any] {
        ["session_runs":sessionRuns,"valid_depth_frames":validDepthFrames,
         "unavailable_depth_frames":unavailableDepthFrames,"delayed_depth_frames":delayedDepthFrames,
         "thermal_state":ProcessInfo.processInfo.thermalState.rawValue,
         "preview_age_ms":previewReceipt.map { max(0,(CACurrentMediaTime()-$0)*1000) as Any } ?? NSNull()]
    }
    var qualityAgeMS: Double? { qualityCapture.map { max(0, (CACurrentMediaTime() - $0) * 1000) } }
    private func receiveQuality(_ value: CameraQuality) {
        guard value.epoch == epoch, active, requested, portrait, sample != nil,
              CACurrentMediaTime() - value.capture < 2 else { return }
        objectWillChange.send()
        inputQuality = value.values
        qualityCapture = value.capture
    }

    init(statusController: StatusController) {
        accessible = statusController
        calibration.onInvalidate = { [weak self] in self?.clearCalibrationSource() }
        calibration.onChange = { [weak self] in self?.configureCalibrationSource() }
        UIDevice.current.beginGeneratingDeviceOrientationNotifications()
        orientationObserver = NotificationCenter.default.addObserver(
            forName: UIDevice.orientationDidChangeNotification, object: nil, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.updateOrientation() }
            }
        portrait = UIDevice.current.orientation == .portrait
    }

    private func clearCalibrationSource() {
        accessible.invalidateDepth(.unknown)
        epoch=UUID();capture.stop();summary=nil;sample=nil;image=nil;previewReceipt=nil;distances=[nil,nil,nil]
        inputQuality=[];floorDiagnostics=[:];clearDepthDetails();resetCheck()
        calibration.resetTransient()
    }
    private func configureCalibrationSource() {
        clearCalibrationSource()
        if active && requested {
            capture.begin(epoch,token:accessible.depthToken,profile:calibration.geometryProfile,region:calibration.region)
        }
    }
    func beginMountCalibration() { calibration.begin();if !requested { start() } }
    func mountMoved() { calibration.moved();if !requested { start() } }
    private func updateOrientation(autoRestart: Bool = true) {
        let value = UIDevice.current.orientation == .portrait
        guard value != portrait else { return }
        portrait = value
        if !value { halt("Hold the phone portrait upright; check reset.") }
        else if autoRestart && requested && active { authorize() }
    }
    func setActive(_ value: Bool) {
        accessible.setSceneActive(value)
        if value && !supported { accessible.invalidateDepth(.unsupported) }
        guard active != value else { return }
        active = value
        if !value { halt("App inactive; depth unknown and check reset.", depthReason: .inactive) }
        else {
            updateOrientation(autoRestart: false)
            if requested && portrait { authorize() }
        }
    }
    func start() {
        guard supported else { status="Scene depth unavailable."; accessible.invalidateDepth(.unsupported); return }
        requested = true
        updateOrientation(autoRestart: false)
        guard portrait else { status="Hold the phone portrait upright to start."; return }
        authorize()
    }
    func stop() { requested=false; halt("Stopped; depth unknown and check reset.") }

    private func authorize() {
        guard active, portrait, requested else { return }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: run()
        case .notDetermined:
            let current=epoch
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                Task { @MainActor in
                    guard let self, self.epoch == current, self.active, self.portrait, self.requested else { return }
                    if granted { self.run() }
                    else { self.requested=false; self.halt("Camera permission denied; unavailable.", depthReason: .permissionDenied) }
                }
            }
        default: requested=false; halt("Camera permission denied. Enable Camera in Settings for CaneSight.", depthReason: .permissionDenied)
        }
    }
    private func run() {
        halt("Starting; waiting for portrait depth.")
        capture.begin(epoch, token: accessible.depthToken,profile:calibration.geometryProfile,region:calibration.region)
        session.delegate=capture; session.delegateQueue=capture.callbacks
        let configuration=ARWorldTrackingConfiguration()
        configuration.worldAlignment = .gravity
        configuration.frameSemantics.insert(.sceneDepth)
        configuration.planeDetection = [.horizontal]
        sessionRuns+=1
        session.run(configuration,options: [.resetTracking,.removeExistingAnchors])
        timer=Timer.scheduledTimer(withTimeInterval: 0.1,repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.tick() }
        }
    }
    private func halt(_ reason: String, pause: Bool=true, depthReason: DepthStatus = .unknown) {
        accessible.invalidateDepth(depthReason)
        calibration.trackingReset()
        epoch=UUID(); capture.stop()
        if pause { session.pause() }
        timer?.invalidate(); timer=nil
        sample=nil; image=nil; previewReceipt=nil; distances=[nil,nil,nil]; if summary != nil { summary=nil }; inputQuality=[]; floorDiagnostics=[:]; floorStatus="Floor unavailable; waiting for fresh tracking."; clearDepthDetails(); lastSource=nil; lastLoss=0
        resetCheck(); status=reason
    }
    private func clearDepthDetails() {
        depthDetails = [String](repeating: "Waiting for a new depth frame.", count: 3)
    }
    func resetCheck() {
        check.reset()
        if let sample { check.observeGeometry(sample.observation.geometry) }
        syncProgress()
    }
    private func syncProgress() { counts=check.counts; target=check.nextTarget }
    func synchronizeDisplay() {
        // Scene activity is independent of whether its presentation is mounted.
        accessible.setSceneActive(active)
        if active && !supported { accessible.invalidateDepth(.unsupported) }
        capture.updateDisplayToken(accessible.depthToken)
    }
    private func tick() {
        synchronizeDisplay()
        accessible.tick()
        capture.updateDisplayToken(accessible.depthToken)
        let now=CACurrentMediaTime()
        if let receipt=previewReceipt, !now.isFinite || now<receipt || now-receipt>=0.5 {
            image=nil;previewReceipt=nil
        }
        guard let sample else { return }
        if !now.isFinite || now < sample.receipt || now-sample.receipt >= 0.5 {
            accessible.invalidateDepth(.stale); calibration.resetTransient(); self.sample=nil; distances=[nil,nil,nil]; if summary != nil { summary=nil }; inputQuality=[]; floorDiagnostics=[:]; floorStatus="Floor unavailable; waiting for fresh tracking."; clearDepthDetails(); resetCheck()
            status="No recent frame; depth unknown and check reset."
        }
    }
    private func receive(_ event: CameraEvent) {
        guard epoch == event.epoch, active, portrait, requested else { return }
        if event.interrupted {
            bridge.sessionWasInterrupted()
            return
        }
        let previewNow=CACurrentMediaTime()
        if let preview=event.preview,let receipt=event.previewReceipt,
           previewNow.isFinite,previewNow>=receipt,previewNow-receipt<0.5 {
            image=preview;previewReceipt=receipt
        }
        if event.loss != lastLoss { check.reset(); lastLoss=event.loss }
        guard let value=event.sample else {
            unavailableDepthFrames+=1
            calibration.trackingReset()
            accessible.invalidateDepth(.unknown)
            sample=nil; distances=[nil,nil,nil]; if summary != nil { summary=nil }; inputQuality=[]; floorDiagnostics=[:]; floorStatus="Floor unavailable; waiting for fresh tracking."; clearDepthDetails(); syncProgress()
            status="Waiting for valid depth/tracking; check reset."
            return
        }
        let now=CACurrentMediaTime()
        guard now.isFinite, now >= value.receipt, now-value.receipt < 0.5,
              let source=value.observation.summary.captureTimestampSeconds,
              lastSource.map({ source > $0 }) ?? true else {
            delayedDepthFrames+=1
            accessible.invalidateDepth(.unknown)
            sample=nil; distances=[nil,nil,nil]; if summary != nil { summary=nil }; inputQuality=[]; floorDiagnostics=[:]; floorStatus="Floor unavailable; waiting for fresh tracking."; clearDepthDetails(); resetCheck()
            status="Delayed frame; depth unknown and check reset."; return
        }
        validDepthFrames+=1
        lastSource=source;sample=value
        calibration.observe(value.mountFrame,timestamp:source)
        // A callback may have replaced the source epoch while observing this frame.
        guard epoch == event.epoch else { return }
        floorDiagnostics=value.mountFrame.diagnostics
        floorStatus=value.mountFrame.problem ?? "Current level-floor geometry supported"
        guard calibration.eligible,let result=value.mountFrame.summary else {
            if summary != nil { summary=nil }
            distances=[nil,nil,nil]
            accessible.invalidateDepth(.unknown)
            status=calibration.message
            clearDepthDetails()
            return
        }
        let sectors=DisplaySectors(imageLeft:result.sectors[0].distanceMetres,
            imageCenter:result.sectors[1].distanceMetres,imageRight:result.sectors[2].distanceMetres)
        guard accessible.showLocalPreview(sectors,sourceMilliseconds:source*1000,
            receiptMilliseconds:value.receipt*1000,token:value.displayToken) else {
            if summary != nil { summary=nil };distances=[nil,nil,nil]
            accessible.invalidateDepth(.unknown);return
        }
        summary=result;distances=result.sectors.map(\.distanceMetres)
        depthDetails=result.sectors.map { sector in
            "Selected region high-confidence coverage: \(Int((sector.validFraction ?? 0)*100))%; \(sector.evidence.rawValue)."
        }
        check.observeGeometry(value.observation.geometry); syncProgress()
        status="Calibrated region live · left / center / right obstacle locations"
    }
    func setApplicationActive(_ value: Bool) { setActive(value) }
    func setInterrupted(_ value: Bool) {
        if value { requested=false; halt("Camera interrupted; depth unknown. Restart when ready.", pause: false) }
    }
    func setTrackingNormal(_ normal: Bool) {
        if !normal { halt("Tracking unavailable; depth unknown.") }
    }
    func sessionFailed() { requested=false; halt("Camera failed; restart when ready.", pause: false) }
    func sessionRestarted() { halt("New session; waiting for fresh depth.") }
    func openSettings() {
        if let url=URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
    }
    func record() {
        guard let sample else { status="Need a new valid frame."; return }
        do {
            try check.record(summary: sample.mountFrame.summary ?? sample.observation.summary, geometry: sample.observation.geometry,
                             receipt: sample.receipt,now: CACurrentMediaTime())
            syncProgress()
            status=check.complete ? "Portrait target check complete for this session." : "Recorded. Keep the phone fixed; follow the next target prompt."
        } catch {
            syncProgress()
            status="Not recorded: need a distinct fresh frame with the requested side at least 0.2 m nearer than both other sides. Unknown values cannot qualify."
        }
    }
}

struct CameraSample: @unchecked Sendable {
    let observation: PortraitObservation
    let image: CGImage
    let mountFrame: CalibratedCameraFrame
    let receipt: Double
    let displayToken: DepthDisplayToken
}
struct CameraQuality: @unchecked Sendable {
    let epoch: UUID
    let capture: Double
    let values: [[String: Any]]
}
struct CameraEvent: @unchecked Sendable {
    let epoch: UUID
    let sample: CameraSample?
    let loss: UInt64
    var interrupted=false
    var preview: CGImage?=nil
    var previewReceipt: Double?=nil
}

/// Two bounded frame slots and a latest-only main delivery. Loss serials survive
/// coalescing, so a later good frame cannot hide a tracking/buffer failure.
final class CameraCapture: NSObject, ARSessionDelegate, @unchecked Sendable {
    let callbacks=DispatchQueue(label: "MountCheck.ARCallbacks")
    private let worker=DispatchQueue(label: "MountCheck.Worker")
    private let qualityWorker=DispatchQueue(label: "MountCheck.Quality", qos: .utility)
    private var qualityBusy=false
    private var nextQuality: Double=0
    private let receiveQuality: @MainActor @Sendable (CameraQuality)->Void
    private let context=CIContext(options: [.cacheIntermediates:false])
    private let lock=NSLock()
    private var epoch: UUID?
    private var pending: (ARFrame,UUID,Double,DepthDisplayToken)?
    private var displayToken: DepthDisplayToken?
    private var working=false
    private var delivery: CameraEvent?
    private var scheduled=false
    private var loss: UInt64=0
    private var next: Double=0
    private var mountProfile: MountProfile?
    private var mountRegion=MountRegion()
    private let device: String
    private var diagnosticsEnabled = ProcessInfo.processInfo.arguments.contains("--sector-quality-probe") ||
        ProcessInfo.processInfo.arguments.contains("--target-inspection")
    func setDiagnostics(_ enabled: Bool) { lock.withLock { diagnosticsEnabled = enabled } }
    private let receive: @MainActor @Sendable (CameraEvent)->Void
    init(device: String,receive: @escaping @MainActor @Sendable (CameraEvent)->Void,
         receiveQuality: @escaping @MainActor @Sendable (CameraQuality)->Void) {
        self.device=device; self.receive=receive; self.receiveQuality=receiveQuality
    }
    func begin(_ value: UUID, token: DepthDisplayToken,profile: MountProfile?,region: MountRegion) {
        lock.lock(); mountProfile=profile;mountRegion=region;epoch=value; displayToken=token; loss=0; next=0; lock.unlock()
    }
    func updateDisplayToken(_ value: DepthDisplayToken) {
        lock.lock(); displayToken=value; lock.unlock()
    }
    func stop() { lock.lock(); epoch=nil; pending=nil; delivery=nil; lock.unlock() }
    func session(_ session: ARSession,didUpdate frame: ARFrame) {
        let now=CACurrentMediaTime()
        lock.lock()
        guard let epoch, let displayToken, now.isFinite, now>=next else { lock.unlock(); return }
        next=now+0.2; pending=(frame,epoch,now,displayToken)
        let launch = !working; working=true; lock.unlock()
        if launch { worker.async { self.process() } }
    }
    private func process() {
        while true {
            lock.lock()
            guard let input=pending else { working=false; lock.unlock(); return }
            pending=nil; let current=epoch==input.1; let profile=mountProfile,region=mountRegion;lock.unlock()
            guard current else { continue }
            var sample: CameraSample?
            // RGB preview does not depend on scene-depth/tracking validity.
            // Both retain the same epoch and bounded callback-recency checks.
            let source=CIImage(cvPixelBuffer:input.0.capturedImage)
            let normalized=input.0.displayTransform(for:.portrait,viewportSize:PortraitDepth.viewport)
            var preview: CGImage?
            if let pixels=try? PortraitPreviewTransform.pixels(imageWidth:source.extent.width,imageHeight:source.extent.height,
                previewWidth:180,previewHeight:320,normalized:normalized) {
                preview=context.createCGImage(source.transformed(by:pixels),from:CGRect(x:0,y:0,width:180,height:320))
            }
            if let observation=try? PortraitDepth.process(input.0),let image=preview {
                    let mount=MountFrameProcessor.process(input.0,observation:observation,profile:profile,region:region,device:device)
                    sample=CameraSample(observation:observation,image:image,mountFrame:mount,receipt:input.2,displayToken:input.3)
                    // Diagnostics own one bounded slot on a separate low-priority queue.
                    // Never delay the frame delivery or production freshness fence.
                    let inspect = lock.withLock { () -> Bool in
                        guard diagnosticsEnabled, !qualityBusy, input.2 >= nextQuality else { return false }
                        qualityBusy=true; nextQuality=input.2+1; return true
                    }
                    if inspect {
                        qualityWorker.async {
                            let values=Self.inputQuality(input.0, mapping: observation.geometry.mapping)
                            let value=CameraQuality(epoch:input.1,capture:input.0.timestamp,values:values)
                            let current=self.lock.withLock { self.qualityBusy=false; return self.epoch==input.1 && self.diagnosticsEnabled }
                            if current { DispatchQueue.main.async { self.receiveQuality(value) } }
                        }
                    }
            }
            emit(sample,epoch:input.1,preview:preview,previewReceipt:input.2)
        }
    }
    /// Optional read-only histogram. Reuses the exact display permutation/crop;
    /// never changes confidence, distances, thresholds or outbound observations.
    private static func inputQuality(_ frame: ARFrame, mapping: DisplayMapping) -> [[String: Any]] {
        guard let depth = frame.sceneDepth, let confidence = depth.confidenceMap,
              let packed = try? DepthPixelBufferReader.copyFrame(depth: depth.depthMap, confidence: confidence,
                captureTimestampSeconds: frame.timestamp, mode: .live, tracking: .normal),
              let oriented = try? mapping.prepare(packed), let levels = oriented.frame.confidence else { return [] }
        let input = oriented.frame, roi = oriented.region
        let x0 = Int(ceil(roi.xMin * Double(input.width))), x1 = Int(floor(roi.xMax * Double(input.width)))
        let y0 = Int(ceil(roi.yMin * Double(input.height))), y1 = Int(floor(roi.yMax * Double(input.height)))
        guard x1-x0 >= 9, y1-y0 >= 8 else { return [] }
        func distribution(_ values: [Float], histogram: Bool = false) -> [String: Any] {
            let sorted = values.sorted(), count = values.count
            var result: [String: Any] = ["count": count,
                "min_m": sorted.first.map { Double($0) as Any } ?? NSNull(),
                "p10_m": count > 0 ? Double(sorted[max(0,Int(ceil(0.1*Double(count)))-1)]) as Any : NSNull(),
                "median_m": count > 0 ? Double(sorted[(count-1)/2]) as Any : NSNull(),
                "under_1_25_m": sorted.prefix { $0 <= 1.25 }.count]
            if histogram {
                result["cumulative_under_m"] = Dictionary(uniqueKeysWithValues:
                    [0.5,1,1.25,1.5,2,2.5,3,4,6].map { edge in
                        (String(edge), sorted.prefix { Double($0) <= edge }.count)
                    })
            }
            return result
        }
        func inspect(_ start: Int, _ end: Int, _ top: Int, _ bottom: Int, histogram: Bool) -> [String: Any] {
            var counts = [0,0,0], positive = [[Float](),[Float](),[Float]()], badConfidence=0, badDepth=0
            for y in top..<bottom { for x in start..<end {
                let offset=y*input.width+x, level=Int(levels[offset]), value=input.metres[offset]
                let valid=value.isFinite && value>0
                if !valid { badDepth += 1 }
                if level<=2 { counts[level] += 1; if valid { positive[level].append(value) } }
                else { badConfidence += 1 }
            } }
            let accepted = positive[2].count
            return ["total_samples": (end-start)*(bottom-top), "confidence_low": counts[0],
                "confidence_medium": counts[1], "confidence_high": counts[2],
                "positive_finite_low": positive[0].count, "positive_finite_medium": positive[1].count,
                "positive_finite_high": accepted, "invalid_depth": badDepth, "invalid_confidence": badConfidence,
                "all_confidence": distribution(positive.flatMap { $0 },histogram:histogram),
                "medium_and_high": distribution(positive[1]+positive[2],histogram:histogram),
                "high_only": distribution(positive[2],histogram:histogram),
                "production_p10_rank": Int(ceil(0.1*Double(accepted)))]
        }
        return DepthImageSector.allCases.enumerated().map { index, position in
            let start=x0+(x1-x0)*index/3, end=x0+(x1-x0)*(index+1)/3
            var result=inspect(start,end,y0,y1,histogram:true)
            result["position"]=position.rawValue
            result["geometry"]=["depth_width":packed.width,"depth_height":packed.height,
                "oriented_width":input.width,"oriented_height":input.height,
                "display_transform":[mapping.a,mapping.b,mapping.c,mapping.d,mapping.tx,mapping.ty],
                "normalized_roi":[roi.xMin,roi.yMin,roi.xMax,roi.yMax],
                "pixel_rect":[start,y0,end,y1],
                "actual_viewport_x_edges":[(Double(start)/Double(input.width)-roi.xMin)/(roi.xMax-roi.xMin),
                                          (Double(end)/Double(input.width)-roi.xMin)/(roi.xMax-roi.xMin)]] as [String:Any]
            var cells=[[String:Any]]()
            for localColumn in 0..<3 { for row in 0..<8 {
                let left=start+(end-start)*localColumn/3, right=start+(end-start)*(localColumn+1)/3
                let top=y0+(y1-y0)*row/8, bottom=y0+(y1-y0)*(row+1)/8
                var cell=inspect(left,right,top,bottom,histogram:false)
                cell["column"]=index*3+localColumn; cell["row"]=row; cell["sector"]=position.rawValue
                cells.append(cell)
            } }
            result["cells"]=cells
            return result
        }
    }
    private func emit(_ sample: CameraSample?,epoch value: UUID,preview: CGImage?=nil,previewReceipt: Double?=nil) {
        lock.lock()
        guard epoch==value else { lock.unlock(); return }
        if sample==nil { loss &+= 1 }
        delivery=CameraEvent(epoch:value,sample:sample,loss:loss,preview:preview,previewReceipt:previewReceipt)
        let launch = !scheduled; scheduled=true; lock.unlock()
        if launch {
            DispatchQueue.main.async {
                self.lock.lock(); let value=self.delivery; self.delivery=nil; self.scheduled=false; self.lock.unlock()
                if let value { self.receive(value) }
            }
        }
    }
    private func interrupt() {
        lock.lock(); let value=epoch; epoch=nil; pending=nil; delivery=nil; lock.unlock()
        if let value {
            let event=CameraEvent(epoch: value,sample: nil,loss: 0,interrupted: true)
            DispatchQueue.main.async { self.receive(event) }
        }
    }
    func sessionWasInterrupted(_ session: ARSession) { interrupt() }
    func session(_ session: ARSession,didFailWithError error: Error) { interrupt() }
}
