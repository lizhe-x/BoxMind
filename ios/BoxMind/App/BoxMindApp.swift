import SwiftUI
import BoxMindKit

@main
struct BoxMindApp: App {
    @State private var model: AppModel = {
        #if DEBUG
        // UI tests start from a clean slate: `-bm-reset` wipes the token, language and onboarding flag.
        if CommandLine.arguments.contains("-bm-reset") {
            KeychainTokenStore().clear()
            for key in [L10n.storageKey, AppModel.onboardedKey] { UserDefaults.standard.removeObject(forKey: key) }
        }
        #endif
        let api: any BoxMindAPI
        let location: any LocationProvider
        #if DEBUG
        if CommandLine.arguments.contains("-bm-mock") {
            api = MockAPI() // in-memory backend: UI tests and offline UI work, no gateway needed
            location = NoLocation() // no permission prompts under UI tests
        } else {
            api = Self.liveAPI()
            location = CoreLocationProvider()
        }
        #else
        api = Self.liveAPI()
        location = CoreLocationProvider()
        #endif
        return AppModel(api: api, prefs: UserDefaultsPreferences(), location: location)
    }()

    private static func liveAPI() -> APIClient {
        let raw = Bundle.main.object(forInfoDictionaryKey: "APIBaseURL") as? String
        let url = URL(string: raw ?? "") ?? URL(string: "http://127.0.0.1:8001")!
        return APIClient(baseURL: url, tokens: KeychainTokenStore())
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .preferredColorScheme(.dark)
        }
    }
}
