import XCTest
import CaneSightStatus
import CaneSightLifecycle

final class LifecycleIntegrationTests: XCTestCase {
    func testActualLifecycleHookClearsDisplayedDepthAndPendingNarration() async {
        await MainActor.run {
            var now = 1000.0
            var cancelCalls = 0
            let status = StatusController(nowMilliseconds: { now }, cancelAudioNow: {
                cancelCalls += 1; return .requested
            })
            status.setSceneActive(true)
            let lifecycle = DepthLifecycle<Int>(nowMilliseconds: { now }, hooks: LifecycleHooks(
                cancelAndDisconnect: { status.setConnection(.disconnected) },
                discardPendingTelemetry: {}, invalidateClockMapping: {},
                depthBecameUnknown: { status.invalidateDepth(.unknown) }))
            lifecycle.setApplicationActive(true)
            lifecycle.setTrackingNormal(true)
            let connection = lifecycle.beginConnection()!
            XCTAssertTrue(lifecycle.connectionReady(connection))
            XCTAssertTrue(lifecycle.clockMappingReady(connection))
            status.setConnection(.connected)
            let capture = lifecycle.beginCapture()!
            let display = status.depthToken
            XCTAssertTrue(lifecycle.submit(1, sequence: 1, captureTime: CaptureTime(
                sourceMilliseconds: 1000, earliestLocalMilliseconds: 1000,
                latestLocalMilliseconds: 1000), lease: capture))
            XCTAssertNotNil(lifecycle.takeForImmediateSend())
            XCTAssertTrue(status.showBoundedCapture(.init(imageLeft: 1, imageCenter: 2, imageRight: nil),
                sourceMilliseconds: 1000, earliestLocalMilliseconds: 1000,
                latestLocalMilliseconds: 1000, token: display))
            let audio = status.beginAudioDisplay()!
            lifecycle.setInterrupted(true)
            XCTAssertEqual(status.snapshot.sectors, .unknown)
            XCTAssertEqual(cancelCalls, 1)
            XCTAssertEqual(status.snapshot.audio, .cancelRequested)
            now = 1010
            XCTAssertFalse(status.showBoundedCapture(.init(imageLeft: 9, imageCenter: 9, imageRight: 9),
                sourceMilliseconds: 1005, earliestLocalMilliseconds: 1005,
                latestLocalMilliseconds: 1005, token: display))
            status.audioStarted(audio)
            XCTAssertEqual(status.snapshot.audio, .cancelRequested)
            lifecycle.setInterrupted(false)
            XCTAssertNil(lifecycle.beginCapture())
            XCTAssertEqual(status.snapshot.sectors, .unknown)
        }
    }

    func testCleanupReentryCannotRestoreDepthOrRecurseThroughUI() async {
        await MainActor.run {
            let status = StatusController(nowMilliseconds: { 1000 })
            status.setSceneActive(true)
            var lifecycle: DepthLifecycle<Int>!
            var unknownCalls = 0
            lifecycle = DepthLifecycle<Int>(nowMilliseconds: { 1000 }, hooks: LifecycleHooks(
                cancelAndDisconnect: { lifecycle.disconnected() },
                discardPendingTelemetry: {}, invalidateClockMapping: {},
                depthBecameUnknown: {
                    unknownCalls += 1
                    status.invalidateDepth(.interrupted)
                    XCTAssertNil(lifecycle.beginCapture())
                }))
            lifecycle.setApplicationActive(true)
            XCTAssertEqual(unknownCalls, 1)
            XCTAssertEqual(status.snapshot.depth, .interrupted)
            XCTAssertEqual(status.snapshot.sectors, .unknown)
        }
    }
}
