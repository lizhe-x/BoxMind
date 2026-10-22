import XCTest

/// M2 loop against the in-app mock backend (`-bm-mock`, no gateway needed): text entry → confirm → done;
/// items without a box → askbox; question → streamed answer with a box card; destructive agent command →
/// confirm card → execute → undo; hold-to-talk releases cleanly.
final class EntryFlowTests: XCTestCase {
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

    /// Wait for a chat bubble whose text contains `fragment` (bubbles scroll into view at the bottom).
    private func waitForBubble(_ app: XCUIApplication, containing fragment: String, timeout: TimeInterval = 60) -> Bool {
        app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", fragment)).firstMatch.waitForExistence(timeout: timeout)
    }

    @MainActor
    func testTextEntryAskAndAgentUndo() throws {
        let app = XCUIApplication()
        app.launchArguments = ["-bm-reset", "-bm-mock"]
        app.launch()
        signIn(app)

        // 1) Text entry with a box label → confirm card → saved
        let input = app.textFields["home.input"]
        input.tap()
        input.typeText("Box 1 also has a flashlight and two AA batteries")
        shot(app, "10-home-typed")
        app.buttons["home.send"].tap()
        XCTAssertTrue(app.staticTexts["entry.confirmTitle"].waitForExistence(timeout: 60), "interpret → confirm card")
        shot(app, "11-confirm")
        app.buttons["entry.save"].tap()
        XCTAssertTrue(app.staticTexts["entry.doneTitle"].waitForExistence(timeout: 30), "ingest → done")
        shot(app, "12-done")
        app.buttons["entry.done"].tap()
        XCTAssertTrue(app.buttons["home.lastBox"].waitForExistence(timeout: 5), "activity card after the first ingest")
        shot(app, "13-home-after")

        // 2) Items without a box → askbox → pick an existing box
        input.tap()
        input.typeText("a roll of duct tape")
        app.buttons["home.send"].tap()
        let pick = app.buttons["entry.pick.1"]
        XCTAssertTrue(pick.waitForExistence(timeout: 60), "askbox lists recent boxes")
        shot(app, "14-askbox")
        pick.tap()
        XCTAssertTrue(app.staticTexts["entry.doneTitle"].waitForExistence(timeout: 30))
        app.buttons["entry.done"].tap()

        // 3) Question → Ask screen, streamed answer, box card
        input.tap()
        input.typeText("Which box is the flashlight in?")
        app.buttons["home.send"].tap()
        XCTAssertTrue(app.buttons["ask.back"].waitForExistence(timeout: 60), "query routes to the chat")
        XCTAssertTrue(waitForBubble(app, containing: "is in Box 1"), "streamed answer finished")
        XCTAssertTrue(app.buttons["ask.box.1"].waitForExistence(timeout: 10), "box card under the answer")
        // Thumbs on the answer: tap down, it stays selected; tap again, it clears.
        let down = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'ask.down.'")).firstMatch
        XCTAssertTrue(down.waitForExistence(timeout: 5), "thumbs under the answer")
        down.tap()
        XCTAssertTrue(down.wait(for: \.isSelected, toEqual: true, timeout: 5))
        down.tap()
        XCTAssertTrue(down.wait(for: \.isSelected, toEqual: false, timeout: 5))
        shot(app, "15-ask-answer")

        // 4) Destructive agent command → confirm card → execute → undo
        let askInput = app.textFields["ask.input"]
        askInput.tap()
        askInput.typeText("delete box 4")
        app.buttons["ask.send"].tap()
        let confirm = app.buttons["ask.confirmActions"]
        XCTAssertTrue(confirm.waitForExistence(timeout: 60), "agent asks for confirmation")
        shot(app, "16-agent-confirm")
        confirm.tap()
        XCTAssertTrue(waitForBubble(app, containing: "Deleted Box 4"), "execution reported")
        shot(app, "17-agent-executed")
        askInput.tap()
        askInput.typeText("undo")
        app.buttons["ask.send"].tap()
        XCTAssertTrue(waitForBubble(app, containing: "Restored Box 4"), "undo reported")
        shot(app, "18-agent-undo")
        app.buttons["ask.back"].tap()
        XCTAssertTrue(app.buttons["tab.boxes"].waitForExistence(timeout: 5))
        app.buttons["tab.boxes"].tap()
        XCTAssertTrue(app.buttons["box.4"].waitForExistence(timeout: 10), "box 4 is back after undo")
        app.buttons["tab.home"].tap()

        // 5) Hold to talk releases cleanly (no mic / no speech model on the simulator → the typing hint)
        let talk = app.descendants(matching: .any)["home.talk"].firstMatch
        XCTAssertTrue(talk.waitForExistence(timeout: 5))
        talk.press(forDuration: 1.5)
        shot(app, "19-after-talk")
        XCTAssertTrue(app.textFields["home.input"].waitForExistence(timeout: 20), "back on home after release")
        XCTAssertFalse(app.staticTexts["Listening…"].exists, "recording overlay dismissed")
    }
}
