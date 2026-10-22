import XCTest
@testable import BoxMindKit

/// Thumbs up / down on replies: the run id travels from the API into the message, the vote goes back.
@MainActor
final class AppModelFeedbackTests: XCTestCase {
    private func model(_ api: ScriptedAPI) -> AppModel {
        AppModel(api: api, prefs: MemoryPreferences(["bm_onboarded": "1"]))
    }

    func testAStreamedAnswerCarriesItsRunId() async {
        let api = ScriptedAPI()
        api.askEvents = [.delta("In box 1."), .done(boxes: [], creditsLeft: -1, runId: "run-ask")]
        let m = model(api)
        await m.ask("where is the tent")
        XCTAssertEqual(m.askMsgs.last?.runId, "run-ask")
        XCTAssertEqual(m.askMsgs.last?.feedback, 0)
    }

    func testAnAgentReplyAndAConfirmCardCarryTheirRunId() async {
        let api = ScriptedAPI()
        api.agentResult = .success(AgentResponse(type: .message, text: "Moved.", runId: "run-agent"))
        let m = model(api)
        await m.agentSend("move the drill to box 5")
        XCTAssertEqual(m.askMsgs.last?.runId, "run-agent")
        api.agentResult = .success(AgentResponse(type: .confirm, text: "", actions: [], runId: "run-confirm"))
        await m.agentSend("delete box 9")
        XCTAssertEqual(m.askMsgs.last?.runId, "run-confirm")
    }

    func testRatingSendsTheVoteAndTappingAgainClearsIt() async {
        let api = ScriptedAPI()
        let m = model(api)
        m.askMsgs = [AskMsg(who: .ai, text: "In box 1.", runId: "run-1")]
        let id = m.askMsgs[0].id
        await m.rate(id, 1)
        XCTAssertEqual(m.askMsgs[0].feedback, 1)
        await m.rate(id, -1)
        XCTAssertEqual(m.askMsgs[0].feedback, -1)
        await m.rate(id, -1)
        XCTAssertEqual(m.askMsgs[0].feedback, 0)
        XCTAssertEqual(api.rateCalls.map(\.value), [1, -1, 0])
        XCTAssertEqual(Set(api.rateCalls.map(\.id)), ["run-1"])
    }

    func testLocalMessagesCannotBeRated() async {
        let api = ScriptedAPI()
        let m = model(api)
        m.askMsgs = [AskMsg(who: .ai, text: "Hi there")]  // greeting: no run behind it
        await m.rate(m.askMsgs[0].id, 1)
        XCTAssertEqual(m.askMsgs[0].feedback, 0)
        XCTAssertTrue(api.rateCalls.isEmpty)
    }

    func testAFailedVoteIsRevertedAndToasted() async {
        let api = ScriptedAPI()
        api.rateResult = .failure(Boom())
        let m = model(api)
        m.askMsgs = [AskMsg(who: .ai, text: "x", runId: "run-1", feedback: 1)]
        await m.rate(m.askMsgs[0].id, -1)
        XCTAssertEqual(m.askMsgs[0].feedback, 1)
        XCTAssertNotNil(m.toast)
    }
}
