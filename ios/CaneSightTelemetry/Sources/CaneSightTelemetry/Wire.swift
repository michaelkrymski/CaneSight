import Foundation

public enum TelemetryError: Error, Equatable, Sendable {
    case configuration, invalidSample, invalidControl, clock, sequenceExhausted, probeCapacity
    case connection, rejected, closed
}
public enum StreamMode: String, Sendable { case live, replay }
public enum Tracking: String, Sendable { case normal, limited, unavailable }
public enum ProducerState: String, Sendable { case starting, ready, degraded }

func validID(_ value: String) -> Bool {
    (1...64).contains(value.utf8.count) && value.utf8.allSatisfy {
        (65...90).contains($0) || (97...122).contains($0) || (48...57).contains($0) || $0 == 45 || $0 == 95
    }
}
func finiteTime(_ value: Double) -> Bool { value.isFinite && value >= 0 }

/// Only a phone grant and nonsecret peer bindings. Enrollment/storage are caller-owned.
public struct PhoneSession: Sendable, CustomStringConvertible, CustomDebugStringConvertible, CustomReflectable {
    public let sessionID: String, sourceID: String, bootID: String, receiverID: String, receiverBootID: String
    public let mode: StreamMode
    public let endpoint: URL
    let token: String
    public var description: String { "PhoneSession(redacted)" }
    public var debugDescription: String { description }
    public var customMirror: Mirror { Mirror(self, children: ["configuration": "redacted"]) }
    public init(origin: URL, sessionID: String, sourceID: String, bootID: String,
                receiverID: String, receiverBootID: String, mode: StreamMode, phoneToken: String) throws {
        guard var parts = URLComponents(url: origin, resolvingAgainstBaseURL: false),
              parts.scheme?.lowercased() == "https", let host = parts.host, !host.isEmpty,
              parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
              parts.path.isEmpty || parts.path == "/",
              parts.port == nil || (1...65535).contains(parts.port!),
              [sessionID, sourceID, bootID, receiverID, receiverBootID].allSatisfy(validID),
              sourceID != receiverID, (32...128).contains(phoneToken.utf8.count),
              phoneToken.utf8.allSatisfy({ (33...126).contains($0) }) else { throw TelemetryError.configuration }
        parts.scheme = "wss"; parts.path = "/v1/telemetry"
        guard let endpoint = parts.url else { throw TelemetryError.configuration }
        self.endpoint = endpoint; self.sessionID = sessionID; self.sourceID = sourceID
        self.bootID = bootID; self.receiverID = receiverID; self.receiverBootID = receiverBootID
        self.mode = mode; token = phoneToken
    }
}

public struct DepthSector: Sendable {
    public let distanceMetres: Double?, validFraction: Double
    public init(distanceMetres: Double?, validFraction: Double) throws {
        guard validFraction.isFinite, (0...1).contains(validFraction),
              distanceMetres == nil || (finiteTime(distanceMetres!) && validFraction > 0) else {
            throw TelemetryError.invalidSample
        }
        self.distanceMetres = distanceMetres; self.validFraction = validFraction
    }
    var wire: [String: Any] { ["distance_m": distanceMetres.map { $0 as Any } ?? NSNull(), "valid_fraction": validFraction] }
}
/// CS-014 supplies original capture milliseconds on the exact injected source clock.
public struct DepthSample: Sendable {
    public let capturedAtMS: Double
    public let tracking: Tracking
    public let left: DepthSector, center: DepthSector, right: DepthSector
    public init(capturedAtMS: Double, tracking: Tracking, left: DepthSector,
                center: DepthSector, right: DepthSector) throws {
        guard finiteTime(capturedAtMS), tracking == .normal ||
              [left, center, right].allSatisfy({ $0.distanceMetres == nil }) else { throw TelemetryError.invalidSample }
        self.capturedAtMS = capturedAtMS; self.tracking = tracking
        self.left = left; self.center = center; self.right = right
    }
}

func encode(_ object: [String: Any]) throws -> Data {
    let data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
    guard data.count <= 8192 else { throw TelemetryError.invalidControl }
    return data
}

/// Strict flat JSON parser for the only inbound type: clock_probe. Rejects duplicate
/// (including escaped-equivalent) keys before dictionary materialization. Nested
/// objects/arrays, bool/null, oversized frames and nonfinite numbers are refused.
struct Probe {
    let nonce: String, t1: Double
    let fields: [String: FlatValue]
    init(data: Data, session: PhoneSession) throws {
        let fields = try FlatObject.parse(data)
        let expected: Set<String> = ["schema_version", "type", "session_id", "mode", "nonce",
            "receiver_id", "receiver_boot_id", "source_id", "source_boot_id", "t1_ms"]
        guard Set(fields.keys) == expected, fields["schema_version"]?.number == 1,
              fields["type"]?.text == "clock_probe", fields["session_id"]?.text == session.sessionID,
              fields["mode"]?.text == session.mode.rawValue,
              fields["source_id"]?.text == session.sourceID, fields["source_boot_id"]?.text == session.bootID,
              fields["receiver_id"]?.text == session.receiverID,
              fields["receiver_boot_id"]?.text == session.receiverBootID,
              let nonce = fields["nonce"]?.text, validID(nonce),
              let t1 = fields["t1_ms"]?.number, finiteTime(t1) else { throw TelemetryError.invalidControl }
        self.fields = fields; self.nonce = nonce; self.t1 = t1
    }
    func reply(t2: Double, t3: Double) throws -> Data {
        var object = fields.mapValues { $0.object }
        object["type"] = "clock_reply"; object["t2_ms"] = t2; object["t3_ms"] = t3
        return try encode(object)
    }
}
enum FlatValue {
    case text(String), number(Double)
    var text: String? { if case .text(let value) = self { return value }; return nil }
    var number: Double? { if case .number(let value) = self { return value }; return nil }
    var object: Any { switch self { case .text(let v): return v; case .number(let v): return v } }
}
struct FlatObject {
    let bytes: [UInt8]
    var position = 0
    mutating func space() { while position < bytes.count && [9,10,13,32].contains(bytes[position]) { position += 1 } }
    mutating func consume(_ byte: UInt8) throws {
        space(); guard position < bytes.count, bytes[position] == byte else { throw TelemetryError.invalidControl }
        position += 1
    }
    mutating func string() throws -> String {
        space(); let start = position
        try consume(34)
        var escaped = false
        while position < bytes.count {
            let byte = bytes[position]; position += 1
            if escaped { escaped = false; continue }
            if byte == 92 { escaped = true; continue }
            if byte == 34 { return try JSONDecoder().decode(String.self, from: Data(bytes[start..<position])) }
        }
        throw TelemetryError.invalidControl
    }
    mutating func object() throws -> [String: FlatValue] {
        try consume(123); space()
        var result: [String: FlatValue] = [:]
        while position < bytes.count && bytes[position] != 125 {
            guard result.count < 10 else { throw TelemetryError.invalidControl }
            let key = try string()
            guard result[key] == nil else { throw TelemetryError.invalidControl }
            try consume(58); space()
            guard position < bytes.count else { throw TelemetryError.invalidControl }
            let value: FlatValue
            if bytes[position] == 34 { value = .text(try string()) }
            else {
                let start = position
                while position < bytes.count && ![44,125].contains(bytes[position]) { position += 1 }
                guard let token = String(bytes: bytes[start..<position], encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
                      token.range(of: #"\A-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?\z"#, options: .regularExpression) != nil,
                      let number = Double(token), finiteTime(number) else { throw TelemetryError.invalidControl }
                value = .number(number)
            }
            result[key] = value; space()
            guard position < bytes.count else { throw TelemetryError.invalidControl }
            if bytes[position] == 125 { break }
            try consume(44); space()
            guard position < bytes.count, bytes[position] != 125 else { throw TelemetryError.invalidControl }
        }
        try consume(125); space()
        guard position == bytes.count else { throw TelemetryError.invalidControl }
        return result
    }
    static func parse(_ data: Data) throws -> [String: FlatValue] {
        guard !data.isEmpty, data.count <= 8192, String(data: data, encoding: .utf8) != nil else { throw TelemetryError.invalidControl }
        var parser = FlatObject(bytes: Array(data))
        return try parser.object()
    }
}
