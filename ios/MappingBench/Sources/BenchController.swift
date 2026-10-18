import ARKit
import AVFoundation
import CoreImage
import QuartzCore
import SwiftUI
import CaneSightDepth
import CaneSightMountMapping
import CaneSightMountMappingARKit

@MainActor final class BenchController: ObservableObject {
    @Published private(set) var status = "Camera stopped; mapping unverified."
    @Published private(set) var image: CGImage?
    @Published private(set) var distances: [Double?] = [nil,nil,nil]
    @Published private(set) var counts = [0,0,0]
    @Published private(set) var target: Int? = 0
    @Published private(set) var requested = false
    let supported = ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)
    private let session = ARSession()
    private var active = false
    private var portrait = false
    private var epoch = UUID()
    private var sample: BenchSample?
    private var check = MountCheck()
    private var lastLoss: UInt64 = 0
    private var lastSource: Double?
    private var timer: Timer?
    private var orientationObserver: NSObjectProtocol?
    private lazy var capture = BenchCapture { [weak self] event in self?.receive(event) }

    init() {
        UIDevice.current.beginGeneratingDeviceOrientationNotifications()
        orientationObserver = NotificationCenter.default.addObserver(
            forName: UIDevice.orientationDidChangeNotification, object: nil, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.updateOrientation() }
            }
        portrait = UIDevice.current.orientation == .portrait
    }

    private func updateOrientation() {
        let value = UIDevice.current.orientation == .portrait
        guard value != portrait else { return }
        portrait = value
        if !value { halt("Hold the phone portrait upright; check reset.") }
        else if requested && active { authorize() }
    }
    func setActive(_ value: Bool) {
        guard active != value else { return }
        active = value
        if !value { halt("App inactive; depth unknown and check reset.") }
        else {
            updateOrientation()
            if requested && portrait { authorize() }
        }
    }
    func start() {
        guard supported else { status="Scene depth unavailable."; return }
        requested = true
        updateOrientation()
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
                    else { self.requested=false; self.halt("Camera permission denied; unavailable.") }
                }
            }
        default: requested=false; halt("Camera permission denied. Enable Camera in Settings for Mount Check.")
        }
    }
    private func run() {
        halt("Starting; waiting for portrait depth.")
        capture.begin(epoch)
        session.delegate=capture; session.delegateQueue=capture.callbacks
        let configuration=ARWorldTrackingConfiguration()
        configuration.frameSemantics.insert(.sceneDepth)
        session.run(configuration,options: [.resetTracking,.removeExistingAnchors])
        timer=Timer.scheduledTimer(withTimeInterval: 0.1,repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.tick() }
        }
    }
    private func halt(_ reason: String, pause: Bool=true) {
        epoch=UUID(); capture.stop()
        if pause { session.pause() }
        timer?.invalidate(); timer=nil
        sample=nil; image=nil; distances=[nil,nil,nil]; lastSource=nil; lastLoss=0
        resetCheck(); status=reason
    }
    func resetCheck() {
        check.reset()
        if let sample { check.observeGeometry(sample.observation.geometry) }
        syncProgress()
    }
    private func syncProgress() { counts=check.counts; target=check.nextTarget }
    private func tick() {
        guard let sample else { return }
        let now=CACurrentMediaTime()
        if !now.isFinite || now < sample.receipt || now-sample.receipt >= 0.5 {
            self.sample=nil; image=nil; distances=[nil,nil,nil]; resetCheck()
            status="No recent frame; depth unknown and check reset."
        }
    }
    private func receive(_ event: BenchEvent) {
        guard epoch == event.epoch, active, portrait, requested else { return }
        if event.interrupted {
            requested=false
            halt("AR interrupted; check reset. Restart after interruption ends.",pause: false)
            return
        }
        if event.loss != lastLoss { check.reset(); lastLoss=event.loss }
        guard let value=event.sample else {
            sample=nil; image=nil; distances=[nil,nil,nil]; syncProgress()
            status="Waiting for valid depth/tracking; check reset."
            return
        }
        let now=CACurrentMediaTime()
        guard now.isFinite, now >= value.receipt, now-value.receipt < 0.5,
              let source=value.observation.summary.captureTimestampSeconds,
              lastSource.map({ source > $0 }) ?? true else {
            sample=nil; image=nil; distances=[nil,nil,nil]; resetCheck()
            status="Delayed frame; depth unknown and check reset."; return
        }
        lastSource=source; sample=value; image=value.image
        distances=value.observation.summary.sectors.map(\.distanceMetres)
        check.observeGeometry(value.observation.geometry); syncProgress()
        status=check.complete ? "Portrait target check complete for this session." : "Live portrait view; physical mapping unverified until target check."
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

struct BenchSample: @unchecked Sendable {
    let observation: PortraitObservation
    let image: CGImage
    let receipt: Double
}
struct BenchEvent: @unchecked Sendable {
    let epoch: UUID
    let sample: BenchSample?
    let loss: UInt64
    var interrupted=false
}

/// Two bounded frame slots and a latest-only main delivery. Loss serials survive
/// coalescing, so a later good frame cannot hide a tracking/buffer failure.
final class BenchCapture: NSObject, ARSessionDelegate, @unchecked Sendable {
    let callbacks=DispatchQueue(label: "MountCheck.ARCallbacks")
    private let worker=DispatchQueue(label: "MountCheck.Worker")
    private let context=CIContext(options: [.cacheIntermediates:false])
    private let lock=NSLock()
    private var epoch: UUID?
    private var pending: (ARFrame,UUID,Double)?
    private var working=false
    private var delivery: BenchEvent?
    private var scheduled=false
    private var loss: UInt64=0
    private var next: Double=0
    private let receive: @MainActor @Sendable (BenchEvent)->Void
    init(receive: @escaping @MainActor @Sendable (BenchEvent)->Void) { self.receive=receive }
    func begin(_ value: UUID) { lock.lock(); epoch=value; loss=0; next=0; lock.unlock() }
    func stop() { lock.lock(); epoch=nil; pending=nil; delivery=nil; lock.unlock() }
    func session(_ session: ARSession,didUpdate frame: ARFrame) {
        let now=CACurrentMediaTime()
        lock.lock()
        guard let epoch, now.isFinite, now>=next else { lock.unlock(); return }
        next=now+0.2; pending=(frame,epoch,now)
        let launch = !working; working=true; lock.unlock()
        if launch { worker.async { self.process() } }
    }
    private func process() {
        while true {
            lock.lock()
            guard let input=pending else { working=false; lock.unlock(); return }
            pending=nil; let current=epoch==input.1; lock.unlock()
            guard current else { continue }
            var sample: BenchSample?
            if let observation=try? PortraitDepth.process(input.0) {
                let source=CIImage(cvPixelBuffer: input.0.capturedImage)
                let t=observation.geometry.mapping
                let w=source.extent.width,h=source.extent.height
                // ARKit uses normalized top-left coordinates; CoreImage uses
                // pixel bottom-left coordinates. Convert both ends explicitly.
                let pixels=CGAffineTransform(a: 180*t.a/w,b: -320*t.b/w,
                    c: -180*t.c/h,d: 320*t.d/h,tx: 180*(t.c+t.tx),ty: 320*(1-t.d-t.ty))
                if let image=context.createCGImage(source.transformed(by: pixels),from: CGRect(x: 0,y: 0,width: 180,height: 320)) {
                    sample=BenchSample(observation: observation,image: image,receipt: input.2)
                }
            }
            emit(sample,epoch: input.1)
        }
    }
    private func emit(_ sample: BenchSample?,epoch value: UUID) {
        lock.lock()
        guard epoch==value else { lock.unlock(); return }
        if sample==nil { loss &+= 1 }
        delivery=BenchEvent(epoch: value,sample: sample,loss: loss)
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
            let event=BenchEvent(epoch: value,sample: nil,loss: 0,interrupted: true)
            DispatchQueue.main.async { self.receive(event) }
        }
    }
    func sessionWasInterrupted(_ session: ARSession) { interrupt() }
    func session(_ session: ARSession,didFailWithError error: Error) { interrupt() }
}
