import ARKit
import AVFoundation
import SwiftUI
import QuartzCore
import CaneSightDepth
import CaneSightDepthARKit
import CaneSightLifecycle
import CaneSightARLifecycle
import CaneSightTelemetry
import CaneSightCoarseLocation
import CaneSightPreviewState

/// Main-actor preview. Never authorizes transport, clock mapping or motor output.
@MainActor
final class CameraController: ObservableObject, DepthLifecycleEvents {
    @Published private(set) var summary: DepthSectorSummary?
    @Published private(set) var status = "Camera stopped; depth unknown."
    @Published private(set) var requested = false
    @Published private(set) var permissionDenied = false
    let supported = ARKitDepthAdapter.supportsSceneDepth
    private let session = ARSession()
    private var active = false
    private var preview = PreviewState<DepthSectorSummary>()
    private var epoch: UUID { preview.epoch }
    private var timer: Timer?
    private lazy var bridge = ARLifecycleBridge(lifecycle: self)
    private lazy var capture = PreviewCapture { [weak self] event in self?.receive(event) }

    func setActive(_ value: Bool) {
        guard active != value else { return }
        active = value
        if value && requested { runIfAuthorized() }
        else if !value { invalidate("App inactive; depth unknown.") }
    }

    func start() {
        guard supported else { status = "LiDAR scene depth unavailable on this device."; return }
        requested = true
        runIfAuthorized()
    }

    private func runIfAuthorized() {
        guard requested, active else { return }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: runSession()
        case .notDetermined:
            invalidate("Camera permission required; depth unknown.")
            let permissionEpoch = epoch
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                Task { @MainActor in
                    guard let self, self.epoch == permissionEpoch, self.active, self.requested else { return }
                    if granted { self.runSession() }
                    else { self.permissionDenied = true; self.requested = false; self.status = "Camera permission denied; depth unavailable." }
                }
            }
        default:
            permissionDenied = true
            requested = false
            invalidate("Camera permission denied or restricted; depth unavailable.")
        }
    }

    private func runSession() {
        guard supported, requested, active else { return }
        invalidate("Starting camera; waiting for a new depth frame.")
        permissionDenied = false
        capture.begin(epoch)
        session.delegate = capture
        session.delegateQueue = capture.callbackQueue
        let configuration = ARWorldTrackingConfiguration()
        configuration.frameSemantics.insert(.sceneDepth)
        session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
        timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.tick() }
        }
    }

    func stop() {
        requested = false
        invalidate("Camera stopped; depth unknown.")
    }

    private func invalidate(_ reason: String) {
        preview.invalidate()
        capture.stop()
        session.pause()
        timer?.invalidate()
        timer = nil
        summary = nil
        status = reason
    }

    private func tick() {
        preview.tick(nowSeconds: CACurrentMediaTime())
        if summary != nil && preview.value == nil {
            summary = nil
            status = "No recent frame; depth unknown."
        }
    }

    private func receive(_ event: PreviewCapture.Event) {
        guard event.epoch == epoch, active, requested else { return }
        switch event.payload {
        case .depth(let result, let receipt):
            let now = CACurrentMediaTime()
            guard preview.accept(result, epoch: event.epoch,
                                 sourceSeconds: result.captureTimestampSeconds,
                                 receiptSeconds: receipt, nowSeconds: now) else {
                summary = nil
                status = "Delayed or invalid frame; depth unknown."
                return
            }
            summary = preview.value
            status = result.reason == .processedFrame
                ? "Live local preview; sensor timing and physical mapping unverified."
                : "Depth unknown: \(result.reason.rawValue)."
        case .interrupted: bridge.sessionWasInterrupted()
        case .interruptionEnded: bridge.sessionInterruptionEnded()
        case .failed: bridge.sessionDidFail()
        }
    }

    func setApplicationActive(_ value: Bool) { setActive(value) }
    func setInterrupted(_ value: Bool) {
        if value { invalidate("AR session interrupted; depth unknown. Stop and restart the camera.") }
        else if requested && active { runIfAuthorized() }
    }
    func setTrackingNormal(_ normal: Bool) {
        if !normal { summary = nil; status = "Tracking unavailable; depth unknown." }
    }
    func sessionFailed() { requested = false; invalidate("AR session failed; stop and restart the camera.") }
    func sessionRestarted() { invalidate("New session; waiting for a new frame.") }
    func openSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
    }
}

/// One replaceable frame, one worker and one replaceable main-actor delivery.
/// ARFrame stays local; only owned depth summaries leave the worker.
final class PreviewCapture: NSObject, ARSessionDelegate, @unchecked Sendable {
    enum Payload: Sendable {
        case depth(DepthSectorSummary, Double), interrupted, interruptionEnded, failed
    }
    struct Event: Sendable { let epoch: UUID; let payload: Payload }
    let callbackQueue = DispatchQueue(label: "CaneSight.ARCallbacks")
    private let worker = DispatchQueue(label: "CaneSight.DepthWorker")
    private let lock = NSLock()
    private var epoch: UUID?
    private var pending: (ARFrame, UUID, Double)?
    private var working = false
    private var delivery: Event?
    private var deliveryScheduled = false
    private var nextReceipt: Double = 0
    private let receive: @MainActor @Sendable (Event) -> Void

    init(receive: @escaping @MainActor @Sendable (Event) -> Void) { self.receive = receive }
    func begin(_ value: UUID) { lock.lock(); epoch = value; nextReceipt = 0; lock.unlock() }
    func stop() { lock.lock(); epoch = nil; pending = nil; delivery = nil; lock.unlock() }

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        let receipt = CACurrentMediaTime()
        lock.lock()
        guard let epoch, receipt.isFinite, receipt >= nextReceipt else { lock.unlock(); return }
        nextReceipt = receipt + 0.1
        pending = (frame, epoch, receipt)
        let launch = !working
        working = true
        lock.unlock()
        if launch { worker.async { self.process() } }
    }

    private func process() {
        let adapter = ARKitDepthAdapter(configuration: try! DepthSectorConfiguration())
        while true {
            lock.lock()
            guard let input = pending else { working = false; lock.unlock(); return }
            pending = nil
            let current = epoch == input.1
            lock.unlock()
            if current {
                let result = adapter.process(input.0)
                emit(Event(epoch: input.1, payload: .depth(result, input.2)))
            }
        }
    }

    private func emit(_ event: Event) {
        lock.lock()
        guard epoch == event.epoch else { lock.unlock(); return }
        delivery = event
        let launch = !deliveryScheduled
        deliveryScheduled = true
        lock.unlock()
        if launch {
            DispatchQueue.main.async {
                self.lock.lock()
                let event = self.delivery
                self.delivery = nil
                self.deliveryScheduled = false
                self.lock.unlock()
                if let event { self.receive(event) }
            }
        }
    }

    private func signal(_ payload: Payload) {
        // Critical loss cannot be replaced by a later depth delivery. Fence the
        // worker immediately, then invalidate UI on its actor. Restart is explicit.
        lock.lock()
        let current = epoch
        epoch = nil
        pending = nil
        delivery = nil
        lock.unlock()
        if let current {
            let event = Event(epoch: current, payload: payload)
            DispatchQueue.main.async { self.receive(event) }
        }
    }
    func sessionWasInterrupted(_ session: ARSession) { signal(.interrupted) }
    func sessionInterruptionEnded(_ session: ARSession) { signal(.interruptionEnded) }
    func session(_ session: ARSession, didFailWithError error: Error) { signal(.failed) }
}
