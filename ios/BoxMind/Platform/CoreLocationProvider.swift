import CoreLocation
import BoxMindKit

/// One-shot "where am I" with the when-in-use permission prompt. Replaces navigator.geolocation.
/// Denied → `.denied` (the model tells the user once); no fix within the timeout → `.unavailable`.
final class CoreLocationProvider: NSObject, LocationProvider, CLLocationManagerDelegate, @unchecked Sendable {
    private let lock = NSLock()
    private var manager: CLLocationManager?
    private var waiters: [CheckedContinuation<LocationResult, Never>] = []

    func currentPosition() async -> LocationResult {
        await withCheckedContinuation { c in
            lock.withLock { waiters.append(c) }
            DispatchQueue.main.async { self.kick() }
        }
    }

    private func kick() {
        if manager == nil {
            let m = CLLocationManager()
            m.delegate = self
            m.desiredAccuracy = kCLLocationAccuracyHundredMeters
            manager = m
        }
        guard let m = manager else { return }
        switch m.authorizationStatus {
        case .notDetermined:
            m.requestWhenInUseAuthorization() // continues in locationManagerDidChangeAuthorization
        case .denied, .restricted:
            finish(.denied)
        default:
            request(m)
        }
    }

    private func request(_ m: CLLocationManager) {
        if let fix = m.location, fix.timestamp.timeIntervalSinceNow > -600 { // 10 min cache, like maximumAge
            finish(.position(GeoPoint(lat: fix.coordinate.latitude, lng: fix.coordinate.longitude)))
            return
        }
        m.requestLocation()
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) { [weak self] in self?.finish(.unavailable) }
    }

    private func finish(_ r: LocationResult) {
        let ws = lock.withLock { let w = waiters; waiters = []; return w }
        for w in ws { w.resume(returning: r) }
    }

    func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        switch m.authorizationStatus {
        case .notDetermined: break
        case .denied, .restricted: finish(.denied)
        default: if !lock.withLock({ waiters.isEmpty }) { request(m) }
        }
    }

    func locationManager(_ m: CLLocationManager, didUpdateLocations locs: [CLLocation]) {
        guard let fix = locs.last else { return }
        finish(.position(GeoPoint(lat: fix.coordinate.latitude, lng: fix.coordinate.longitude)))
    }

    func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {
        finish((error as? CLError)?.code == .denied ? .denied : .unavailable)
    }
}
