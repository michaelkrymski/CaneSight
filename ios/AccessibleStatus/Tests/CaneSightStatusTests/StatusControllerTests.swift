import XCTest
@testable import CaneSightStatus

final class StatusControllerTests: XCTestCase {
    func testDefaultsAreUnknownAndUnwiredCancellationCannotPretendSuccess() async {
        await MainActor.run {
            let model = StatusController(nowMilliseconds: { 100 })
            XCTAssertEqual(model.snapshot, .initial)
            model.cancelAudio()
            XCTAssertEqual(model.snapshot.audio, .unavailable)
            XCTAssertFalse(model.snapshot.canCancelAudio)
            model.setSceneActive(true)
            XCTAssertNil(model.beginAudioDisplay())
        }
    }

    func testInvalidDistancesStayUnknownRatherThanZeroOrFar() {
        let sectors = DisplaySectors(imageLeft: .nan, imageCenter: -.infinity, imageRight: 0)
        XCTAssertEqual(sectors, .unknown)
        XCTAssertEqual(DisplaySectors(imageLeft: -1, imageCenter: .infinity, imageRight: 1.25).distances,
                       [nil, nil, 1.25])
    }

    func testPreviewIsExplicitlyUnverifiedAndExpiresWithoutMoreCallbacks() async {
        await MainActor.run {
            var now = 1000.0
            let model = StatusController(nowMilliseconds: { now })
            model.setSceneActive(true)
            XCTAssertTrue(model.showLocalPreview(.init(imageLeft: 2, imageCenter: nil, imageRight: 1),
                sourceMilliseconds: 12, receiptMilliseconds: now, token: model.depthToken))
            XCTAssertEqual(model.snapshot.depth, .localPreview)
            XCTAssertNil(model.snapshot.sectors.imageCenter)
            now = 1499; model.tick()
            XCTAssertEqual(model.snapshot.sectors.imageLeft, 2)
            now = 1500; model.tick()
            XCTAssertEqual(model.snapshot.depth, .stale)
            XCTAssertEqual(model.snapshot.sectors, .unknown)
        }
    }

    func testHeartbeatAndConnectionChangesCannotRenewDepth() async {
        await MainActor.run {
            var now = 1000.0
            let model = StatusController(nowMilliseconds: { now })
            model.setSceneActive(true)
            XCTAssertTrue(model.showBoundedCapture(.init(imageLeft: 1, imageCenter: 2, imageRight: 3),
                sourceMilliseconds: 99, earliestLocalMilliseconds: 800, latestLocalMilliseconds: 900,
                token: model.depthToken))
            now = 1299; model.setConnection(.connected); model.tick()
            XCTAssertEqual(model.snapshot.depth, .boundedCapture)
            now = 1300; model.setConnection(.connected); model.tick()
            XCTAssertEqual(model.snapshot.depth, .stale)
            XCTAssertEqual(model.snapshot.connection, .connected)
        }
    }

    func testUnknownBoundsFutureAndStaleInputsCannotBecomeRecent() async {
        await MainActor.run {
            for (lower, upper) in [(Double.nan,1000.0), (800,1001), (500,600), (700,1000), (1000,900), (-1,0)] {
                let model = StatusController(nowMilliseconds: { 1000 })
                model.setSceneActive(true)
                XCTAssertFalse(model.showBoundedCapture(.init(imageLeft: 1, imageCenter: 1, imageRight: 1),
                    sourceMilliseconds: 4, earliestLocalMilliseconds: lower, latestLocalMilliseconds: upper,
                    token: model.depthToken))
                XCTAssertEqual(model.snapshot.sectors, .unknown)
            }
        }
    }

    func testBackgroundAndInterruptionRejectOldWorkersAndResumeNeedsNewFrames() async {
        await MainActor.run {
            let model = StatusController(nowMilliseconds: { 1000 })
            model.setSceneActive(true)
            let before = model.depthToken
            model.invalidateDepth(.interrupted)
            XCTAssertFalse(model.showLocalPreview(.unknown, sourceMilliseconds: 1,
                receiptMilliseconds: 1000, token: before))
            let resumed = model.depthToken
            model.setSceneActive(false); model.setSceneActive(true)
            XCTAssertEqual(model.snapshot.sectors, .unknown)
            XCTAssertEqual(model.snapshot.depth, .waiting)
            XCTAssertFalse(model.showLocalPreview(.unknown, sourceMilliseconds: 2,
                receiptMilliseconds: 1000, token: resumed))
            XCTAssertTrue(model.showLocalPreview(.unknown, sourceMilliseconds: 3,
                receiptMilliseconds: 1000, token: model.depthToken))
        }
    }

    func testDuplicateSourceAndFuturePreviewReceiptAreRejected() async {
        await MainActor.run {
            let model = StatusController(nowMilliseconds: { 1000 })
            model.setSceneActive(true)
            XCTAssertTrue(model.showLocalPreview(.unknown, sourceMilliseconds: 10,
                receiptMilliseconds: 1000, token: model.depthToken))
            XCTAssertFalse(model.showLocalPreview(.unknown, sourceMilliseconds: 10,
                receiptMilliseconds: 1000, token: model.depthToken))
            XCTAssertFalse(model.showLocalPreview(.unknown, sourceMilliseconds: 11,
                receiptMilliseconds: 1001, token: model.depthToken))
        }
    }

    func testClockReversalFaultIsLatchedAndClearsAudioAndDepth() async {
        await MainActor.run {
            var now = 1000.0, cancellations = 0
            let model = StatusController(nowMilliseconds: { now }, cancelAudioNow: {
                cancellations += 1; return .requested
            })
            model.setSceneActive(true)
            XCTAssertTrue(model.showLocalPreview(.unknown, sourceMilliseconds: 10,
                receiptMilliseconds: now, token: model.depthToken))
            XCTAssertNotNil(model.beginAudioDisplay())
            now = 999; model.tick()
            XCTAssertEqual(model.snapshot.depth, .clockFailed)
            XCTAssertEqual(cancellations, 1)
            now = 1100; model.setSceneActive(false); model.setSceneActive(true)
            XCTAssertEqual(model.snapshot.depth, .clockFailed)
            XCTAssertNil(model.beginAudioDisplay())
            XCTAssertFalse(model.showLocalPreview(.unknown, sourceMilliseconds: 11,
                receiptMilliseconds: now, token: model.depthToken))
        }
    }

    func testNonfiniteOrNegativeClockFailsClosed() async {
        await MainActor.run {
            for time in [Double.nan, Double.infinity, -1, Double.greatestFiniteMagnitude] {
                let model = StatusController(nowMilliseconds: { time })
                model.tick()
                XCTAssertEqual(model.snapshot.depth, .clockFailed)
                XCTAssertEqual(model.snapshot.sectors, .unknown)
            }
        }
    }

    func testAudioAdmissionAlsoObservesClockFaultWithoutWaitingForTick() async {
        await MainActor.run {
            let model = StatusController(nowMilliseconds: { .nan }, cancelAudioNow: { .requested })
            model.setSceneActive(true)
            XCTAssertNil(model.beginAudioDisplay())
            XCTAssertEqual(model.snapshot.depth, .clockFailed)
        }
    }

    func testCancelRunsLocalAdapterWhileOfflineAndRejectsLatePlayback() async {
        await MainActor.run {
            var calls = 0
            let model = StatusController(nowMilliseconds: { 1000 }, cancelAudioNow: {
                calls += 1; return .requested
            })
            model.setSceneActive(true)
            model.setConnection(.disconnected)
            let old = model.beginAudioDisplay()!
            model.audioStarted(old)
            model.cancelAudio()
            XCTAssertEqual(calls, 1)
            XCTAssertEqual(model.snapshot.audio, .cancelRequested)
            XCTAssertTrue(model.snapshot.canCancelAudio)
            model.audioStarted(old); model.audioFinished(old)
            XCTAssertEqual(model.snapshot.audio, .cancelRequested)
            XCTAssertNotNil(model.beginAudioDisplay()) // explicit NEW host request only
        }
    }

    func testCancelFailureIsVisibleAndBlocksNewNarration() async {
        await MainActor.run {
            let model = StatusController(nowMilliseconds: { 1000 }, cancelAudioNow: { .failed })
            model.setSceneActive(true)
            model.cancelAudio()
            XCTAssertEqual(model.snapshot.audio, .cancelFailed)
            XCTAssertNil(model.beginAudioDisplay())
            XCTAssertTrue(model.snapshot.canCancelAudio) // retry/manual control remains reachable
        }
    }

    func testReentrantCancelAndNewAudioCannotUndoCancellation() async {
        await MainActor.run {
            var model: StatusController!
            var calls = 0
            var old: AudioDisplayToken!
            model = StatusController(nowMilliseconds: { 1000 }, cancelAudioNow: {
                calls += 1
                model.cancelAudio()
                XCTAssertNil(model.beginAudioDisplay())
                model.audioStarted(old)
                return .requested
            })
            model.setSceneActive(true)
            old = model.beginAudioDisplay()!
            model.cancelAudio()
            XCTAssertEqual(calls, 1)
            XCTAssertEqual(model.snapshot.audio, .cancelRequested)
        }
    }

    func testSourceLossCancelsPendingAudioButReconnectDoesNotRestartIt() async {
        await MainActor.run {
            var calls = 0
            let model = StatusController(nowMilliseconds: { 1000 }, cancelAudioNow: {
                calls += 1; return .requested
            })
            model.setSceneActive(true)
            let old = model.beginAudioDisplay()!
            model.invalidateDepth(.interrupted)
            XCTAssertEqual(calls, 1)
            model.setConnection(.connected)
            model.audioStarted(old)
            XCTAssertEqual(model.snapshot.audio, .cancelRequested)
            XCTAssertEqual(model.snapshot.depth, .interrupted)
        }
    }

    func testConnectionLossPreservesIndependentLocalDepthButCancelsNarration() async {
        await MainActor.run {
            var calls = 0
            let model = StatusController(nowMilliseconds: { 1000 }, cancelAudioNow: {
                calls += 1; return .requested
            })
            model.setSceneActive(true); model.setConnection(.connected)
            XCTAssertTrue(model.showLocalPreview(.init(imageLeft: 1, imageCenter: nil, imageRight: nil),
                sourceMilliseconds: 8, receiptMilliseconds: 1000, token: model.depthToken))
            XCTAssertNotNil(model.beginAudioDisplay())
            model.setConnection(.disconnected)
            XCTAssertEqual(calls, 1)
            XCTAssertEqual(model.snapshot.depth, .localPreview)
            XCTAssertEqual(model.snapshot.sectors.imageLeft, 1)
        }
    }

    func testOnlyOneAudioDisplaySlotAndOldCompletionCannotFinishNewRequest() async {
        await MainActor.run {
            let model = StatusController(nowMilliseconds: { 1000 }, cancelAudioNow: { .requested })
            model.setSceneActive(true)
            let old = model.beginAudioDisplay()!
            XCTAssertNil(model.beginAudioDisplay())
            model.cancelAudio()
            let current = model.beginAudioDisplay()!
            model.audioStarted(current); model.audioFinished(old)
            XCTAssertEqual(model.snapshot.audio, .playing)
            model.audioFinished(current)
            XCTAssertEqual(model.snapshot.audio, .idle)
        }
    }

    func testReentrantObserverInvalidationLeavesAuthoritativeSnapshotUnknown() async {
        await MainActor.run {
            let model = StatusController(nowMilliseconds: { 1000 })
            model.setSceneActive(true)
            var notifications = 0
            model.onChange = { value in
                notifications += 1
                if value.depth == .localPreview { model.invalidateDepth(.interrupted) }
            }
            XCTAssertTrue(model.showLocalPreview(.init(imageLeft: 1, imageCenter: 2, imageRight: 3),
                sourceMilliseconds: 1000, receiptMilliseconds: 1000, token: model.depthToken))
            XCTAssertEqual(model.snapshot.sectors, .unknown)
            XCTAssertEqual(model.snapshot.depth, .interrupted)
            XCTAssertEqual(notifications, 1) // cleanup cannot recurse through observer delivery
        }
    }
}
