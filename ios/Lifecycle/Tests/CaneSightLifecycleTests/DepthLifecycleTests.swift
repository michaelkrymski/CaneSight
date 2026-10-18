import XCTest
@testable import CaneSightLifecycle

@MainActor private final class Rig {
    var time: Double = 1000
    var purges = 0
    var closes = 0
    var maps = 0
    var unknowns = 0
    lazy var guardrail = DepthLifecycle<String>(nowMilliseconds: { [unowned self] in self.time }, hooks:
        LifecycleHooks(cancelAndDisconnect: { [unowned self] in self.closes += 1 },
                       discardPendingTelemetry: { [unowned self] in self.purges += 1 },
                       invalidateClockMapping: { [unowned self] in self.maps += 1 },
                       depthBecameUnknown: { [unowned self] in self.unknowns += 1 }))

    func recover() -> LifecycleLease {
        guardrail.setApplicationActive(true)
        guardrail.setTrackingNormal(true)
        let connection = guardrail.beginConnection()!
        XCTAssertTrue(guardrail.connectionReady(connection))
        XCTAssertTrue(guardrail.clockMappingReady(connection))
        return guardrail.beginCapture()!
    }

    func capture(_ source: Double? = nil, lower: Double? = nil, upper: Double? = nil) -> CaptureTime {
        CaptureTime(sourceMilliseconds: source ?? time,
                    earliestLocalMilliseconds: lower ?? time,
                    latestLocalMilliseconds: upper ?? time)
    }

    @discardableResult func submit(_ sequence: UInt64, lease: LifecycleLease) -> Bool {
        guardrail.submit("depth-\(sequence)", sequence: sequence, captureTime: capture(), lease: lease)
    }
}

final class DepthLifecycleTests: XCTestCase {
    func testClockFaultNotifiesOnceEvenWhenUnknownHookReadsGuard() async {
        await MainActor.run {
            var time = 1000.0
            var notifications = 0
            var lifecycle: DepthLifecycle<String>!
            lifecycle = DepthLifecycle(nowMilliseconds: { time }, hooks: LifecycleHooks(
                cancelAndDisconnect: {}, discardPendingTelemetry: {}, invalidateClockMapping: {},
                depthBecameUnknown: {
                    notifications += 1
                    XCTAssertNil(lifecycle.beginCapture())
                }))
            lifecycle.setApplicationActive(true)
            lifecycle.setTrackingNormal(true)
            let lease = lifecycle.beginConnection()!
            XCTAssertTrue(lifecycle.connectionReady(lease))
            XCTAssertTrue(lifecycle.clockMappingReady(lease))
            let before = notifications
            time = .nan
            XCTAssertNil(lifecycle.beginCapture())
            XCTAssertEqual(notifications, before + 1)
            XCTAssertNil(lifecycle.takeForImmediateSend())
            XCTAssertNil(lifecycle.beginConnection())
            XCTAssertEqual(notifications, before + 1)
            XCTAssertTrue(lifecycle.requiresReenrollment)
        }
    }

    func testCleanupCannotReconnectFromSynchronousTransportHook() async {
        await MainActor.run {
            var lifecycle: DepthLifecycle<String>!
            var disconnects = 0
            lifecycle = DepthLifecycle(nowMilliseconds: { 1000 }, hooks: LifecycleHooks(
                cancelAndDisconnect: {
                    disconnects += 1
                    // A host may synchronously report transport close while it
                    // clears a socket, or attempt reconnect from that callback.
                    lifecycle.disconnected()
                    XCTAssertNil(lifecycle.beginConnection())
                }, discardPendingTelemetry: {}, invalidateClockMapping: {}, depthBecameUnknown: {}))
            lifecycle.setApplicationActive(true)
            lifecycle.setTrackingNormal(true)
            let lease = lifecycle.beginConnection()!
            XCTAssertTrue(lifecycle.connectionReady(lease))
            XCTAssertTrue(lifecycle.clockMappingReady(lease))
            let before = disconnects
            lifecycle.disconnected()
            XCTAssertEqual(disconnects, before + 1)
            XCTAssertNil(lifecycle.beginCapture())
            XCTAssertFalse(lifecycle.connectionReady(lease))
            // Recovery outside cleanup still requires a new lease and mapping.
            let fresh = lifecycle.beginConnection()!
            XCTAssertTrue(lifecycle.connectionReady(fresh))
            XCTAssertTrue(lifecycle.clockMappingReady(fresh))
            XCTAssertNotNil(lifecycle.beginCapture())
        }
    }

    func testStartsUnknownAndNeedsActiveTrackingConnectionAndMapping() async {
        await MainActor.run {
            let r = Rig()
            XCTAssertNil(r.guardrail.beginCapture())
            XCTAssertNil(r.guardrail.beginConnection())
            r.guardrail.setApplicationActive(true)
            XCTAssertNil(r.guardrail.beginConnection())
            r.guardrail.setTrackingNormal(true)
            let connection = r.guardrail.beginConnection()!
            XCTAssertNil(r.guardrail.beginCapture())
            XCTAssertTrue(r.guardrail.connectionReady(connection))
            XCTAssertNil(r.guardrail.beginCapture())
            XCTAssertTrue(r.guardrail.clockMappingReady(connection))
            XCTAssertNil(r.guardrail.takeForImmediateSend())
            XCTAssertTrue(r.submit(1, lease: r.guardrail.beginCapture()!))
            XCTAssertEqual(r.guardrail.takeForImmediateSend()?.payload, "depth-1")
        }
    }

    func testInterruptionPurgesQueuedAndInFlightSamplesAndClockMap() async {
        await MainActor.run {
            let r = Rig()
            let old = r.recover()
            XCTAssertTrue(r.submit(1, lease: old))
            let sending = r.guardrail.takeForImmediateSend()!
            r.time += 1
            XCTAssertTrue(r.submit(2, lease: old))
            let count = r.purges
            r.guardrail.setInterrupted(true)
            XCTAssertEqual(r.purges, count + 1)
            XCTAssertEqual(r.purges, r.closes)
            XCTAssertEqual(r.purges, r.maps)
            XCTAssertEqual(r.purges, r.unknowns)
            XCTAssertNil(r.guardrail.takeForImmediateSend())
            XCTAssertFalse(r.guardrail.maySend(sending))
            XCTAssertFalse(r.submit(3, lease: old))
            r.guardrail.setInterrupted(false)
            XCTAssertNil(r.guardrail.beginConnection()) // tracking must be observed again
            let fresh = r.recover()
            XCTAssertFalse(r.submit(3, lease: old)) // late worker, still within 500 ms
            r.time += 1
            XCTAssertTrue(r.submit(3, lease: fresh))
        }
    }

    func testBackgroundAndResumeDoNotRestoreCachedTracking() async {
        await MainActor.run {
            let r = Rig()
            let lease = r.recover()
            XCTAssertTrue(r.submit(5, lease: lease))
            r.guardrail.setApplicationActive(false)
            XCTAssertNil(r.guardrail.takeForImmediateSend())
            r.guardrail.setTrackingNormal(true) // late camera callback while inactive
            XCTAssertNil(r.guardrail.beginConnection())
            r.guardrail.setApplicationActive(true)
            XCTAssertNil(r.guardrail.beginConnection())
            let fresh = r.recover()
            XCTAssertFalse(r.submit(6, lease: lease))
            r.time += 1
            XCTAssertTrue(r.submit(6, lease: fresh))
        }
    }

    func testLimitedOrUnavailableTrackingRequiresFreshCapture() async {
        await MainActor.run {
            let r = Rig()
            let old = r.recover()
            XCTAssertTrue(r.submit(1, lease: old))
            r.guardrail.setTrackingNormal(false)
            XCTAssertNil(r.guardrail.takeForImmediateSend())
            XCTAssertNil(r.guardrail.beginCapture())
            r.time += 100
            let fresh = r.recover()
            XCTAssertFalse(r.guardrail.submit("old", sequence: 2,
                captureTime: r.capture(1001, lower: 1001, upper: 1001), lease: fresh))
            XCTAssertTrue(r.submit(2, lease: fresh))
        }
    }

    func testFailureNeedsExplicitSessionRestart() async {
        await MainActor.run {
            let r = Rig()
            _ = r.recover()
            r.guardrail.sessionFailed()
            r.guardrail.setTrackingNormal(true)
            XCTAssertNil(r.guardrail.beginConnection())
            r.guardrail.sessionRestarted()
            XCTAssertNil(r.guardrail.beginConnection())
            let lease = r.recover()
            XCTAssertTrue(r.submit(10, lease: lease))
        }
    }

    func testReconnectRejectsOldCompletionsAndPreservesSequenceHighWater() async {
        await MainActor.run {
            let r = Rig()
            let old = r.recover()
            XCTAssertTrue(r.submit(10, lease: old))
            r.guardrail.disconnected()
            let attempt1 = r.guardrail.beginConnection()!
            let attempt2 = r.guardrail.beginConnection()!
            XCTAssertFalse(r.guardrail.connectionReady(attempt1))
            XCTAssertTrue(r.guardrail.connectionReady(attempt2))
            XCTAssertFalse(r.guardrail.clockMappingReady(old))
            XCTAssertTrue(r.guardrail.clockMappingReady(attempt2))
            XCTAssertNil(r.guardrail.takeForImmediateSend())
            let lease = r.guardrail.beginCapture()!
            r.time += 1
            XCTAssertFalse(r.submit(10, lease: lease))
            XCTAssertFalse(r.submit(9, lease: lease))
            XCTAssertTrue(r.submit(11, lease: lease))
            let message = r.guardrail.takeForImmediateSend()!
            XCTAssertEqual(message.sequence, 11)
            XCTAssertEqual(message.captureTime.sourceMilliseconds, 1001)
        }
    }

    func testSingleLatestSlotAndAgeRecheckedAtSend() async {
        await MainActor.run {
            let r = Rig()
            let token = r.recover()
            XCTAssertTrue(r.submit(1, lease: token))
            r.time += 1
            XCTAssertTrue(r.submit(2, lease: token))
            let sample = r.guardrail.takeForImmediateSend()!
            XCTAssertEqual(sample.sequence, 2)
            XCTAssertNil(r.guardrail.takeForImmediateSend())
            r.time += 500
            XCTAssertTrue(r.guardrail.maySend(sample))
            r.time += 0.01
            XCTAssertFalse(r.guardrail.maySend(sample))
            XCTAssertTrue(r.submit(3, lease: token))
            r.time += 501
            XCTAssertNil(r.guardrail.takeForImmediateSend())
        }
    }

    func testRejectsFutureInvalidUncertainAndPreRecoveryCapture() async {
        await MainActor.run {
            let r = Rig()
            let lease = r.recover()
            r.time = 1400
            let invalid: [CaptureTime] = [
                r.capture(.nan), r.capture(-1), r.capture(.infinity),
                r.capture(lower: .nan), r.capture(upper: .infinity),
                r.capture(lower: 1401, upper: 1401),
                r.capture(lower: 1300, upper: 1200),
                r.capture(lower: 999, upper: 1001),
                r.capture(lower: 1100, upper: 1400)
            ]
            for time in invalid {
                XCTAssertFalse(r.guardrail.submit("bad", sequence: 1, captureTime: time, lease: lease))
            }
            XCTAssertTrue(r.guardrail.submit("bounded", sequence: 1,
                captureTime: r.capture(5000, lower: 1200, upper: 1400), lease: lease))
            XCTAssertEqual(r.guardrail.takeForImmediateSend()?.captureTime.sourceMilliseconds, 5000)
        }
    }

    func testClockReversalAndInvalidClockRequireOperatorReenrollment() async {
        await MainActor.run {
            for bad in [999.0, Double.nan, Double.infinity, -1.0] {
                let r = Rig()
                let lease = r.recover()
                XCTAssertTrue(r.submit(1, lease: lease))
                r.time = bad
                XCTAssertNil(r.guardrail.takeForImmediateSend())
                XCTAssertTrue(r.guardrail.requiresReenrollment)
                r.time = 2000
                r.guardrail.sessionRestarted()
                r.guardrail.setTrackingNormal(true)
                XCTAssertNil(r.guardrail.beginConnection())
            }
        }
    }

    func testExplicitEpochChangeCannotBeClearedByReconnect() async {
        await MainActor.run {
            let r = Rig()
            _ = r.recover()
            r.guardrail.requireNewEnrollment()
            XCTAssertNil(r.guardrail.beginConnection())
            XCTAssertNil(r.guardrail.beginCapture())
            XCTAssertTrue(r.guardrail.requiresReenrollment)
        }
    }
}
