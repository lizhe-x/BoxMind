import XCTest
@testable import BoxMindKit

/// Mirrors the "helpers" group of frontend/tests/store.test.ts and the i18n helper test.
final class DisplayTests: XCTestCase {
    func testI18nHelpers() {
        XCTAssertEqual(L10n.tr(.en, .items_n, ["n": 3]), "3 item types")
        XCTAssertEqual(L10n.tr(.zh, .items_n, ["n": 3]), "3 类物品")
        XCTAssertEqual(L10n.boxName(for: "4", lang: .en), "Box 4")
        XCTAssertEqual(L10n.boxName(for: "4号", lang: .zh), "4号箱")
        XCTAssertEqual(L10n.boxName(for: "Kitchen spare", lang: .en), "Kitchen spare")
        XCTAssertEqual(L10n.markerText("7号"), "7")
        XCTAssertEqual(L10n.markerText("ABC"), "ABC")
        XCTAssertEqual(L10n.authError(.en, detail: "too_soon", fallback: .err_send_failed), "Too many requests, wait a moment")
        XCTAssertEqual(L10n.authError(.zh, detail: "send_failed: smtp", fallback: .err_send_failed), "发送失败")
        XCTAssertEqual(L10n.authError(.en, detail: nil, fallback: .err_verify_failed), "Verification failed")
        XCTAssertEqual(L10n.authError(.en, detail: "HTTP 500", fallback: .err_verify_failed), "HTTP 500")
        XCTAssertEqual(Lang.norm("zh-Hans"), .zh)
        XCTAssertEqual(Lang.norm(nil), .en)
    }

    func testPlainTextStripsLeakedMarkdown() {
        XCTAssertEqual(Display.plainText("The **drill** is in `Box 2`."), "The drill is in Box 2.")
    }

    func testFmtItems() {
        XCTAssertEqual(Display.fmtItems([ItemDraft(name: "tent", qtyText: "×1"), ItemDraft(name: "poles", qtyText: "×2")]),
                       "tent ×1 · poles ×2")
    }

    func testFmtTimeBucketsInBothLanguages() {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "Asia/Shanghai")!
        let now = cal.date(from: DateComponents(year: 2026, month: 10, day: 20, hour: 15))!
        func at(_ seconds: TimeInterval) -> Date { now.addingTimeInterval(-seconds) }
        XCTAssertEqual(Display.fmtTime(at(30), lang: .en, now: now, calendar: cal), "just now")
        XCTAssertEqual(Display.fmtTime(at(5 * 60), lang: .en, now: now, calendar: cal), "5 min ago")
        XCTAssertEqual(Display.fmtTime(at(5 * 60), lang: .zh, now: now, calendar: cal), "5 分钟前")
        XCTAssertEqual(Display.fmtTime(at(3 * 3600), lang: .en, now: now, calendar: cal), "today")
        XCTAssertEqual(Display.fmtTime(at(3 * 3600), lang: .zh, now: now, calendar: cal), "今天")
        XCTAssertEqual(Display.fmtTime(at(2 * 86400), lang: .en, now: now, calendar: cal), "Oct 18")
        XCTAssertEqual(Display.fmtTime(at(2 * 86400), lang: .zh, now: now, calendar: cal), "10月18日")
        XCTAssertEqual(Display.fmtTime(at(400 * 86400), lang: .en, now: now, calendar: cal), "Sep 15, 2025")
        XCTAssertEqual(Display.fmtTime(at(400 * 86400), lang: .zh, now: now, calendar: cal), "2025年9月15日")
    }

    func testIsNewBoxIsA24hWindow() {
        let now = Date()
        XCTAssertTrue(Display.isNewBox(ScriptedAPI.sampleBox(createdAt: now.addingTimeInterval(-3600)), now: now))
        XCTAssertFalse(Display.isNewBox(ScriptedAPI.sampleBox(createdAt: now.addingTimeInterval(-90_000)), now: now))
    }

    func testDistTextUsesHaversineAndDegradesWithoutAPosition() {
        let home = GeoPoint(lat: 39.9042, lng: 116.4074)
        XCTAssertNil(Display.distText(userPos: nil, lat: 39.9, lng: 116.4))
        XCTAssertNil(Display.distText(userPos: home, lat: nil, lng: nil))
        XCTAssertEqual(Display.distText(userPos: home, lat: 39.9045, lng: 116.4075), "nearby")
        XCTAssertEqual(Display.distText(userPos: home, lat: 39.95, lng: 116.4074, lang: .en), "5.1 km away")
        XCTAssertEqual(Display.distText(userPos: home, lat: 40.2, lng: 116.4074, lang: .zh), "距你 33 km")
    }

    func testBadgeFontSizeShrinksLongLabels() {
        XCTAssertEqual(Display.badgeFontSize("7", base: 26), 26)
        XCTAssertEqual(Display.badgeFontSize("A12", base: 26), 20)
        XCTAssertEqual(Display.badgeFontSize("Kitchen spare", base: 26), 13)
    }
}
