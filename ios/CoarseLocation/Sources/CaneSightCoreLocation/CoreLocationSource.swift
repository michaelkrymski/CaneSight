#if canImport(CoreLocation) && canImport(UIKit)
import CoreLocation
import UIKit
import CaneSightCoarseLocation

/// Created on MainActor so CLLocationManager delivers delegates on its main
/// run loop. Forward synchronously; do not queue a late authorized fix after an
/// opt-out. Host scene callbacks must also run on this actor.
@MainActor public final class CoreLocationSource {
    public let context: CoarseLocationContext
    private let manager: CLLocationManager
    private let delegate: LocationDelegate
    private var consented = false
    private var foreground = false
    private var collecting = false
    private var requestedPermission = false

    public init(policy: LocationPolicy, purgeCachedAndQueuedContext: @escaping () -> Void) {
        let clock = LocationSystemClock()
        context = CoarseLocationContext(policy: policy, clock: { clock.read() },
            purgeCachedAndQueuedContext: purgeCachedAndQueuedContext)
        manager = CLLocationManager()
        delegate = LocationDelegate()
        delegate.owner = self
        manager.delegate = delegate
        manager.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
        manager.distanceFilter = kCLDistanceFilterNone
        manager.pausesLocationUpdatesAutomatically = true
        manager.allowsBackgroundLocationUpdates = false
        authorizationChanged()
    }

    /// Call only after explicit UI opt-in for coarse context sharing. OS location
    /// permission alone is not sharing consent. This choice is not persisted.
    public func setSharingConsent(_ value: Bool) {
        consented = value
        context.setConsent(value)
        updateCollection()
    }

    /// Forward the camera/app scene's active state, including lock/background.
    public func setForegroundActive(_ value: Bool) {
        foreground = value
        context.setActive(value)
        updateCollection()
    }

    /// Call when tearing down the source. Release any host context snapshots too.
    public func stop() {
        foreground = false
        context.setActive(false)
        manager.stopUpdatingLocation()
        collecting = false
    }

    fileprivate func authorizationChanged() {
        let state: LocationAuthorization
        switch manager.authorizationStatus {
        case .authorizedAlways, .authorizedWhenInUse: state = .authorized
        case .denied: state = .denied
        case .restricted: state = .restricted
        case .notDetermined: state = .undetermined
        @unknown default: state = .denied
        }
        context.setAuthorization(state)
        updateCollection()
    }

    private func updateCollection() {
        guard consented, foreground else { stopCollection(); return }
        switch manager.authorizationStatus {
        case .notDetermined:
            stopCollection()
            if !requestedPermission {
                requestedPermission = true
                manager.requestWhenInUseAuthorization()
            }
        case .authorizedWhenInUse, .authorizedAlways:
            if !collecting {
                collecting = true
                manager.startUpdatingLocation()
            }
        default:
            stopCollection()
        }
    }

    private func stopCollection() {
        if collecting { manager.stopUpdatingLocation() }
        collecting = false
    }

    fileprivate func received(_ locations: [CLLocation]) {
        // Recheck OS authorization before each admission, not just on a delayed
        // authorization callback. Only the newest fix in a batch is considered.
        authorizationChanged()
        guard let latest = locations.max(by: { $0.timestamp < $1.timestamp }) else {
            context.locationFailed()
            return
        }
        context.receive(LocationFix(latitude: latest.coordinate.latitude,
            longitude: latest.coordinate.longitude, horizontalAccuracyMeters: latest.horizontalAccuracy,
            originalFixUTCSeconds: latest.timestamp.timeIntervalSince1970))
    }

    fileprivate func failed() { context.locationFailed() }
}

private final class LocationDelegate: NSObject, CLLocationManagerDelegate {
    weak var owner: CoreLocationSource?

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        MainActor.assumeIsolated { owner?.authorizationChanged() }
    }
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        MainActor.assumeIsolated { owner?.received(locations) }
    }
    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        // Do not log errors or CLLocation descriptions, which can include data.
        MainActor.assumeIsolated { owner?.failed() }
    }
}
#endif
