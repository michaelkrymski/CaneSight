import XCTest
@testable import CaneSightTelemetry
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

func grant(origin: String = "https://fixture.invalid", mode: StreamMode = .replay) throws -> PhoneSession {
    try PhoneSession(origin: URL(string: origin)!, sessionID: "demo-session", sourceID: "phone-1",
        bootID: "phone-boot-1", receiverID: "pi-1", receiverBootID: "pi-boot-1", mode: mode,
        phoneToken: String(repeating: "x", count: 40))
}
func sample(_ time: Double, distance: Double? = 1.2, tracking: Tracking = .normal) throws -> DepthSample {
    let sector = try DepthSector(distanceMetres: distance, validFraction: 0.8)
    return try DepthSample(capturedAtMS: time, tracking: tracking, left: sector, center: sector, right: sector)
}
func object(_ packet: Transmission) throws -> [String: Any] {
    try XCTUnwrap(JSONSerialization.jsonObject(with: packet.data) as? [String: Any])
}
func probe(_ nonce: String = "nonce-1") -> Data {
    Data(#"{"schema_version":1,"type":"clock_probe","session_id":"demo-session","mode":"replay","nonce":"NONCE","receiver_id":"pi-1","receiver_boot_id":"pi-boot-1","source_id":"phone-1","source_boot_id":"phone-boot-1","t1_ms":1000}"#.replacingOccurrences(of: "NONCE", with: nonce).utf8)
}
func readyCore() throws -> TelemetryCore {
    var core = TelemetryCore(session: try grant())
    try core.connecting(now: 1000); try core.opened(now: 1000)
    try core.setProducerState(.ready, now: 1000)
    let heartbeat = try XCTUnwrap(core.next(now: 1000))
    try core.completed(heartbeat.id, now: 1000)
    return core
}

final class CoreTests: XCTestCase {
    func testOriginalCaptureNullsIdentityAndIndependentSequences() throws {
        var core = try readyCore()
        try core.offer(sample(1001, distance: nil), now: 1010)
        let packet = try XCTUnwrap(core.next(now: 1010)), json = try object(packet)
        XCTAssertEqual(json["capture_monotonic_ms"] as? Double, 1001)
        XCTAssertEqual(json["seq"] as? Int, 0)
        XCTAssertEqual(json["boot_id"] as? String, "phone-boot-1")
        XCTAssertEqual(json["mode"] as? String, "replay")
        XCTAssertTrue(json["capture_utc"] is NSNull)
        let sectors = try XCTUnwrap(json["sectors"] as? [String: [String: Any]])
        XCTAssertTrue(sectors["left"]?["distance_m"] is NSNull)
        XCTAssertLessThanOrEqual(packet.data.count, 8192)
        try core.completed(packet.id, now: 1011)
        let heartbeat = try XCTUnwrap(core.next(now: 2000))
        XCTAssertEqual(try object(heartbeat)["seq"] as? Int, 1)
    }
    func testLatestOnlyAndNoConcurrentSendOrCatchupBurst() throws {
        var core = try readyCore()
        for time in 1001...1050 { try core.offer(sample(Double(time)), now: Double(time)) }
        let first = try XCTUnwrap(core.next(now: 1050))
        XCTAssertEqual(try object(first)["capture_monotonic_ms"] as? Double, 1050)
        try core.offer(sample(1051), now: 1051)
        XCTAssertNil(try core.next(now: 1051))
        try core.completed(first.id, now: 1052)
        XCTAssertNil(try core.next(now: 1149))
        let second = try XCTUnwrap(core.next(now: 1150))
        XCTAssertEqual(try object(second)["seq"] as? Int, 1)
        try core.completed(second.id, now: 1150)
        XCTAssertNil(try core.next(now: 1150))
        XCTAssertEqual(core.status.droppedDepth, 49)
    }
    func testTenHzRateUnderFastProducer() throws {
        var core = try readyCore()
        var captures = [Double]()
        for now in 1001...1999 {
            try core.offer(sample(Double(now)), now: Double(now))
            if let packet = try core.next(now: Double(now)) {
                captures.append(Double(now)); try core.completed(packet.id, now: Double(now))
            }
        }
        XCTAssertEqual(captures.count, 10)
        XCTAssertTrue(zip(captures.dropFirst(), captures).allSatisfy { $0-$1 >= 100 })
    }
    func testReconnectRetainsSequenceAndRejectsPreconnectionCapture() throws {
        var core = try readyCore()
        try core.offer(sample(1001), now: 1001)
        let old = try XCTUnwrap(core.next(now: 1001))
        try core.disconnected(now: 1002)
        XCTAssertFalse(try core.offer(sample(1003), now: 1003))
        try core.connecting(now: 1100); try core.opened(now: 1100)
        XCTAssertFalse(try core.completed(old.id, now: 1100))
        XCTAssertFalse(try core.offer(sample(1099), now: 1100))
        XCTAssertFalse(core.status.pendingDepth)
        try core.offer(sample(1101), now: 1101)
        let next = try XCTUnwrap(core.next(now: 1101))
        XCTAssertEqual(try object(next)["seq"] as? Int, 1)
        XCTAssertEqual(try object(next)["capture_monotonic_ms"] as? Double, 1101)
    }
    func testSuspendResumeRequiresNewReadyAndNewCapture() throws {
        var core = try readyCore()
        try core.offer(sample(1001), now: 1001)
        try core.suspend(now: 1002); try core.resume(now: 1100)
        try core.connecting(now: 1100); try core.opened(now: 1100)
        XCTAssertFalse(try core.offer(sample(1101), now: 1101))
        try core.setProducerState(.ready, now: 1102)
        XCTAssertFalse(try core.offer(sample(1101), now: 1102))
        XCTAssertTrue(try core.offer(sample(1103), now: 1103))
    }
    func testStaleFutureRepeatedCaptureAndBoundaryAreSuppressed() throws {
        var core = try readyCore()
        XCTAssertFalse(try core.offer(sample(1200), now: 1100))
        XCTAssertTrue(try core.offer(sample(1101), now: 1101))
        XCTAssertFalse(try core.offer(sample(1101), now: 1102))
        XCTAssertNil(try core.next(now: 1602))
        XCTAssertFalse(try core.offer(sample(1102), now: 1603))
        try core.offer(sample(1604), now: 1604)
        let packet = try XCTUnwrap(core.next(now: 1604))
        XCTAssertTrue(try core.sendTimedOut(now: 2104))
        XCTAssertFalse(try core.completed(packet.id, now: 2104))
        XCTAssertEqual(core.status.phase, .disconnected)
    }
    func testClockReversalAndInvalidClockLatchFaultAcrossReconnect() throws {
        for value in [999, Double.nan, Double.infinity, -1] {
            var core = try readyCore()
            XCTAssertThrowsError(try core.observe(now: value))
            XCTAssertEqual(core.status.failure, .clock)
            try core.connecting(now: 2000)
            XCTAssertEqual(core.status.phase, .failed)
            XCTAssertNil(try core.next(now: 2000))
        }
    }
    func testSequenceOverflowRequiresNewEpoch() throws {
        var core = try readyCore(); core.depthSequence = TelemetryCore.maximumSequence
        try core.offer(sample(1001), now: 1001)
        let last = try XCTUnwrap(core.next(now: 1001))
        XCTAssertEqual(try object(last)["seq"] as? UInt64, TelemetryCore.maximumSequence)
        try core.completed(last.id, now: 1001)
        try core.offer(sample(1101), now: 1101)
        XCTAssertThrowsError(try core.next(now: 1101))
        XCTAssertEqual(core.status.failure, .sequenceExhausted)
    }
    func testClockReplyPreservesBindingsUsesLocalT2T3AndIsRateLimited() throws {
        var core = try readyCore()
        XCTAssertTrue(try core.receiveProbe(probe(), receivedAtMS: 1100))
        XCTAssertFalse(try core.receiveProbe(probe("nonce-2"), receivedAtMS: 1101))
        let packet = try XCTUnwrap(core.next(now: 1110)), json = try object(packet)
        XCTAssertEqual(json["type"] as? String, "clock_reply")
        XCTAssertEqual(json["t1_ms"] as? Double, 1000)
        XCTAssertEqual(json["t2_ms"] as? Double, 1100)
        XCTAssertEqual(json["t3_ms"] as? Double, 1110)
        try core.completed(packet.id, now: 1111)
        XCTAssertFalse(try core.receiveProbe(probe(), receivedAtMS: 2100))
        XCTAssertTrue(try core.receiveProbe(probe("nonce-2"), receivedAtMS: 2100))
        XCTAssertEqual(try object(XCTUnwrap(core.next(now: 2600)))["type"] as? String, "heartbeat")
    }
    func testStrictInboundRejectsDuplicateEscapedUnknownNestedAndForeignFields() throws {
        let original = String(decoding: probe(), as: UTF8.self)
        let invalid = [original.replacingOccurrences(of: "\"t1_ms\":1000", with: "\"t1_ms\":1000,\"t1_ms\":1000"),
            original.replacingOccurrences(of: "\"t1_ms\":1000", with: "\"t1_ms\":1000,\"t1_\\u006ds\":1000"),
            original.replacingOccurrences(of: "\"t1_ms\":1000", with: "\"t1_ms\":NaN"),
            original.replacingOccurrences(of: "\"t1_ms\":1000", with: "\"t1_ms\":1e999"),
            original.replacingOccurrences(of: "\"t1_ms\":1000", with: "\"t1_ms\":true"),
            original.replacingOccurrences(of: "\"t1_ms\":1000", with: "\"t1_ms\":{}"),
            original.replacingOccurrences(of: "phone-boot-1", with: "foreign-boot"),
            original.replacingOccurrences(of: "\"schema_version\":1", with: "\"schema_version\":true"),
            original.replacingOccurrences(of: "replay", with: "live"), original+"{}", "["+original+"]", String(repeating: " ", count: 8193)]
        for text in invalid { var core = try readyCore(); XCTAssertThrowsError(try core.receiveProbe(Data(text.utf8), receivedAtMS: 1100), text) }
    }
    func testSampleValidationPreservesUnknownNotSentinels() throws {
        XCTAssertThrowsError(try sample(Double.nan))
        XCTAssertThrowsError(try sample(1000, distance: .infinity))
        XCTAssertThrowsError(try sample(1000, tracking: .limited))
        XCTAssertThrowsError(try DepthSector(distanceMetres: 0, validFraction: 0))
        XCTAssertThrowsError(try DepthSector(distanceMetres: nil, validFraction: 1.1))
        XCTAssertNoThrow(try sample(1000, distance: nil, tracking: .unavailable))
    }
    func testGrantAndNativeRequestRejectUnsafeOriginsAndRedactCredentials() throws {
        for origin in ["http://fixture.invalid", "https://user:pass@fixture.invalid", "https://fixture.invalid/path", "https://fixture.invalid?token=x", "https://fixture.invalid#fragment"] {
            XCTAssertThrowsError(try grant(origin: origin))
        }
        let session = try grant(), request = NativeWebSocket.request(for: session)
        XCTAssertEqual(request.url?.absoluteString, "wss://fixture.invalid/v1/telemetry")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer "+String(repeating: "x", count: 40))
        XCTAssertNil(request.value(forHTTPHeaderField: "Origin"))
        XCTAssertFalse(String(reflecting: session).contains(String(repeating: "x", count: 40)))
        XCTAssertFalse(String(describing: session).contains("fixture.invalid"))
    }

    func testClockProbeHistoryAndCapacityPersistAcrossReconnect() throws {
        var core = try readyCore()
        try core.receiveProbe(probe(), receivedAtMS: 1100)
        try core.disconnected(now: 1101)
        try core.connecting(now: 1200); try core.opened(now: 1200)
        XCTAssertFalse(try core.receiveProbe(probe("nonce-2"), receivedAtMS: 1200))
        XCTAssertFalse(try core.receiveProbe(probe(), receivedAtMS: 2100))
        core.seenNonces = Set((0..<1024).map { "old-\($0)" })
        XCTAssertThrowsError(try core.receiveProbe(probe("new-nonce"), receivedAtMS: 2100))
        XCTAssertEqual(core.status.failure, .probeCapacity)
    }
}
