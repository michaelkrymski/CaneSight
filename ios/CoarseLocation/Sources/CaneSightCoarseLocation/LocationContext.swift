import Foundation

public enum LocationAuthorization: Sendable {
    case undetermined, denied, restricted, authorized
}

public enum LocationUnavailability: String, Sendable {
    case noConsent, unauthorized, inactive, noFix, invalidFix, staleFix, clockFault
}

/// A paired reading on receipt. UTC dates a Core Location fix; monotonic time
/// ages it afterward so repeated reads cannot refresh an old fix.
public struct LocationClock: Sendable {
    public let utcSeconds: Double
    public let monotonicMilliseconds: Double
    public init(utcSeconds: Double, monotonicMilliseconds: Double) {
        self.utcSeconds = utcSeconds
        self.monotonicMilliseconds = monotonicMilliseconds
    }
}

/// Transient input only. Never retain, serialize or log precise input fixes.
public struct LocationFix: Sendable {
    public let latitude: Double
    public let longitude: Double
    public let horizontalAccuracyMeters: Double
    public let originalFixUTCSeconds: Double
    public init(latitude: Double, longitude: Double, horizontalAccuracyMeters: Double,
                originalFixUTCSeconds: Double) {
        self.latitude = latitude
        self.longitude = longitude
        self.horizontalAccuracyMeters = horizontalAccuracyMeters
        self.originalFixUTCSeconds = originalFixUTCSeconds
    }
}

/// Local P1 context, deliberately NOT a v1 wire message or Codable payload.
/// Unavailable snapshots contain no coordinates, fix time, age or accuracy.
public struct LocationSnapshot: Sendable {
    public let consented: Bool
    public let unavailable: LocationUnavailability?
    public let latitude: Double?
    public let longitude: Double?
    public let originalFixUTCSeconds: Double?
    public let fixAgeMilliseconds: Double?
    public let horizontalAccuracyMeters: Double?
    public let coarseAccuracyMeters: Double?

    fileprivate init(consented: Bool, unavailable: LocationUnavailability? = nil,
                     latitude: Double? = nil, longitude: Double? = nil,
                     originalFixUTCSeconds: Double? = nil, fixAgeMilliseconds: Double? = nil,
                     horizontalAccuracyMeters: Double? = nil, coarseAccuracyMeters: Double? = nil) {
        self.consented = consented
        self.unavailable = unavailable
        self.latitude = latitude
        self.longitude = longitude
        self.originalFixUTCSeconds = originalFixUTCSeconds
        self.fixAgeMilliseconds = fixAgeMilliseconds
        self.horizontalAccuracyMeters = horizontalAccuracyMeters
        self.coarseAccuracyMeters = coarseAccuracyMeters
    }
}

public struct LocationPolicy: Sendable {
    public let maximumFixAgeMilliseconds: Double
    public let maximumHorizontalAccuracyMeters: Double
    public init(maximumFixAgeMilliseconds: Double = 10_000,
                maximumHorizontalAccuracyMeters: Double = 20) throws {
        guard maximumFixAgeMilliseconds.isFinite, maximumFixAgeMilliseconds > 0,
              maximumHorizontalAccuracyMeters.isFinite, maximumHorizontalAccuracyMeters > 0 else {
            throw ConfigurationError.invalidThreshold
        }
        self.maximumFixAgeMilliseconds = maximumFixAgeMilliseconds
        self.maximumHorizontalAccuracyMeters = maximumHorizontalAccuracyMeters
    }
    public enum ConfigurationError: Error { case invalidThreshold }
}

/// Foreground-only context, separate from depth/signal/motor policy. The supplied
/// purge callback must synchronously remove any consumer's cached/queued context.
@MainActor public final class CoarseLocationContext {
    private struct Cached {
        let latitude: Double
        let longitude: Double
        let accuracy: Double
        let fixUTC: Double
        let initialAge: Double
        let receivedMonotonic: Double
    }
    private let policy: LocationPolicy
    private let now: () -> LocationClock
    private let purge: () -> Void
    private var consent = false
    private var authorization = LocationAuthorization.undetermined
    private var active = false
    private var cached: Cached?
    private var lastClock: LocationClock?
    private var clockFailed = false
    private var captureFloorUTC: Double = .infinity
    private var latestFixUTC: Double?
    private var lastEmission: Double?
    private var reason = LocationUnavailability.noFix

    public init(policy: LocationPolicy, clock: @escaping () -> LocationClock,
                purgeCachedAndQueuedContext: @escaping () -> Void) {
        self.policy = policy
        self.now = clock
        self.purge = purgeCachedAndQueuedContext
    }

    private var permitted: Bool { consent && authorization == .authorized && active && !clockFailed }

    private func clear(_ why: LocationUnavailability) {
        cached = nil
        reason = why
        purge()
    }

    private func readClock() -> LocationClock? {
        // Notify once. A UI purge hook may synchronously read the unavailable
        // snapshot; it must not recursively trigger another purge on clock fault.
        guard !clockFailed else { return nil }
        let value = now()
        var valid = value.utcSeconds.isFinite && value.utcSeconds >= 0
            && value.monotonicMilliseconds.isFinite && value.monotonicMilliseconds >= 0
        if let old = lastClock {
            let elapsed = value.monotonicMilliseconds - old.monotonicMilliseconds
            // Fail closed on wall-clock steps too: a new cached CLLocation must
            // not be made younger by changing the phone's date/time.
            valid = valid && elapsed >= 0
                && abs((value.utcSeconds - old.utcSeconds) * 1000 - elapsed) <= 1000
        }
        guard valid, !clockFailed else {
            clockFailed = true
            clear(.clockFault)
            return nil
        }
        lastClock = value
        return value
    }

    private func resetForPermissionChange() {
        clear(.noFix)
        captureFloorUTC = readClock()?.utcSeconds ?? .infinity
        // Do not reset the emission limiter, including on opt-out/opt-in.
    }

    public func setConsent(_ value: Bool) {
        guard consent != value else { return }
        consent = value
        resetForPermissionChange()
    }

    public func setAuthorization(_ value: LocationAuthorization) {
        guard authorization != value else { return }
        authorization = value
        resetForPermissionChange()
    }

    public func setActive(_ value: Bool) {
        guard active != value else { return }
        active = value
        resetForPermissionChange()
    }

    public func locationFailed() { clear(.noFix) }

    @discardableResult public func receive(_ fix: LocationFix) -> Bool {
        guard let time = readClock(), permitted else { return false }
        let age = (time.utcSeconds - fix.originalFixUTCSeconds) * 1000
        guard fix.latitude.isFinite, (-90...90).contains(fix.latitude),
              fix.longitude.isFinite, (-180...180).contains(fix.longitude),
              fix.horizontalAccuracyMeters.isFinite, fix.horizontalAccuracyMeters >= 0,
              fix.horizontalAccuracyMeters <= policy.maximumHorizontalAccuracyMeters,
              fix.originalFixUTCSeconds.isFinite, fix.originalFixUTCSeconds >= captureFloorUTC,
              latestFixUTC.map({ fix.originalFixUTCSeconds > $0 }) ?? true,
              age.isFinite, age >= 0 else {
            clear(.invalidFix)
            return false
        }
        guard age <= policy.maximumFixAgeMilliseconds else {
            clear(.staleFix)
            return false
        }
        latestFixUTC = fix.originalFixUTCSeconds
        // 0.001 degree cells; raw coordinates are never stored. 80 m bounds
        // rounding displacement (half-cell diagonal on the equator <79 m).
        cached = Cached(latitude: (fix.latitude * 1000).rounded() / 1000,
                        longitude: (fix.longitude * 1000).rounded() / 1000,
                        accuracy: fix.horizontalAccuracyMeters, fixUTC: fix.originalFixUTCSeconds,
                        initialAge: age, receivedMonotonic: time.monotonicMilliseconds)
        return true
    }

    public func snapshot() -> LocationSnapshot {
        guard let time = readClock() else { return unknown(.clockFault) }
        guard consent else { return unknown(.noConsent) }
        guard authorization == .authorized else { return unknown(.unauthorized) }
        guard active else { return unknown(.inactive) }
        guard let fix = cached else { return unknown(reason) }
        let age = fix.initialAge + time.monotonicMilliseconds - fix.receivedMonotonic
        guard age <= policy.maximumFixAgeMilliseconds else {
            clear(.staleFix)
            return unknown(.staleFix)
        }
        return LocationSnapshot(consented: consent, latitude: fix.latitude, longitude: fix.longitude,
            originalFixUTCSeconds: fix.fixUTC, fixAgeMilliseconds: age,
            horizontalAccuracyMeters: fix.accuracy, coarseAccuracyMeters: fix.accuracy + 80)
    }

    private func unknown(_ why: LocationUnavailability) -> LocationSnapshot {
        LocationSnapshot(consented: consent, unavailable: why)
    }

    /// In-process handoff only, at most 1 Hz; never an outbound network queue.
    /// Poll on the host's timer. The separate reviewed GPS transport is pending.
    public func nextContextSnapshot() -> LocationSnapshot? {
        guard let time = readClock() else { return nil }
        guard lastEmission.map({ time.monotonicMilliseconds - $0 >= 1000 }) ?? true else { return nil }
        lastEmission = time.monotonicMilliseconds
        return snapshot()
    }
}
