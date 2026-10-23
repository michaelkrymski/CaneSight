import SwiftUI
import AVFoundation
import QuartzCore
import CaneSightStatus
import CaneSightStatusUI
import CaneSightCoarseLocation
import CaneSightCoreLocation

@MainActor final class AppServices: ObservableObject {
    let speech: LocalStatusSpeech
    let status: StatusController
    let statusUI: AccessibleStatusModel
    let camera: CameraController
    let location: LocalLocationController
    private var lifecycleProof = [[String: Int]]()

    init() {
        let speech = LocalStatusSpeech()
        self.speech=speech
        let status=StatusController(nowMilliseconds: { CACurrentMediaTime()*1000 }, cancelAudioNow: {
            speech.cancel()
        })
        self.status=status
        statusUI=AccessibleStatusModel(controller: status)
        camera=CameraController(statusController: status)
        location=LocalLocationController()
    }
    func setActive(_ active: Bool) {
        let before = camera.distances.compactMap { $0 }.count
        status.setSceneActive(active)
        camera.setActive(active)
        location.setActive(active)
        if !active { _ = speech.cancel() }
        // Opt-in test evidence only: counts/booleans, never readings or timestamps.
        if ProcessInfo.processInfo.arguments.contains("--lifecycle-probe"), lifecycleProof.count < 24 {
            lifecycleProof.append(["active": active ? 1 : 0, "knownBefore": before,
                "knownAfter": camera.distances.compactMap { $0 }.count])
            if let folder = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first,
               let data = try? JSONSerialization.data(withJSONObject: lifecycleProof) {
                try? data.write(to: folder.appendingPathComponent("cs013-lifecycle-proof.json"), options: .atomic)
            }
        }
    }
    func readStatus() {
        status.cancelAudio()
        guard let ticket=status.beginAudioDisplay() else { return }
        // Fixed app status only: no scene description, distances, movement or
        // queued repeat. A new explicit request is required after cancellation.
        let text="CaneSight research prototype. \(status.snapshot.depth.text). \(status.snapshot.connection.text). No crossing permission."
        speech.speak(text, onStart: { [weak status] in status?.audioStarted(ticket) },
                     onFinish: { [weak status] in status?.audioFinished(ticket) })
    }
}

/// One local utterance. Invalidate callbacks before stopping the sink; neither
/// VoiceOver nor system audio is controlled. Audible speaker delay is unmeasured.
@MainActor final class LocalStatusSpeech: NSObject, AVSpeechSynthesizerDelegate {
    private let synthesizer=AVSpeechSynthesizer()
    private var current: ObjectIdentifier?
    private var onStart: (() -> Void)?
    private var onFinish: (() -> Void)?
    override init() { super.init(); synthesizer.delegate=self }
    func speak(_ text: String, onStart: @escaping () -> Void, onFinish: @escaping () -> Void) {
        guard cancel() == .requested else { onFinish(); return }
        let utterance=AVSpeechUtterance(string: text)
        current=ObjectIdentifier(utterance); self.onStart=onStart; self.onFinish=onFinish
        synthesizer.speak(utterance)
    }
    @discardableResult func cancel() -> CancellationResult {
        let needed = current != nil || synthesizer.isSpeaking || synthesizer.isPaused
        current=nil; onStart=nil; onFinish=nil
        let accepted=synthesizer.stopSpeaking(at: .immediate)
        return !needed || accepted ? .requested : .failed
    }
    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didStart utterance: AVSpeechUtterance) {
        let id=ObjectIdentifier(utterance)
        Task { @MainActor [weak self] in if self?.current == id { self?.onStart?() } }
    }
    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        let id=ObjectIdentifier(utterance)
        Task { @MainActor [weak self] in
            guard let self, self.current == id else { return }
            let completion=self.onFinish
            self.current=nil; self.onStart=nil; self.onFinish=nil
            completion?()
        }
    }
}

@MainActor final class LocalLocationController: ObservableObject {
    @Published private(set) var consent=false
    @Published private(set) var snapshot: LocationSnapshot?
    private var active=false
    private var timer: Timer?
    private lazy var source=CoreLocationSource(policy: try! LocationPolicy(),
        purgeCachedAndQueuedContext: { [weak self] in self?.snapshot=nil })
    func setActive(_ value: Bool) {
        active=value
        source.setForegroundActive(value)
        timer?.invalidate(); timer=nil
        if value {
            refresh()
            timer=Timer.scheduledTimer(withTimeInterval: 1,repeats: true) { [weak self] _ in
                MainActor.assumeIsolated { self?.refresh() }
            }
        } else { snapshot=nil }
    }
    func setConsent(_ value: Bool) {
        consent=value
        source.setSharingConsent(value)
        refresh()
    }
    private func refresh() { snapshot=active ? source.context.snapshot() : nil }
    var message: String {
        guard consent else { return "Location off" }
        guard let snapshot else { return "Location unavailable while inactive" }
        switch snapshot.unavailable {
        case nil: return "Coarse location available locally"
        case .noConsent: return "Location off"
        case .unauthorized: return "Location permission unavailable"
        case .inactive: return "Location unavailable while inactive"
        case .noFix: return "Waiting for a new location fix"
        case .invalidFix: return "Location quality insufficient"
        case .staleFix: return "Location expired; waiting for a new fix"
        case .clockFault: return "Location clock unavailable"
        }
    }
}
