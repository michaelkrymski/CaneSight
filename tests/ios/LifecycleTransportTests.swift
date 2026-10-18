import Foundation
import XCTest
import CaneSightLifecycle
import CaneSightTelemetry
@testable import CaneSightHostLifecycle

private final class Clock: @unchecked Sendable {
    private let lock = NSLock()
    private var value = 1000.0
    func now() -> Double { lock.withLock { value } }
    func set(_ value: Double) { lock.withLock { self.value = value } }
}

private final class Flag: @unchecked Sendable {
    private let lock = NSLock()
    private var value = true
    func get() -> Bool { lock.withLock { value } }
    func set(_ value: Bool) { lock.withLock { self.value = value } }
}

private final class Socket: TelemetrySocket, @unchecked Sendable {
    private let lock = NSLock()
    private var ended = false
    private var incoming: CheckedContinuation<Data, Error>?
    private var outgoing: [CheckedContinuation<Void, Error>] = []
    private var sent: [Data] = []
    private var cancelCount = 0
    let blockSends: Bool
    init(blockSends: Bool = false) { self.blockSends = blockSends }
    func healthy() -> Bool { lock.withLock { !ended } }
    func cancellations() -> Int { lock.withLock { cancelCount } }
    func packets() -> [Data] { lock.withLock { sent } }
    func send(_ data: Data) async throws {
        if blockSends {
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                lock.withLock {
                    if ended { continuation.resume(throwing: TelemetryError.connection) }
                    else { outgoing.append(continuation) }
                }
            }
        } else {
            try lock.withLock {
                guard !ended else { throw TelemetryError.connection }
                sent.append(data)
            }
        }
    }
    func receive() async throws -> Data {
        try await withCheckedThrowingContinuation { continuation in
            lock.withLock {
                if ended { continuation.resume(throwing: TelemetryError.connection) }
                else { incoming = continuation }
            }
        }
    }
    func cancel() {
        let pending = lock.withLock {
            ended = true; cancelCount += 1
            let result = (incoming, outgoing); incoming = nil; outgoing = []
            return result
        }
        pending.0?.resume(throwing: TelemetryError.connection)
        pending.1.forEach { $0.resume(throwing: TelemetryError.connection) }
    }
}

private final class Pool: @unchecked Sendable {
    private let lock = NSLock()
    private var sockets: [Socket] = []
    let firstBlocked: Bool
    init(firstBlocked: Bool = false) { self.firstBlocked = firstBlocked }
    func open() -> Socket {
        lock.withLock {
            let socket = Socket(blockSends: sockets.isEmpty && firstBlocked)
            sockets.append(socket); return socket
        }
    }
    func all() -> [Socket] { lock.withLock { sockets } }
}

private final class LateDial: @unchecked Sendable {
    private let lock = NSLock()
    private var waiting: CheckedContinuation<any TelemetrySocket, Error>?
    func started() -> Bool { lock.withLock { waiting != nil } }
    func open() async throws -> any TelemetrySocket {
        // Deliberately ignores cancellation until completed by the test.
        try await withCheckedThrowingContinuation { continuation in
            lock.withLock { waiting = continuation }
        }
    }
    func complete(_ socket: Socket) {
        let waiter = lock.withLock { let value = waiting; waiting = nil; return value }
        waiter?.resume(returning: socket)
    }
}

@MainActor private final class Rig {
    let clock = Clock()
    let pool: Pool
    var unknowns = 0
    var bridge: LifecycleTelemetry!
    init(firstBlocked: Bool = false, factory: TelemetryClient.SocketFactory? = nil,
         bounds: @escaping @Sendable (Double) -> CaptureTime? = {
             CaptureTime(sourceMilliseconds: $0, earliestLocalMilliseconds: $0, latestLocalMilliseconds: $0)
         }) throws {
        pool = Pool(firstBlocked: firstBlocked)
        let clock = self.clock, pool = self.pool
        let grant = try PhoneSession(origin: URL(string: "https://fixture.invalid")!,
            sessionID: "fixture-session", sourceID: "phone", bootID: "phone-boot",
            receiverID: "pi", receiverBootID: "pi-boot", mode: .replay,
            phoneToken: String(repeating: "x", count: 40))
        let verified = try VerifiedCaptureClock(evidenceID: "synthetic-same-clock", nowMilliseconds: {
            clock.now()
        }, bound: bounds)
        bridge = LifecycleTelemetry(session: grant, clock: verified,
            unknown: { [weak self] in self?.unknowns += 1 },
            socketFactory: factory ?? { _ in pool.open() })
    }
    func enable() { bridge.setApplicationActive(true); bridge.setTrackingNormal(true) }
    func stop() { bridge.close() }
    func sample(_ source: Double) throws -> CaneSightTelemetry.DepthSample {
        let near = try CaneSightTelemetry.DepthSector(distanceMetres: 0.8, validFraction: 1)
        let far = try CaneSightTelemetry.DepthSector(distanceMetres: 2, validFraction: 1)
        return try CaneSightTelemetry.DepthSample(capturedAtMS: source, tracking: .normal,
                                                  left: near, center: far, right: far)
    }
}

private func decoded(_ sockets: [Socket]) -> [[String: Any]] {
    sockets.flatMap { $0.packets() }.compactMap { (try? JSONSerialization.jsonObject(with: $0)) as? [String: Any] }
}

final class LifecycleTransportTests: XCTestCase {
    private func eventually(_ predicate: @escaping @MainActor @Sendable () -> Bool) async throws {
        for _ in 0..<2000 {
            if await MainActor.run(body: predicate) { return }
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        XCTFail("Synthetic actor did not reach expected state")
        throw TelemetryError.connection
    }

    func test_fence_revokes_registered_cancel_synchronously_and_rejects_old_ticket() {
        let fence = CaptureTransportFence(), socket = Socket()
        let old = fence.open()
        XCTAssertNil(fence.captureTicket())
        fence.allowCaptures(old)
        XCTAssertEqual(fence.captureTicket(), old)
        XCTAssertTrue(fence.register(old, cancel: { socket.cancel() }))
        fence.revoke()
        XCTAssertFalse(socket.healthy())
        XCTAssertNil(fence.captureTicket())
        let fresh = fence.open()
        XCTAssertNotEqual(old, fresh)
        let late = Socket()
        XCTAssertFalse(fence.register(old, cancel: { late.cancel() }))
        XCTAssertFalse(late.healthy())
        XCTAssertTrue(fence.current(fresh))
    }

    func test_no_socket_until_active_and_new_normal_tracking() async throws {
        let rig = try await MainActor.run { try Rig() }
        await MainActor.run {
            rig.bridge.setTrackingNormal(true)
            rig.bridge.setApplicationActive(true)
            XCTAssertTrue(rig.pool.all().isEmpty)
            XCTAssertNil(rig.bridge.captureFence.captureTicket())
            rig.bridge.setTrackingNormal(true)
        }
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        await MainActor.run { rig.stop() }
    }

    func test_actual_actor_sends_original_capture_after_host_admission() async throws {
        let rig = try await MainActor.run { try Rig() }
        await rig.enable()
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        try await MainActor.run {
            rig.clock.set(1100)
            XCTAssertTrue(rig.bridge.submit(try rig.sample(1100), ticket: rig.bridge.captureFence.captureTicket()))
        }
        try await eventually { decoded(rig.pool.all()).contains { $0["type"] as? String == "depth_observation" } }
        await MainActor.run {
            let packet = decoded(rig.pool.all()).first { $0["type"] as? String == "depth_observation" }!
            XCTAssertEqual(packet["capture_monotonic_ms"] as? Double, 1100)
            XCTAssertEqual(packet["seq"] as? Int, 0)
            XCTAssertNil(packet["token"])
            rig.stop()
        }
    }

    func test_background_closes_socket_before_queued_actor_cleanup_runs() async throws {
        let rig = try await MainActor.run { try Rig() }
        await rig.enable()
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        await MainActor.run {
            let socket = rig.pool.all().last!
            rig.bridge.setApplicationActive(false)
            // There has been no await: MainActor's new cleanup Task cannot run yet.
            XCTAssertGreaterThan(socket.cancellations(), 0)
            XCTAssertFalse(socket.healthy())
            XCTAssertNil(rig.bridge.captureFence.captureTicket())
            rig.stop()
        }
    }

    func test_old_worker_ticket_is_rejected_after_fresh_reconnection() async throws {
        let rig = try await MainActor.run { try Rig() }
        await rig.enable()
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        let old = await MainActor.run { rig.bridge.captureFence.captureTicket()! }
        await MainActor.run {
            rig.bridge.setInterrupted(true)
            rig.clock.set(1200)
            rig.bridge.setInterrupted(false)
            rig.bridge.setTrackingNormal(true)
        }
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        try await MainActor.run {
            rig.clock.set(1300)
            XCTAssertFalse(rig.bridge.submit(try rig.sample(1100), ticket: old))
            XCTAssertTrue(rig.bridge.submit(try rig.sample(1300), ticket: rig.bridge.captureFence.captureTicket()))
        }
        try await eventually { decoded(rig.pool.all()).contains { $0["capture_monotonic_ms"] as? Double == 1300 } }
        await MainActor.run {
            XCTAssertFalse(decoded(rig.pool.all()).contains { $0["capture_monotonic_ms"] as? Double == 1100 })
            rig.stop()
        }
    }

    func test_cancelled_late_dial_is_closed_instead_of_adopted() async throws {
        let dial = LateDial()
        let rig = try await MainActor.run { try Rig(factory: { _ in try await dial.open() }) }
        await rig.enable()
        try await eventually { dial.started() }
        await MainActor.run { rig.bridge.setInterrupted(true) }
        let late = Socket(); dial.complete(late)
        try await eventually { !late.healthy() }
        await MainActor.run {
            XCTAssertNil(rig.bridge.captureFence.captureTicket())
            rig.stop()
        }
    }

    func test_callback_thread_revocation_cannot_be_hidden_by_next_good_frame() async throws {
        let rig = try await MainActor.run { try Rig() }
        await rig.enable()
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        let fence = await MainActor.run { rig.bridge.captureFence }
        fence.revoke() // Same synchronous API used by AR callback/worker loss.
        await MainActor.run {
            XCTAssertNil(rig.bridge.captureFence.captureTicket())
            rig.clock.set(1200)
            rig.bridge.setTrackingNormal(true)
        }
        try await eventually { rig.bridge.captureFence.captureTicket() != nil && rig.pool.all().count == 2 }
        await MainActor.run { rig.stop() }
    }

    func test_pending_mailbox_does_not_replay_after_blocked_send_and_suspend() async throws {
        let rig = try await MainActor.run { try Rig(firstBlocked: true) }
        await rig.enable()
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        try await MainActor.run {
            rig.clock.set(1100)
            XCTAssertTrue(rig.bridge.submit(try rig.sample(1100), ticket: rig.bridge.captureFence.captureTicket()))
            rig.bridge.setApplicationActive(false)
            rig.clock.set(1200)
            rig.enable()
        }
        try await eventually { rig.bridge.captureFence.captureTicket() != nil && rig.pool.all().count == 2 }
        try await MainActor.run {
            rig.clock.set(1300)
            XCTAssertTrue(rig.bridge.submit(try rig.sample(1300), ticket: rig.bridge.captureFence.captureTicket()))
        }
        try await eventually { decoded(rig.pool.all()).contains { $0["capture_monotonic_ms"] as? Double == 1300 } }
        await MainActor.run {
            XCTAssertFalse(decoded(rig.pool.all()).contains { $0["capture_monotonic_ms"] as? Double == 1100 })
            rig.stop()
        }
    }

    func test_source_sequence_history_survives_reconnection() async throws {
        let rig = try await MainActor.run { try Rig() }
        await rig.enable()
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        try await MainActor.run {
            rig.clock.set(1100)
            XCTAssertTrue(rig.bridge.submit(try rig.sample(1100), ticket: rig.bridge.captureFence.captureTicket()))
        }
        try await eventually { decoded(rig.pool.all()).contains { $0["type"] as? String == "depth_observation" } }
        await MainActor.run {
            rig.bridge.setApplicationActive(false); rig.clock.set(1200); rig.enable()
        }
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        try await MainActor.run {
            rig.clock.set(1300)
            XCTAssertTrue(rig.bridge.submit(try rig.sample(1300), ticket: rig.bridge.captureFence.captureTicket()))
        }
        try await eventually { decoded(rig.pool.all()).filter { $0["type"] as? String == "depth_observation" }.count == 2 }
        await MainActor.run {
            let packets = decoded(rig.pool.all()).filter { $0["type"] as? String == "depth_observation" }
            XCTAssertEqual(packets.compactMap { $0["seq"] as? Int }, [0,1])
            rig.stop()
        }
    }

    func test_retimed_or_future_capture_mapping_is_rejected() async throws {
        for mode in 0...1 {
            let rig = try await MainActor.run { try Rig(bounds: { source in
                let offset = source >= 1100 ? 1000.0 : 0.0
                return CaptureTime(sourceMilliseconds: source + (mode == 0 && source >= 1100 ? 1 : 0),
                            earliestLocalMilliseconds: source + offset, latestLocalMilliseconds: source + offset)
            }) }
            await rig.enable()
            try await eventually { rig.bridge.captureFence.captureTicket() != nil }
            try await MainActor.run {
                rig.clock.set(1100)
                XCTAssertFalse(rig.bridge.submit(try rig.sample(1100), ticket: rig.bridge.captureFence.captureTicket()))
                rig.stop()
            }
        }
    }

    func test_clock_reset_requires_new_enrollment_not_tracking_recovery() async throws {
        let rig = try await MainActor.run { try Rig() }
        await rig.enable()
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        try await MainActor.run {
            let ticket = rig.bridge.captureFence.captureTicket()
            rig.clock.set(900)
            XCTAssertFalse(rig.bridge.submit(try rig.sample(900), ticket: ticket))
            XCTAssertNil(rig.bridge.captureFence.captureTicket())
            rig.clock.set(2000); rig.enable()
            XCTAssertNil(rig.bridge.captureFence.captureTicket())
            rig.stop()
        }
    }

    func test_mapping_loss_closes_transport_and_recovery_needs_new_capture() async throws {
        let enabled = Flag()
        let rig = try await MainActor.run { try Rig(bounds: { source in
            enabled.get() ? CaptureTime(sourceMilliseconds: source, earliestLocalMilliseconds: source,
                                       latestLocalMilliseconds: source) : nil
        }) }
        await rig.enable()
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        let old = await MainActor.run { rig.bridge.captureFence.captureTicket()! }
        try await MainActor.run {
            enabled.set(false); rig.clock.set(1100)
            XCTAssertFalse(rig.bridge.submit(try rig.sample(1100), ticket: old))
            XCTAssertNil(rig.bridge.captureFence.captureTicket())
            XCTAssertFalse(rig.pool.all().last!.healthy())
            rig.bridge.setTrackingNormal(true)
            XCTAssertNil(rig.bridge.captureFence.captureTicket())
            enabled.set(true); rig.clock.set(1200); rig.bridge.setTrackingNormal(true)
        }
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        try await MainActor.run {
            rig.clock.set(1300)
            XCTAssertFalse(rig.bridge.submit(try rig.sample(1100), ticket: old))
            XCTAssertTrue(rig.bridge.submit(try rig.sample(1300), ticket: rig.bridge.captureFence.captureTicket()))
            rig.stop()
        }
    }

    func test_close_is_terminal_and_withdraws_all_admission() async throws {
        let rig = try await MainActor.run { try Rig() }
        await rig.enable()
        try await eventually { rig.bridge.captureFence.captureTicket() != nil }
        await MainActor.run {
            rig.stop(); rig.enable()
            XCTAssertNil(rig.bridge.captureFence.captureTicket())
            XCTAssertFalse(rig.pool.all().last!.healthy())
        }
    }
}
