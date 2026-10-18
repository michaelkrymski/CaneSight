import XCTest
@testable import CaneSightTelemetry

final class TestClock: @unchecked Sendable {
    private let lock = NSLock()
    private var time: Double = 1000
    func read() -> Double { lock.withLock { time } }
    func set(_ time: Double) { lock.withLock { self.time = time } }
}
final class TestSocket: TelemetrySocket, @unchecked Sendable {
    private let lock = NSLock()
    private var output = [Data]()
    private var read: CheckedContinuation<Data, Error>?
    private var write: CheckedContinuation<Void, Error>?
    private var ended = false
    let blocked: Bool
    init(blocked: Bool = false) { self.blocked = blocked }
    var sent: [Data] { lock.withLock { output } }
    var cancelled: Bool { lock.withLock { ended } }
    func send(_ data: Data) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            lock.lock()
            if ended { lock.unlock(); continuation.resume(throwing: TelemetryError.closed); return }
            output.append(data)
            if blocked { write = continuation; lock.unlock() }
            else { lock.unlock(); continuation.resume() }
        }
    }
    func receive() async throws -> Data {
        try await withCheckedThrowingContinuation { continuation in
            lock.lock()
            if ended { lock.unlock(); continuation.resume(throwing: TelemetryError.closed); return }
            read = continuation; lock.unlock()
        }
    }
    func incoming(_ data: Data) {
        let continuation = lock.withLock { let result = read; read = nil; return result }
        continuation?.resume(returning: data)
    }
    func finishWrite() {
        let continuation = lock.withLock { let result = write; write = nil; return result }
        continuation?.resume()
    }
    func cancel() {
        lock.lock(); ended = true
        let read = self.read, write = self.write
        self.read = nil; self.write = nil; lock.unlock()
        read?.resume(throwing: TelemetryError.closed); write?.resume(throwing: TelemetryError.closed)
    }
}
final class TestFactory: @unchecked Sendable {
    let lock = NSLock()
    var values = [TestSocket]()
    private var attemptCount = 0
    let blockFirst: Bool
    let reject: Bool
    init(blockFirst: Bool = false, reject: Bool = false) { self.blockFirst = blockFirst; self.reject = reject }
    func make(_ grant: PhoneSession) async throws -> any TelemetrySocket {
        lock.withLock { attemptCount += 1 }
        if reject { throw TelemetryError.rejected }
        return lock.withLock {
            let socket = TestSocket(blocked: blockFirst && values.isEmpty)
            values.append(socket); return socket
        }
    }
    var sockets: [TestSocket] { lock.withLock { values } }
    var attempts: Int { lock.withLock { attemptCount } }
}
final class LateFactory: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<any TelemetrySocket, Error>?
    var waiting: Bool { lock.withLock { continuation != nil } }
    func make(_ grant: PhoneSession) async throws -> any TelemetrySocket {
        try await withCheckedThrowingContinuation { next in lock.withLock { continuation = next } }
    }
    func complete(_ socket: TestSocket) {
        let next = lock.withLock { let old = continuation; continuation = nil; return old }
        next?.resume(returning: socket)
    }
}
enum TestTimeout: Error { case expired }
final class ClientTests: XCTestCase {
    func until(_ condition: () async -> Bool, file: StaticString = #filePath, line: UInt = #line) async throws {
        for _ in 0..<200 {
            if await condition() { return }
            try await Task.sleep(nanoseconds: 5_000_000)
        }
        XCTFail("Timed out waiting for bounded transport state", file: file, line: line)
        throw TestTimeout.expired
    }
    func setup(_ factory: TestFactory = TestFactory()) async throws -> (TelemetryClient, TestClock, TestFactory) {
        let clock = TestClock()
        let client = TelemetryClient(session: try grant(), clock: { clock.read() }, socketFactory: { try await factory.make($0) })
        await client.start()
        try await until { await client.status().phase == .connected }
        await client.setProducerState(.ready)
        return (client, clock, factory)
    }
    func testSynchronousProducerMailboxIsBoundedAndKeepsOnlyNewestCapture() async throws {
        let (client, clock, factory) = try await setup(TestFactory(blockFirst: true))
        do {
            try await until { factory.sockets.first?.sent.count == 1 }
            clock.set(1100)
            for time in 1001...1100 { client.submit(try sample(Double(time))) }
            await client.tick()
            factory.sockets[0].finishWrite()
            try await until { factory.sockets[0].sent.count == 2 }
            let json = try JSONSerialization.jsonObject(with: factory.sockets[0].sent[1]) as! [String: Any]
            XCTAssertEqual(json["capture_monotonic_ms"] as? Double, 1100)
            XCTAssertEqual(json["type"] as? String, "depth_observation")
        } catch { await client.close(); throw error }
        await client.close()
        XCTAssertTrue(factory.sockets[0].cancelled)
    }
    func testBlockedSendTimesOutIndependentlyAndNoBufferedReplayOnReconnect() async throws {
        let (client, clock, factory) = try await setup(TestFactory(blockFirst: true))
        do {
            try await until { factory.sockets[0].sent.count == 1 }
            clock.set(1200); client.submit(try sample(1200)); await client.tick()
            XCTAssertEqual(factory.sockets[0].sent.count, 1)
            clock.set(1500); await client.tick()
            XCTAssertTrue(factory.sockets[0].cancelled)
            clock.set(2000); await client.tick()
            try await until { let state = await client.status(); return factory.sockets.count == 2 && state.phase == .connected }
            // Only a current heartbeat may be sent after reconnect, not buffered depth.
            await client.tick()
            try await until { !factory.sockets[1].sent.isEmpty }
            for data in factory.sockets[1].sent {
                let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]
                XCTAssertNotEqual(json["type"] as? String, "depth_observation")
            }
            clock.set(2001); client.submit(try sample(2001)); await client.tick()
            try await until { await client.status().sentDepth == 1 }
        } catch { await client.close(); throw error }
        await client.close()
    }
    func testSuspendCancelsSocketAndRequiresReadyAfterFreshConnection() async throws {
        let (client, clock, factory) = try await setup()
        clock.set(1100); client.submit(try sample(1100))
        await client.suspend()
        XCTAssertTrue(factory.sockets[0].cancelled)
        var state = await client.status(); XCTAssertEqual(state.phase, .suspended)
        clock.set(2000); client.submit(try sample(2000))
        await client.resume(); await client.tick()
        try await until { await client.status().phase == .connected }
        state = await client.status(); XCTAssertEqual(state.producer, .starting)
        XCTAssertFalse(state.pendingDepth)
        await client.close()
    }
    func testClockFaultAndInvalidInboundCloseConnectionWithoutRetry() async throws {
        for invalidControl in [false, true] {
            let (client, clock, factory) = try await setup()
            if invalidControl {
                // Ensure receive() is installed before injecting a frame.
                try await Task.sleep(nanoseconds: 20_000_000)
                factory.sockets[0].incoming(Data("{}".utf8))
            } else { clock.set(999); await client.tick() }
            try await until { await client.status().phase == .failed }
            try await until { factory.sockets[0].cancelled }
            clock.set(10000); await client.tick()
            XCTAssertEqual(factory.sockets.count, 1)
            await client.close()
        }
    }
    func testAuthenticationRejectionIsLatchedRatherThanRetried() async throws {
        let factory = TestFactory(reject: true), clock = TestClock()
        let client = TelemetryClient(session: try grant(), clock: { clock.read() }, socketFactory: { try await factory.make($0) })
        await client.start()
        try await until { await client.status().failure == .rejected }
        clock.set(20000); await client.tick()
        let state = await client.status(); XCTAssertEqual(state.phase, .failed)
        XCTAssertEqual(factory.attempts, 1)
        await client.close()
    }
    func testClockProbeFlowsThroughReceiveAndOneSendSlot() async throws {
        let (client, clock, factory) = try await setup()
        try await until { factory.sockets[0].sent.count == 1 }
        try await Task.sleep(nanoseconds: 20_000_000)
        clock.set(1100); factory.sockets[0].incoming(probe())
        try await until { factory.sockets[0].sent.count == 2 }
        let reply = try JSONSerialization.jsonObject(with: factory.sockets[0].sent[1]) as! [String: Any]
        XCTAssertEqual(reply["t2_ms"] as? Double, 1100)
        XCTAssertEqual(reply["t3_ms"] as? Double, 1100)
        await client.close()
    }

    func testDialTimeoutFencesAndCancelsLateSuccessfulHandshake() async throws {
        let factory = LateFactory(), clock = TestClock(), socket = TestSocket()
        let client = TelemetryClient(session: try grant(), clock: { clock.read() },
                                     socketFactory: { try await factory.make($0) })
        await client.start()
        try await until { factory.waiting }
        clock.set(6000); await client.tick()
        let status = await client.status(); XCTAssertEqual(status.phase, .disconnected)
        factory.complete(socket)
        try await until { socket.cancelled }
        XCTAssertTrue(socket.sent.isEmpty)
        await client.close()
    }

    func testClockThrowClosesClientBeforeAnyConnection() async throws {
        let factory = TestFactory()
        let client = TelemetryClient(session: try grant(), clock: { throw TelemetryError.clock },
                                     socketFactory: { try await factory.make($0) })
        await client.start()
        try await until { await client.status().phase == .failed }
        XCTAssertEqual(factory.attempts, 0)
        await client.close()
    }
}
