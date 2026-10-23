import Foundation
import CoreFoundation
import CaneSightTelemetry

/// Invalidations synchronously prevent new depth sends and cancel the current
/// socket. Bytes already handed to the OS cannot be recalled; receiver expiry
/// remains independently required. No claim of physical motor inhibition.
public final class DiagnosticSendFence: @unchecked Sendable {
    public init() {}
    private let lock = NSLock()
    private var ended = false, depthAllowed = false
    private var replies: UInt64 = 0
    private var wireDepth: UInt64 = 0, allNumeric: UInt64 = 0
    private var numeric = ["left": UInt64(0), "center": UInt64(0), "right": UInt64(0)]
    public var wireDepthDiagnostics: [String: UInt64] { lock.withLock {
        ["completed_native_depth_sends": wireDepth, "all_three_numeric_sends": allNumeric,
         "left_numeric_sends": numeric["left"]!, "center_numeric_sends": numeric["center"]!,
         "right_numeric_sends": numeric["right"]!]
    } }
    public var completedClockReplies: UInt64 { lock.withLock { replies } }
    private var socket: (any TelemetrySocket)?
    public func attach(_ value: any TelemetrySocket) throws -> any TelemetrySocket {
        let allowed = lock.withLock { () -> Bool in
            guard !ended else { return false }; socket = value; return true
        }
        guard allowed else { value.cancel(); throw TelemetryError.closed }
        return FencedSocket(native: value, fence: self)
    }
    public func permitDepth() { lock.withLock { if !ended { depthAllowed = true } } }
    public func invalidate(end: Bool = false) {
        let current = lock.withLock { () -> (any TelemetrySocket)? in
            depthAllowed = false; ended = ended || end
            let old = socket; socket = nil; return old
        }
        current?.cancel()
    }
    func completed(_ data: Data) {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        if obj["type"] as? String == "clock_reply" {
            lock.withLock { if replies < .max { replies += 1 } }
        } else if obj["type"] as? String == "depth_observation", let sectors = obj["sectors"] as? [String: [String: Any]] {
            let measured = ["left", "center", "right"].filter { name in
                guard let value = sectors[name]?["distance_m"] as? NSNumber,
                      CFGetTypeID(value) != CFBooleanGetTypeID() else { return false }
                return value.doubleValue.isFinite && value.doubleValue > 0
            }
            lock.withLock {
                if wireDepth < .max { wireDepth += 1 }
                if measured.count == 3 && allNumeric < .max { allNumeric += 1 }
                for name in measured { if numeric[name]! < .max { numeric[name]! += 1 } }
            }
        }
    }
    func permits(_ data: Data) -> Bool {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return false }
        let needsDepth = obj["type"] as? String == "depth_observation" || obj["state"] as? String == "ready"
        return lock.withLock { !ended && (!needsDepth || depthAllowed) }
    }
}
private struct FencedSocket: TelemetrySocket {
    let native: any TelemetrySocket
    let fence: DiagnosticSendFence
    func send(_ data: Data) async throws {
        guard fence.permits(data) else { throw TelemetryError.closed }
        try await native.send(data)
        fence.completed(data)
    }
    func receive() async throws -> Data { try await native.receive() }
    func cancel() { native.cancel() }
}
