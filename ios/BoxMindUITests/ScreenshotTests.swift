import XCTest

/// App Store screenshots (run on an iPhone 17 Pro Max simulator, 6.9", with `-bm-mock` so no backend is needed).
/// Export with `xcrun xcresulttool export attachments`; names are numbered in presentation order.
final class ScreenshotTests: XCTestCase {
    private func shot(_ app: XCUIApplication, _ name: String) {
        let a = XCTAttachment(screenshot: app.screenshot())
        a.name = name
        a.lifetime = .keepAlways
        add(a)
    }

    @MainActor
    private func signIn(_ app: XCUIApplication) {
        let email = app.textFields["login.email"]
        XCTAssertTrue(email.waitForExistence(timeout: 10))
        email.tap()
        email.typeText("ios-test@example.com")
        app.buttons["login.getCode"].tap()
        let dev = app.staticTexts["login.devCode"]
        XCTAssertTrue(dev.waitForExistence(timeout: 15))
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
    func testCaptureStoreScreenshots() throws {
        let app = XCUIApplication()
        app.launchArguments = ["-bm-reset", "-bm-mock"]
        app.launch()
        signIn(app)
        usleep(500_000)
        shot(app, "01-home")

        // Entry confirm card
        let input = app.textFields["home.input"]
        input.tap()
        input.typeText("Box 1 also has a flashlight and two AA batteries")
        app.buttons["home.send"].tap()
        XCTAssertTrue(app.staticTexts["entry.confirmTitle"].waitForExistence(timeout: 30))
        usleep(600_000)
        shot(app, "02-entry-confirm")
        app.buttons["entry.save"].tap()
        XCTAssertTrue(app.staticTexts["entry.doneTitle"].waitForExistence(timeout: 30))
        usleep(600_000)
        shot(app, "03-entry-done")
        app.buttons["entry.done"].tap()

        // Ask: streamed answer with a box card
        input.tap()
        input.typeText("Which box is the flashlight in?")
        app.buttons["home.send"].tap()
        XCTAssertTrue(app.buttons["ask.box.1"].waitForExistence(timeout: 30))
        usleep(600_000)
        shot(app, "04-ask")
        app.buttons["ask.back"].tap()

        // Camera result sheet
        XCTAssertTrue(app.buttons["home.camera"].waitForExistence(timeout: 5))
        app.buttons["home.camera"].tap()
        let shutter = app.buttons["cam.shutter"]
        XCTAssertTrue(shutter.waitForExistence(timeout: 5))
        shutter.tap()
        XCTAssertTrue(app.staticTexts["cam.result"].waitForExistence(timeout: 30))
        usleep(700_000)
        shot(app, "05-camera-result")
        app.buttons["cam.back"].tap()

        // Scan found
        app.buttons["home.scan"].tap()
        let manual = app.buttons["scan.manualLink"]
        XCTAssertTrue(manual.waitForExistence(timeout: 5))
        manual.tap()
        let field = app.textFields["scan.manualField"]
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap()
        field.typeText("2")
        app.buttons["scan.manualConfirm"].tap()
        XCTAssertTrue(app.staticTexts["scan.found"].waitForExistence(timeout: 15))
        usleep(700_000)
        shot(app, "06-scan-found")
        app.buttons["scan.back"].tap()

        // Boxes grid and detail
        app.buttons["tab.boxes"].tap()
        XCTAssertTrue(app.buttons["box.1"].waitForExistence(timeout: 10))
        usleep(500_000)
        shot(app, "07-boxes")
        app.buttons["box.1"].tap()
        XCTAssertTrue(app.buttons["detail.back"].waitForExistence(timeout: 5))
        usleep(700_000)
        shot(app, "08-box-detail")
    }
}
