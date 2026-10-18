import Foundation

public enum ConnectionPhase: String, Sendable { case disconnected, connecting, connected, suspended, failed, closed }
public struct TelemetryStatus: Sendable {
    public let phase: ConnectionPhase
    public let producer: ProducerState
    public let pendingDepth: Bool, pendingProbe: Bool, sending: Bool
    public let sentDepth: UInt64, droppedDepth: UInt64
    public let failure: TelemetryError?
}
public struct Transmission: Sendable {
    public let id: UUID, data: Data, deadlineMS: Double
    let kind: String
}
/// Deterministic single-owner state machine. TelemetryClient serializes access.
/// A connection is not sensor readiness; all producer state is explicitly supplied.
public struct TelemetryCore {
    public static let maximumSequence: UInt64 = 9_007_199_254_740_991
    let session: PhoneSession
    var phase: ConnectionPhase = .disconnected
    var producer: ProducerState = .starting
    var failure: TelemetryError?
    var lastNow: Double?
    var openedAt = Double.infinity
    var latest: DepthSample?
    var probe: (value: Probe, received: Double)?
    var flight: Transmission?
    var depthSequence: UInt64 = 0, heartbeatSequence: UInt64 = 0
    var readyAfter = -Double.infinity
    var highestCapture = -Double.infinity
    var lastDepthSend = -Double.infinity, lastHeartbeatSend = -Double.infinity
    var lastProbeReceived = -Double.infinity
    var seenNonces = Set<String>()
    var sentDepth: UInt64 = 0, droppedDepth: UInt64 = 0
    public init(session: PhoneSession) { self.session = session }
    public var status: TelemetryStatus {
        TelemetryStatus(phase: phase, producer: producer, pendingDepth: latest != nil,
            pendingProbe: probe != nil, sending: flight != nil, sentDepth: sentDepth,
            droppedDepth: droppedDepth, failure: failure)
    }
    public mutating func observe(now: Double) throws {
        guard finiteTime(now), lastNow == nil || now >= lastNow! else {
            fail(.clock); throw TelemetryError.clock
        }
        lastNow = now
    }
    mutating func clear() { latest = nil; probe = nil; flight = nil }
    public mutating func fail(_ reason: TelemetryError) {
        clear(); failure = failure ?? reason; phase = .failed
    }
    public mutating func connecting(now: Double) throws {
        try observe(now: now)
        guard phase == .disconnected else { return }
        clear(); phase = .connecting
    }
    public mutating func opened(now: Double) throws {
        try observe(now: now)
        guard phase == .connecting else { throw TelemetryError.closed }
        clear(); phase = .connected; openedAt = now
    }
    public mutating func disconnected(now: Double) throws {
        try observe(now: now); clear()
        if phase != .failed && phase != .closed && phase != .suspended { phase = .disconnected }
    }
    public mutating func suspend(now: Double) throws {
        try observe(now: now); clear()
        if phase != .failed && phase != .closed { phase = .suspended; producer = .degraded }
    }
    public mutating func resume(now: Double) throws {
        try observe(now: now)
        if phase == .suspended { clear(); phase = .disconnected; producer = .starting }
    }
    public mutating func close() { clear(); phase = .closed }
    public mutating func setProducerState(_ state: ProducerState, now: Double) throws {
        try observe(now: now)
        if producer != state {
            latest = nil
            if state != .ready { flight = nil; probe = nil }
            if state == .ready { readyAfter = now }
        }
        producer = state
    }
    @discardableResult public mutating func offer(_ sample: DepthSample, now: Double) throws -> Bool {
        try observe(now: now)
        guard phase == .connected, producer == .ready, sample.capturedAtMS > max(openedAt, readyAfter),
              sample.capturedAtMS > highestCapture, (0...500).contains(now-sample.capturedAtMS) else {
            if droppedDepth < .max { droppedDepth += 1 }; return false
        }
        if latest != nil && droppedDepth < .max { droppedDepth += 1 }
        highestCapture = sample.capturedAtMS; latest = sample
        return true
    }
    @discardableResult public mutating func receiveProbe(_ data: Data, receivedAtMS: Double) throws -> Bool {
        try observe(now: receivedAtMS)
        guard phase == .connected else { return false }
        let value = try Probe(data: data, session: session)
        guard !seenNonces.contains(value.nonce), receivedAtMS-lastProbeReceived >= 1000,
              probe == nil else { return false }
        guard seenNonces.count < 1024 else { fail(.probeCapacity); throw TelemetryError.probeCapacity }
        seenNonces.insert(value.nonce); lastProbeReceived = receivedAtMS
        probe = (value, receivedAtMS); return true
    }
    public mutating func sendTimedOut(now: Double) throws -> Bool {
        try observe(now: now)
        return flight.map { now >= $0.deadlineMS } ?? false
    }
    mutating func sequence(depth: Bool) throws -> UInt64 {
        let value = depth ? depthSequence : heartbeatSequence
        guard value <= Self.maximumSequence else { fail(.sequenceExhausted); throw TelemetryError.sequenceExhausted }
        if depth { depthSequence += 1 } else { heartbeatSequence += 1 }
        return value
    }
    func envelope(type: String, sequence: UInt64, captured: Double) -> [String: Any] {
        ["schema_version": 1, "type": type, "session_id": session.sessionID,
         "source_id": session.sourceID, "boot_id": session.bootID, "mode": session.mode.rawValue,
         "seq": sequence, "capture_monotonic_ms": captured, "capture_utc": NSNull()]
    }
    public mutating func next(now: Double) throws -> Transmission? {
        try observe(now: now)
        guard phase == .connected, flight == nil else { return nil }
        if let pending = probe, now-pending.received >= 500 { probe = nil }
        if let sample = latest, !(0...500).contains(now-sample.capturedAtMS) {
            latest = nil; if droppedDepth < .max { droppedDepth += 1 }
        }
        let packet: Transmission
        if let pending = probe {
            probe = nil
            packet = Transmission(id: UUID(), data: try pending.value.reply(t2: pending.received, t3: now),
                                  deadlineMS: pending.received+500, kind: "clock_reply")
        } else if now-lastHeartbeatSend >= 1000 {
            var object = envelope(type: "heartbeat", sequence: try sequence(depth: false), captured: now)
            object["state"] = producer.rawValue
            packet = Transmission(id: UUID(), data: try encode(object), deadlineMS: now+500, kind: "heartbeat")
            lastHeartbeatSend = now
        } else if let sample = latest, producer == .ready, now-lastDepthSend >= 100 {
            latest = nil
            var object = envelope(type: "depth_observation", sequence: try sequence(depth: true), captured: sample.capturedAtMS)
            object["tracking"] = sample.tracking.rawValue
            object["sectors"] = ["left": sample.left.wire, "center": sample.center.wire, "right": sample.right.wire]
            packet = Transmission(id: UUID(), data: try encode(object),
                                  deadlineMS: min(now+500, sample.capturedAtMS+500), kind: "depth_observation")
            lastDepthSend = now
        } else { return nil }
        // Do not start a send at its expiry boundary.
        guard now < packet.deadlineMS else { return nil }
        flight = packet; return packet
    }
    @discardableResult public mutating func completed(_ id: UUID, now: Double) throws -> Bool {
        try observe(now: now)
        guard let packet = flight, packet.id == id else { return false }
        guard now < packet.deadlineMS else { try disconnected(now: now); return false }
        flight = nil
        if packet.kind == "depth_observation" && sentDepth < .max { sentDepth += 1 }
        return true
    }
}
