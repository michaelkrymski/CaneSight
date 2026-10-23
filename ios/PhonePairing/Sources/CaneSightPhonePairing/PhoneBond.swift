import Foundation
import CaneSightTelemetry

public enum BondError: Error, Equatable { case invalidFile, invalidResponse, rejected(Int), clock }
private func identity(_ value: String) -> Bool {
    (1...64).contains(value.utf8.count) && value.utf8.allSatisfy {
        (65...90).contains($0) || (97...122).contains($0) || (48...57).contains($0) || $0 == 45 || $0 == 95
    }
}
private func token(_ value: String) -> Bool {
    (32...128).contains(value.utf8.count) && value.utf8.allSatisfy { (33...126).contains($0) }
}
/// Existing phone-role enrollment only. Never provisions or exports a credential.
public struct PhoneBond: Sendable, CustomStringConvertible, CustomDebugStringConvertible, CustomReflectable {
    public let origin: URL
    public let sourceID: String
    private let bondID: String, secret: String
    public var description: String { "PhoneBond(redacted)" }
    public var debugDescription: String { description }
    public var customMirror: Mirror { Mirror(self, children: ["credential": "redacted"]) }
    public init(data: Data) throws {
        guard data.count <= 2048,
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              Set(obj.keys) == ["schema_version", "base_url", "bond_id", "role", "source_id", "token"],
              let schema = obj["schema_version"] as? NSNumber, schema == 1,
              CFGetTypeID(schema) != CFBooleanGetTypeID(), obj["role"] as? String == "phone",
              let base = obj["base_url"] as? String,
              var parts = URLComponents(string: base), parts.scheme == "https", let host = parts.host, !host.isEmpty,
              parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
              parts.path.isEmpty || parts.path == "/", parts.port == nil || (1...65535).contains(parts.port!),
              let bond = obj["bond_id"] as? String, identity(bond),
              let source = obj["source_id"] as? String, identity(source),
              let secret = obj["token"] as? String, token(secret) else { throw BondError.invalidFile }
        parts.path = ""
        guard let url = parts.url else { throw BondError.invalidFile }
        origin = url; sourceID = source; bondID = bond; self.secret = secret
    }
    public func request(bootID: String) throws -> URLRequest {
        guard identity(bootID) else { throw BondError.invalidFile }
        var request = URLRequest(url: origin.appendingPathComponent("v1/bonds/connect"))
        request.httpMethod = "POST"; request.timeoutInterval = 5
        request.setValue("Bearer " + secret, forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["bond_id": bondID, "role": "phone", "boot_id": bootID])
        return request
    }
    public func response(_ data: Data, status: Int, bootID: String) throws -> PhoneSession? {
        guard data.count <= 8192 else { throw BondError.invalidResponse }
        guard status == 200 || status == 202 else { throw BondError.rejected(status) }
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let schema = obj["schema_version"] as? NSNumber, schema == 1,
              CFGetTypeID(schema) != CFBooleanGetTypeID() else { throw BondError.invalidResponse }
        if status == 202 {
            guard Set(obj.keys) == ["schema_version", "state"], obj["state"] as? String == "waiting_for_peer" else {
                throw BondError.invalidResponse
            }
            return nil
        }
        guard obj["state"] as? String == "paired", obj["mode"] as? String == "live",
              let device = obj["device"] as? [String: String],
              let peer = obj["peer"] as? [String: String], Set(peer.keys) == ["source_id", "boot_id"],
              device["source_id"] == sourceID, device["boot_id"] == bootID,
              let session = obj["session_id"] as? String,
              let peerID = peer["source_id"], let peerBoot = peer["boot_id"],
              let secret = device["token"],
              let lease = obj["expires_in_seconds"] as? NSNumber,
              CFGetTypeID(lease) != CFBooleanGetTypeID(), lease.doubleValue.isFinite, lease.doubleValue > 10 else {
            throw BondError.invalidResponse
        }
        do {
            return try PhoneSession(origin: origin, sessionID: session, sourceID: sourceID, bootID: bootID,
                receiverID: peerID, receiverBootID: peerBoot, mode: .live, phoneToken: secret)
        } catch { throw BondError.invalidResponse }
    }
}

import CoreFoundation

/// Default OS TLS, no redirects, no cookies/cache/credential store. No helper needed.
public final class BondHTTPClient: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    public func poll(_ bond: PhoneBond, bootID: String) async throws -> PhoneSession? {
        let config = URLSessionConfiguration.ephemeral
        config.urlCache = nil; config.httpCookieStorage = nil; config.urlCredentialStorage = nil
        config.connectionProxyDictionary = [:]
        let session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
        defer { session.invalidateAndCancel() }
        let (bytes, response) = try await session.bytes(for: bond.request(bootID: bootID))
        guard let response = response as? HTTPURLResponse else { throw BondError.invalidResponse }
        var data = Data()
        for try await byte in bytes {
            guard data.count < 8192 else { throw BondError.invalidResponse }
            data.append(byte)
        }
        return try bond.response(data, status: response.statusCode, bootID: bootID)
    }
    public func urlSession(_ session: URLSession, task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}

/// Diagnostic elapsed epoch, matching the earlier device bench. This detects
/// observed discontinuities; it does NOT establish sensor or receiver drift bounds.
public struct DiagnosticEpoch: Sendable {
    private let origin: Double
    private var last: Double = 0
    private var failed = false
    public init(originMilliseconds: Double) { origin = originMilliseconds }
    public mutating func observe(rawMilliseconds raw: Double, continuousElapsed elapsed: Double) throws -> Double {
        let now = raw - origin
        guard !failed, now.isFinite, elapsed.isFinite, now >= last, elapsed >= 0,
              abs(now - elapsed) <= 100 else { failed = true; throw BondError.clock }
        last = now; return now
    }
    public mutating func capture(rawMilliseconds raw: Double, now: Double) throws -> Double {
        let capture = raw - origin
        guard !failed, capture.isFinite, now.isFinite, capture >= 0, now >= capture, now - capture < 500 else {
            failed = true; throw BondError.clock
        }
        return capture
    }
}
