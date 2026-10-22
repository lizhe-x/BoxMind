import XCTest

/// End-to-end smoke test against the Debug backend (dev-mode login): sign in → onboarding → boxes → detail → settings.
/// Set TEST_RUNNER_BM_SHOT_DIR to a host directory to also save screenshots there.
final class SmokeTests: XCTestCase {
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
    func testSignInAndBrowse() throws {
        let app = XCUIApplication()
        app.launchArguments = ["-bm-reset"]
        app.launch()

        let email = app.textFields["login.email"]
        XCTAssertTrue(email.waitForExistence(timeout: 10), "login screen")
        email.tap()
        email.typeText("ios-test@example.com")
        shot(app, "01-login")
        app.buttons["login.getCode"].tap()

        let dev = app.staticTexts["login.devCode"]
        XCTAssertTrue(dev.waitForExistence(timeout: 15), "dev-mode code (backend must run without SMTP)")
        let code = dev.label
        let codeField = app.textFields["login.code"]
        codeField.tap()
        codeField.typeText(code)
        shot(app, "02-code")
        app.buttons["login.signIn"].tap()

        let skip = app.buttons["onboarding.skip"]
        XCTAssertTrue(skip.waitForExistence(timeout: 15), "onboarding after first sign-in")
        shot(app, "03-onboarding")
        skip.tap()

        XCTAssertTrue(app.buttons["tab.boxes"].waitForExistence(timeout: 5))
        shot(app, "04-home")
        app.buttons["tab.boxes"].tap()
        let first = app.buttons["box.1"]
        XCTAssertTrue(first.waitForExistence(timeout: 10), "seeded box 1")
        shot(app, "05-boxes")
        first.tap()
        XCTAssertTrue(app.staticTexts["Box 1"].waitForExistence(timeout: 5))
        shot(app, "06-detail")
        app.buttons["detail.back"].tap()
        XCTAssertTrue(app.buttons["tab.settings"].waitForExistence(timeout: 5))
        app.buttons["tab.settings"].tap()
        XCTAssertTrue(app.staticTexts["ios-test@example.com"].waitForExistence(timeout: 5))
        shot(app, "07-settings")
    }
}
