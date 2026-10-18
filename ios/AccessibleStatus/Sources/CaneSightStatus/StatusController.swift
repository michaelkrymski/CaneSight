import Foundation

public enum ConnectionStatus: String, Sendable, CaseIterable {
    case unavailable, disconnected, connecting, connected

    public var text: String {
        switch self {
        case .unavailable: return "Connection unavailable"
        case .disconnected: return "Disconnected"
        case .connecting: return "Connecting"
        case .connected: return "Connected; sensor readiness is separate"
        }
    }
}

public enum DepthStatus: String, Sendable, CaseIterable {
    case unknown, waiting, inactive, interrupted, stale, permissionDenied, unsupported, failed, clockFailed
    case localPreview, boundedCapture

    public var text: String {
        switch self {
        case .unknown: return "Depth unknown"
        case .waiting: return "Waiting for fresh depth"
        case .inactive: return "App inactive; depth unknown"
        case .interrupted: return "Depth interrupted; waiting for fresh data"
        case .stale: return "Depth expired; unknown"
        case .permissionDenied: return "Camera permission denied; depth unavailable"
        case .unsupported: return "Depth unsupported on this device"
        case .failed: return "Depth unavailable"
        case .clockFailed: return "Clock unavailable; depth unknown"
        case .localPreview: return "Local depth preview; capture timing unverified"
        case .boundedCapture: return "Recent depth observation"
        }
    }
}

public enum AudioStatus: String, Sendable {
    case unavailable, idle, pending, playing, cancelling, cancelRequested, cancelFailed

    public var text: String {
        switch self {
        case .unavailable: return "Audio control unavailable"
        case .idle: return "No requested narration"
        case .pending: return "Narration requested"
        case .playing: return "Narration active"
        case .cancelling: return "Requesting audio cancellation"
        case .cancelRequested: return "Audio cancellation requested; output silence unverified"
        case .cancelFailed: return "Audio cancellation failed; use the local audio control"
        }
    }
}

public struct DisplaySectors: Equatable, Sendable {
    public let imageLeft: Double?
    public let imageCenter: Double?
    public let imageRight: Double?

    public init(imageLeft: Double?, imageCenter: Double?, imageRight: Double?) {
        func valid(_ value: Double?) -> Double? {
            guard let value, value.isFinite, value > 0 else { return nil }
            return value
        }
        self.imageLeft = valid(imageLeft)
        self.imageCenter = valid(imageCenter)
        self.imageRight = valid(imageRight)
    }

    public static let unknown = DisplaySectors(imageLeft: nil, imageCenter: nil, imageRight: nil)
    public var distances: [Double?] { [imageLeft, imageCenter, imageRight] }
}

/// UI epoch only; never a protocol readiness, transport, or speech authorization.
public struct DepthDisplayToken: Equatable, Sendable { fileprivate let value: UUID }
public struct AudioDisplayToken: Equatable, Sendable { fileprivate let value: UUID }

public struct StatusSnapshot: Equatable, Sendable {
    public let depth: DepthStatus
    public let connection: ConnectionStatus
    public let audio: AudioStatus
    public let sectors: DisplaySectors
    public let canCancelAudio: Bool
    public static let initial = StatusSnapshot(depth: .inactive, connection: .unavailable,
        audio: .unavailable, sectors: .unknown, canCancelAudio: false)
}

public enum CancellationResult: Equatable, Sendable { case requested, failed }

/// Presentation only. The host still owns CS-017 lifecycle, original capture
/// clock mapping, CS-016 transport, and CS-040 speech/consent/priority gates.
@MainActor public final class StatusController {
    public private(set) var snapshot = StatusSnapshot.initial
    public var onChange: ((StatusSnapshot) -> Void)?
    public var depthToken: DepthDisplayToken { DepthDisplayToken(value: depthEpoch) }

    private let nowMilliseconds: () -> Double
    private var cancelAction: (() -> CancellationResult)?
    private var depthEpoch = UUID()
    private var audioEpoch = UUID()
    private var audioToken: AudioDisplayToken?
    private var active = false
    private var lastNow: Double?
    private var clockFailed = false
    private var lastSource: Double?
    private var expiry: Double?
    private var cancelling = false
    private var notifying = false

    public init(nowMilliseconds: @escaping () -> Double,
                cancelAudioNow: (() -> CancellationResult)? = nil) {
        self.nowMilliseconds = nowMilliseconds
        self.cancelAction = cancelAudioNow
        if cancelAudioNow != nil { replace(audio: .idle) }
    }

    private func replace(depth: DepthStatus? = nil, connection: ConnectionStatus? = nil,
                         audio: AudioStatus? = nil, sectors: DisplaySectors? = nil) {
        let value = StatusSnapshot(depth: depth ?? snapshot.depth,
            connection: connection ?? snapshot.connection, audio: audio ?? snapshot.audio,
            sectors: sectors ?? snapshot.sectors, canCancelAudio: cancelAction != nil && !cancelling)
        guard value != snapshot else { return }
        snapshot = value
        // A host observer may synchronously clear lifecycle/transport state. Never
        // recursively deliver or create an unbounded notification queue.
        guard !notifying else { return }
        notifying = true
        onChange?(value)
        notifying = false
    }

    private func clock() -> Double? {
        guard !clockFailed else { return nil }
        let value = nowMilliseconds()
        guard value.isFinite, value >= 0, value <= 9_007_199_254_740,
              lastNow.map({ value >= $0 }) ?? true else {
            clockFailed = true
            clearDepth(.clockFailed)
            cancelIfNeeded()
            return nil
        }
        lastNow = value
        return value
    }

    public func setSceneActive(_ value: Bool) {
        guard active != value else { return }
        active = value
        clearDepth(value ? .waiting : .inactive)
        if !value { cancelIfNeeded() }
    }

    private func clearDepth(_ reason: DepthStatus) {
        depthEpoch = UUID()
        lastSource = nil
        expiry = nil
        replace(depth: clockFailed ? .clockFailed : reason, sectors: .unknown)
    }

    /// Call synchronously from the host's CS-017 depthBecameUnknown hook.
    /// Available states cannot be supplied through this invalidation API.
    public func invalidateDepth(_ reason: DepthStatus = .unknown) {
        clearDepth(reason == .localPreview || reason == .boundedCapture ? .unknown : reason)
        cancelIfNeeded()
    }

    public func setConnection(_ value: ConnectionStatus) {
        replace(connection: value)
        if value != .connected { cancelIfNeeded() }
        // A heartbeat/reconnect never renews depth or restores requested audio.
        // Independently healthy LOCAL depth may remain visible while offline.
    }

    /// Local-only preview. The deadline is explicitly callback recency, not sensor
    /// capture age. Never use this method to establish telemetry/motor readiness.
    @discardableResult public func showLocalPreview(
        _ sectors: DisplaySectors, sourceMilliseconds: Double, receiptMilliseconds: Double,
        token: DepthDisplayToken
    ) -> Bool {
        guard token == depthToken, active, let now = clock() else { return false }
        guard sourceMilliseconds.isFinite, sourceMilliseconds >= 0,
              lastSource.map({ sourceMilliseconds > $0 }) ?? true,
              receiptMilliseconds.isFinite, receiptMilliseconds >= 0,
              receiptMilliseconds <= now, now - receiptMilliseconds < 500 else {
            invalidateDepth(.unknown)
            return false
        }
        lastSource = sourceMilliseconds
        expiry = receiptMilliseconds + 500
        replace(depth: .localPreview, sectors: sectors)
        return true
    }

    /// Host provides conservative source-capture bounds from a VERIFIED mapping,
    /// not receipt time. This repeats a presentation expiry check, not calibration.
    @discardableResult public func showBoundedCapture(
        _ sectors: DisplaySectors, sourceMilliseconds: Double,
        earliestLocalMilliseconds: Double, latestLocalMilliseconds: Double,
        token: DepthDisplayToken
    ) -> Bool {
        guard token == depthToken, active, let now = clock() else { return false }
        let lower = earliestLocalMilliseconds, upper = latestLocalMilliseconds
        guard sourceMilliseconds.isFinite, sourceMilliseconds >= 0,
              lastSource.map({ sourceMilliseconds > $0 }) ?? true,
              lower.isFinite, upper.isFinite, lower >= 0, lower <= upper,
              upper <= now, now - lower < 500, upper - lower <= 200 else {
            invalidateDepth(.unknown)
            return false
        }
        lastSource = sourceMilliseconds
        expiry = lower + 500
        replace(depth: .boundedCapture, sectors: sectors)
        return true
    }

    /// Call independently of incoming data, e.g. the view's 100ms display tick.
    public func tick() {
        guard let now = clock() else { return }
        if let expiry, now >= expiry { clearDepth(.stale); cancelIfNeeded() }
    }

    /// Observe an already authorized CS-040 job. This does not start speech or
    /// authorize scene sharing. Keep the token with that job's callbacks.
    public func beginAudioDisplay() -> AudioDisplayToken? {
        guard active, !clockFailed, !cancelling, cancelAction != nil, clock() != nil,
              snapshot.audio != .cancelFailed, audioToken == nil else { return nil }
        audioEpoch = UUID()
        let token = AudioDisplayToken(value: audioEpoch)
        audioToken = token
        replace(audio: .pending)
        return token
    }

    public func audioStarted(_ token: AudioDisplayToken) {
        guard !cancelling, active, token == audioToken else { return }
        replace(audio: .playing)
    }

    public func audioFinished(_ token: AudioDisplayToken) {
        guard !cancelling, token == audioToken else { return }
        audioToken = nil
        replace(audio: .idle)
    }

    private func cancelIfNeeded() {
        if audioToken != nil { cancelAudio() }
    }

    /// Always a local synchronous hook, even when disconnected. Invalidate the
    /// display ticket BEFORE calling it, so queued/reentrant callbacks cannot
    /// undo cancellation. The hook must invalidate pending jobs AND stop the
    /// local speech sink before returning; no network wait, speech queue or await.
    /// Requested means the adapter accepted the request, NOT verified silence.
    public func cancelAudio() {
        guard !cancelling, let cancelAction else { return }
        cancelling = true
        audioEpoch = UUID()
        audioToken = nil
        replace(audio: .cancelling)
        let result = cancelAction()
        cancelling = false
        replace(audio: result == .requested ? .cancelRequested : .cancelFailed)
    }
}
