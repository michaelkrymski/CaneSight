import Foundation
import XCTest
@testable import CaneSightTelemetry

private enum NativeDeadline: Error { case elapsed }

final class NativeWebSocketTests: XCTestCase {
    private func endpoint(_ name: String) throws -> String {
        #if os(macOS)
        guard let origin = ProcessInfo.processInfo.environment[name] else {
            throw XCTSkip("Run tests/ios/test_native_websocket.py for local native network fixtures")
        }
        // The harness owns loopback listeners; never use external credentials.
        guard let url = URL(string: origin), url.scheme == "https", url.host == "127.0.0.1",
              url.port != nil else { throw TelemetryError.configuration }
        return origin
        #else
        throw XCTSkip("Native loopback harness is a macOS test, not iPhone evidence")
        #endif
    }
    private func bounded<T: Sendable>(_ operation: @escaping @Sendable () async throws -> T) async throws -> T {
        try await withThrowingTaskGroup(of: T.self) { group in
            group.addTask { try await operation() }
            group.addTask {
                try await Task.sleep(nanoseconds: 3_000_000_000)
                throw NativeDeadline.elapsed
            }
            defer { group.cancelAll() }
            return try await group.next()!
        }
    }
    func testUntrustedTLSFailsClosedUsingOSVerification() async throws {
        let session = try grant(origin: endpoint("CANESIGHT_NATIVE_UNTRUSTED_ORIGIN"))
        do {
            let socket = try await bounded { try await NativeWebSocket.connect(session) }
            socket.cancel()
            XCTFail("A generated untrusted certificate must never open a socket")
        } catch let failure as TelemetryError {
            XCTAssertEqual(failure, .rejected)
        }
    }
    func testCancellationEndsARealStalledTLSHandshake() async throws {
        let session = try grant(origin: endpoint("CANESIGHT_NATIVE_STALLED_ORIGIN"))
        let dial = Task { try await NativeWebSocket.connect(session) }
        defer { dial.cancel() }
        // The loopback peer accepts TCP but never completes the TLS handshake.
        try await Task.sleep(nanoseconds: 100_000_000)
        dial.cancel()
        do {
            let socket = try await bounded { try await dial.value }
            socket.cancel()
            XCTFail("Cancelled dial must not open a socket")
        } catch let failure as TelemetryError {
            XCTAssertEqual(failure, .closed)
        }
    }
}
