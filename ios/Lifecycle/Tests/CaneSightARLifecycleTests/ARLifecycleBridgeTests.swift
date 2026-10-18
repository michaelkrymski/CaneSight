#if canImport(ARKit) && canImport(UIKit)
import XCTest
import ARKit
import UIKit
import CaneSightLifecycle
import CaneSightARLifecycle

@MainActor private final class Recorder: DepthLifecycleEvents {
    var events: [String] = []
    func setApplicationActive(_ active: Bool) { events.append("active:\(active)") }
    func setInterrupted(_ interrupted: Bool) { events.append("interrupted:\(interrupted)") }
    func setTrackingNormal(_ normal: Bool) { events.append("normal:\(normal)") }
    func sessionFailed() { events.append("failed") }
    func sessionRestarted() { events.append("restart") }
}

/// Requires the Apple SDK. Not executed by the Linux core test command.
final class ARLifecycleBridgeTests: XCTestCase {
    func testForwardsInterruptionFailureTrackingAndSceneLifecycle() async {
        await MainActor.run {
            let recorder = Recorder()
            let bridge = ARLifecycleBridge(lifecycle: recorder)
            bridge.sceneBecameActive()
            bridge.cameraTrackingChanged(.normal)
            bridge.sessionWasInterrupted()
            bridge.sessionInterruptionEnded()
            bridge.cameraTrackingChanged(.limited(.relocalizing))
            bridge.cameraTrackingChanged(.notAvailable)
            bridge.sessionDidFail()
            bridge.sessionDidRunNewConfiguration()
            bridge.sceneBecameInactive()
            XCTAssertEqual(recorder.events, ["active:true", "normal:true", "interrupted:true",
                "interrupted:false", "normal:false", "normal:false", "failed", "restart", "active:false"])
        }
    }

    func testStoppingObservationInvalidatesActivity() async {
        await MainActor.run {
            let recorder = Recorder()
            let bridge = ARLifecycleBridge(lifecycle: recorder)
            bridge.sceneBecameActive()
            bridge.stopObserving()
            XCTAssertEqual(recorder.events, ["active:true", "active:false"])
        }
    }
}
#endif
