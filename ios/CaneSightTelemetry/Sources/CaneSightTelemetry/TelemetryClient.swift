import Foundation

private final class LatestDepth: @unchecked Sendable {
    private let lock = NSLock()
    private var value: DepthSample?
    private var enabled = false
    func put(_ sample: DepthSample) {
        lock.lock(); defer { lock.unlock() }
        if enabled && (value == nil || sample.capturedAtMS > value!.capturedAtMS) { value = sample }
    }
    func take() -> DepthSample? {
        lock.lock(); defer { lock.unlock() }
        let result = value; value = nil; return result
    }
    func clear() { lock.lock(); value = nil; enabled = false; lock.unlock() }
    func enable() { lock.lock(); value = nil; enabled = true; lock.unlock() }
}

/// Header-authenticated native phone transport. Explicit source clock injection
/// is required; CS-014 capture timestamps and clock replies must use that clock.
/// No default ARKit clock equivalence, source readiness or enrollment is inferred.
public actor TelemetryClient {
    public typealias SocketFactory = @Sendable (PhoneSession) async throws -> any TelemetrySocket
    private let grant: PhoneSession
    private let clock: @Sendable () throws -> Double
    private let factory: SocketFactory
    private let mailbox = LatestDepth()
    private var core: TelemetryCore
    private var generation = UUID()
    private var socket: (any TelemetrySocket)?
    private var ticker: Task<Void, Never>?, dialTask: Task<Void, Never>?
    private var sendTask: Task<Void, Never>?, receiveTask: Task<Void, Never>?
    private var dialStarted: Double?
    private var retryAt: Double = 0, retryDelay: Double = 500
    private var running = false
    public init(session: PhoneSession, clock: @escaping @Sendable () throws -> Double,
                socketFactory: @escaping SocketFactory = { try await NativeWebSocket.connect($0) }) {
        grant = session; self.clock = clock; factory = socketFactory; core = TelemetryCore(session: session)
    }
    /// Synchronous latest-only producer handoff: no Task per AR frame or FIFO.
    public nonisolated func submit(_ sample: DepthSample) { mailbox.put(sample) }
    public func status() -> TelemetryStatus { core.status }
    private func now() -> Double? {
        do { let value = try clock(); try core.observe(now: value); return value }
        catch { core.fail(.clock); return nil }
    }
    public func start() {
        guard !running, core.status.phase != .closed, core.status.phase != .failed else { return }
        running = true
        ticker = Task { [weak self] in
            while !Task.isCancelled {
                await self?.tick()
                do { try await Task.sleep(nanoseconds: 10_000_000) } catch { return }
            }
        }
    }
    /// CS-017 calls this on interruption/backgrounding; no automatic ready recovery.
    public func suspend() {
        guard let time = now() else { breakConnection(retry: false, at: 0); return }
        try? core.suspend(now: time); breakConnection(retry: false, at: time)
    }
    public func resume() {
        guard let time = now() else { breakConnection(retry: false, at: 0); return }
        try? core.resume(now: time); retryAt = time
    }
    public func setProducerState(_ state: ProducerState) {
        let previous = core.status.producer
        guard let time = now() else { breakConnection(retry: false, at: 0); return }
        try? core.setProducerState(state, now: time)
        if state != .ready && state != previous {
            breakConnection(retry: true, at: time)
        }
    }
    public func close() {
        running = false; core.close()
        ticker?.cancel(); ticker = nil
        breakConnection(retry: false, at: 0)
    }
    private func breakConnection(retry: Bool, at time: Double) {
        generation = UUID(); mailbox.clear()
        socket?.cancel(); socket = nil
        dialTask?.cancel(); sendTask?.cancel(); receiveTask?.cancel()
        dialTask = nil; sendTask = nil; receiveTask = nil; dialStarted = nil
        // Retain all sequence/capture/rate high-water marks through reconnect.
        if core.status.phase != .failed && core.status.phase != .closed {
            try? core.disconnected(now: time)
        }
        if retry { retryAt = time+retryDelay; retryDelay = min(8000, retryDelay*2) }
    }
    // Internal for deterministic scheduling tests; the public timer uses the same path.
    func tick() {
        guard running else { return }
        guard let time = now() else { breakConnection(retry: false, at: 0); return }
        let phase = core.status.phase
        guard phase != .closed && phase != .failed && phase != .suspended else {
            breakConnection(retry: false, at: time); return
        }
        if let dialStarted, time-dialStarted >= 5000 {
            breakConnection(retry: true, at: time); return
        }
        if (try? core.sendTimedOut(now: time)) == true {
            breakConnection(retry: true, at: time); return
        }
        if let sample = mailbox.take() { _ = try? core.offer(sample, now: time) }
        if socket == nil && dialTask == nil && time >= retryAt {
            try? core.connecting(now: time)
            guard core.status.phase == .connecting else { return }
            let epoch = generation, factory = self.factory, grant = self.grant
            dialStarted = time
            dialTask = Task { [weak self] in
                do {
                    let channel = try await factory(grant)
                    guard !Task.isCancelled, let self else { channel.cancel(); return }
                    await self.opened(channel, epoch: epoch)
                } catch { await self?.failed(error, epoch: epoch) }
            }
        }
        if let channel = socket, sendTask == nil {
            let epoch = generation
            sendTask = Task { [weak self] in await self?.sendOne(channel, epoch: epoch) }
        }
    }
    private func opened(_ channel: any TelemetrySocket, epoch: UUID) {
        guard epoch == generation, let time = now(), core.status.phase == .connecting else {
            channel.cancel(); return
        }
        do { try core.opened(now: time) }
        catch { channel.cancel(); core.fail(.clock); return }
        mailbox.enable(); socket = channel; dialTask = nil; dialStarted = nil; retryDelay = 500
        receiveTask = Task { [weak self] in
            do {
                while !Task.isCancelled {
                    let data = try await channel.receive()
                    guard let self else { channel.cancel(); return }
                    await self.received(data, epoch: epoch)
                }
            } catch { await self?.failed(error, epoch: epoch) }
        }
    }
    private func received(_ data: Data, epoch: UUID) {
        guard epoch == generation else { return }
        guard let time = now() else { breakConnection(retry: false, at: 0); return }
        do { _ = try core.receiveProbe(data, receivedAtMS: time) }
        catch { core.fail(.invalidControl); breakConnection(retry: false, at: time) }
    }
    private func sendOne(_ channel: any TelemetrySocket, epoch: UUID) async {
        guard epoch == generation else { return }
        guard let time = now() else { breakConnection(retry: false, at: 0); return }
        do {
            // Build t3 immediately before handing bytes to the native send API.
            guard let packet = try core.next(now: time) else { sendTask = nil; return }
            try await channel.send(packet.data)
            guard epoch == generation else { return }
            guard let completedAt = now() else { breakConnection(retry: false, at: 0); return }
            if !(try core.completed(packet.id, now: completedAt)) {
                breakConnection(retry: true, at: completedAt); return
            }
            sendTask = nil
        } catch { failed(error, epoch: epoch) }
    }
    private func failed(_ error: Error, epoch: UUID) {
        guard epoch == generation else { return }
        guard let time = now() else { breakConnection(retry: false, at: 0); return }
        let failure = error as? TelemetryError
        let fatal = failure == .rejected || failure == .invalidControl || failure == .sequenceExhausted || failure == .probeCapacity
        if fatal { core.fail(failure!) }
        breakConnection(retry: !fatal, at: time)
    }
    deinit {
        ticker?.cancel(); dialTask?.cancel(); sendTask?.cancel(); receiveTask?.cancel(); socket?.cancel()
    }
}
