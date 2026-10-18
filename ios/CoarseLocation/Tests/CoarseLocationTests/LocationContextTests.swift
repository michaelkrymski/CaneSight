import XCTest
@testable import CaneSightCoarseLocation

@MainActor private final class Rig {
    var utc: Double = 2000
    var mono: Double = 1000
    var purges = 0
    lazy var context = CoarseLocationContext(policy: try! LocationPolicy(), clock: { [unowned self] in
        LocationClock(utcSeconds: self.utc, monotonicMilliseconds: self.mono)
    }, purgeCachedAndQueuedContext: { [unowned self] in self.purges += 1 })

    func start() {
        context.setActive(true)
        context.setConsent(true)
        context.setAuthorization(.authorized)
    }
    func advance(_ ms: Double) { mono += ms; utc += ms / 1000 }
    func fix(lat: Double = 10.123456, lon: Double = 20.654321,
             accuracy: Double = 5, ageMS: Double = 0) -> LocationFix {
        LocationFix(latitude: lat, longitude: lon, horizontalAccuracyMeters: accuracy,
                    originalFixUTCSeconds: utc - ageMS / 1000)
    }
}

final class LocationContextTests: XCTestCase {
    func testConfigurationRejectsInvalidThresholds() {
        for value in [0.0, -1, .nan, .infinity] {
            XCTAssertThrowsError(try LocationPolicy(maximumFixAgeMilliseconds: value))
            XCTAssertThrowsError(try LocationPolicy(maximumHorizontalAccuracyMeters: value))
        }
    }

    func testRequiresBothConsentAndAuthorizationAndActiveScene() async {
        await MainActor.run {
            let r = Rig()
            XCTAssertEqual(r.context.snapshot().unavailable, .noConsent)
            XCTAssertFalse(r.context.receive(r.fix()))
            r.context.setConsent(true)
            XCTAssertEqual(r.context.snapshot().unavailable, .unauthorized)
            r.context.setAuthorization(.authorized)
            XCTAssertEqual(r.context.snapshot().unavailable, .inactive)
            r.context.setActive(true)
            XCTAssertEqual(r.context.snapshot().unavailable, .noFix)
            XCTAssertTrue(r.context.receive(r.fix()))
            XCTAssertNil(r.context.snapshot().unavailable)
        }
    }

    func testCoordinatesRoundedAndUncertaintyIncludesQuantization() async {
        await MainActor.run {
            let r = Rig(); r.start()
            XCTAssertTrue(r.context.receive(r.fix()))
            let result = r.context.snapshot()
            XCTAssertEqual(result.latitude, 10.123)
            XCTAssertEqual(result.longitude, 20.654)
            XCTAssertEqual(result.horizontalAccuracyMeters, 5)
            XCTAssertEqual(result.coarseAccuracyMeters, 85)
            XCTAssertEqual(result.originalFixUTCSeconds, 2000)
            XCTAssertEqual(result.fixAgeMilliseconds, 0)
            XCTAssertTrue(result.consented)
        }
    }

    func testFixAgeIncludesPreReceiptDelayAndMonotonicElapsedTime() async {
        await MainActor.run {
            let r = Rig(); r.start(); r.advance(2000)
            XCTAssertTrue(r.context.receive(r.fix(ageMS: 1000)))
            r.advance(500)
            XCTAssertEqual(r.context.snapshot().fixAgeMilliseconds!, 1500, accuracy: 0.001)
            r.advance(8500)
            XCTAssertNil(r.context.snapshot().unavailable) // age exactly 10s
            r.advance(0.1)
            let expired = r.context.snapshot()
            XCTAssertEqual(expired.unavailable, .staleFix)
            XCTAssertNil(expired.latitude)
            XCTAssertNil(expired.longitude)
            XCTAssertNil(expired.originalFixUTCSeconds)
            XCTAssertNil(expired.horizontalAccuracyMeters)
        }
    }

    func testRevocationPurgesImmediatelyAndDelayedFixCannotRestore() async {
        await MainActor.run {
            let r = Rig(); r.start()
            let old = r.fix()
            XCTAssertTrue(r.context.receive(old))
            let count = r.purges
            r.context.setConsent(false)
            XCTAssertEqual(r.purges, count + 1)
            XCTAssertFalse(r.context.receive(old))
            XCTAssertFalse(r.context.snapshot().consented)
            XCTAssertNil(r.context.snapshot().latitude)
            r.advance(100)
            r.context.setConsent(true)
            XCTAssertFalse(r.context.receive(old))
            r.advance(1)
            XCTAssertTrue(r.context.receive(r.fix()))
        }
    }

    func testDeniedRestrictedOrUndeterminedPurgesAndBlocksFixes() async {
        await MainActor.run {
            for permission in [LocationAuthorization.denied, .restricted, .undetermined] {
                let r = Rig(); r.start()
                XCTAssertTrue(r.context.receive(r.fix()))
                r.context.setAuthorization(permission)
                XCTAssertEqual(r.context.snapshot().unavailable, .unauthorized)
                XCTAssertNil(r.context.snapshot().latitude)
                XCTAssertFalse(r.context.receive(r.fix()))
            }
        }
    }

    func testBackgroundAndResumeRequireNewFix() async {
        await MainActor.run {
            let r = Rig(); r.start()
            let old = r.fix()
            XCTAssertTrue(r.context.receive(old))
            r.context.setActive(false)
            XCTAssertEqual(r.context.snapshot().unavailable, .inactive)
            r.advance(100)
            r.context.setActive(true)
            XCTAssertEqual(r.context.snapshot().unavailable, .noFix)
            XCTAssertFalse(r.context.receive(old))
            r.advance(1)
            XCTAssertTrue(r.context.receive(r.fix()))
        }
    }

    func testInvalidPoorStaleFutureAndOutOfRangeFixesStayUnavailable() async {
        await MainActor.run {
            let r = Rig(); r.start(); r.advance(20_000)
            let bad = [r.fix(lat: .nan), r.fix(lon: .infinity), r.fix(lat: 90.1),
                r.fix(lon: -180.1), r.fix(accuracy: -1), r.fix(accuracy: .nan),
                r.fix(accuracy: .infinity), r.fix(accuracy: 20.1),
                r.fix(ageMS: -1), r.fix(ageMS: 10_001)]
            for fix in bad {
                XCTAssertFalse(r.context.receive(fix))
                XCTAssertNotNil(r.context.snapshot().unavailable)
                XCTAssertNil(r.context.snapshot().latitude)
            }
        }
    }

    func testPolesAntimeridianAndThresholdAccuracyAreValid() async {
        await MainActor.run {
            for pair in [(90.0, 180.0), (-90.0, -180.0), (0.0, 0.0)] {
                let r = Rig(); r.start()
                XCTAssertTrue(r.context.receive(r.fix(lat: pair.0, lon: pair.1, accuracy: 20)))
                XCTAssertEqual(r.context.snapshot().latitude, pair.0)
                XCTAssertEqual(r.context.snapshot().longitude, pair.1)
            }
        }
    }

    func testDuplicateOrOutOfOrderFixNeverMakesCachedFixYounger() async {
        await MainActor.run {
            let r = Rig(); r.start(); r.advance(100)
            let old = r.fix()
            XCTAssertTrue(r.context.receive(old))
            r.advance(50)
            XCTAssertFalse(r.context.receive(old))
            XCTAssertNil(r.context.snapshot().latitude)
            XCTAssertFalse(r.context.receive(r.fix(ageMS: 100)))
            XCTAssertTrue(r.context.receive(r.fix()))
        }
    }

    func testHandoffRateAtMostOneHzAndDoesNotRenewFixTime() async {
        await MainActor.run {
            let r = Rig(); r.start()
            XCTAssertTrue(r.context.receive(r.fix()))
            XCTAssertEqual(r.context.nextContextSnapshot()?.fixAgeMilliseconds, 0)
            XCTAssertNil(r.context.nextContextSnapshot())
            r.advance(999)
            XCTAssertNil(r.context.nextContextSnapshot())
            r.advance(1)
            let second = r.context.nextContextSnapshot()!
            XCTAssertEqual(second.originalFixUTCSeconds, 2000)
            XCTAssertEqual(second.fixAgeMilliseconds, 1000)
            r.context.setConsent(false)
            r.context.setConsent(true)
            XCTAssertNil(r.context.nextContextSnapshot()) // consent toggle cannot bypass rate cap
        }
    }

    func testClockReversalNonfiniteAndWallStepsFailClosedPermanently() async {
        await MainActor.run {
            for mode in 0...3 {
                let r = Rig(); r.start()
                XCTAssertTrue(r.context.receive(r.fix()))
                switch mode {
                case 0: r.mono -= 1
                case 1: r.mono = .nan
                case 2: r.utc += 2
                default: r.utc -= 2
                }
                XCTAssertEqual(r.context.snapshot().unavailable, .clockFault)
                let count = r.purges
                XCTAssertNil(r.context.snapshot().latitude)
                XCTAssertEqual(r.purges, count) // no repeated/reentrant fault notifications
                r.mono = 2000; r.utc = 2001
                XCTAssertFalse(r.context.receive(r.fix()))
                XCTAssertEqual(r.context.snapshot().unavailable, .clockFault)
            }
        }
    }

    func testProviderFailureClearsCoarseFix() async {
        await MainActor.run {
            let r = Rig(); r.start()
            XCTAssertTrue(r.context.receive(r.fix()))
            r.context.locationFailed()
            XCTAssertEqual(r.context.snapshot().unavailable, .noFix)
            XCTAssertNil(r.context.snapshot().latitude)
        }
    }
}
