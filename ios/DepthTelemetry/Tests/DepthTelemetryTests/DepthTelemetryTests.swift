import XCTest
import CaneSightDepth
import CaneSightTelemetry
import CaneSightDepthTelemetry

func makeSummary(time: Double = 1.234567, mode: DepthMode = .replay,
                 tracking: DepthTracking = .normal, confidence: [UInt8]? = nil,
                 missingConfidence: Bool = false) throws -> DepthSectorSummary {
        let values = (0..<96).map { Float($0 / 32 + 1) }
        return DepthSectorProcessor(configuration: try DepthSectorConfiguration()).process(
            DepthFrame(width: 96, height: 1, metres: values,
                confidence: missingConfidence ? nil : (confidence ?? Array(repeating: 2, count: 96)),
                captureTimestampSeconds: time, mode: mode, tracking: tracking))
    }
final class DepthTelemetryTests: XCTestCase {
    let adapter = DepthTelemetryAdapter(sessionMode: .replay)
    func testPreservesOriginalCaptureAndImageColumnOrder() throws {
        let value = try adapter.sample(from: makeSummary())
        XCTAssertEqual(value.capturedAtMS, 1.234567 * 1000)
        XCTAssertEqual(value.tracking, .normal)
        XCTAssertEqual(value.left.distanceMetres, 1)
        XCTAssertEqual(value.center.distanceMetres, 2)
        XCTAssertEqual(value.right.distanceMetres, 3)
        XCTAssertEqual(value.left.validFraction, 1)
    }
    func testLowConfidenceStaysNullWithActualCoverage() throws {
        var confidence = Array(repeating: UInt8(2), count: 96)
        for index in 0..<30 { confidence[index] = 0 }
        let value = try adapter.sample(from: makeSummary(confidence: confidence))
        XCTAssertNil(value.left.distanceMetres)
        XCTAssertEqual(value.left.validFraction, 2.0/32)
        XCTAssertEqual(value.center.distanceMetres, 2)
    }
    func testMissingConfidenceAndTrackingLossDoNotReuseDistances() throws {
        _ = try adapter.sample(from: makeSummary())
        for input in [try makeSummary(missingConfidence: true), try makeSummary(tracking: .limited),
                      try makeSummary(tracking: .unavailable)] {
            let value = try adapter.sample(from: input)
            XCTAssertEqual(value.tracking, .unavailable)
            XCTAssertTrue([value.left, value.center, value.right].allSatisfy { $0.distanceMetres == nil })
            XCTAssertEqual(value.capturedAtMS, 1.234567 * 1000)
        }
    }
    func testInvalidOrAbsentTimestampCannotBecomeReceiptTime() throws {
        for time in [Double.nan, .infinity, -1] {
            XCTAssertThrowsError(try adapter.sample(from: makeSummary(time: time))) {
                XCTAssertEqual($0 as? DepthTelemetryError, .missingCaptureTime)
            }
        }
        XCTAssertThrowsError(try adapter.sample(from: .unavailable(mode: .replay,
            captureTimestampSeconds: nil, reason: .missingDepth)))
    }
    func testReplayCannotBecomeLiveAndLiveCannotBecomeReplay() throws {
        XCTAssertThrowsError(try adapter.sample(from: makeSummary(mode: .live))) {
            XCTAssertEqual($0 as? DepthTelemetryError, .modeMismatch)
        }
        let live = DepthTelemetryAdapter(sessionMode: .live)
        XCTAssertThrowsError(try live.sample(from: makeSummary()))
        XCTAssertNoThrow(try live.sample(from: makeSummary(mode: .live)))
    }
    func testConvertedSampleStillObeysCoreRateReadinessAndReconnect() throws {
        let session = try PhoneSession(origin: URL(string: "https://fixture.invalid")!,
            sessionID: "test-session", sourceID: "phone", bootID: "boot",
            receiverID: "pi", receiverBootID: "pi-boot", mode: .replay,
            phoneToken: String(repeating: "x", count: 40))
        var core = TelemetryCore(session: session)
        try core.connecting(now: 1000); try core.opened(now: 1000)
        XCTAssertFalse(try core.offer(adapter.sample(from: makeSummary(time: 1.001)), now: 1001))
        try core.setProducerState(.ready, now: 1001)
        let heartbeat = try XCTUnwrap(core.next(now: 1001))
        try core.completed(heartbeat.id, now: 1001)
        XCTAssertTrue(try core.offer(adapter.sample(from: makeSummary(time: 1.002)), now: 1002))
        let first = try XCTUnwrap(core.next(now: 1002))
        try core.completed(first.id, now: 1002)
        XCTAssertTrue(try core.offer(adapter.sample(from: makeSummary(time: 1.003)), now: 1003))
        XCTAssertNil(try core.next(now: 1003))
        try core.disconnected(now: 1004)
        try core.connecting(now: 1100); try core.opened(now: 1100)
        XCTAssertNil(try core.next(now: 1100))
        XCTAssertFalse(try core.offer(adapter.sample(from: makeSummary(time: 1.003)), now: 1100))
        XCTAssertTrue(try core.offer(adapter.sample(from: makeSummary(time: 1.101)), now: 1101))
        let second = try XCTUnwrap(core.next(now: 1102))
        let bytes = try XCTUnwrap(JSONSerialization.jsonObject(with: second.data) as? [String: Any])
        XCTAssertEqual(bytes["seq"] as? Int, 1)
        XCTAssertEqual(bytes["capture_monotonic_ms"] as? Double, 1.101 * 1000)
    }
}
