import Foundation
import BoxMindKit

/// Language choice and onboarding flag (replaces localStorage in the web client).
struct UserDefaultsPreferences: PreferenceStore {
    func string(_ key: String) -> String? { UserDefaults.standard.string(forKey: key) }
    func set(_ value: String?, for key: String) {
        if let value { UserDefaults.standard.set(value, forKey: key) } else { UserDefaults.standard.removeObject(forKey: key) }
    }
}
