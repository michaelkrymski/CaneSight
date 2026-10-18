#if canImport(ARKit) && canImport(UIKit)
import ARKit
import UIKit
import CaneSightLifecycle

/// Forward from the host's ARSession delegate, serialized on MainActor. This
/// bridge deliberately does not replace CS-014/016's delegate or own ARSession.
@MainActor public final class ARLifecycleBridge {
    private let lifecycle: any DepthLifecycleEvents
    private var observers: [NSObjectProtocol] = []

    public init(lifecycle: any DepthLifecycleEvents) { self.lifecycle = lifecycle }

    public func sessionWasInterrupted() { lifecycle.setInterrupted(true) }
    public func sessionInterruptionEnded() { lifecycle.setInterrupted(false) }
    public func sessionDidFail() { lifecycle.sessionFailed() }
    public func sessionDidRunNewConfiguration() { lifecycle.sessionRestarted() }

    public func cameraTrackingChanged(_ state: ARCamera.TrackingState) {
        if case .normal = state { lifecycle.setTrackingNormal(true) }
        else { lifecycle.setTrackingNormal(false) }
    }

    public func sceneBecameActive() { lifecycle.setApplicationActive(true) }
    public func sceneBecameInactive() { lifecycle.setApplicationActive(false) }

    /// Observe the specific camera scene, not another window's active state.
    /// Call stopObserving on teardown. Notifications invalidate synchronously on
    /// the main queue; enqueueing a Task here could let an old send slip through.
    public func observe(_ scene: UIScene) {
        stopObserving()
        let center = NotificationCenter.default
        for name in [UIScene.willDeactivateNotification, UIScene.didEnterBackgroundNotification,
                     UIScene.didDisconnectNotification] {
            observers.append(center.addObserver(forName: name, object: scene, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.sceneBecameInactive() }
            })
        }
        observers.append(center.addObserver(forName: UIScene.didActivateNotification, object: scene, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.sceneBecameActive() }
        })
        // App-wide loss of focus (including lock/overlays) always fails closed.
        observers.append(center.addObserver(forName: UIApplication.willResignActiveNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.sceneBecameInactive() }
        })
        lifecycle.setApplicationActive(scene.activationState == .foregroundActive)
    }

    public func stopObserving() {
        observers.forEach { NotificationCenter.default.removeObserver($0) }
        observers.removeAll()
        lifecycle.setApplicationActive(false)
    }
}
#endif
