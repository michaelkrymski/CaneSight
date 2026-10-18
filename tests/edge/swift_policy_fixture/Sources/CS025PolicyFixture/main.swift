import Foundation
import CaneSightTelemetry

// Every value is synthetic. A +200ms source offset and zero drift are fixture
// assumptions, not device calibration or a claim about ARFrame's clock.
let probe: [String: Any] = ["schema_version": 1, "type": "clock_probe",
    "session_id": "demo-session", "mode": "replay", "nonce": "swift-policy-probe",
    "receiver_id": "pi-1", "receiver_boot_id": "pi-boot-1",
    "source_id": "phone-1", "source_boot_id": "phone-boot-1", "t1_ms": 1000]
let probeData = try JSONSerialization.data(withJSONObject: probe, options: [.sortedKeys])
var scenarios: [String: [[String: Any]]] = [:]
for side in ["left", "center", "right"] {
    let session = try PhoneSession(origin: URL(string: "https://fixture.invalid")!,
        sessionID: "demo-session", sourceID: "phone-1", bootID: "phone-boot-1",
        receiverID: "pi-1", receiverBootID: "pi-boot-1", mode: .replay,
        phoneToken: String(repeating: "x", count: 40))
    var core = TelemetryCore(session: session)
    try core.connecting(now: 1200); try core.opened(now: 1200)
    try core.setProducerState(.ready, now: 1200)
    var packets: [[String: Any]] = []
    func drain(_ time: Double) throws {
        // Completes each synthetic send; there is no socket or native actor run.
        if let transmission = try core.next(now: time) {
            packets.append(["phone_time_ms": time, "wire_base64": transmission.data.base64EncodedString()])
            try core.completed(transmission.id, now: time)
        }
    }
    guard try core.receiveProbe(probeData, receivedAtMS: 1200) else { fatalError("Synthetic probe refused") }
    try drain(1200) // Actual Swift clock reply.
    try drain(1201) // Actual Swift ready heartbeat.
    let near = try DepthSector(distanceMetres: 0.8, validFraction: 1)
    let far = try DepthSector(distanceMetres: 2, validFraction: 1)
    for time in [1700.0, 1800.0] {
        let sample = try DepthSample(capturedAtMS: time, tracking: .normal,
            left: side == "left" ? near : far,
            center: side == "center" ? near : far,
            right: side == "right" ? near : far)
        guard try core.offer(sample, now: time) else { fatalError("Synthetic sample refused") }
        try drain(time)
    }
    let unknown = try DepthSector(distanceMetres: nil, validFraction: 0)
    guard try core.offer(DepthSample(capturedAtMS: 1900, tracking: .limited,
        left: unknown, center: unknown, right: unknown), now: 1900) else { fatalError("Synthetic unknown refused") }
    try drain(1900)
    try drain(2201) // Health after unknown must not restore prior depth.
    scenarios[side] = packets
}
let result: [String: Any] = ["origin": "synthetic", "probe_base64": probeData.base64EncodedString(),
    "source_offset_ms": 200, "relative_drift_ppm": 0, "scenarios": scenarios]
let output = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
print(String(decoding: output, as: UTF8.self))
