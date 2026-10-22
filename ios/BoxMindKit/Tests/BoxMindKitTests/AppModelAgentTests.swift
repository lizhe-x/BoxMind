import XCTest
@testable import BoxMindKit

/// Mirrors "agent confirm card" in frontend/tests/store.test.ts, plus the streamed-answer edge cases.
@MainActor
final class AppModelAgentTests: XCTestCase {
    private let actions = [AgentAction(tool: "delete_box", args: .object(["box": .string("5")]), summary: "Delete box “5”")]

    private func model(_ api: ScriptedAPI) -> AppModel {
        AppModel(api: api, prefs: MemoryPreferences(["bm_onboarded": "1"]))
    }

    func testAConfirmResponseRendersACardInsteadOfExecuting() async {
        let api = ScriptedAPI()
        api.agentResult = .success(AgentResponse(type: .confirm, text: "", actions: actions, executed: nil))
        let m = model(api)
        await m.agentSend("delete box 5")
        XCTAssertFalse(m.thinking)
        let last = m.askMsgs.last
        XCTAssertEqual(last?.text, "Please confirm this action:")
        XCTAssertEqual(last?.confirm, actions)
        XCTAssertTrue(api.executeCalls.isEmpty)
        XCTAssertEqual(api.boxesCalls, 0)
    }

    func testAConfirmResponseWithExecutedSiblingsRefreshesTheBoxes() async {
        let api = ScriptedAPI()
        api.agentResult = .success(AgentResponse(type: .confirm, text: "", actions: actions,
                                                 executed: [.init(tool: "move_items", result: .object(["ok": .bool(true)]))]))
        let m = model(api)
        await m.agentSend("move then delete")
        XCTAssertEqual(api.boxesCalls, 1)
    }

    func testConfirmingExecutesEachActionClearsTheCardRefreshesAndReports() async {
        let api = ScriptedAPI()
        api.executeResults = [.success(ExecuteResult(ok: true, summary: "Deleted box “Box 5”"))]
        let m = model(api)
        m.askMsgs = [AskMsg(who: .ai, text: "confirm?", confirm: actions)]
        await m.agentConfirm(actions)
        XCTAssertEqual(api.executeCalls.first?.tool, "delete_box")
        XCTAssertEqual(api.executeCalls.first?.args, .object(["box": .string("5")]))
        XCTAssertNil(m.askMsgs[0].confirm)
        XCTAssertEqual(m.askMsgs.last?.text, "Deleted box “Box 5”")
        XCTAssertEqual(api.boxesCalls, 1)
        XCTAssertFalse(m.thinking)
    }

    func testAFailedExecutionIsReportedInlineNotThrown() async {
        let api = ScriptedAPI()
        api.executeResults = [.failure(Boom()), .success(ExecuteResult(ok: false, error: "box not found"))]
        let m = model(api)
        await m.agentConfirm(actions + actions)
        XCTAssertEqual(m.askMsgs.last?.text, "Failed; box not found")
    }

    func testCancelClearsTheCardAndAcknowledges() {
        let m = model(ScriptedAPI())
        m.askMsgs = [AskMsg(who: .ai, text: "confirm?", confirm: actions)]
        m.agentCancel()
        XCTAssertNil(m.askMsgs[0].confirm)
        XCTAssertEqual(m.askMsgs.last?.text, "OK, cancelled.")
    }

    func testAgentTransportErrorBecomesAChatMessage() async {
        let api = ScriptedAPI()
        api.agentResult = .failure(Boom())
        let m = model(api)
        await m.agentSend("x")
        XCTAssertFalse(m.thinking)
        XCTAssertTrue(m.askMsgs.last?.text.contains("Something went wrong") == true)
    }

    // MARK: streamed answers

    func testStreamErrorReplacesThePartialAnswer() async {
        let api = ScriptedAPI()
        api.askEvents = [.delta("half"), .error("llm down")]
        let m = model(api)
        await m.ask("q")
        XCTAssertEqual(m.askMsgs.map(\.text), ["q", "Something went wrong, please try again later."])
        XCTAssertFalse(m.thinking)
    }

    func testDoneAttachesBoxCardsAndCountsAQuery() async {
        let api = ScriptedAPI()
        let ref = BoxRef(id: "b1", label: "1", name: "Box 1", locationText: nil, colorA: "#000", colorB: "#111", gpsLat: nil, gpsLng: nil)
        api.askEvents = [.delta("Box 1."), .done(boxes: [ref], creditsLeft: -1)]
        let m = model(api)
        m.me = ScriptedAPI.sampleMe()
        await m.ask("where")
        XCTAssertEqual(m.askMsgs.last?.boxes, [ref])
        XCTAssertEqual(m.me?.used, 4)
    }

    func testChatSendRoutesNonQueriesToTheAgent() async {
        let api = ScriptedAPI()
        api.interpretResult = .success(ScriptedAPI.interpret(intent: .operation))
        api.agentResult = .success(AgentResponse(type: .message, text: "ok", actions: nil, executed: nil))
        let m = model(api)
        await m.chatSend("rename box 1")
        XCTAssertEqual(api.agentCalls.count, 1)
        XCTAssertTrue(api.askCalls.isEmpty)

        api.interpretResult = .failure(Boom()) // parse failure → asked as a question
        api.askEvents = [.done(boxes: [], creditsLeft: -1)]
        await m.chatSend("where is it")
        XCTAssertEqual(api.askCalls, ["where is it"])
    }

    func testLogoutClearsTheChat() async {
        let api = ScriptedAPI()
        let m = model(api)
        m.openAsk()
        XCTAssertEqual(m.askMsgs.count, 1)
        m.logout()
        XCTAssertTrue(m.askMsgs.isEmpty)
    }
}
