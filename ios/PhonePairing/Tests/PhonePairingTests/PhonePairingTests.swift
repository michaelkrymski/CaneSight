import XCTest
@testable import CaneSightPhonePairing

final class PhonePairingTests: XCTestCase {
    // Synthetic values only. No real token is present in these fixtures.
    func fixture(_ changes: [String: Any] = [:]) throws -> Data {
        var obj: [String: Any] = ["schema_version": 1, "base_url": "https://64.177.50.116/",
            "bond_id": "test-bond", "role": "phone", "source_id": "test-phone", "token": String(repeating: "x", count: 32)]
        for (key, value) in changes { obj[key] = value }
        return try JSONSerialization.data(withJSONObject: obj)
    }
    func reply(device: String = "test-phone", boot: String = "boot-test", peer: String = "test-pi", lease: Double = 60) throws -> Data {
        try JSONSerialization.data(withJSONObject: ["schema_version": 1, "state": "paired", "mode": "live",
            "session_id": "test-session", "expires_in_seconds": lease,
            "device": ["source_id": device, "boot_id": boot, "token": String(repeating: "y", count: 32)],
            "peer": ["source_id": peer, "boot_id": "pi-boot"]])
    }
    func testPhoneOnlyAndHTTPSOrigin() throws {
        for changes: [String: Any] in [["role": "pi"], ["base_url": "http://64.177.50.116"],
            ["base_url": "https://user:pass@example.com"], ["base_url": "https://example.com/path"],
            ["base_url": "https://example.com?token=x"], ["schema_version": true], ["token": "short"],
            ["operator_token": "forbidden"], ["source_id": "bad/source"]] {
            XCTAssertThrowsError(try PhoneBond(data: fixture(changes)))
        }
        XCTAssertThrowsError(try PhoneBond(data: Data(repeating: 32, count: 2049)))
    }
    func testRequestUsesHeaderAndRedactsReflection() throws {
        let bond = try PhoneBond(data: fixture())
        let request = try bond.request(bootID: "boot-test")
        XCTAssertEqual(request.url?.absoluteString, "https://64.177.50.116/v1/bonds/connect")
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertNotNil(request.value(forHTTPHeaderField: "Authorization"))
        XCTAssertFalse(String(decoding: request.httpBody!, as: UTF8.self).contains("token"))
        XCTAssertEqual(String(describing: bond), "PhoneBond(redacted)")
        XCTAssertEqual(String(reflecting: bond), "PhoneBond(redacted)")
        XCTAssertFalse(String(describing: Mirror(reflecting: bond).children.first!.value).contains(String(repeating: "x", count: 32)))
    }
    func testWaitingIsNotPaired() throws {
        let bond = try PhoneBond(data: fixture())
        let waiting = Data(#"{"schema_version":1,"state":"waiting_for_peer"}"#.utf8)
        XCTAssertNil(try bond.response(waiting, status: 202, bootID: "boot-test"))
        XCTAssertThrowsError(try bond.response(waiting, status: 200, bootID: "boot-test"))
        XCTAssertThrowsError(try bond.response(waiting, status: 401, bootID: "boot-test"))
        XCTAssertThrowsError(try bond.response(waiting, status: 302, bootID: "boot-test"))
    }
    func testSessionBindsDeviceBootAndPeer() throws {
        let bond = try PhoneBond(data: fixture())
        let grant = try XCTUnwrap(bond.response(reply(), status: 200, bootID: "boot-test"))
        XCTAssertEqual(grant.sourceID, "test-phone"); XCTAssertEqual(grant.receiverID, "test-pi")
        XCTAssertThrowsError(try bond.response(reply(device: "other-phone"), status: 200, bootID: "boot-test"))
        XCTAssertThrowsError(try bond.response(reply(boot: "old-boot"), status: 200, bootID: "boot-test"))
        XCTAssertThrowsError(try bond.response(reply(peer: "test-phone"), status: 200, bootID: "boot-test"))
        XCTAssertThrowsError(try bond.response(reply(lease: 0), status: 200, bootID: "boot-test"))
    }
    func testRebasePreservesAgeAndRejectsClockJumpPermanently() throws {
        var epoch = DiagnosticEpoch(originMilliseconds: 1000)
        let now = try epoch.observe(rawMilliseconds: 1100, continuousElapsed: 100)
        let capture = try epoch.capture(rawMilliseconds: 1075, now: now)
        XCTAssertEqual(now - capture, 25)
        XCTAssertThrowsError(try epoch.observe(rawMilliseconds: 2000, continuousElapsed: 110))
        XCTAssertThrowsError(try epoch.observe(rawMilliseconds: 1120, continuousElapsed: 120))
    }
    func testPreEpochFutureAndStaleCaptureRejected() throws {
        for raw in [999.0, 1601, 1000] {
            var epoch = DiagnosticEpoch(originMilliseconds: 1000)
            let now = try epoch.observe(rawMilliseconds: 1600, continuousElapsed: 600)
            XCTAssertThrowsError(try epoch.capture(rawMilliseconds: raw, now: now))
        }
    }
}
