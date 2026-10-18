import Foundation
import CaneSightTelemetry
let session = try PhoneSession(origin: URL(string: "https://fixture.invalid")!, sessionID: "demo-session",
    sourceID: "phone-1", bootID: "phone-boot-1", receiverID: "pi-1", receiverBootID: "pi-boot-1",
    mode: .replay, phoneToken: String(repeating: "x", count: 40))
var core = TelemetryCore(session: session)
try core.connecting(now: 1000); try core.opened(now: 1000)
try core.setProducerState(.ready, now: 1000)
if let packet = try core.next(now: 1001) { print(String(decoding: packet.data, as: UTF8.self)); try core.completed(packet.id, now: 1001) }
let known = try DepthSector(distanceMetres: 1.2, validFraction: 0.8)
let unknown = try DepthSector(distanceMetres: nil, validFraction: 0.02)
try core.offer(DepthSample(capturedAtMS: 1002, tracking: .normal, left: known, center: known, right: unknown), now: 1002)
if let packet = try core.next(now: 1002) { print(String(decoding: packet.data, as: UTF8.self)); try core.completed(packet.id, now: 1002) }
try core.offer(DepthSample(capturedAtMS: 1102, tracking: .limited, left: unknown, center: unknown, right: unknown), now: 1102)
if let packet = try core.next(now: 1102) { print(String(decoding: packet.data, as: UTF8.self)); try core.completed(packet.id, now: 1102) }
let probe = #"{"schema_version":1,"type":"clock_probe","session_id":"demo-session","mode":"replay","nonce":"fixture-nonce","receiver_id":"pi-1","receiver_boot_id":"pi-boot-1","source_id":"phone-1","source_boot_id":"phone-boot-1","t1_ms":1000}"#
try core.receiveProbe(Data(probe.utf8), receivedAtMS: 1200)
if let packet = try core.next(now: 1201) { print(String(decoding: packet.data, as: UTF8.self)); try core.completed(packet.id, now: 1201) }
