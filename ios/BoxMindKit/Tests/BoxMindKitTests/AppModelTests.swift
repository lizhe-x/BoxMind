import XCTest
@testable import BoxMindKit

/// Mirrors the "language", "toast" and "helpers" groups of frontend/tests/store.test.ts.
@MainActor
final class AppModelTests: XCTestCase {
    func testDefaultsToEnglish() {
        let m = AppModel(api: ScriptedAPI(token: nil), prefs: MemoryPreferences())
        XCTAssertEqual(m.lang, .en)
        XCTAssertEqual(m.t(.tab_home), "Home")
        XCTAssertEqual(m.screen, .onboarding)
    }

    func testSetLangPersistsLocallyAndSyncsToTheServerWhenSignedIn() async {
        let api = ScriptedAPI()
        let prefs = MemoryPreferences()
        let m = AppModel(api: api, prefs: prefs)
        await m.setLang(.zh) // not signed in yet → local only
        XCTAssertEqual(prefs.string("bm_lang"), "zh")
        XCTAssertTrue(api.updateCalls.isEmpty)

        api.meResult = .success(ScriptedAPI.sampleMe(lang: "zh"))
        await m.start()
        XCTAssertTrue(m.authed && m.authChecked)
        await m.setLang(.en)
        XCTAssertEqual(api.updateCalls.last?.lang, "en")
        XCTAssertEqual(m.me?.lang, "en")
    }

    func testRefreshAdoptsTheServerLanguage() async throws {
        let api = ScriptedAPI()
        api.meResult = .success(ScriptedAPI.sampleMe(lang: "zh-CN"))
        let prefs = MemoryPreferences(["bm_lang": "en"])
        let m = AppModel(api: api, prefs: prefs)
        try await m.refresh()
        XCTAssertEqual(m.lang, .zh)
        XCTAssertEqual(prefs.string("bm_lang"), "zh")
    }

    func testLoginPushesALanguageChosenBeforeSigningInToAFreshAccount() async throws {
        let api = ScriptedAPI(token: nil)
        let prefs = MemoryPreferences(["bm_onboarded": "1"])
        let m = AppModel(api: api, prefs: prefs)
        await m.setLang(.zh)
        api.meResult = .success(ScriptedAPI.sampleMe(lang: "en")) // server default for a new account
        try await m.login(email: "a@b.co", code: "123456")
        XCTAssertTrue(m.authed)
        XCTAssertEqual(m.lang, .zh)
        XCTAssertEqual(api.updateCalls.first?.lang, "zh")
        XCTAssertEqual(m.screen, .home)
    }

    func testStartWithoutATokenShowsLogin() async {
        let m = AppModel(api: ScriptedAPI(token: nil), prefs: MemoryPreferences())
        await m.start()
        XCTAssertTrue(m.authChecked)
        XCTAssertFalse(m.authed)
    }

    func testStartWithARejectedTokenShowsLogin() async {
        let api = ScriptedAPI()
        api.meResult = .failure(APIError.unauthorized)
        let m = AppModel(api: api, prefs: MemoryPreferences())
        await m.start()
        XCTAssertTrue(m.authChecked)
        XCTAssertFalse(m.authed)
    }

    func testToastsFollowTheActiveLanguage() async {
        let api = ScriptedAPI()
        api.updateMeResult = .failure(Boom())
        let m = AppModel(api: api, prefs: MemoryPreferences(["bm_lang": "zh"]))
        await m.updateMe(gpsEnabled: false)
        XCTAssertEqual(m.toast, "设置保存失败,请重试")
    }

    func testUpdateMeIsOptimisticAndRollsBack() async {
        let api = ScriptedAPI()
        let m = AppModel(api: api, prefs: MemoryPreferences())
        await m.start()
        XCTAssertEqual(m.me?.gpsEnabled, true)
        api.updateMeResult = .failure(Boom())
        await m.updateMe(gpsEnabled: false)
        XCTAssertEqual(m.me?.gpsEnabled, true) // rolled back
        XCTAssertNotNil(m.toast)
    }

    func testOpenBoxRemembersWhereToGoBack() {
        let m = AppModel(api: ScriptedAPI(), prefs: MemoryPreferences(["bm_onboarded": "1"]))
        m.go(.home)
        m.openBox("b1")
        XCTAssertEqual(m.screen, .boxdetail)
        XCTAssertEqual(m.activeBoxId, "b1")
        m.openBox("b2") // detail → detail keeps the original origin
        m.backFromDetail()
        XCTAssertEqual(m.screen, .home)
    }

    func testLogoutClearsSessionState() async {
        let api = ScriptedAPI()
        api.boxesResult = .success([ScriptedAPI.sampleBox()])
        let m = AppModel(api: api, prefs: MemoryPreferences(["bm_onboarded": "1"]))
        await m.start()
        XCTAssertEqual(m.boxes.count, 1)
        m.logout()
        XCTAssertFalse(api.hasToken)
        XCTAssertFalse(m.authed)
        XCTAssertTrue(m.boxes.isEmpty)
        XCTAssertNil(m.me)
        XCTAssertEqual(m.screen, .home)
    }

    func testDeleteAccountSignsOut() async throws {
        let api = ScriptedAPI()
        let m = AppModel(api: api, prefs: MemoryPreferences())
        await m.start()
        try await m.deleteAccount()
        XCTAssertEqual(api.deleteCalls, 1)
        XCTAssertFalse(m.authed)
    }
}

// MARK: - M4: offline start, location

final class ScriptedLocation: LocationProvider, @unchecked Sendable {
    private let lock = NSLock()
    var result: LocationResult = .unavailable
    var calls = 0
    init(_ result: LocationResult = .unavailable) { self.result = result }
    func currentPosition() async -> LocationResult {
        lock.withLock { calls += 1 }
        return result
    }
}

@MainActor
final class AppModelOfflineAndLocationTests: XCTestCase {
    func testStartOfflineKeepsTheSessionAndToasts() async {
        let api = ScriptedAPI()
        api.meResult = .failure(APIError.transport("offline"))
        let m = AppModel(api: api, prefs: MemoryPreferences([AppModel.onboardedKey: "1"]))
        await m.start()
        XCTAssertTrue(m.authChecked)
        XCTAssertTrue(m.authed, "a network failure is not a rejected token")
        XCTAssertNil(m.me)
        XCTAssertEqual(m.toast, m.t(.toast_offline))

        api.meResult = .success(ScriptedAPI.sampleMe())
        api.boxesResult = .success([ScriptedAPI.sampleBox()])
        await m.reconnectIfNeeded()
        XCTAssertNotNil(m.me)
        XCTAssertEqual(m.boxes.count, 1)
        let calls = api.boxesCalls
        await m.reconnectIfNeeded() // already loaded → no extra calls
        XCTAssertEqual(api.boxesCalls, calls)
    }

    func testReconnectWithARejectedTokenLogsOut() async {
        let api = ScriptedAPI()
        api.meResult = .failure(APIError.transport("offline"))
        let m = AppModel(api: api, prefs: MemoryPreferences())
        await m.start()
        api.meResult = .failure(APIError.unauthorized)
        await m.reconnectIfNeeded()
        XCTAssertFalse(m.authed)
    }

    func testStartFetchesThePositionOnlyWhenGpsIsEnabled() async {
        let loc = ScriptedLocation(.position(GeoPoint(lat: 1, lng: 2)))
        let api = ScriptedAPI()
        api.meResult = .success(ScriptedAPI.sampleMe(gps: false))
        let m = AppModel(api: api, prefs: MemoryPreferences(), location: loc)
        await m.start()
        XCTAssertNil(m.userPos)
        XCTAssertEqual(loc.calls, 0)

        api.meResult = .success(ScriptedAPI.sampleMe(gps: true))
        let m2 = AppModel(api: api, prefs: MemoryPreferences(), location: loc)
        await m2.start()
        XCTAssertEqual(m2.userPos, GeoPoint(lat: 1, lng: 2))
    }

    func testALaunchTimeDenialStaysSilent() async {
        let api = ScriptedAPI()
        api.meResult = .success(ScriptedAPI.sampleMe(gps: true))
        let m = AppModel(api: api, prefs: MemoryPreferences(), location: ScriptedLocation(.denied))
        await m.start()
        XCTAssertNil(m.userPos)
        XCTAssertNil(m.toast)
    }

    func testTurningGpsOnLooksUpThePositionAndOffForgetsIt() async {
        let loc = ScriptedLocation(.position(GeoPoint(lat: 3, lng: 4)))
        let api = ScriptedAPI()
        api.meResult = .success(ScriptedAPI.sampleMe(gps: false))
        let m = AppModel(api: api, prefs: MemoryPreferences(), location: loc)
        await m.start()
        await m.updateMe(gpsEnabled: true)
        XCTAssertEqual(m.me?.gpsEnabled, true)
        XCTAssertEqual(m.userPos, GeoPoint(lat: 3, lng: 4))
        await m.updateMe(gpsEnabled: false)
        XCTAssertNil(m.userPos)
        XCTAssertEqual(loc.calls, 1)
    }

    func testTurningGpsOnWhenDeniedExplainsOnce() async {
        let api = ScriptedAPI()
        api.meResult = .success(ScriptedAPI.sampleMe(gps: false))
        let m = AppModel(api: api, prefs: MemoryPreferences(), location: ScriptedLocation(.denied))
        await m.start()
        await m.updateMe(gpsEnabled: true)
        XCTAssertEqual(m.toast, m.t(.gps_denied))
        XCTAssertNil(m.userPos)
    }

    func testAFailedSettingsSaveDoesNotTouchThePosition() async {
        let loc = ScriptedLocation(.position(GeoPoint(lat: 3, lng: 4)))
        let api = ScriptedAPI()
        api.meResult = .success(ScriptedAPI.sampleMe(gps: false))
        api.updateMeResult = .failure(Boom())
        let m = AppModel(api: api, prefs: MemoryPreferences(), location: loc)
        await m.start()
        await m.updateMe(gpsEnabled: true)
        XCTAssertEqual(m.toast, m.t(.toast_settings_failed))
        XCTAssertEqual(loc.calls, 0)
        XCTAssertEqual(m.me?.gpsEnabled, false) // rolled back
    }
}
