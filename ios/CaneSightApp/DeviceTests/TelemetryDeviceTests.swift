import ARKit
import AVFoundation
import Foundation
import QuartzCore
import XCTest
import CaneSightDepth
import CaneSightDepthARKit
@testable import CaneSightTelemetry

private struct CaptureTiming: Sendable {
    let source: Double, receipt: Double
    let originalTimePreserved: Bool
}
private final class CaptureCollector: NSObject, ARSessionDelegate, @unchecked Sendable {
    private let lock = NSLock()
    private var values = [CaptureTiming]()
    private var nextCapture: Double = 0
    private let adapter = ARKitDepthAdapter(configuration: try! DepthSectorConfiguration())
    private let telemetry = DepthTelemetryAdapter(sessionMode: .live)
    var samples: [CaptureTiming] { lock.withLock { values } }
    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        let receipt = CACurrentMediaTime()
        guard lock.withLock({
            guard values.count < 30, receipt >= nextCapture else { return false }
            nextCapture = receipt + 0.1
            return true
        }) else { return }
        let summary = adapter.process(frame)
        guard summary.reason == .processedFrame, let converted = try? telemetry.sample(from: summary) else { return }
        let value = CaptureTiming(source: frame.timestamp, receipt: receipt,
            originalTimePreserved: summary.captureTimestampSeconds == frame.timestamp &&
                converted.capturedAtMS == frame.timestamp * 1000)
        lock.withLock { if values.count < 30 { values.append(value) } }
    }
}

private final class NativeProbeRecord: @unchecked Sendable {
    private let lock = NSLock()
    private var sequences = [UInt64]()
    private var dials = 0
    var heartbeatSequences: [UInt64] { lock.withLock { sequences } }
    var connections: Int { lock.withLock { dials } }
    func opened() { lock.withLock { dials += 1 } }
    func completed(_ sequence: UInt64) { lock.withLock { sequences.append(sequence) } }
}
private struct RecordedNativeSocket: TelemetrySocket {
    let underlying: any TelemetrySocket
    let record: NativeProbeRecord
    func send(_ data: Data) async throws {
        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              object["type"] as? String == "heartbeat", object["state"] as? String == "starting",
              let sequence = object["seq"] as? UInt64,
              let elapsed = object["capture_monotonic_ms"] as? Double,
              elapsed >= 0, elapsed < 30_000 else { throw TelemetryError.invalidControl }
        try await underlying.send(data)
        record.completed(sequence)
    }
    func receive() async throws -> Data { try await underlying.receive() }
    func cancel() { underlying.cancel() }
}

/// Actual sensor and OS-network probes, separate from injected transport tests.
/// No raw frame, image, position, credential or boot timestamp is logged or sent.
final class TelemetryDeviceTests: XCTestCase {
    func testNativeStartingHeartbeatAndReconnect() async throws {
        // USB-delivered phone-role file only; never operator/Pi credentials.
        let file = try XCTUnwrap(FileManager.default.urls(for: .documentDirectory,
            in: .userDomainMask).first).appendingPathComponent("cs016-phone-pair.json")
        guard FileManager.default.fileExists(atPath: file.path) else {
            throw XCTSkip("Fresh phone-role private grant file not installed")
        }
        let data = try Data(contentsOf: file)
        try FileManager.default.removeItem(at: file) // single process epoch; never reuse on a relaunch
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let phone = try XCTUnwrap(object["phone"] as? [String: String])
        let peer = try XCTUnwrap(object["pi"] as? [String: String])
        guard object["origin"] as? String == "https://64.177.50.116",
              object["mode"] as? String == "live", peer["token"] == nil,
              object["operator_token"] == nil else { throw TelemetryError.configuration }
        let grant = try PhoneSession(origin: URL(string: "https://64.177.50.116")!,
            sessionID: XCTUnwrap(object["session_id"] as? String),
            sourceID: XCTUnwrap(phone["source_id"]), bootID: XCTUnwrap(phone["boot_id"]),
            receiverID: XCTUnwrap(peer["source_id"]), receiverBootID: XCTUnwrap(peer["boot_id"]),
            mode: .live, phoneToken: XCTUnwrap(phone["token"]))
        let clock = ContinuousClock(), start = ContinuousClock.now
        let record = NativeProbeRecord()
        let client = TelemetryClient(session: grant, clock: {
            let parts = start.duration(to: clock.now).components
            return Double(parts.seconds)*1000 + Double(parts.attoseconds)/1e15
        }, socketFactory: {
            let native = try await NativeWebSocket.connect($0)
            record.opened()
            return RecordedNativeSocket(underlying: native, record: record)
        })
        await client.start()
        do {
            try await waitForHeartbeats(3, client: client, record: record)
            await client.suspend()
            let stopped = await client.status()
            XCTAssertEqual(stopped.phase, .suspended)
            await client.resume()
            try await waitForHeartbeats(5, client: client, record: record)
            let state = await client.status()
            XCTAssertEqual(state.phase, .connected)
            XCTAssertEqual(state.producer, .starting)
            XCTAssertEqual(state.sentDepth, 0)
            XCTAssertEqual(record.connections, 2)
            let sequences = record.heartbeatSequences
            XCTAssertGreaterThanOrEqual(sequences.count, 5)
            XCTAssertTrue(zip(sequences.dropFirst(), sequences).allSatisfy { $0 > $1 })
            // Let the paired test receiver drain its last message; this is not
            // an acknowledgement or a remote-delivery/freshness assertion.
            try await Task.sleep(nanoseconds: 200_000_000)
            print("CS016_NATIVE_PHONE starting_heartbeats=\(sequences.count) connections=\(record.connections) depth_sent=0 peer_delivery_unverified=true")
        } catch { await client.close(); throw error }
        await client.close()
    }

    private func waitForHeartbeats(_ count: Int, client: TelemetryClient, record: NativeProbeRecord) async throws {
        for _ in 0..<200 {
            let status = await client.status()
            if status.phase == .failed { throw status.failure ?? TelemetryError.connection }
            if record.heartbeatSequences.count >= count { return }
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        XCTFail("Native phone-only heartbeat deadline expired")
        throw TelemetryError.connection
    }

    @MainActor func testLiveDepthCaptureTimingAndRestart() async throws {
        #if targetEnvironment(simulator)
        throw XCTSkip("Real ARKit depth requires a physical supported phone")
        #else
        guard ARKitDepthAdapter.supportsSceneDepth else { throw XCTSkip("Scene depth unsupported") }
        guard AVCaptureDevice.authorizationStatus(for: .video) == .authorized else {
            throw XCTSkip("Camera permission must be granted through the normal app flow")
        }
        let session = ARSession()
        let queue = DispatchQueue(label: "CaneSight.CS016.capture-timing")
        let configuration = ARWorldTrackingConfiguration()
        configuration.frameSemantics.insert(.sceneDepth)
        var previousCapture: Double?
        defer { session.pause(); session.delegate = nil }
        for pass in 0..<2 {
            let collector = CaptureCollector()
            session.delegateQueue = queue; session.delegate = collector
            session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
            for _ in 0..<300 {
                if collector.samples.count == 30 { break }
                try await Task.sleep(nanoseconds: 50_000_000)
            }
            session.pause()
            let rows = collector.samples
            XCTAssertEqual(rows.count, 30, "Need 30 actual processed depth frames per run")
            XCTAssertTrue(rows.allSatisfy(\.originalTimePreserved))
            XCTAssertTrue(zip(rows.dropFirst(), rows).allSatisfy { $0.source > $1.source && $0.receipt >= $1.receipt })
            if let previousCapture, let first = rows.first { XCTAssertGreaterThan(first.source, previousCapture) }
            previousCapture = rows.last?.source
            let differences = rows.map { ($0.receipt - $0.source) * 1000 }.sorted()
            XCTAssertTrue(differences.allSatisfy { $0.isFinite && $0 >= 0 && $0 < 500 },
                "Capture/media-clock relationship outside the local observation budget")
            // Only elapsed candidate deltas, never absolute boot/source times.
            if differences.count == 30 {
                print("CS016_CAPTURE_CALLBACK_DELTA_MS run=\(pass) count=30 min=\(differences[0]) median=\(differences[15]) p95=\(differences[28]) max=\(differences[29])")
            }
            // This checks pause/restart, not phone lock, sleep, or Pi clock drift.
            try await Task.sleep(nanoseconds: 300_000_000)
        }
        #endif
    }

    func testPublicBackendHTTPSReachability() async throws {
        var request = URLRequest(url: URL(string: "https://64.177.50.116/healthz")!)
        request.timeoutInterval = 8
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCredentialStorage = nil; configuration.httpCookieStorage = nil
        let session = URLSession(configuration: configuration)
        defer { session.invalidateAndCancel() }
        do {
            let (_, response) = try await session.data(for: request)
            XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        } catch {
            let code = (error as NSError).code
            print("CS016_PUBLIC_BACKEND_UNAVAILABLE code=\(code)")
            throw XCTSkip("Public backend unreachable with default OS TLS; no live WSS acceptance")
        }
    }
}
