import Foundation

/// All hooks run synchronously on the same actor as the transport. They must not
/// enqueue a purge behind a reconnect or leave an old URLSession send running.
@MainActor public struct LifecycleHooks {
    public let cancelAndDisconnect: () -> Void
    public let discardPendingTelemetry: () -> Void
    public let invalidateClockMapping: () -> Void
    public let depthBecameUnknown: () -> Void

    public init(cancelAndDisconnect: @escaping () -> Void,
                discardPendingTelemetry: @escaping () -> Void,
                invalidateClockMapping: @escaping () -> Void,
                depthBecameUnknown: @escaping () -> Void) {
        self.cancelAndDisconnect = cancelAndDisconnect
        self.discardPendingTelemetry = discardPendingTelemetry
        self.invalidateClockMapping = invalidateClockMapping
        self.depthBecameUnknown = depthBecameUnknown
    }
}

/// Opaque barrier for async work. Old capture, connect and calibration callbacks
/// cannot be reused following any loss of capture/transport validity.
public struct LifecycleLease: Equatable, Sendable {
    fileprivate let generation: UUID
}

/// Capture time mapped into the injected local monotonic clock, in milliseconds.
/// The caller must supply a VERIFIED conservative interval, never callback receipt
/// time. Original source time is retained separately for protocol serialization.
public struct CaptureTime: Sendable {
    public let sourceMilliseconds: Double
    public let earliestLocalMilliseconds: Double
    public let latestLocalMilliseconds: Double

    public init(sourceMilliseconds: Double, earliestLocalMilliseconds: Double,
                latestLocalMilliseconds: Double) {
        self.sourceMilliseconds = sourceMilliseconds
        self.earliestLocalMilliseconds = earliestLocalMilliseconds
        self.latestLocalMilliseconds = latestLocalMilliseconds
    }
}

public struct DepthSample<Payload: Sendable>: Sendable {
    public let payload: Payload
    public let sequence: UInt64
    public let captureTime: CaptureTime
    fileprivate let lease: LifecycleLease
}

/// Lifecycle inputs also serve as a seam for the host's ARSession delegate.
@MainActor public protocol DepthLifecycleEvents: AnyObject {
    func setApplicationActive(_ active: Bool)
    func setInterrupted(_ interrupted: Bool)
    func setTrackingNormal(_ normal: Bool)
    func sessionFailed()
    func sessionRestarted()
}

/// One bounded pending observation. This is a local freshness gate, never a
/// crossing/motor verdict. The Pi independently enforces its own clock/age gate.
@MainActor public final class DepthLifecycle<Payload: Sendable>: DepthLifecycleEvents {
    private let now: () -> Double
    private let hooks: LifecycleHooks
    private var generation = UUID()
    private var active = false
    private var interrupted = false
    private var trackingNormal = false
    private var failed = false
    private var connected = false
    private var mapped = false
    private var cutoff: Double = 0
    private var lastNow: Double?
    private var lastSequence: UInt64?
    private var lastSourceTime: Double?
    private var pending: DepthSample<Payload>?
    public private(set) var requiresReenrollment = false

    public init(nowMilliseconds: @escaping () -> Double, hooks: LifecycleHooks) {
        self.now = nowMilliseconds
        self.hooks = hooks
    }

    private var captureAvailable: Bool {
        active && !interrupted && trackingNormal && !failed && !requiresReenrollment
    }

    private func invalidate() {
        generation = UUID()
        connected = false
        mapped = false
        pending = nil
        hooks.discardPendingTelemetry()
        hooks.cancelAndDisconnect()
        hooks.invalidateClockMapping()
        hooks.depthBecameUnknown()
    }

    private func clock() -> Double? {
        let value = now()
        guard value.isFinite, value >= 0,
              lastNow.map({ value >= $0 }) ?? true else {
            requiresReenrollment = true
            invalidate()
            return nil
        }
        lastNow = value
        return value
    }

    public func setApplicationActive(_ value: Bool) {
        guard active != value else { return }
        active = value
        // A resume never restores tracking or an old connection.
        trackingNormal = false
        invalidate()
    }

    public func setInterrupted(_ value: Bool) {
        guard interrupted != value else { return }
        interrupted = value
        trackingNormal = false
        invalidate()
    }

    public func setTrackingNormal(_ value: Bool) {
        guard trackingNormal != value else { return }
        trackingNormal = value
        invalidate()
    }

    public func sessionFailed() {
        failed = true
        trackingNormal = false
        invalidate()
    }

    /// Host calls only after explicitly running a new AR session configuration.
    /// This does not authorize a new protocol source boot or clear sequence IDs.
    public func sessionRestarted() {
        failed = false
        trackingNormal = false
        invalidate()
    }

    public func disconnected() { invalidate() }

    /// Call on capture-clock reset or identity/session change. Replace this guard
    /// only after operator enrollment of the new source epoch/session succeeds.
    public func requireNewEnrollment() {
        requiresReenrollment = true
        invalidate()
    }

    public func beginConnection() -> LifecycleLease? {
        guard clock() != nil, captureAvailable else { return nil }
        // Parallel connection attempts invalidate one another, including pending
        // sends on an existing transport. Only the newest completion is eligible.
        invalidate()
        return LifecycleLease(generation: generation)
    }

    @discardableResult public func connectionReady(_ lease: LifecycleLease) -> Bool {
        guard let time = clock(), captureAvailable, current(lease), !connected else { return false }
        connected = true
        cutoff = time
        return true
    }

    /// CS-016 supplies a fresh verified mapping after connecting. This method does
    /// not compute a mapping or replace the receiver's protocol clock exchange.
    @discardableResult public func clockMappingReady(_ lease: LifecycleLease) -> Bool {
        guard let time = clock(), captureAvailable, connected, current(lease), !mapped else { return false }
        mapped = true
        cutoff = time
        return true
    }

    public func beginCapture() -> LifecycleLease? {
        guard clock() != nil, captureAvailable, connected, mapped else { return nil }
        return LifecycleLease(generation: generation)
    }

    private func current(_ lease: LifecycleLease) -> Bool { lease.generation == generation }

    private func fresh(_ time: CaptureTime, at instant: Double) -> Bool {
        let lower = time.earliestLocalMilliseconds
        let upper = time.latestLocalMilliseconds
        return time.sourceMilliseconds.isFinite && time.sourceMilliseconds >= 0
            && lower.isFinite && upper.isFinite && lower >= cutoff
            && lower <= upper && upper <= instant && instant - lower <= 500
            && (upper - lower) / 2 <= 100
    }

    /// Invoke on this actor after worker processing. Delayed pre-interruption
    /// work is rejected even if its timestamp would otherwise still be fresh.
    @discardableResult public func submit(_ payload: Payload, sequence: UInt64,
                                         captureTime: CaptureTime, lease: LifecycleLease) -> Bool {
        guard let time = clock(), captureAvailable, connected, mapped, current(lease),
              fresh(captureTime, at: time),
              lastSequence.map({ sequence > $0 }) ?? true,
              lastSourceTime.map({ captureTime.sourceMilliseconds > $0 }) ?? true else { return false }
        lastSequence = sequence
        lastSourceTime = captureTime.sourceMilliseconds
        pending = DepthSample(payload: payload, sequence: sequence, captureTime: captureTime, lease: lease)
        return true
    }

    /// Rechecks age immediately before handing bytes to the transport. Do not
    /// queue the returned value for a reconnect. No heartbeat calls this method.
    public func takeForImmediateSend() -> DepthSample<Payload>? {
        let sample = pending
        pending = nil
        guard let time = clock(), let sample, captureAvailable, connected, mapped,
              current(sample.lease), fresh(sample.captureTime, at: time) else { return nil }
        return sample
    }

    /// Revalidate after any asynchronous serialization/await, on this actor.
    public func maySend(_ sample: DepthSample<Payload>) -> Bool {
        guard let time = clock() else { return false }
        return captureAvailable && connected && mapped && current(sample.lease)
            && fresh(sample.captureTime, at: time)
    }
}
