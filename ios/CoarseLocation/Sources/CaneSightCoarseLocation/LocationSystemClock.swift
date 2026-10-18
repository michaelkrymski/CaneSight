import Foundation

/// GPS-local time only. ContinuousClock advances through device sleep; awake
/// uptime would diverge from UTC on resume and falsely latch a clock fault.
/// The monotonic origin belongs to this reader instance, not a source boot or
/// an ARFrame clock. Never use it as an implicit cross-device clock mapping.
public struct LocationSystemClock: Sendable {
    private let continuous: ContinuousClock
    private let origin: ContinuousClock.Instant

    public init() {
        let clock = ContinuousClock()
        continuous = clock
        origin = clock.now
    }

    public func read() -> LocationClock {
        Self.sample(utcSeconds: Date().timeIntervalSince1970,
                    elapsed: origin.duration(to: continuous.now))
    }

    /// Keep the exact same conversion available to deterministic virtual-sleep
    /// tests. Negative/nonfinite readings are not clamped into valid times.
    static func sample(utcSeconds: Double, elapsed: Duration) -> LocationClock {
        let parts = elapsed.components
        return LocationClock(utcSeconds: utcSeconds,
            monotonicMilliseconds: Double(parts.seconds) * 1000
                + Double(parts.attoseconds) / 1_000_000_000_000_000)
    }
}
