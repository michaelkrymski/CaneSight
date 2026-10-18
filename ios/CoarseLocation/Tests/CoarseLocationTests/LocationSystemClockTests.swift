import XCTest
@testable import CaneSightCoarseLocation

final class LocationSystemClockTests: XCTestCase {
    func testDurationConversionPreservesFractionAndSign() {
        let fractional = LocationSystemClock.sample(utcSeconds: 2000,
            elapsed: .seconds(2) + .microseconds(123_456))
        XCTAssertEqual(fractional.utcSeconds, 2000)
        XCTAssertEqual(fractional.monotonicMilliseconds, 2123.456, accuracy: 0.000001)
        XCTAssertEqual(LocationSystemClock.sample(utcSeconds: 2000,
            elapsed: .milliseconds(-1250)).monotonicMilliseconds, -1250)
    }

    func testSystemReaderProducesFiniteNondecreasingTime() {
        let clock = LocationSystemClock()
        let first = clock.read()
        let second = clock.read()
        XCTAssertTrue(first.utcSeconds.isFinite)
        XCTAssertTrue(first.monotonicMilliseconds.isFinite)
        XCTAssertGreaterThanOrEqual(first.monotonicMilliseconds, 0)
        XCTAssertGreaterThanOrEqual(second.monotonicMilliseconds, first.monotonicMilliseconds)
    }

    func testThirtySecondSleepClearsOldFixAndRecoversWithNewFix() async {
        await MainActor.run {
            var utc = 2000.0
            var continuousElapsed = Duration.zero
            let context = CoarseLocationContext(policy: try! LocationPolicy(), clock: {
                LocationSystemClock.sample(utcSeconds: utc, elapsed: continuousElapsed)
            }, purgeCachedAndQueuedContext: {})
            context.setConsent(true)
            context.setAuthorization(.authorized)
            context.setActive(true)
            let old = LocationFix(latitude: 10, longitude: 20,
                horizontalAccuracyMeters: 5, originalFixUTCSeconds: utc)
            XCTAssertTrue(context.receive(old))
            _ = context.nextContextSnapshot()
            context.setActive(false)
            // ContinuousClock's contract includes system sleep. Awake uptime
            // would remain unchanged here and cause a permanent clockFault.
            utc += 30
            continuousElapsed += .seconds(30)
            context.setActive(true)
            XCTAssertEqual(context.snapshot().unavailable, .noFix)
            XCTAssertNil(context.snapshot().latitude)
            XCTAssertFalse(context.receive(old))
            utc += 0.1
            continuousElapsed += .milliseconds(100)
            XCTAssertTrue(context.receive(LocationFix(latitude: 10, longitude: 20,
                horizontalAccuracyMeters: 5, originalFixUTCSeconds: utc)))
            let fresh = context.nextContextSnapshot()!
            XCTAssertNil(fresh.unavailable)
            XCTAssertEqual(fresh.originalFixUTCSeconds, utc)
            XCTAssertEqual(fresh.fixAgeMilliseconds, 0)
            XCTAssertNil(context.nextContextSnapshot()) // no replay/rate bypass
        }
    }

    func testSleepTimeCannotKeepUnrefreshedFixAlive() async {
        await MainActor.run {
            var utc = 2000.0
            var elapsed = Duration.zero
            let context = CoarseLocationContext(policy: try! LocationPolicy(), clock: {
                LocationSystemClock.sample(utcSeconds: utc, elapsed: elapsed)
            }, purgeCachedAndQueuedContext: {})
            context.setConsent(true); context.setAuthorization(.authorized); context.setActive(true)
            XCTAssertTrue(context.receive(LocationFix(latitude: 10, longitude: 20,
                horizontalAccuracyMeters: 5, originalFixUTCSeconds: utc)))
            // Even if the host misses an inactive callback, elapsed sleep must
            // age the original fix. No new receipt/heartbeat can refresh it.
            utc += 30; elapsed += .seconds(30)
            XCTAssertEqual(context.snapshot().unavailable, .staleFix)
            XCTAssertNil(context.snapshot().latitude)
        }
    }

    func testRealUTCStepDuringSleepStillLatchesClockFault() async {
        await MainActor.run {
            var utc = 2000.0
            var elapsed = Duration.zero
            let context = CoarseLocationContext(policy: try! LocationPolicy(), clock: {
                LocationSystemClock.sample(utcSeconds: utc, elapsed: elapsed)
            }, purgeCachedAndQueuedContext: {})
            context.setConsent(true); context.setAuthorization(.authorized); context.setActive(true)
            context.setActive(false)
            utc += 32; elapsed += .seconds(30) // actual two-second date/time step
            context.setActive(true)
            XCTAssertEqual(context.snapshot().unavailable, .clockFault)
            utc += 1; elapsed += .seconds(1)
            XCTAssertFalse(context.receive(LocationFix(latitude: 10, longitude: 20,
                horizontalAccuracyMeters: 5, originalFixUTCSeconds: utc)))
            XCTAssertNil(context.snapshot().latitude)
        }
    }
}
