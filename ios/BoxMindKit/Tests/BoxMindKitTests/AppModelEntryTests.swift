import XCTest
@testable import BoxMindKit

/// Mirrors "submitText routes one sentence to the right pipeline", "confirmEntry writes through"
/// and "voice recording hand-off" in frontend/tests/store.test.ts.
@MainActor
final class AppModelEntryTests: XCTestCase {
    private let headlamp = [ItemDraft(name: "headlamp", qtyText: "×1")]

    private func model(_ api: ScriptedAPI = ScriptedAPI()) -> AppModel {
        AppModel(api: api, prefs: MemoryPreferences(["bm_onboarded": "1"]))
    }

    // MARK: submitText routing

    func testIngestWithABoxLabelShowsTheConfirmCard() async {
        let api = ScriptedAPI()
        api.interpretResult = .success(ScriptedAPI.interpret(boxLabel: "5", items: headlamp))
        let m = model(api)
        await m.submitText("box 5 has a headlamp")
        XCTAssertEqual(m.entryPhase, .confirm)
        XCTAssertEqual(m.parsed?.items, headlamp)
        XCTAssertEqual(m.rawText, "box 5 has a headlamp")
        XCTAssertEqual(api.interpretCalls.first?.text, "box 5 has a headlamp")
        XCTAssertNil(api.interpretCalls.first?.target)
    }

    func testIngestWithoutABoxLabelAsksWhichBox() async {
        let api = ScriptedAPI()
        api.interpretResult = .success(ScriptedAPI.interpret(items: headlamp))
        let m = model(api)
        await m.submitText("a headlamp")
        XCTAssertEqual(m.entryPhase, .askbox)
    }

    func testALockedTargetBoxSkipsAskboxAndIsForwardedToInterpret() async {
        let api = ScriptedAPI()
        api.interpretResult = .success(ScriptedAPI.interpret(items: headlamp))
        let m = model(api)
        m.setTargetBox(ScriptedAPI.sampleBox(id: "target"))
        await m.submitText("a headlamp")
        XCTAssertEqual(m.entryPhase, .confirm)
        XCTAssertEqual(api.interpretCalls.first?.target, "target")
    }

    func testIngestWithNoItemsGoesBackToInputWithAToast() async {
        let api = ScriptedAPI()
        api.interpretResult = .success(ScriptedAPI.interpret(boxLabel: "5"))
        let m = model(api)
        await m.submitText("hmm…")
        XCTAssertEqual(m.entryPhase, .input)
        XCTAssertTrue(m.toast?.contains("couldn't find any items") == true)
    }

    func testQueryOpensChatAndStreamsTheAnswer() async {
        let api = ScriptedAPI()
        api.interpretResult = .success(ScriptedAPI.interpret(intent: .query))
        api.askEvents = [.delta("In "), .delta("box 1"), .done(boxes: [], creditsLeft: -1)]
        let m = model(api)
        await m.submitText("where is the headlamp")
        XCTAssertEqual(m.screen, .ask)
        XCTAssertEqual(m.entryPhase, .idle)
        XCTAssertEqual(m.askMsgs.map(\.who), [.ai, .user, .ai]) // greeting + question + answer
        XCTAssertTrue(m.askMsgs[0].text.contains("where is the drill"))
        XCTAssertEqual(m.askMsgs[2].text, "In box 1")
        XCTAssertFalse(m.askMsgs[2].streaming)
        XCTAssertEqual(api.askCalls, ["where is the headlamp"])
        XCTAssertTrue(api.agentCalls.isEmpty)
    }

    func testOperationOpensChatAndCallsTheAgentWithHistoryAndGps() async {
        let api = ScriptedAPI()
        api.interpretResult = .success(ScriptedAPI.interpret(intent: .operation))
        api.agentResult = .success(AgentResponse(type: .message, text: "Renamed.", actions: nil, executed: nil))
        let m = model(api)
        m.userPos = GeoPoint(lat: 1, lng: 2)
        m.askMsgs = [AskMsg(who: .ai, text: "hi"), AskMsg(who: .user, text: "x"), AskMsg(who: .ai, text: "pending", confirm: [])]
        await m.submitText("rename box 7 to tools")
        XCTAssertFalse(m.thinking)
        let call = api.agentCalls.first
        XCTAssertEqual(call?.message, "rename box 7 to tools")
        XCTAssertEqual(call?.history, [AgentMessage(role: "assistant", content: "hi"), AgentMessage(role: "user", content: "x")])
        XCTAssertEqual(call?.gps, GeoPoint(lat: 1, lng: 2))
        XCTAssertEqual(m.askMsgs.last?.text, "Renamed.")
        XCTAssertTrue(api.askCalls.isEmpty)
    }

    func testInterpretFailureGoesBackToInputWithAToast() async {
        let api = ScriptedAPI()
        api.interpretResult = .failure(Boom())
        let m = model(api)
        await m.submitText("x")
        XCTAssertEqual(m.entryPhase, .input)
        XCTAssertEqual(m.toast, "The AI could not parse that, please try again")
    }

    func testIgnoresEmptyInputAndConcurrentSubmits() async {
        let api = ScriptedAPI()
        let m = model(api)
        await m.submitText("   ")
        XCTAssertTrue(api.interpretCalls.isEmpty)
        m.entryBusy = true
        await m.submitText("x")
        XCTAssertTrue(api.interpretCalls.isEmpty)
    }

    // MARK: confirmEntry

    func testConfirmIngestsUploadsAudioRefreshesAndReports() async {
        let api = ScriptedAPI()
        let parsed = ScriptedAPI.interpret(boxLabel: "5", items: headlamp, locationText: "garage")
        var saved = ScriptedAPI.sampleBox(label: "5")
        saved.locationText = "garage"
        api.ingestResult = .success(IngestResult(box: saved, created: true))
        api.uploadAudioResult = .failure(Boom()) // must not break the flow
        let m = model(api)
        m.parsed = parsed
        m.rawText = "raw"
        m.entrySource = .voice
        m.pendingAudio = AudioClip(data: Data([1]))
        m.userPos = GeoPoint(lat: 1, lng: 2)
        await m.confirmEntry()
        let req = api.ingestCalls.first
        XCTAssertNil(req?.boxId)
        XCTAssertEqual(req?.boxLabel, "5")
        XCTAssertEqual(req?.items, headlamp)
        XCTAssertEqual(req?.locationText, "garage")
        XCTAssertEqual(req?.gpsLat, 1)
        XCTAssertEqual(req?.gpsLng, 2)
        XCTAssertEqual(req?.rawText, "raw")
        XCTAssertEqual(req?.source, "voice")
        XCTAssertEqual(api.uploadAudioCalls.first?.boxId, "b1")
        XCTAssertEqual(m.entryPhase, .done)
        XCTAssertNil(m.pendingAudio)
        XCTAssertNil(m.targetBox)
        XCTAssertEqual(m.doneInfo, DoneInfo(boxId: "b1", title: "Created Box 5 and saved", line1: "headlamp ×1", line2: "Location: garage", markerTip: nil))
        XCTAssertEqual(api.boxesCalls, 1) // refresh
    }

    func testPickNewBoxUsesTheSuggestedLabelAndRemindsToWriteIt() async {
        let api = ScriptedAPI()
        api.ingestResult = .success(IngestResult(box: ScriptedAPI.sampleBox(label: "4"), created: true))
        let m = model(api)
        m.parsed = ScriptedAPI.interpret(items: headlamp, nextLabel: "4")
        await m.pickNewBox()
        XCTAssertEqual(api.ingestCalls.first?.boxLabel, "4")
        XCTAssertTrue(m.doneInfo?.markerTip?.contains("“4”") == true)
        XCTAssertEqual(m.doneInfo?.title, "Created Box 4 and saved")
    }

    func testPickExistingSavesIntoThatBox() async {
        let api = ScriptedAPI()
        api.ingestResult = .success(IngestResult(box: ScriptedAPI.sampleBox(id: "b9", label: "9"), created: false))
        let m = model(api)
        m.parsed = ScriptedAPI.interpret(items: headlamp)
        await m.pickExisting("b9")
        XCTAssertEqual(api.ingestCalls.first?.boxId, "b9")
        XCTAssertEqual(m.doneInfo?.title, "Saved to Box 9")
        XCTAssertEqual(m.doneInfo?.line2, "Location to be added")
    }

    func testIngestFailureKeepsTheConfirmCardAndToasts() async {
        let api = ScriptedAPI()
        api.ingestResult = .failure(Boom())
        let m = model(api)
        m.parsed = ScriptedAPI.interpret(boxLabel: "5", items: headlamp)
        m.entryPhase = .confirm
        await m.confirmEntry()
        XCTAssertEqual(m.entryPhase, .confirm)
        XCTAssertFalse(m.entryBusy)
        XCTAssertEqual(m.toast, "Saving failed, please try again")
    }

    // MARK: voice hand-off

    func testEmptyTranscriptFallsBackToTypingWithoutBreakingTheLoop() async {
        let api = ScriptedAPI()
        let m = model(api)
        m.beginRecording()
        XCTAssertEqual(m.entryPhase, .recording)
        XCTAssertEqual(m.entrySource, .voice)
        await m.finishRecording(text: "   ", audio: nil)
        XCTAssertEqual(m.entryPhase, .idle)
        XCTAssertEqual(m.screen, .home)
        XCTAssertTrue(m.toast?.contains("typing") == true)
        XCTAssertTrue(api.interpretCalls.isEmpty)
    }

    func testTranscriptWithAudioKeepsTheClipForTheIngest() async {
        let api = ScriptedAPI()
        api.interpretResult = .success(ScriptedAPI.interpret(boxLabel: "2", items: headlamp))
        let m = model(api)
        m.beginRecording()
        await m.finishRecording(text: "box 2 has a headlamp", audio: AudioClip(data: Data([7])))
        XCTAssertEqual(m.entryPhase, .confirm)
        XCTAssertEqual(m.pendingAudio?.data, Data([7]))
    }

    func testEditAndReparse() async {
        let api = ScriptedAPI()
        api.interpretResult = .success(ScriptedAPI.interpret(boxLabel: "5", items: headlamp))
        let m = model(api)
        await m.submitText("box 5 has a hedlamp")
        m.toEdit()
        XCTAssertEqual(m.entryPhase, .edit)
        m.cancelEdit()
        XCTAssertEqual(m.entryPhase, .confirm)
        m.toEdit()
        m.setRawText("box 5 has a headlamp")
        await m.reparse()
        XCTAssertEqual(api.interpretCalls.last?.text, "box 5 has a headlamp")
        XCTAssertEqual(m.entryPhase, .confirm)
    }
}
