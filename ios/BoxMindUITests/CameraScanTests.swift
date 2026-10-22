import XCTest

/// M3 loop against the in-app mock backend (`-bm-mock`): photo intake → result sheet → save; scan with the
/// handwritten-label fallback → "record here" locks the target → typed entry skips the box question; box detail
/// item add / delete.
final class CameraScanTests: XCTestCase {
    private var shotDir: URL? {
        ProcessInfo.processInfo.environment["BM_SHOT_DIR"].map { URL(fileURLWithPath: $0) }
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        let s = app.screenshot()
        let a = XCTAttachment(screenshot: s)
        a.name = name
        a.lifetime = .keepAlways
        add(a)
        if let dir = shotDir {
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            try? s.pngRepresentation.write(to: dir.appending(path: "\(name).png"))
        }
    }

    @MainActor
    private func signIn(_ app: XCUIApplication) {
        let email = app.textFields["login.email"]
        XCTAssertTrue(email.waitForExistence(timeout: 10), "login screen")
        email.tap()
        email.typeText("ios-test@example.com")
        app.buttons["login.getCode"].tap()
        let dev = app.staticTexts["login.devCode"]
        XCTAssertTrue(dev.waitForExistence(timeout: 15), "dev-mode code")
        let codeField = app.textFields["login.code"]
        codeField.tap()
        codeField.typeText(dev.label)
        app.buttons["login.signIn"].tap()
        let skip = app.buttons["onboarding.skip"]
        XCTAssertTrue(skip.waitForExistence(timeout: 15))
        skip.tap()
        XCTAssertTrue(app.textFields["home.input"].waitForExistence(timeout: 5))
    }

    @MainActor
    func testPhotoIntakeScanFallbackAndItemEditing() throws {
        let app = XCUIApplication()
        app.launchArguments = ["-bm-reset", "-bm-mock"]
        app.launch()
        signIn(app)

        // 1) Photo intake: shutter (placeholder shot on the simulator) → result sheet → unselect / select → save
        app.buttons["home.camera"].tap()
        let shutter = app.buttons["cam.shutter"]
        XCTAssertTrue(shutter.waitForExistence(timeout: 5), "viewfinder")
        shot(app, "30-camera")
        shutter.tap()
        XCTAssertTrue(app.staticTexts["cam.result"].waitForExistence(timeout: 30), "recognition result sheet")
        usleep(600_000) // let the sheet finish sliding in before tapping inside it
        shot(app, "31-camera-result")
        XCTAssertEqual(app.textFields["cam.name.0"].value as? String, "Backpack")
        app.buttons["cam.toggle.2"].tap() // low-confidence item starts unchecked → select it
        app.buttons["cam.toggle.1"].tap() // and drop the stove
        let confirm = app.buttons["cam.confirm"]
        XCTAssertTrue(confirm.label.contains("2"), "two item types selected: \(confirm.label)")
        confirm.tap()
        XCTAssertTrue(app.staticTexts["entry.doneTitle"].waitForExistence(timeout: 30), "saved → done card on home")
        shot(app, "32-photo-done")
        app.buttons["entry.done"].tap()

        // 2) Scan: handwritten-label fallback creates box 7 → "record here" → typed entry goes straight to confirm
        app.buttons["home.scan"].tap()
        let manual = app.buttons["scan.manualLink"]
        XCTAssertTrue(manual.waitForExistence(timeout: 5), "scan screen")
        shot(app, "33-scan")
        manual.tap()
        let field = app.textFields["scan.manualField"]
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap()
        field.typeText("7")
        app.buttons["scan.manualConfirm"].tap()
        XCTAssertTrue(app.staticTexts["scan.found"].waitForExistence(timeout: 15), "found sheet")
        usleep(600_000)
        XCTAssertTrue(app.staticTexts["Box 7"].exists)
        shot(app, "34-scan-found")
        app.buttons["scan.recordHere"].tap()
        XCTAssertTrue(app.otherElements["home.target"].waitForExistence(timeout: 5) || app.staticTexts["home.target"].exists, "target chip")
        let input = app.textFields["home.input"]
        input.tap()
        input.typeText("a roll of duct tape")
        app.buttons["home.send"].tap()
        XCTAssertTrue(app.staticTexts["entry.confirmTitle"].waitForExistence(timeout: 30), "locked target → confirm, no askbox")
        shot(app, "35-target-confirm")
        app.buttons["entry.save"].tap()
        XCTAssertTrue(app.staticTexts["entry.doneTitle"].waitForExistence(timeout: 30))
        app.buttons["entry.done"].tap()

        // 3) Box detail: the new box 7 has the tape; add an item, then delete it
        app.buttons["tab.boxes"].tap()
        let box7 = app.buttons["box.7"]
        XCTAssertTrue(box7.waitForExistence(timeout: 10))
        box7.tap()
        XCTAssertTrue(app.textFields.matching(NSPredicate(format: "value CONTAINS %@", "duct tape")).firstMatch.waitForExistence(timeout: 5), "tape item")
        let add = app.textFields["detail.addField"]
        add.tap()
        add.typeText("Lantern")
        app.buttons["detail.add"].tap()
        let lantern = app.textFields.matching(NSPredicate(format: "value == %@", "Lantern")).firstMatch
        XCTAssertTrue(lantern.waitForExistence(timeout: 10), "item added")
        shot(app, "36-detail-edit")
        app.buttons["detail.deleteItem.Lantern"].tap()
        XCTAssertTrue(lantern.waitForNonExistence(timeout: 10), "item deleted")
        app.buttons["detail.back"].tap()
        XCTAssertTrue(app.buttons["tab.boxes"].waitForExistence(timeout: 5))
    }
}
