import Foundation
import CaneSightLifecycle
import CaneSightTelemetry

/// Caller-owned calibration, not a calibration algorithm or a readiness claim.
/// nowMilliseconds MUST use the source clock used by ARFrame capture timestamps
/// and native clock replies. Bounds must include independently measured error.
struct VerifiedCaptureClock: Sendable {
    let evidenceID: String
    let nowMilliseconds: @Sendable () -> Double
    let bound: @Sendable (Double) -> CaptureTime?
    init(evidenceID: String, nowMilliseconds: @escaping @Sendable () -> Double,
         bound: @escaping @Sendable (Double) -> CaptureTime?) throws {
        guard evidenceID.range(of: #"\A[A-Za-z0-9_-]{1,64}\z"#, options: .regularExpression) != nil else {
            throw TelemetryError.configuration
        }
        self.evidenceID = evidenceID; self.nowMilliseconds = nowMilliseconds; self.bound = bound
    }
}

struct TransportCaptureTicket: Equatable, Sendable { fileprivate let epoch: UUID }

/// A synchronous boundary usable from both AR callbacks and MainActor. No FIFO.
/// cancel handlers must be prompt and must prevent further native sends; the
/// accepted NativeWebSocket.cancel implementation provides that contract.
final class CaptureTransportFence: @unchecked Sendable {
    private let lock = NSLock()
    private var epoch = UUID()
    private var enabled = false
    private var captures = false
    private var cancellation: (@Sendable () -> Void)?
    func open() -> TransportCaptureTicket {
        revoke()
        return lock.withLock {
            enabled = true
            return TransportCaptureTicket(epoch: epoch)
        }
    }
    func connectionTicket() -> TransportCaptureTicket? {
        lock.withLock { enabled ? TransportCaptureTicket(epoch: epoch) : nil }
    }
    func captureTicket() -> TransportCaptureTicket? {
        lock.withLock { enabled && captures ? TransportCaptureTicket(epoch: epoch) : nil }
    }
    func current(_ ticket: TransportCaptureTicket) -> Bool {
        lock.withLock { enabled && epoch == ticket.epoch }
    }
    func allowCaptures(_ ticket: TransportCaptureTicket) {
        lock.withLock { if enabled && epoch == ticket.epoch { captures = true } }
    }
    @discardableResult func register(_ ticket: TransportCaptureTicket,
                                    cancel: @escaping @Sendable () -> Void) -> Bool {
        let accepted = lock.withLock {
            guard enabled && epoch == ticket.epoch else { return false }
            cancellation = cancel; return true
        }
        if !accepted { cancel() }
        return accepted
    }
    @discardableResult func revoke(_ ticket: TransportCaptureTicket? = nil) -> Bool {
        let result: (Bool, (@Sendable () -> Void)?) = lock.withLock {
            if let ticket, (!enabled || epoch != ticket.epoch) { return (false, nil) }
            enabled = false; captures = false; epoch = UUID()
            let cancel = cancellation; cancellation = nil
            return (true, cancel)
        }
        result.1?() // Outside the lock; synchronous even while the actor is busy.
        return result.0
    }
}

private final class FencedTelemetrySocket: TelemetrySocket, @unchecked Sendable {
    let inner: any TelemetrySocket
    let fence: CaptureTransportFence
    let ticket: TransportCaptureTicket
    let lost: @Sendable (TransportCaptureTicket) -> Void
    init(_ inner: any TelemetrySocket, fence: CaptureTransportFence,
         ticket: TransportCaptureTicket, lost: @escaping @Sendable (TransportCaptureTicket) -> Void) {
        self.inner = inner; self.fence = fence; self.ticket = ticket; self.lost = lost
    }
    func send(_ data: Data) async throws {
        guard fence.current(ticket) else { throw TelemetryError.connection }
        do { try await inner.send(data) }
        catch { cancel(); throw error }
    }
    func receive() async throws -> Data {
        guard fence.current(ticket) else { throw TelemetryError.connection }
        do {
            let data = try await inner.receive()
            guard fence.current(ticket) else { throw TelemetryError.connection }
            return data
        } catch { cancel(); throw error }
    }
    func cancel() {
        let notify = fence.revoke(ticket)
        inner.cancel()
        if notify { lost(ticket) }
    }
}

@MainActor private final class LifecycleTelemetryOwner { weak var value: LifecycleTelemetry? }

/// Opt-in session transport. Synchronous fence first, actor cleanup second.
/// One client preserves its wire sequence/capture history across recovery.
@MainActor final class LifecycleTelemetry: DepthLifecycleEvents {
    nonisolated let captureFence = CaptureTransportFence()
    private let clock: VerifiedCaptureClock
    private let client: TelemetryClient
    private let unknown: () -> Void
    private var revision = UUID()
    private var connection: LifecycleLease?
    private var socketTicket: TransportCaptureTicket?
    private var recovery: Task<Void, Never>?
    private var cleanup: Task<Void, Never>?
    private var cleanupPending = false
    private var closed = false
    private var sequence: UInt64 = 0
    private lazy var guardrail = DepthLifecycle<CaneSightTelemetry.DepthSample>(
        nowMilliseconds: clock.nowMilliseconds, hooks: LifecycleHooks(
            cancelAndDisconnect: { [weak self] in self?.invalidateTransport() },
            discardPendingTelemetry: {}, invalidateClockMapping: {},
            depthBecameUnknown: { [weak self] in self?.unknown() }))

    init(session: PhoneSession, clock: VerifiedCaptureClock, unknown: @escaping () -> Void,
         socketFactory: @escaping TelemetryClient.SocketFactory = { try await NativeWebSocket.connect($0) }) {
        self.clock = clock; self.unknown = unknown
        let fence = captureFence
        let owner = LifecycleTelemetryOwner()
        let lost: @Sendable (TransportCaptureTicket) -> Void = { ticket in
            Task { @MainActor in owner.value?.socketLost(ticket) }
        }
        client = TelemetryClient(session: session, clock: { clock.nowMilliseconds() }, socketFactory: { grant in
            guard let ticket = fence.connectionTicket() else { throw TelemetryError.connection }
            let opening = Task { try await socketFactory(grant) }
            // Still await a cancelled opening: even a factory that ignores
            // cancellation must have its eventual socket closed, never leaked.
            fence.register(ticket, cancel: { opening.cancel() })
            do {
                let socket = try await opening.value
                guard fence.register(ticket, cancel: { socket.cancel() }) else { throw TelemetryError.connection }
                let wrapped = FencedTelemetrySocket(socket, fence: fence, ticket: ticket, lost: lost)
                Task { @MainActor in owner.value?.socketOpened(ticket) }
                return wrapped
            } catch {
                if fence.revoke(ticket) { lost(ticket) }
                throw error
            }
        })
        owner.value = self
    }

    private func invalidateTransport() {
        revision = UUID(); connection = nil; socketTicket = nil
        recovery?.cancel(); recovery = nil
        captureFence.revoke()
        cleanupPending = true
        guard cleanup == nil else { return }
        cleanup = Task { @MainActor [weak self] in
            guard let self else { return }
            // Coalesce loss bursts rather than queueing one actor Task per frame.
            while self.cleanupPending {
                self.cleanupPending = false
                await self.client.suspend()
            }
            if self.closed { await self.client.close() }
            self.cleanup = nil
        }
    }
    private func recover() {
        guard !closed, recovery == nil, socketTicket == nil else { return }
        let now = clock.nowMilliseconds()
        guard let mapping = clock.bound(now), mapping.sourceMilliseconds == now,
              mapping.earliestLocalMilliseconds.isFinite, mapping.latestLocalMilliseconds.isFinite,
              mapping.earliestLocalMilliseconds <= mapping.latestLocalMilliseconds,
              mapping.latestLocalMilliseconds - mapping.earliestLocalMilliseconds <= 200 else {
            // Still validate the clock so reversal cannot be hidden by a missing
            // mapping. No connection or per-frame cleanup Task is created here.
            _ = guardrail.beginCapture()
            return
        }
        guard let lease = guardrail.beginConnection() else { return }
        let current = revision
        recovery = Task { @MainActor [weak self] in
            guard let self else { return }
            await self.cleanup?.value
            guard self.revision == current, !Task.isCancelled else { return }
            await self.client.resume()
            guard self.revision == current, !Task.isCancelled else { return }
            await self.client.setProducerState(.ready)
            guard self.revision == current, !Task.isCancelled else { return }
            self.connection = lease
            self.socketTicket = self.captureFence.open()
            await self.client.start()
            if self.revision == current { self.recovery = nil }
        }
    }
    private func socketOpened(_ ticket: TransportCaptureTicket) {
        guard ticket == socketTicket, captureFence.current(ticket), let connection,
              guardrail.connectionReady(connection), guardrail.clockMappingReady(connection) else {
            captureFence.revoke(ticket); return
        }
        captureFence.allowCaptures(ticket)
    }
    private func socketLost(_ ticket: TransportCaptureTicket) {
        guard ticket == socketTicket else { return }
        guardrail.disconnected() // Recovery waits for a newly observed normal frame.
    }
    func setApplicationActive(_ active: Bool) { guardrail.setApplicationActive(active) }
    func setInterrupted(_ interrupted: Bool) { guardrail.setInterrupted(interrupted) }
    func setTrackingNormal(_ normal: Bool) {
        // A worker/AR callback may have revoked synchronously while MainActor
        // was busy. A later good frame cannot hide that loss or reuse its socket.
        if let ticket = socketTicket, !captureFence.current(ticket) { guardrail.disconnected() }
        guardrail.setTrackingNormal(normal)
        if normal { recover() }
    }
    func sessionFailed() { guardrail.sessionFailed() }
    func sessionRestarted() {
        guardrail.setInterrupted(false)
        guardrail.sessionRestarted()
    }
    @discardableResult func submit(_ sample: CaneSightTelemetry.DepthSample,
                                   ticket: TransportCaptureTicket?) -> Bool {
        guard !closed, let ticket, captureFence.current(ticket) else { return false }
        guard let bounds = clock.bound(sample.capturedAtMS), bounds.sourceMilliseconds == sample.capturedAtMS else {
            guardrail.disconnected() // Mapping loss also purges the actor mailbox.
            return false
        }
        guard let lease = guardrail.beginCapture(), sequence < UInt64.max else { return false }
        guard guardrail.submit(sample, sequence: sequence, captureTime: bounds, lease: lease),
              let delivery = guardrail.takeForImmediateSend(), guardrail.maySend(delivery),
              captureFence.current(ticket) else { return false }
        sequence += 1
        client.submit(delivery.payload) // Nonisolated synchronous latest-only mailbox.
        return true
    }
    func close() {
        closed = true; guardrail.requireNewEnrollment()
    }
    deinit { captureFence.revoke() }
}
