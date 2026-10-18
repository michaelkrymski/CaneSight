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

/// Actual sensor and OS-network probes, separate from injected transport tests.
/// No raw frame, image, position, credential or boot timestamp is logged or sent.
final class TelemetryDeviceTests: XCTestCase {
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
