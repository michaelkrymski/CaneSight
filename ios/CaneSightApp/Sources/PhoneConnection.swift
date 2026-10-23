import SwiftUI
import Combine
import Security
import QuartzCore
import CaneSightDepth
import CaneSightTelemetry
import CaneSightPhonePairing

private enum PhoneBondStore {
    static let service = "com.michaelkrymski.CaneSight.phone-bond.v1"
    static var query: [String: Any] { [kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service, kSecAttrAccount as String: "phone"] }
    static func load() throws -> Data? {
        var q = query; q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(q as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data else { throw BondError.invalidFile }
        _ = try PhoneBond(data: data)
        return data
    }
    static func save(_ data: Data) throws {
        _ = try PhoneBond(data: data)
        let attributes: [String: Any] = [kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            guard SecItemAdd(query.merging(attributes) { _, new in new } as CFDictionary, nil) == errSecSuccess else {
                throw BondError.invalidFile
            }
        } else if status != errSecSuccess { throw BondError.invalidFile }
    }
}

private final class PhoneDiagnosticClock: @unchecked Sendable {
    private let lock = NSLock()
    private let start = ContinuousClock.now
    private var epoch = DiagnosticEpoch(originMilliseconds: CACurrentMediaTime() * 1000)
    private var observations: UInt64 = 0
    private var maxDiscrepancyMS: Double = 0
    var diagnostics: (checks: UInt64, maxMismatchMS: Double) { lock.withLock { (observations, maxDiscrepancyMS) } }
    func now() throws -> Double {
        try lock.withLock {
            let p = start.duration(to: ContinuousClock.now).components
            let continuous = Double(p.seconds) * 1000 + Double(p.attoseconds) / 1e15
            let elapsed = try epoch.observe(rawMilliseconds: CACurrentMediaTime() * 1000, continuousElapsed: continuous)
            observations += 1; maxDiscrepancyMS = max(maxDiscrepancyMS, abs(elapsed - continuous))
            return elapsed
        }
    }
    func capture(_ raw: Double) throws -> (captured: Double, delta: Double) {
        let current = try now()
        let captured = try lock.withLock { try epoch.capture(rawMilliseconds: raw, now: current) }
        return (captured, current - captured)
    }
}

private struct SectorQualityTally {
    var frames = 0, measured = 0, coverageRejected = 0, samplesRejected = 0, unavailable = 0
    var minFraction = 1.0, maxFraction = 0.0, sumFraction = 0.0
    var minSamples = Int.max, maxSamples = 0, lastSamples = 0, totalSamples = 0
    mutating func observe(_ sector: CaneSightDepth.DepthSector) {
        frames += 1
        switch sector.evidence {
        case .measured: measured += 1
        case .insufficientCoverage: coverageRejected += 1
        case .insufficientSamples: samplesRejected += 1
        case .unavailable: unavailable += 1
        }
        let fraction = sector.validFraction ?? 0
        minFraction = min(minFraction, fraction); maxFraction = max(maxFraction, fraction); sumFraction += fraction
        minSamples = min(minSamples, sector.validSamples); maxSamples = max(maxSamples, sector.validSamples)
        lastSamples = sector.validSamples; totalSamples = sector.totalSamples
    }
    var snapshot: [String: Any] { ["frames": frames, "numeric_frames": measured,
        "insufficient_coverage": coverageRejected, "insufficient_samples": samplesRejected, "unavailable": unavailable,
        "min_high_confidence_valid_fraction": frames == 0 ? 0 : minFraction,
        "mean_high_confidence_valid_fraction": frames == 0 ? 0 : sumFraction / Double(frames),
        "max_high_confidence_valid_fraction": maxFraction,
        "min_valid_samples": frames == 0 ? 0 : minSamples, "max_valid_samples": maxSamples,
        "last_valid_samples": lastSamples, "last_total_samples": totalSamples] }
}

@MainActor final class PhoneConnection: ObservableObject {
    @Published private(set) var message = "Not paired · no phone bond imported" {
        didSet { if message != oldValue { recordProbe() } }
    }
    @Published private(set) var hasBond = false
    @Published private(set) var connected = false
    @Published private(set) var sentDepth: UInt64 = 0
    @Published private(set) var requested = false
    @Published var diagnosticConsent = false { didSet { if !diagnosticConsent { setDiagnosticDepth(false) } } }
    @Published private(set) var diagnosticDepth = false {
        didSet { UIApplication.shared.isIdleTimerDisabled = active && diagnosticDepth }
    }
    private weak var camera: CameraController?
    private var senderElapsedMS: Double = 0
    private var sourceCaptures: UInt64 = 0
    private var firstSourceCapture: Double?
    private var lastSourceCapture: Double?
    private var maxCaptureDeltaMS: Double = 0
    private var localClockFailed = false
    private var sectorQuality = [String: SectorQualityTally]()
    private var allNumericCaptures: UInt64 = 0
    private var clockChecks: UInt64 = 0
    private var clockMaxMismatchMS: Double = 0
    private var bond: PhoneBond?
    private var active = false
    private var task: Task<Void, Never>?
    private var fence: DiagnosticSendFence?
    private var latest: DepthSectorSummary?
    private var sourceVersion: UInt64 = 0
    private var subscription: AnyCancellable?
    private var generation = UUID()

    init(camera: CameraController) {
        self.camera = camera
        do {
            if let data = try PhoneBondStore.load() {
                let saved = try PhoneBond(data: data)
                guard saved.origin.absoluteString == "https://64.177.50.116" else { throw BondError.invalidFile }
                bond = saved; hasBond = true
                message = "Phone bond saved · disconnected"
            }
        } catch { message = "Saved phone bond unavailable; unlock the phone and retry" }
        subscription = camera.$summary.sink { [weak self] value in
            guard let self else { return }
            self.latest = value
            if value == nil || value?.reason != .processedFrame { self.sourceVersion &+= 1; self.fence?.invalidate() }
        }
    }
    private var lastProbeWrite: Double = -.infinity
    private func recordProbe() {
        guard ProcessInfo.processInfo.arguments.contains("--phone-connection-probe"),
              let folder = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first else { return }
        // Bounded local diagnostics; no identities, credentials, images or location.
        // Spatial measurements are independently sampled and never readiness inputs.
        let now=CACurrentMediaTime()
        guard now-lastProbeWrite >= 1 else { return }
        lastProbeWrite=now
        let value: [String: Any] = ["status": message, "wss_connected": connected,
            "depth_sends": sentDepth, "diagnostic_depth_enabled": diagnosticDepth,
            "connection_requested": requested, "foreground_active": active,
            "camera_requested": camera?.requested ?? false, "camera_status": camera?.status ?? "Unavailable",
            "sender_elapsed_ms": senderElapsedMS, "source_capture_count": sourceCaptures,
            "source_capture_span_ms": (lastSourceCapture ?? 0) - (firstSourceCapture ?? 0),
            "max_local_capture_delta_ms": maxCaptureDeltaMS, "local_clock_guard_failed": localClockFailed,
            "clock_replies_sent": fence?.completedClockReplies ?? 0,
            "local_clock_observations": clockChecks, "max_media_continuous_discrepancy_ms": clockMaxMismatchMS,
            "sector_quality": sectorQuality.mapValues { $0.snapshot }, "all_three_numeric_captures": allNumericCaptures,
            "floor_filter": camera?.floorDiagnostics ?? [:],
            "current_input_quality": camera?.inputQuality ?? [],
            "input_quality_age_ms": camera?.qualityAgeMS.map { $0 as Any } ?? NSNull(),
            "target_inspection": camera?.inspectionSnapshot ?? [:],
            "wire_depth_quality": fence?.wireDepthDiagnostics ?? [:],
            "capture_age_eligibility": "unknown", "drift_bounds_verified": false]
        if let data = try? JSONSerialization.data(withJSONObject: value) {
            try? data.write(to: folder.appendingPathComponent("phone-connection-probe.json"),
                options: [.atomic, .completeFileProtection])
        }
    }
    func importFile(_ url: URL) {
        disconnect()
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        do {
            let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 2049
            guard size <= 2048 else { throw BondError.invalidFile }
            let data = try Data(contentsOf: url)
            let imported = try PhoneBond(data: data)
            guard imported.origin.absoluteString == "https://64.177.50.116" else { throw BondError.invalidFile }
            try PhoneBondStore.save(data)
            bond = imported; hasBond = true; message = "Phone bond saved securely · tap Connect"
        } catch { message = "Import failed: select the existing phone-role bond JSON for this backend" }
    }
    func connect() {
        guard active, !requested else { return }
        // Existing private file can also be delivered over USB. Consume it only
        // after successful validation and Keychain storage. Never create a grant.
        if bond == nil, let folder = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            let file = folder.appendingPathComponent("phone-bond.json")
            if FileManager.default.fileExists(atPath: file.path) {
                importFile(file)
                if hasBond { try? FileManager.default.removeItem(at: file) }
            }
        }
        guard bond != nil else { message = "Existing private phone-bond.json is missing; import it first"; return }
        requested = true; begin()
    }
    func disconnect() {
        requested = false; diagnosticDepth = false; diagnosticConsent = false
        stop(); message = hasBond ? "Phone bond saved · disconnected" : "Not paired · no phone bond imported"
    }
    func setDiagnosticDepth(_ value: Bool) {
        diagnosticDepth = value && diagnosticConsent && requested
        sourceVersion &+= 1
        if !diagnosticDepth { fence?.invalidate() }
    }
    func setActive(_ value: Bool) {
        guard value != active else { return }
        active = value
        if !value {
            diagnosticDepth = false; diagnosticConsent = false; stop()
            if requested { message = "Paused while inactive · depth stopped" }
        } else if requested { begin() }
    }
    private func stop() {
        generation = UUID(); fence?.invalidate(end: true); fence = nil
        task?.cancel(); task = nil; latest = nil; sourceVersion &+= 1
        connected = false; sentDepth = 0
        senderElapsedMS = 0; sourceCaptures = 0; firstSourceCapture = nil; lastSourceCapture = nil
        maxCaptureDeltaMS = 0; localClockFailed = false
        sectorQuality = [:]; allNumericCaptures = 0; clockChecks = 0; clockMaxMismatchMS = 0
    }
    private func begin() {
        stop()
        guard let bond, requested, active else { return }
        let epoch = generation, fence = DiagnosticSendFence()
        self.fence = fence
        // New transport epoch on each foreground/connect. Sequence counters and
        // diagnostic clock are never reset within an existing backend boot binding.
        let boot = "boot-" + UUID().uuidString.lowercased()
        task = Task { [weak self] in
            guard let self else { return }
            await self.run(bond: bond, boot: boot, epoch: epoch, fence: fence)
        }
    }
    private func run(bond: PhoneBond, boot: String, epoch: UUID, fence: DiagnosticSendFence) async {
        let http = BondHTTPClient(), clock = PhoneDiagnosticClock()
        var client: TelemetryClient?
        var sessionID: String?
        var nextPoll = ContinuousClock.now
        var lastCapture: Double = -1
        var producer: ProducerState = .starting
        do {
            while !Task.isCancelled, epoch == generation, active, requested {
                senderElapsedMS = try clock.now()
                if ContinuousClock.now >= nextPoll {
                    message = client == nil ? "Pairing with backend…" : message
                    let grant: PhoneSession?
                    do { grant = try await http.poll(bond, bootID: boot) }
                    catch let network as URLError {
                        try Task.checkCancellation()
                        guard epoch == generation else { break }
                        fence.invalidate()
                        if let client { await client.suspend(); producer = .starting }
                        connected = false
                        message = "Backend unavailable (network code \(network.code.rawValue)) · retrying"
                        try await Task.sleep(for: .seconds(2))
                        continue
                    }
                    try Task.checkCancellation()
                    guard epoch == generation else { break }
                    nextPoll = .now.advanced(by: .seconds(grant == nil ? 2 : 10))
                    guard let grant else {
                        if client != nil { throw BondError.invalidResponse }
                        message = "Phone authenticated · waiting for Pi"
                        try await Task.sleep(for: .milliseconds(100)); continue
                    }
                    // A session rotation must start fresh at the UI level. Never
                    // reset sequences on a reused session or replay an old mailbox.
                    if let sessionID, sessionID != grant.sessionID { throw BondError.invalidResponse }
                    if client == nil {
                        sessionID = grant.sessionID
                        let created = TelemetryClient(session: grant, clock: { try clock.now() }, socketFactory: {
                            try fence.attach(await NativeWebSocket.connect($0))
                        })
                        client = created; await created.start()
                    } else if let client, await client.status().phase == .suspended {
                        await client.resume(); producer = .starting
                    }
                }
                if let client {
                    let status = await client.status()
                    try Task.checkCancellation()
                    guard epoch == generation else { break }
                    if status.phase == .failed { throw status.failure ?? TelemetryError.connection }
                    connected = status.phase == .connected; sentDepth = status.sentDepth
                    let version = sourceVersion
                    if diagnosticDepth, diagnosticConsent, connected,
                       let summary = latest, summary.reason == .processedFrame,
                       let raw = summary.captureTimestampSeconds.map({ $0 * 1000 }), raw > lastCapture {
                        let observation = try clock.capture(raw)
                        let capture = observation.captured
                        if producer != .ready {
                            await client.setProducerState(.ready); producer = .ready
                        }
                        guard epoch == generation, version == sourceVersion, diagnosticDepth else { continue }
                        func sector(_ position: DepthImageSector) throws -> CaneSightTelemetry.DepthSector {
                            guard let value = summary.sectors.first(where: { $0.position == position }) else {
                                throw TelemetryError.invalidSample
                            }
                            return try .init(distanceMetres: value.evidence == .measured ? value.distanceMetres : nil,
                                validFraction: value.validFraction ?? 0)
                        }
                        let sample = try DepthSample(capturedAtMS: capture, tracking: .normal,
                            left: sector(.imageLeft), center: sector(.imageCenter), right: sector(.imageRight))
                        fence.permitDepth(); client.submit(sample); lastCapture = raw
                        sourceCaptures += 1
                        firstSourceCapture = firstSourceCapture ?? capture; lastSourceCapture = capture
                        maxCaptureDeltaMS = max(maxCaptureDeltaMS, observation.delta)
                        for sector in summary.sectors { sectorQuality[sector.position.rawValue, default: SectorQualityTally()].observe(sector) }
                        if summary.sectors.count == 3 && summary.sectors.allSatisfy({ $0.evidence == .measured && $0.distanceMetres != nil }) {
                            allNumericCaptures += 1
                        }
                    } else if !diagnosticDepth || latest == nil || latest?.reason != .processedFrame {
                        if producer != .degraded {
                            await client.setProducerState(.degraded); producer = .degraded
                        }
                    }
                    senderElapsedMS = try clock.now()
                    let localClock = clock.diagnostics; clockChecks = localClock.checks; clockMaxMismatchMS = localClock.maxMismatchMS
                    message = connected ? "Paired · WSS connected · depth sends: \(sentDepth)" : "Paired · reconnecting WSS…"
                }
                try await Task.sleep(for: .milliseconds(100))
            }
        } catch {
            if epoch == generation, !Task.isCancelled {
                if let error = error as? BondError, case .rejected(let code) = error {
                    message = "Pairing rejected (HTTP \(code)) · saved bond retained"
                } else if (error as? BondError) == .clock || (error as? TelemetryError) == .clock {
                    localClockFailed = true
                    message = "Diagnostic clock check failed · depth stopped; reconnect required"
                } else if (error as? BondError) == .invalidResponse {
                    message = "Pairing response rejected or session rotated · reconnect required"
                } else if let transport = error as? TelemetryError {
                    message = "WSS stopped (\(transport)) · reconnect required; saved bond retained"
                } else if let network = error as? URLError {
                    message = "Backend connection failed (network code \(network.code.rawValue)) · reconnect required"
                } else { message = "Connection stopped · reconnect required; saved bond retained" }
                requested = false; diagnosticDepth = false; connected = false
                recordProbe()
            }
        }
        fence.invalidate(end: true)
        if let client { await client.close() }
    }
}
