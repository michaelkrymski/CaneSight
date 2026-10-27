import ARKit
import AVFoundation
import CoreImage
import QuartzCore
import SwiftUI
import CaneSightDepth
import CaneSightMountMapping
import CaneSightMountMappingARKit
import CaneSightStatus
import CaneSightLifecycle
import CaneSightARLifecycle
import CaneSightTelemetry

@MainActor final class CameraController: ObservableObject, DepthLifecycleEvents {
    let accessible: StatusController
    @Published private(set) var summary: DepthSectorSummary?
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
    private lazy var capture = CameraCapture { [weak self] event in self?.receive(event) }
    private var telemetry: LifecycleTelemetry?

    /// Called by reviewed enrollment/clock integration, never by camera Start.
    /// No credential storage or assumed ARFrame clock equivalence is added here.
    func configureTelemetry(session: PhoneSession, clock: VerifiedCaptureClock) throws {
        guard telemetry == nil else { throw TelemetryError.configuration }
        let transport = LifecycleTelemetry(session: session, clock: clock, unknown: { [weak self] in
            self?.clearTransportDepth()
        })
        telemetry = transport
        capture.setTransportFence(transport.captureFence)
        transport.setApplicationActive(active)
    }

    private func clearTransportDepth() {
        accessible.invalidateDepth(.unknown)
        sample=nil; image=nil; distances=[nil,nil,nil]; summary=nil; clearDepthDetails(); resetCheck()
    }

    init(statusController: StatusController) {
        accessible = statusController
        UIDevice.current.beginGeneratingDeviceOrientationNotifications()
        orientationObserver = NotificationCenter.default.addObserver(
            forName: UIDevice.orientationDidChangeNotification, object: nil, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.updateOrientation() }
            }
        portrait = UIDevice.current.orientation == .portrait
    }

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
        telemetry?.setApplicationActive(value)
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
        telemetry?.sessionRestarted()
        capture.begin(epoch, token: accessible.depthToken)
        session.delegate=capture; session.delegateQueue=capture.callbacks
        let configuration=ARWorldTrackingConfiguration()
        configuration.frameSemantics.insert(.sceneDepth)
        session.run(configuration,options: [.resetTracking,.removeExistingAnchors])
        timer=Timer.scheduledTimer(withTimeInterval: 0.1,repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.tick() }
        }
    }
    private func halt(_ reason: String, pause: Bool=true, depthReason: DepthStatus = .unknown) {
        telemetry?.setTrackingNormal(false)
        accessible.invalidateDepth(depthReason)
        epoch=UUID(); capture.stop()
        if pause { session.pause() }
        timer?.invalidate(); timer=nil
        sample=nil; image=nil; distances=[nil,nil,nil]; summary=nil; clearDepthDetails(); lastSource=nil; lastLoss=0
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
        guard let sample else { return }
        let now=CACurrentMediaTime()
        if !now.isFinite || now < sample.receipt || now-sample.receipt >= 0.5 {
            telemetry?.setTrackingNormal(false)
            accessible.invalidateDepth(.stale); self.sample=nil; image=nil; distances=[nil,nil,nil]; summary=nil; clearDepthDetails(); resetCheck()
            status="No recent frame; depth unknown and check reset."
        }
    }
    private func receive(_ event: CameraEvent) {
        guard epoch == event.epoch, active, portrait, requested else { return }
        if event.interrupted {
            bridge.sessionWasInterrupted()
            return
        }
        if event.loss != lastLoss { check.reset(); lastLoss=event.loss }
        guard let value=event.sample else {
            telemetry?.setTrackingNormal(false)
            accessible.invalidateDepth(.unknown)
            sample=nil; image=nil; distances=[nil,nil,nil]; summary=nil; clearDepthDetails(); syncProgress()
            status="Waiting for valid depth/tracking; check reset."
            return
        }
        let now=CACurrentMediaTime()
        guard now.isFinite, now >= value.receipt, now-value.receipt < 0.5,
              let source=value.observation.summary.captureTimestampSeconds,
              lastSource.map({ source > $0 }) ?? true else {
            telemetry?.setTrackingNormal(false)
            accessible.invalidateDepth(.unknown)
            sample=nil; image=nil; distances=[nil,nil,nil]; summary=nil; clearDepthDetails(); resetCheck()
            status="Delayed frame; depth unknown and check reset."; return
        }
        let result=value.observation.summary
        if result.reason == .processedFrame {
            telemetry?.setTrackingNormal(true)
        } else {
            telemetry?.setTrackingNormal(false)
        }
        let sectors=DisplaySectors(imageLeft: result.sectors[0].distanceMetres,
            imageCenter: result.sectors[1].distanceMetres, imageRight: result.sectors[2].distanceMetres)
        guard accessible.showLocalPreview(sectors, sourceMilliseconds: source*1000,
            receiptMilliseconds: value.receipt*1000, token: value.displayToken) else {
            accessible.invalidateDepth(.unknown)
            sample=nil; image=nil; distances=[nil,nil,nil]; summary=nil; clearDepthDetails(); resetCheck()
            status="Waiting for a new display frame."; return
        }
        lastSource=source; sample=value; image=value.image; summary=result
        distances=result.sectors.map(\.distanceMetres)
        let configuration = try! DepthSectorConfiguration()
        depthDetails=value.observation.summary.sectors.map { sector in
            let coverage = Int((sector.validFraction ?? 0) * 100)
            switch sector.evidence {
            case .measured:
                return "High-confidence depth: \(coverage)% of this column."
            case .insufficientCoverage:
                let minimum = Int(configuration.minimumValidFraction * 100)
                return "Not enough high-confidence depth: \(coverage)%; need \(minimum)%."
            case .insufficientSamples:
                return "Too few usable depth samples: \(sector.validSamples); need \(configuration.minimumValidSamples)."
            case .unavailable:
                return "Depth unavailable for this column."
            }
        }
        check.observeGeometry(value.observation.geometry); syncProgress()
        status=check.complete ? "Portrait target check complete for this session." : "Live portrait view; repeat target check after remounting."
        if result.reason == .processedFrame, result.sectors.count == 3 {
            let values = result.sectors
            if let left = try? CaneSightTelemetry.DepthSector(distanceMetres: values[0].distanceMetres, validFraction: values[0].validFraction ?? 0),
               let center = try? CaneSightTelemetry.DepthSector(distanceMetres: values[1].distanceMetres, validFraction: values[1].validFraction ?? 0),
               let right = try? CaneSightTelemetry.DepthSector(distanceMetres: values[2].distanceMetres, validFraction: values[2].validFraction ?? 0),
               let depth = try? CaneSightTelemetry.DepthSample(capturedAtMS: source*1000, tracking: .normal,
                                                             left: left, center: center, right: right) {
                telemetry?.submit(depth, ticket: value.transportTicket)
            }
        }
    }
    func setApplicationActive(_ value: Bool) { setActive(value) }
    func setInterrupted(_ value: Bool) {
        telemetry?.setInterrupted(value)
        if value { requested=false; halt("Camera interrupted; depth unknown. Restart when ready.", pause: false) }
    }
    func setTrackingNormal(_ normal: Bool) {
        if !normal { halt("Tracking unavailable; depth unknown.") }
    }
    func sessionFailed() { telemetry?.sessionFailed(); requested=false; halt("Camera failed; restart when ready.", pause: false) }
    func sessionRestarted() { halt("New session; waiting for fresh depth.") }
    func openSettings() {
        if let url=URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
    }
    func record() {
        guard let sample else { status="Need a new valid frame."; return }
        do {
            try check.record(summary: sample.observation.summary, geometry: sample.observation.geometry,
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
    let receipt: Double
    let displayToken: DepthDisplayToken
    let transportTicket: TransportCaptureTicket?
}
struct CameraEvent: @unchecked Sendable {
    let epoch: UUID
    let sample: CameraSample?
    let loss: UInt64
    var interrupted=false
}

/// Two bounded frame slots and a latest-only main delivery. Loss serials survive
/// coalescing, so a later good frame cannot hide a tracking/buffer failure.
final class CameraCapture: NSObject, ARSessionDelegate, @unchecked Sendable {
    let callbacks=DispatchQueue(label: "MountCheck.ARCallbacks")
    private let worker=DispatchQueue(label: "MountCheck.Worker")
    private let context=CIContext(options: [.cacheIntermediates:false])
    private let lock=NSLock()
    private var epoch: UUID?
    private var pending: (ARFrame,UUID,Double,DepthDisplayToken,TransportCaptureTicket?)?
    private var transportFence: CaptureTransportFence?
    private var displayToken: DepthDisplayToken?
    private var working=false
    private var delivery: CameraEvent?
    private var scheduled=false
    private var loss: UInt64=0
    private var next: Double=0
    private let receive: @MainActor @Sendable (CameraEvent)->Void
    init(receive: @escaping @MainActor @Sendable (CameraEvent)->Void) { self.receive=receive }
    func setTransportFence(_ value: CaptureTransportFence) {
        lock.lock(); transportFence=value; lock.unlock()
    }
    func begin(_ value: UUID, token: DepthDisplayToken) {
        lock.lock(); epoch=value; displayToken=token; loss=0; next=0; lock.unlock()
    }
    func updateDisplayToken(_ value: DepthDisplayToken) {
        lock.lock(); displayToken=value; lock.unlock()
    }
    func stop() { lock.lock(); epoch=nil; pending=nil; delivery=nil; lock.unlock() }
    func session(_ session: ARSession,didUpdate frame: ARFrame) {
        let now=CACurrentMediaTime()
        lock.lock(); let fence=transportFence; lock.unlock()
        if !frame.timestamp.isFinite || frame.timestamp < 0 { fence?.revoke() }
        if case .normal = frame.camera.trackingState {
            if frame.sceneDepth == nil { fence?.revoke() }
        } else { fence?.revoke() }
        // Ticket belongs to capture admission, never to later worker completion.
        let ticket=fence?.captureTicket()
        lock.lock()
        guard let epoch, let displayToken, now.isFinite, now>=next else { lock.unlock(); return }
        next=now+0.2; pending=(frame,epoch,now,displayToken,ticket)
        let launch = !working; working=true; lock.unlock()
        if launch { worker.async { self.process() } }
    }
    private func process() {
        while true {
            lock.lock()
            guard let input=pending else { working=false; lock.unlock(); return }
            pending=nil; let current=epoch==input.1; lock.unlock()
            guard current else { continue }
            var sample: CameraSample?
            if let observation=try? PortraitDepth.process(input.0) {
                let source=CIImage(cvPixelBuffer: input.0.capturedImage)
                let t=observation.geometry.mapping
                let w=source.extent.width,h=source.extent.height
                // ARKit uses normalized top-left coordinates; CoreImage uses
                // pixel bottom-left coordinates. Convert both ends explicitly.
                let pixels=CGAffineTransform(a: 180*t.a/w,b: -320*t.b/w,
                    c: -180*t.c/h,d: 320*t.d/h,tx: 180*(t.c+t.tx),ty: 320*(1-t.d-t.ty))
                if let image=context.createCGImage(source.transformed(by: pixels),from: CGRect(x: 0,y: 0,width: 180,height: 320)) {
                    sample=CameraSample(observation: observation,image: image,receipt: input.2,
                                        displayToken: input.3,transportTicket: input.4)
                }
            }
            emit(sample,epoch: input.1)
        }
    }
    private func emit(_ sample: CameraSample?,epoch value: UUID) {
        lock.lock()
        guard epoch==value else { lock.unlock(); return }
        if sample==nil { loss &+= 1 }
        let fence=transportFence
        delivery=CameraEvent(epoch: value,sample: sample,loss: loss)
        let launch = !scheduled; scheduled=true; lock.unlock()
        if sample == nil { fence?.revoke() }
        if launch {
            DispatchQueue.main.async {
                self.lock.lock(); let value=self.delivery; self.delivery=nil; self.scheduled=false; self.lock.unlock()
                if let value { self.receive(value) }
            }
        }
    }
    private func interrupt() {
        lock.lock(); let value=epoch; let fence=transportFence; epoch=nil; pending=nil; delivery=nil; lock.unlock()
        fence?.revoke() // Before the MainActor event can wait behind UI work.
        if let value {
            let event=CameraEvent(epoch: value,sample: nil,loss: 0,interrupted: true)
            DispatchQueue.main.async { self.receive(event) }
        }
    }
    func sessionWasInterrupted(_ session: ARSession) { interrupt() }
    func session(_ session: ARSession,didFailWithError error: Error) { interrupt() }
}
