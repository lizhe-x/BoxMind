import Foundation
@testable import BoxMindKit

/// Scripted backend for AppModel tests: the Swift twin of `vi.mock('../src/api')` in store.test.ts.
final class ScriptedAPI: BoxMindAPI, @unchecked Sendable {
    private let lock = NSLock()
    private var _token: String?
    var meResult: Result<Me, Error> = .success(ScriptedAPI.sampleMe())
    var boxesResult: Result<[Box], Error> = .success([])
    var updateMeResult: Result<Me, Error>?
    var updateCalls: [(lang: String?, gps: Bool?)] = []
    var deleteCalls = 0
    var boxesCalls = 0

    // M2 scripts
    var interpretResult: Result<InterpretResult, Error> = .failure(Boom())
    var interpretCalls: [(text: String, target: String?)] = []
    var ingestResult: Result<IngestResult, Error> = .failure(Boom())
    var ingestCalls: [IngestRequest] = []
    var uploadAudioResult: Result<String, Error> = .success("/media/a.m4a")
    var uploadAudioCalls: [(boxId: String, clip: AudioClip)] = []
    var transcribeResult: Result<String, Error> = .success("")
    var askEvents: [AskEvent] = []
    var askError: Error?
    var askCalls: [String] = []
    var agentResult: Result<AgentResponse, Error> = .failure(Boom())
    var agentCalls: [(message: String, history: [AgentMessage], gps: GeoPoint?)] = []
    var executeResults: [Result<ExecuteResult, Error>] = []
    var executeCalls: [(tool: String, args: JSONValue)] = []

    // M3 scripts
    var recognizeResult: Result<RecogResult, Error> = .failure(Boom())
    var recognizeCalls: [PhotoClip] = []
    var resolveResult: Result<ResolveResult, Error> = .failure(Boom())
    var resolveCalls: [(code: String?, label: String?, create: Bool)] = []
    var uploadPhotoResult: Result<String, Error> = .success("/media/x.jpg")
    var uploadPhotoCalls: [(boxId: String, photo: PhotoClip, setCover: Bool)] = []
    var setCoverResult: Result<Box, Error>?
    var setCoverCalls: [(boxId: String, url: String)] = []
    var itemResult: Result<Item, Error> = .success(Item(id: "i1", name: "x", qtyText: "×1", note: nil, createdAt: .now))
    var addItemCalls: [(boxId: String, name: String, qtyText: String?)] = []
    var updateItemCalls: [(boxId: String, itemId: String, name: String?, qtyText: String?)] = []
    var deleteItemError: Error?
    var deleteItemCalls: [(boxId: String, itemId: String)] = []

    init(token: String? = "tok") { _token = token }

    static func sampleMe(lang: String = "en", gps: Bool = true) -> Me {
        Me(userId: "u1", email: "a@b.co", lang: lang, gpsEnabled: gps, creditBalance: 50, used: 3, boxCount: 0, itemCount: 0)
    }

    static func sampleBox(id: String = "b1", label: String = "1", createdAt: Date = .now) -> Box {
        Box(id: id, label: label, name: "Box \(label)", barcode: nil, photoURL: nil, locationText: nil,
            gpsLat: nil, gpsLng: nil, colorA: "#9C7A52", colorB: "#7A5E3E", source: "text",
            createdAt: createdAt, updatedAt: createdAt, items: [], photos: [], audios: [])
    }

    var hasToken: Bool { lock.withLock { _token != nil } }
    func logout() { lock.withLock { _token = nil } }
    func requestCode(email: String) async throws -> CodeRequested { CodeRequested(sent: true, devMode: true, devCode: "123456") }
    func verifyCode(email: String, code: String) async throws -> String {
        lock.withLock { _token = "tok-new" }
        return email
    }
    func me() async throws -> Me { try meResult.get() }
    func updateMe(lang: String?, gpsEnabled: Bool?) async throws -> Me {
        lock.withLock { updateCalls.append((lang, gpsEnabled)) }
        if let r = updateMeResult { return try r.get() }
        var m = try meResult.get()
        if let lang { m.lang = lang }
        if let gpsEnabled { m.gpsEnabled = gpsEnabled }
        return m
    }
    func deleteAccount() async throws {
        lock.withLock { deleteCalls += 1; _token = nil }
    }
    func boxes() async throws -> [Box] {
        lock.withLock { boxesCalls += 1 }
        return try boxesResult.get()
    }
    func box(id: String) async throws -> Box { try boxesResult.get().first { $0.id == id }! }
    func export(format: ExportFormat) async throws -> Data { Data("[]".utf8) }
    func mediaURL(_ path: String) -> URL { URL(string: "https://api.test\(path)")! }

    func interpret(text: String, targetBoxId: String?) async throws -> InterpretResult {
        lock.withLock { interpretCalls.append((text, targetBoxId)) }
        return try interpretResult.get()
    }
    func ingest(_ req: IngestRequest) async throws -> IngestResult {
        lock.withLock { ingestCalls.append(req) }
        return try ingestResult.get()
    }
    func uploadAudio(boxId: String, clip: AudioClip) async throws -> String {
        lock.withLock { uploadAudioCalls.append((boxId, clip)) }
        return try uploadAudioResult.get()
    }
    func transcribe(clip: AudioClip, language: String?) async throws -> String { try transcribeResult.get() }
    func askStream(question: String) -> AsyncThrowingStream<AskEvent, Error> {
        let (events, error) = lock.withLock { askCalls.append(question); return (askEvents, askError) }
        return AsyncThrowingStream { c in
            for e in events { c.yield(e) }
            c.finish(throwing: error)
        }
    }
    func agent(message: String, history: [AgentMessage], gps: GeoPoint?) async throws -> AgentResponse {
        lock.withLock { agentCalls.append((message, history, gps)) }
        return try agentResult.get()
    }
    func agentExecute(tool: String, args: JSONValue) async throws -> ExecuteResult {
        let next: Result<ExecuteResult, Error> = lock.withLock {
            executeCalls.append((tool, args))
            return executeResults.isEmpty ? .failure(Boom()) : executeResults.removeFirst()
        }
        return try next.get()
    }
    func tts(text: String) async throws -> AudioClip { AudioClip(data: Data(), mimeType: "audio/wav", filename: "tts") }

    func recognize(photo: PhotoClip) async throws -> RecogResult {
        lock.withLock { recognizeCalls.append(photo) }
        return try recognizeResult.get()
    }
    func resolveCode(code: String?, label: String?, create: Bool) async throws -> ResolveResult {
        lock.withLock { resolveCalls.append((code, label, create)) }
        return try resolveResult.get()
    }
    func uploadPhoto(boxId: String, photo: PhotoClip, setCover: Bool) async throws -> String {
        lock.withLock { uploadPhotoCalls.append((boxId, photo, setCover)) }
        return try uploadPhotoResult.get()
    }
    func setCover(boxId: String, url: String) async throws -> Box {
        lock.withLock { setCoverCalls.append((boxId, url)) }
        if let r = setCoverResult { return try r.get() }
        return try boxesResult.get().first { $0.id == boxId } ?? Self.sampleBox(id: boxId)
    }
    func addItem(boxId: String, name: String, qtyText: String?) async throws -> Item {
        lock.withLock { addItemCalls.append((boxId, name, qtyText)) }
        return try itemResult.get()
    }
    func updateItem(boxId: String, itemId: String, name: String?, qtyText: String?) async throws -> Item {
        lock.withLock { updateItemCalls.append((boxId, itemId, name, qtyText)) }
        return try itemResult.get()
    }
    func deleteItem(boxId: String, itemId: String) async throws {
        lock.withLock { deleteItemCalls.append((boxId, itemId)) }
        if let e = deleteItemError { throw e }
    }

    static func interpret(intent: Intent = .ingest, boxLabel: String? = nil, box: Box? = nil,
                          items: [ItemDraft] = [], locationText: String? = nil, nextLabel: String = "1") -> InterpretResult {
        InterpretResult(intent: intent, boxLabel: boxLabel, box: box, items: items, locationText: locationText,
                        language: "en", nextLabel: nextLabel)
    }
}

struct Boom: Error {}
