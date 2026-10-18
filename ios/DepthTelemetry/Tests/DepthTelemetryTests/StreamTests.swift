import Foundation
import XCTest
import CaneSightDepth
import CaneSightTelemetry
import CaneSightDepthTelemetry

private final class SourceClock: @unchecked Sendable {
    private let lock = NSLock()
    private var value: Double = 1000
    func read() -> Double { lock.withLock { value } }
    func set(_ value: Double) { lock.withLock { self.value = value } }
}
private final class Channel: TelemetrySocket, @unchecked Sendable {
    private let lock = NSLock()
    private var output = [Data]()
    private var read: CheckedContinuation<Data, Error>?
    private var write: CheckedContinuation<Void, Error>?
    private var ended = false
    let blockFirst: Bool
    init(blockFirst: Bool) { self.blockFirst = blockFirst }
    var packets: [[String: Any]] {
        lock.withLock { output }.compactMap { (try? JSONSerialization.jsonObject(with: $0)) as? [String: Any] }
    }
    func send(_ data: Data) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            lock.lock()
            guard !ended else { lock.unlock(); continuation.resume(throwing: TelemetryError.closed); return }
            output.append(data)
            if blockFirst && output.count == 1 { write = continuation; lock.unlock() }
            else { lock.unlock(); continuation.resume() }
        }
    }
    func receive() async throws -> Data {
        try await withCheckedThrowingContinuation { continuation in
            lock.lock()
            guard !ended else { lock.unlock(); continuation.resume(throwing: TelemetryError.closed); return }
            read = continuation; lock.unlock()
        }
    }
    func release() {
        let pending = lock.withLock { let value = write; write = nil; return value }
        pending?.resume()
    }
    func cancel() {
        lock.lock(); ended = true
        let read = self.read, write = self.write
        self.read = nil; self.write = nil; lock.unlock()
        read?.resume(throwing: TelemetryError.closed); write?.resume(throwing: TelemetryError.closed)
    }
}
private final class Channels: @unchecked Sendable {
    private let lock = NSLock()
    private var values = [Channel]()
    var all: [Channel] { lock.withLock { values } }
    func make() -> Channel {
        lock.withLock {
            let value = Channel(blockFirst: values.isEmpty)
            values.append(value); return value
        }
    }
}
private enum WaitFailure: Error { case timeout }

final class StreamTests: XCTestCase {
    private func wait(_ condition: () async -> Bool) async throws {
        for _ in 0..<400 {
            if await condition() { return }
            try await Task.sleep(nanoseconds: 5_000_000)
        }
        XCTFail("Session-bound stream did not reach expected state")
        throw WaitFailure.timeout
    }
    func testProducerToWireLatestOnlyAndResumeNeedsFreshReadyCapture() async throws {
        let grant = try PhoneSession(origin: URL(string: "https://fixture.invalid")!,
            sessionID: "stream-test", sourceID: "phone", bootID: "phone-boot",
            receiverID: "pi", receiverBootID: "pi-boot", mode: .replay,
            phoneToken: String(repeating: "x", count: 40))
        let clock = SourceClock(), channels = Channels()
        let stream = DepthTelemetryStream(session: grant, clock: { clock.read() },
            socketFactory: { _ in channels.make() })
        var state = await stream.status()
        XCTAssertEqual(state.phase, .disconnected)
        XCTAssertTrue(channels.all.isEmpty)
        await stream.start()
        do {
            try await wait { await stream.status().phase == .connected }
            await stream.setProducerState(.ready)
            try await wait { channels.all.first?.packets.count == 1 }
            clock.set(1100)
            for index in 1...100 { try stream.submit(makeSummary(time: Double(1000 + index) / 1000)) }
            XCTAssertThrowsError(try stream.submit(makeSummary(time: 1.1, mode: .live)))
            channels.all[0].release()
            try await wait { await stream.status().sentDepth == 1 }
            let packets = channels.all[0].packets.filter { $0["type"] as? String == "depth_observation" }
            XCTAssertEqual(packets.count, 1)
            XCTAssertEqual(packets.first?["capture_monotonic_ms"] as? Double, 1.1 * 1000)
            XCTAssertEqual(packets.first?["seq"] as? Int, 0)
            XCTAssertEqual(packets.first?["session_id"] as? String, "stream-test")
            await stream.suspend()
            clock.set(2000)
            try stream.submit(makeSummary(time: 2)) // disabled mailbox discards this
            await stream.resume()
            try await wait { await stream.status().phase == .connected }
            state = await stream.status()
            XCTAssertEqual(state.producer, .starting)
            XCTAssertFalse(state.pendingDepth)
            try await wait { channels.all.count == 2 && !channels.all[1].packets.isEmpty }
            XCTAssertTrue(channels.all[1].packets.allSatisfy { $0["type"] as? String != "depth_observation" })
            await stream.setProducerState(.ready)
            clock.set(2001)
            try stream.submit(makeSummary(time: 2.001))
            try await wait { await stream.status().sentDepth == 2 }
            let fresh = channels.all[1].packets.first { $0["type"] as? String == "depth_observation" }
            XCTAssertEqual(fresh?["seq"] as? Int, 1)
            XCTAssertEqual(fresh?["capture_monotonic_ms"] as? Double, 2.001 * 1000)
        } catch { await stream.close(); throw error }
        await stream.close()
        state = await stream.status()
        XCTAssertEqual(state.phase, .closed)
    }
}
