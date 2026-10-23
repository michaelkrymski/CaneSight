import XCTest
import CaneSightTelemetry
@testable import CaneSightPhonePairing

private final class RecordingSocket: TelemetrySocket, @unchecked Sendable {
    private let lock = NSLock()
    private var sends = 0, cancellations = 0
    var sent: Int { lock.withLock { sends } }
    var cancelled: Int { lock.withLock { cancellations } }
    func send(_ data: Data) async throws { lock.withLock { sends += 1 } }
    func receive() async throws -> Data { throw TelemetryError.closed }
    func cancel() { lock.withLock { cancellations += 1 } }
}
final class SendFenceTests: XCTestCase {
    let depth = Data(#"{"type":"depth_observation"}"#.utf8)
    let ready = Data(#"{"type":"heartbeat","state":"ready"}"#.utf8)
    let starting = Data(#"{"type":"heartbeat","state":"starting"}"#.utf8)
    func testDepthAndReadyAreDeniedUntilExplicitPermission() async throws {
        let gate = DiagnosticSendFence(), socket = RecordingSocket()
        let wrapped = try gate.attach(socket)
        try await wrapped.send(starting)
        do { try await wrapped.send(depth); XCTFail("Depth sent without permission") } catch {}
        do { try await wrapped.send(ready); XCTFail("Ready sent without permission") } catch {}
        XCTAssertEqual(socket.sent, 1)
        gate.permitDepth(); try await wrapped.send(depth)
        gate.invalidate()
        XCTAssertEqual(socket.cancelled, 1)
        do { try await wrapped.send(depth); XCTFail("Old depth survived invalidation") } catch {}
        XCTAssertEqual(socket.sent, 2)
    }
    func testWireQualityCountsActualNumericAndNullSectors() async throws {
        let gate = DiagnosticSendFence(), socket = RecordingSocket()
        let wrapped = try gate.attach(socket); gate.permitDepth()
        try await wrapped.send(Data(#"{"type":"depth_observation","sectors":{"left":{"distance_m":0.8},"center":{"distance_m":1.1},"right":{"distance_m":1.2}}}"#.utf8))
        try await wrapped.send(Data(#"{"type":"depth_observation","sectors":{"left":{"distance_m":0.8},"center":{"distance_m":null},"right":{"distance_m":null}}}"#.utf8))
        try await wrapped.send(Data(#"{"type":"depth_observation","sectors":{"left":{"distance_m":true},"center":{"distance_m":null},"right":{"distance_m":null}}}"#.utf8))
        let counts = gate.wireDepthDiagnostics
        XCTAssertEqual(counts["completed_native_depth_sends"], 3)
        XCTAssertEqual(counts["all_three_numeric_sends"], 1)
        XCTAssertEqual(counts["left_numeric_sends"], 2)
        XCTAssertEqual(counts["center_numeric_sends"], 1)
        XCTAssertEqual(counts["right_numeric_sends"], 1)
    }
    func testClockCounterCountsCompletedRepliesOnly() async throws {
        let gate = DiagnosticSendFence(), socket = RecordingSocket()
        let wrapped = try gate.attach(socket)
        try await wrapped.send(starting)
        XCTAssertEqual(gate.completedClockReplies, 0)
        try await wrapped.send(Data(#"{"type":"clock_reply"}"#.utf8))
        XCTAssertEqual(gate.completedClockReplies, 1)
        gate.invalidate(end: true)
        do { try await wrapped.send(Data(#"{"type":"clock_reply"}"#.utf8)); XCTFail("Ended socket sent") } catch {}
        XCTAssertEqual(gate.completedClockReplies, 1)
    }
    func testEndedGenerationRejectsLateSocketAndCannotRearm() async throws {
        let gate = DiagnosticSendFence(), socket = RecordingSocket()
        let wrapped = try gate.attach(socket)
        gate.permitDepth(); gate.invalidate(end: true); gate.permitDepth()
        do { try await wrapped.send(depth); XCTFail("Ended generation rearmed") } catch {}
        let late = RecordingSocket()
        XCTAssertThrowsError(try gate.attach(late))
        XCTAssertEqual(late.cancelled, 1); XCTAssertEqual(socket.sent, 0)
    }
}
