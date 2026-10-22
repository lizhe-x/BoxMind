import XCTest
@testable import BoxMindKit

/// Photo intake, scan and box editing: mirrors the "photo intake" / "scan" groups of store.test.ts.
@MainActor
final class AppModelCameraScanTests: XCTestCase {
    private var api: ScriptedAPI!
    private var model: AppModel!

    override func setUp() async throws {
        api = ScriptedAPI()
        api.boxesResult = .success([ScriptedAPI.sampleBox(id: "b1", label: "1")])
        model = AppModel(api: api, prefs: MemoryPreferences([AppModel.onboardedKey: "1"]))
        await model.start()
    }

    private func recog(_ items: [RecogItem], boxLabel: String? = nil, exists: Bool = false, next: String = "3") -> RecogResult {
        RecogResult(boxLabel: boxLabel, boxExists: exists, items: items, nextLabel: next)
    }

    private var shot: PhotoClip { PhotoClip(data: Data("img".utf8)) }

    // MARK: Photo intake

    func testLowConfidenceItemsStartUncheckedOthersChecked() async {
        api.recognizeResult = .success(recog([
            RecogItem(name: "backpack", qtyText: "×1", confidence: .high),
            RecogItem(name: "tent", qtyText: "×1", confidence: .medium),
            RecogItem(name: "gloves", qtyText: "some", confidence: .low),
        ], boxLabel: "2"))
        model.openCamera()
        XCTAssertEqual(model.screen, .camera)
        await model.recognizePhoto(shot)
        XCTAssertEqual(model.camPhase, .result)
        XCTAssertEqual(model.recog?.items.map(\.selected), [true, true, false])
        XCTAssertEqual(model.recog?.targetLabel, "2")
        XCTAssertEqual(model.pendingPhoto, shot)
        XCTAssertEqual(api.recognizeCalls.count, 1)
    }

    func testEmptyRecognitionReturnsToTheViewfinderWithAHint() async {
        api.recognizeResult = .success(recog([], next: "1"))
        await model.recognizePhoto(shot)
        XCTAssertEqual(model.camPhase, .live)
        XCTAssertNil(model.recog)
        XCTAssertEqual(model.toast, model.t(.recog_none))
    }

    func testA502FromTheVisionEndpointGetsASpecificMessage() async {
        api.recognizeResult = .failure(APIError.http(status: 502, detail: "vision_upstream_error"))
        await model.recognizePhoto(shot)
        XCTAssertEqual(model.camPhase, .live)
        XCTAssertEqual(model.toast, model.t(.recog_unavailable))
        api.recognizeResult = .failure(APIError.transport("offline"))
        await model.recognizePhoto(shot)
        XCTAssertEqual(model.toast, model.t(.recog_failed))
    }

    func testToggleEditAddThenConfirmIngestsOnlySelectedWithThePhotoAsCover() async {
        api.recognizeResult = .success(recog([
            RecogItem(name: "backpack", qtyText: "×1", confidence: .high),
            RecogItem(name: "gloves", qtyText: "some", confidence: .low),
        ]))
        await model.recognizePhoto(shot)
        model.toggleRecogItem(1)
        model.editRecogItem(1, qtyText: "×2")
        model.addRecogItem("  headlamp ")
        model.addRecogItem("   ")
        model.toggleRecogItem(99) // out of range → ignored
        XCTAssertEqual(model.recog?.items.map { [$0.name, $0.qtyText, "\($0.selected)"] },
                       [["backpack", "×1", "true"], ["gloves", "×2", "true"], ["headlamp", "×1", "true"]])
        model.toggleRecogItem(0)
        XCTAssertEqual(model.recog?.selectedCount, 2)

        let newBox = ScriptedAPI.sampleBox(id: "nb", label: "3")
        api.ingestResult = .success(IngestResult(box: newBox, created: true))
        api.boxesResult = .success([newBox])
        await model.confirmPhoto()

        let sent = api.ingestCalls.first
        XCTAssertEqual(sent?.boxLabel, "3")
        XCTAssertEqual(sent?.source, "photo")
        XCTAssertEqual(sent?.items, [ItemDraft(name: "gloves", qtyText: "×2"), ItemDraft(name: "headlamp", qtyText: "×1")])
        XCTAssertEqual(api.uploadPhotoCalls.count, 1)
        XCTAssertEqual(api.uploadPhotoCalls.first?.boxId, "nb")
        XCTAssertEqual(api.uploadPhotoCalls.first?.setCover, true)
        XCTAssertEqual(model.screen, .home)
        XCTAssertEqual(model.entryPhase, .done)
        XCTAssertEqual(model.camPhase, .live)
        XCTAssertNil(model.recog)
        XCTAssertNil(model.pendingPhoto)
        XCTAssertTrue(model.doneInfo?.markerTip?.contains("“3”") == true)
        XCTAssertEqual(model.doneInfo?.line2, model.t(.photo_line2))
        XCTAssertEqual(model.boxes.map(\.id), ["nb"]) // refreshed
    }

    func testConfirmWithNothingSelectedIsRefused() async {
        api.recognizeResult = .success(recog([RecogItem(name: "x", qtyText: "×1", confidence: .low)]))
        await model.recognizePhoto(shot)
        await model.confirmPhoto()
        XCTAssertTrue(api.ingestCalls.isEmpty)
        XCTAssertEqual(model.toast, model.t(.select_one))
        XCTAssertEqual(model.camPhase, .result)
    }

    func testAFailedPhotoUploadDoesNotUndoTheSavedItems() async {
        api.recognizeResult = .success(recog([RecogItem(name: "x", qtyText: "×1", confidence: .high)], boxLabel: "1", exists: true))
        await model.recognizePhoto(shot)
        api.ingestResult = .success(IngestResult(box: ScriptedAPI.sampleBox(id: "b1", label: "1"), created: false))
        api.uploadPhotoResult = .failure(Boom())
        await model.confirmPhoto()
        XCTAssertEqual(model.entryPhase, .done)
        XCTAssertNil(model.doneInfo?.markerTip) // existing box: no reminder to write the label
        XCTAssertEqual(model.doneInfo?.title, model.t(.done_saved, ["name": "Box 1"]))
    }

    func testIngestFailureKeepsTheResultSheetAndToasts() async {
        api.recognizeResult = .success(recog([RecogItem(name: "x", qtyText: "×1", confidence: .high)]))
        await model.recognizePhoto(shot)
        api.ingestResult = .failure(Boom())
        await model.confirmPhoto()
        XCTAssertEqual(model.camPhase, .result)
        XCTAssertFalse(model.entryBusy)
        XCTAssertEqual(model.toast, model.t(.toast_save_failed))
    }

    func testRetakeClearsTheDraft() async {
        api.recognizeResult = .success(recog([RecogItem(name: "x", qtyText: "×1", confidence: .high)]))
        await model.recognizePhoto(shot)
        model.retakePhoto()
        XCTAssertEqual(model.camPhase, .live)
        XCTAssertNil(model.recog)
    }

    // MARK: Scan

    func testUnknownCodeSuggestsTheHandwrittenLabelFallback() async {
        model.openScan()
        XCTAssertEqual(model.screen, .scan)
        api.resolveResult = .failure(APIError.http(status: 404, detail: "box not found"))
        await model.resolveScan("BX-1")
        XCTAssertEqual(model.scanPhase, .scanning)
        XCTAssertEqual(model.toast, model.t(.scan_unknown))
        XCTAssertEqual(api.resolveCalls.first?.code, "BX-1")
        XCTAssertEqual(api.resolveCalls.first?.create, false)
        api.resolveResult = .failure(APIError.transport("offline"))
        await model.resolveScan("BX-1")
        XCTAssertEqual(model.toast, model.t(.scan_failed))
    }

    func testAKnownCodeShowsTheBox() async {
        let found = ScriptedAPI.sampleBox(id: "found", label: "7")
        api.resolveResult = .success(ResolveResult(box: found, created: false))
        await model.resolveScan("BX-7")
        XCTAssertEqual(model.scanPhase, .found)
        XCTAssertEqual(model.foundBox?.id, "found")
    }

    func testManualLabelCreatesOrFindsABoxAndRecordHereLocksItAsTarget() async {
        let found = ScriptedAPI.sampleBox(id: "found", label: "7")
        api.resolveResult = .success(ResolveResult(box: found, created: true))
        await model.scanManual(" 7 ")
        XCTAssertEqual(api.resolveCalls.count, 1)
        XCTAssertNil(api.resolveCalls.first?.code)
        XCTAssertEqual(api.resolveCalls.first?.label, "7")
        XCTAssertEqual(api.resolveCalls.first?.create, true)
        XCTAssertEqual(model.scanPhase, .found)
        model.recordToFound()
        XCTAssertEqual(model.targetBox?.id, "found")
        XCTAssertEqual(model.screen, .home)
        await model.scanManual("   ")
        XCTAssertEqual(api.resolveCalls.count, 1) // blank ignored
    }

    func testManualLabelFailureToasts() async {
        api.resolveResult = .failure(Boom())
        await model.scanManual("7")
        XCTAssertEqual(model.toast, model.t(.op_failed))
        XCTAssertEqual(model.scanPhase, .scanning)
    }

    func testOpenScanResetsAPreviousResult() async {
        api.resolveResult = .success(ResolveResult(box: ScriptedAPI.sampleBox(id: "f"), created: false))
        await model.resolveScan("x")
        model.openScan()
        XCTAssertEqual(model.scanPhase, .scanning)
        XCTAssertNil(model.foundBox)
    }

    // MARK: Box editing

    func testBoxEditsWriteThroughAndRefresh() async {
        let before = api.boxesCalls
        await model.addBoxItem(boxId: "b1", name: "  lamp ")
        XCTAssertEqual(api.addItemCalls.first?.name, "lamp")
        await model.addBoxItem(boxId: "b1", name: "  ")
        XCTAssertEqual(api.addItemCalls.count, 1)
        await model.updateBoxItem(boxId: "b1", itemId: "i1", qtyText: "×3")
        XCTAssertEqual(api.updateItemCalls.first?.qtyText, "×3")
        XCTAssertNil(api.updateItemCalls.first?.name)
        await model.deleteBoxItem(boxId: "b1", itemId: "i1")
        XCTAssertEqual(api.deleteItemCalls.first?.itemId, "i1")
        await model.setBoxCover(boxId: "b1", url: "/media/p.jpg")
        XCTAssertEqual(api.setCoverCalls.first?.url, "/media/p.jpg")
        XCTAssertEqual(model.toast, model.t(.toast_cover_set))
        await model.addBoxPhoto(boxId: "b1", photo: shot, setCover: false)
        XCTAssertEqual(api.uploadPhotoCalls.first?.setCover, false)
        XCTAssertEqual(api.boxesCalls, before + 5)
    }

    func testBoxEditFailuresToastWithoutThrowing() async {
        api.itemResult = .failure(Boom())
        await model.addBoxItem(boxId: "b1", name: "lamp")
        XCTAssertEqual(model.toast, model.t(.toast_add_failed))
        await model.updateBoxItem(boxId: "b1", itemId: "i1", name: "x")
        XCTAssertEqual(model.toast, model.t(.toast_save_item_failed))
        api.deleteItemError = Boom()
        await model.deleteBoxItem(boxId: "b1", itemId: "i1")
        XCTAssertEqual(model.toast, model.t(.toast_delete_failed))
        api.setCoverResult = .failure(Boom())
        await model.setBoxCover(boxId: "b1", url: "/media/p.jpg")
        XCTAssertEqual(model.toast, model.t(.toast_cover_failed))
        api.uploadPhotoResult = .failure(Boom())
        await model.addBoxPhoto(boxId: "b1", photo: shot, setCover: true)
        XCTAssertEqual(model.toast, model.t(.toast_photo_failed))
    }
}
