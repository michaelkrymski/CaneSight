import CaneSightDepth
import CaneSightTelemetry

public enum DepthTelemetryError: Error, Equatable, Sendable {
    case modeMismatch, missingCaptureTime, invalidSectors
}

/// Converts CS-014 source-image columns to v1 camera sectors. This conversion
/// establishes neither physical side mapping nor capture-clock equivalence.
public struct DepthTelemetryAdapter: Sendable {
    public let sessionMode: StreamMode
    public init(sessionMode: StreamMode) { self.sessionMode = sessionMode }

    public func sample(from summary: DepthSectorSummary) throws -> DepthSample {
        guard summary.mode.rawValue == sessionMode.rawValue else { throw DepthTelemetryError.modeMismatch }
        guard let seconds = summary.captureTimestampSeconds,
              DepthLimits.validTimestamp(seconds) else { throw DepthTelemetryError.missingCaptureTime }
        guard summary.sectors.count == 3,
              Set(summary.sectors.map(\.position)).count == 3 else { throw DepthTelemetryError.invalidSectors }
        // CS-014 discards tracking subtype when returning an unavailable summary.
        // Never reconstruct "normal" from previous frames or nonnil coverage.
        let tracking: Tracking = summary.reason == .processedFrame ? .normal : .unavailable
        func sector(_ position: DepthImageSector) throws -> CaneSightTelemetry.DepthSector {
            guard let value = summary.sectors.first(where: { $0.position == position }) else {
                throw DepthTelemetryError.invalidSectors
            }
            let measured = tracking == .normal && value.evidence == .measured
            return try CaneSightTelemetry.DepthSector(
                distanceMetres: measured ? value.distanceMetres : nil,
                validFraction: value.validFraction ?? 0)
        }
        return try DepthSample(capturedAtMS: seconds * 1000, tracking: tracking,
            left: sector(.imageLeft), center: sector(.imageCenter), right: sector(.imageRight))
    }

    /// No task or queue per frame: the client's existing latest-only mailbox
    /// enforces connection, readiness, capture age and rate limits.
    public func submit(_ summary: DepthSectorSummary, to client: TelemetryClient) throws {
        client.submit(try sample(from: summary))
    }
}
