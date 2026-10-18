import ARKit
import AVFoundation
import Foundation
import QuartzCore
import XCTest
import CaneSightDepth
import CaneSightDepthARKit
@testable import CaneSightTelemetry

// Bench only: one fixed source epoch for captures, sends and clock replies.
// Never send boot uptime. An observed clock discontinuity permanently fails it.
private struct BenchEpoch {
    let origin: Double
    private var last: Double = 0
    init(origin: Double) { self.origin = origin }
    mutating func observe(raw: Double, elapsed: Double) throws -> Double {
        let value = raw - origin
        guard value.isFinite, elapsed.isFinite, value >= last, elapsed >= 0,
              abs(value - elapsed) <= 100 else { throw TelemetryError.clock }
        last = value
        return value
    }
    func capture(_ raw: Double, now: Double) throws -> Double {
        let value = raw - origin
        guard value.isFinite, value >= 0, now >= value, now - value < 500 else {
            throw TelemetryError.clock
        }
        return value
    }
}
private final class BenchSourceClock: @unchecked Sendable {
    private let lock = NSLock()
    private let start = ContinuousClock.now
    private var epoch = BenchEpoch(origin: CACurrentMediaTime() * 1000)
    private var failed = false
    private func tick() throws -> Double {
        guard !failed else { throw TelemetryError.clock }
        let parts = start.duration(to: ContinuousClock.now).components
        let elapsed = Double(parts.seconds) * 1000 + Double(parts.attoseconds) / 1e15
        do { return try epoch.observe(raw: CACurrentMediaTime() * 1000, elapsed: elapsed) }
        catch { failed = true; throw error }
    }
    func now() throws -> Double { try lock.withLock { try tick() } }
    func capture(_ raw: Double) throws -> Double {
        try lock.withLock {
            let now = try tick()
            do { return try epoch.capture(raw, now: now) }
            catch { failed = true; throw error }
        }
    }
}
private final class DepthPairRecord: @unchecked Sendable {
    private let lock = NSLock()
    private var depthTimes = [Double]()
    private var counts: [String: Int] = [:]
    private var lastSequences: [String: UInt64] = [:]
    private var lastCapture: Double = -1
    private var dials = 0
    func opened() { lock.withLock { dials += 1 } }
    var depthCount: Int { lock.withLock { depthTimes.count } }
    var connections: Int { lock.withLock { dials } }
    func sent(_ data: Data) throws {
        try lock.withLock {
            let value = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
            let kind = try XCTUnwrap(value["type"] as? String)
            guard ["depth_observation", "heartbeat", "clock_reply"].contains(kind) else {
                throw TelemetryError.invalidControl
            }
            counts[kind, default: 0] += 1
            guard counts[kind, default: 0] <= 900 else { throw TelemetryError.invalidControl }
            if kind == "clock_reply" { return }
            let seq = try XCTUnwrap(value["seq"] as? UInt64)
            guard lastSequences[kind].map({ seq > $0 }) ?? true else { throw TelemetryError.invalidControl }
            lastSequences[kind] = seq
            let captured = try XCTUnwrap(value["capture_monotonic_ms"] as? Double)
            guard captured.isFinite, captured >= 0, captured < 90_000 else { throw TelemetryError.clock }
            if kind == "depth_observation" {
                guard captured > lastCapture else { throw TelemetryError.clock }
                lastCapture = captured; depthTimes.append(captured)
            }
        }
    }
}
private struct DepthPairSocket: TelemetrySocket {
    let native: any TelemetrySocket
    let record: DepthPairRecord
    func send(_ data: Data) async throws { try await native.send(data); try record.sent(data) }
    func receive() async throws -> Data { try await native.receive() }
    func cancel() { native.cancel() }
}
private final class LiveDepthCollector: NSObject, ARSessionDelegate, @unchecked Sendable {
    private let lock = NSLock()
    private let adapter = ARKitDepthAdapter(configuration: try! DepthSectorConfiguration())
    private let converter = DepthTelemetryAdapter(sessionMode: .live)
    private let clock: BenchSourceClock
    private let client: TelemetryClient
    private var enabled = false, failed = false
    private var frames = 0
    private var next: Double = 0
    init(clock: BenchSourceClock, client: TelemetryClient) { self.clock = clock; self.client = client }
    var processed: Int { lock.withLock { frames } }
    var hasFailed: Bool { lock.withLock { failed } }
    func enable(_ value: Bool) { lock.withLock { enabled = value } }
    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        lock.withLock {
            guard enabled, !failed, frames < 1800 else { return }
            let raw = frame.timestamp * 1000
            guard raw >= next else { return }
            next = raw + 50 // Bounded 20 Hz processing; transport still caps sends at 10 Hz.
            do {
                let summary = adapter.process(frame)
                guard summary.reason == .processedFrame else { return }
                let original = try converter.sample(from: summary)
                guard original.capturedAtMS == raw else { throw TelemetryError.clock }
                let rebased = try clock.capture(original.capturedAtMS)
                client.submit(try DepthSample(capturedAtMS: rebased, tracking: original.tracking,
                    left: original.left, center: original.center, right: original.right))
                frames += 1
            } catch { failed = true; enabled = false }
        }
    }
}

final class LiveDepthPairTests: XCTestCase {
    func testBenchEpochPreservesAgeAndRejectsClockDiscontinuities() throws {
        var clock = BenchEpoch(origin: 1_000_000)
        let now = try clock.observe(raw: 1_000_200, elapsed: 200)
        let capture = try clock.capture(1_000_160, now: now)
        XCTAssertEqual(now - capture, 40)
        XCTAssertThrowsError(try clock.capture(999_999, now: now))
        XCTAssertThrowsError(try clock.capture(1_000_201, now: now))
        XCTAssertThrowsError(try clock.observe(raw: 1_000_199, elapsed: 201))
        XCTAssertThrowsError(try clock.observe(raw: 1_000_300, elapsed: 600))
        XCTAssertThrowsError(try clock.capture(.nan, now: now))
    }

    @MainActor func testLocalRebasedDepthCapturePause() async throws {
        #if targetEnvironment(simulator)
        throw XCTSkip("Physical supported iPhone required")
        #else
        guard ARKitDepthAdapter.supportsSceneDepth,
              AVCaptureDevice.authorizationStatus(for: .video) == .authorized else {
            throw XCTSkip("Real scene depth and normal camera consent required")
        }
        let clock = BenchSourceClock()
        let grant = try PhoneSession(origin: URL(string: "https://invalid.example")!,
            sessionID: "local", sourceID: "phone", bootID: "local-boot", receiverID: "pi",
            receiverBootID: "local-pi", mode: .live, phoneToken: String(repeating: "x", count: 40))
        // Never start this client. It is only a disabled latest-only sink.
        let client = TelemetryClient(session: grant, clock: { try clock.now() },
            socketFactory: { _ in throw TelemetryError.connection })
        let collector = LiveDepthCollector(clock: clock, client: client)
        let session = ARSession()
        session.delegateQueue = DispatchQueue(label: "CaneSight.CS016.local-rebased")
        session.delegate = collector
        let config = ARWorldTrackingConfiguration()
        config.frameSemantics.insert(.sceneDepth)
        defer { collector.enable(false); session.pause(); session.delegate = nil }
        for _ in 0..<2 {
            let before = collector.processed
            collector.enable(true)
            session.run(config, options: [.resetTracking, .removeExistingAnchors])
            for _ in 0..<300 {
                if collector.processed >= before + 20 || collector.hasFailed { break }
                try await Task.sleep(nanoseconds: 50_000_000)
            }
            collector.enable(false); session.pause()
            XCTAssertFalse(collector.hasFailed)
            XCTAssertGreaterThanOrEqual(collector.processed, before + 20)
            try await Task.sleep(nanoseconds: 300_000_000)
        }
        print("CS016_LOCAL_REBASED processed_frames=\(collector.processed) network_started=false")
        #endif
    }

    @MainActor func testClockCharacterizationDepth() async throws {
        #if targetEnvironment(simulator)
        throw XCTSkip("Physical supported iPhone required")
        #else
        guard ARKitDepthAdapter.supportsSceneDepth,
              AVCaptureDevice.authorizationStatus(for: .video) == .authorized else {
            throw XCTSkip("Real scene depth and camera consent required")
        }
        let file = try XCTUnwrap(FileManager.default.urls(for: .documentDirectory,
            in: .userDomainMask).first).appendingPathComponent("cs013-clock-pair.json")
        guard FileManager.default.fileExists(atPath: file.path) else { throw XCTSkip("Fresh private phone role required") }
        let data = try Data(contentsOf: file); try FileManager.default.removeItem(at: file)
        let value = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let phone = try XCTUnwrap(value["phone"] as? [String: String])
        let pi = try XCTUnwrap(value["pi"] as? [String: String])
        guard Set(value.keys) == ["origin", "session_id", "mode", "phone", "pi"],
              Set(phone.keys) == ["source_id", "boot_id", "token"], Set(pi.keys) == ["source_id", "boot_id"],
              value["origin"] as? String == "https://64.177.50.116", value["mode"] as? String == "live" else {
            throw TelemetryError.configuration
        }
        let grant = try PhoneSession(origin: URL(string: "https://64.177.50.116")!,
            sessionID: XCTUnwrap(value["session_id"] as? String), sourceID: XCTUnwrap(phone["source_id"]),
            bootID: XCTUnwrap(phone["boot_id"]), receiverID: XCTUnwrap(pi["source_id"]),
            receiverBootID: XCTUnwrap(pi["boot_id"]), mode: .live, phoneToken: XCTUnwrap(phone["token"]))
        let clock = BenchSourceClock(), record = DepthPairRecord()
        let client = TelemetryClient(session: grant, clock: { try clock.now() }, socketFactory: {
            let socket = try await NativeWebSocket.connect($0); record.opened()
            return DepthPairSocket(native: socket, record: record)
        })
        let collector = LiveDepthCollector(clock: clock, client: client)
        let session = ARSession()
        session.delegateQueue = DispatchQueue(label: "CaneSight.clock-characterization")
        session.delegate = collector
        let config = ARWorldTrackingConfiguration(); config.frameSemantics.insert(.sceneDepth)
        await client.start()
        do {
            for _ in 0..<300 {
                if await client.status().phase == .connected { break }
                try await Task.sleep(nanoseconds: 50_000_000)
            }
            guard await client.status().phase == .connected else { throw TelemetryError.connection }
            collector.enable(true); session.run(config, options: [.resetTracking, .removeExistingAnchors])
            for _ in 0..<300 {
                if collector.processed > 0 || collector.hasFailed { break }
                try await Task.sleep(nanoseconds: 50_000_000)
            }
            guard collector.processed > 0, !collector.hasFailed else { throw TelemetryError.clock }
            await client.setProducerState(.ready)
            let start = ContinuousClock.now
            while start.duration(to: ContinuousClock.now) < .seconds(65) {
                guard !collector.hasFailed, await client.status().phase == .connected else { throw TelemetryError.connection }
                try await Task.sleep(nanoseconds: 100_000_000)
            }
            guard record.depthCount >= 400 else { throw TelemetryError.connection }
            print("CS013_CLOCK_CHARACTERIZATION depth_sent=\(record.depthCount) connections=\(record.connections) processed_frames=\(collector.processed) duration_seconds=65")
        } catch {
            collector.enable(false); session.pause(); session.delegate = nil; await client.close(); throw error
        }
        collector.enable(false); session.pause(); session.delegate = nil; await client.close()
        #endif
    }

    @MainActor func testRealDepthPairPauseReconnect() async throws {
        #if targetEnvironment(simulator)
        throw XCTSkip("Physical supported iPhone required")
        #else
        guard ARKitDepthAdapter.supportsSceneDepth,
              AVCaptureDevice.authorizationStatus(for: .video) == .authorized else {
            throw XCTSkip("Real scene depth and normal camera consent required")
        }
        let file = try XCTUnwrap(FileManager.default.urls(for: .documentDirectory,
            in: .userDomainMask).first).appendingPathComponent("cs016-depth-pair.json")
        guard FileManager.default.fileExists(atPath: file.path) else {
            throw XCTSkip("Fresh depth-test phone-role private file required")
        }
        let data = try Data(contentsOf: file)
        try FileManager.default.removeItem(at: file)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let phone = try XCTUnwrap(object["phone"] as? [String: String])
        let peer = try XCTUnwrap(object["pi"] as? [String: String])
        guard Set(object.keys) == ["origin", "session_id", "mode", "phone", "pi"],
              Set(phone.keys) == ["source_id", "boot_id", "token"],
              Set(peer.keys) == ["source_id", "boot_id"],
              object["origin"] as? String == "https://64.177.50.116",
              object["mode"] as? String == "live" else { throw TelemetryError.configuration }
        let grant = try PhoneSession(origin: URL(string: "https://64.177.50.116")!,
            sessionID: XCTUnwrap(object["session_id"] as? String),
            sourceID: XCTUnwrap(phone["source_id"]), bootID: XCTUnwrap(phone["boot_id"]),
            receiverID: XCTUnwrap(peer["source_id"]), receiverBootID: XCTUnwrap(peer["boot_id"]),
            mode: .live, phoneToken: XCTUnwrap(phone["token"]))
        let clock = BenchSourceClock(), record = DepthPairRecord()
        let client = TelemetryClient(session: grant, clock: { try clock.now() }, socketFactory: {
            let native = try await NativeWebSocket.connect($0)
            record.opened()
            return DepthPairSocket(native: native, record: record)
        })
        let collector = LiveDepthCollector(clock: clock, client: client)
        let session = ARSession()
        session.delegateQueue = DispatchQueue(label: "CaneSight.CS016.live-depth-pair")
        session.delegate = collector
        let config = ARWorldTrackingConfiguration()
        config.frameSemantics.insert(.sceneDepth)
        await client.start()
        do {
            for pass in 0..<2 {
                if pass > 0 { await client.resume() }
                for _ in 0..<300 {
                    if await client.status().phase == .connected { break }
                    try await Task.sleep(nanoseconds: 50_000_000)
                }
                let connected = await client.status()
                XCTAssertEqual(connected.phase, .connected)
                guard connected.phase == .connected else { throw TelemetryError.connection }
                let before = record.depthCount
                let previousFrames = collector.processed
                collector.enable(true)
                session.run(config, options: [.resetTracking, .removeExistingAnchors])
                for _ in 0..<300 {
                    if collector.processed > previousFrames || collector.hasFailed { break }
                    try await Task.sleep(nanoseconds: 50_000_000)
                }
                guard collector.processed > previousFrames, !collector.hasFailed else { throw TelemetryError.clock }
                // Only a real newly processed frame permits local producer readiness.
                // Pi capture-age eligibility still remains unknown.
                await client.setProducerState(.ready)
                for _ in 0..<400 {
                    if record.depthCount >= before + 40 || collector.hasFailed { break }
                    if await client.status().phase == .failed { break }
                    try await Task.sleep(nanoseconds: 50_000_000)
                }
                collector.enable(false); session.pause()
                guard !collector.hasFailed, record.depthCount >= before + 40 else { throw TelemetryError.clock }
                if pass == 0 {
                    await client.suspend()
                    let stopped = await client.status()
                    XCTAssertEqual(stopped.phase, .suspended)
                    XCTAssertFalse(stopped.pendingDepth)
                    let count = record.depthCount
                    try await Task.sleep(nanoseconds: 1_200_000_000)
                    XCTAssertEqual(record.depthCount, count)
                }
            }
            try await Task.sleep(nanoseconds: 500_000_000)
            XCTAssertEqual(record.connections, 2)
            print("CS016_REAL_DEPTH sent=\(record.depthCount) connections=\(record.connections) processed_frames=\(collector.processed) capture_age_eligibility=unknown")
        } catch {
            collector.enable(false); session.pause(); session.delegate = nil
            await client.close(); throw error
        }
        collector.enable(false); session.pause(); session.delegate = nil
        await client.close()
        #endif
    }
}
