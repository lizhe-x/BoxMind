#if DEBUG
// In-memory backend for UI tests and offline UI work (`-bm-mock`). It fakes just enough of the LLM
// endpoints to drive every screen: rule-based interpret, canned streamed answers, a delete/undo agent.
import Foundation
import BoxMindKit

final class MockAPI: BoxMindAPI, @unchecked Sendable {
    private let lock = NSLock()
    private var token: String?
    private var boxes: [Box]
    private var lastDeleted: Box?
    private var used = 0
    private var photoSeq = 0

    init() {
        let now = Date()
        func box(_ id: String, _ label: String, _ name: String, _ loc: String?, _ items: [(String, String)], colors: (String, String)) -> Box {
            Box(id: id, label: label, name: name, barcode: nil, photoURL: nil, locationText: loc, gpsLat: nil, gpsLng: nil,
                colorA: colors.0, colorB: colors.1, source: "text", createdAt: now.addingTimeInterval(-86_400 * 3), updatedAt: now.addingTimeInterval(-3600),
                items: items.enumerated().map { Item(id: "\(id)-\($0.offset)", name: $0.element.0, qtyText: $0.element.1, note: nil, createdAt: now) },
                photos: [], audios: [])
        }
        boxes = [
            box("b4", "4", "Box 4", nil, [], colors: ("#B08A5E", "#8A6A42")),
            box("bk", "Kitchen spare", "Kitchen spare", "Under the kitchen sink", [("Food containers", "×6"), ("Glasses", "×4")], colors: ("#A3835A", "#7D6241")),
            box("b2", "2", "Box 2", "Attic, by the window", [("Winter coats", "×3"), ("Snow boots", "×2")], colors: ("#9C7A52", "#7A5E3E")),
            box("b1", "1", "Box 1", "Garage, left shelf, 2nd tier", [("Tent", "×1"), ("Sleeping bag", "×2"), ("Headlamp", "×1")], colors: ("#9C7A52", "#6E5638")),
        ]
    }

    // MARK: Session

    var hasToken: Bool { lock.withLock { token != nil } }
    func logout() { lock.withLock { token = nil } }
    func requestCode(email: String) async throws -> CodeRequested { CodeRequested(sent: true, devMode: true, devCode: "123456") }
    func verifyCode(email: String, code: String) async throws -> String {
        guard code == "123456" else { throw APIError.http(status: 400, detail: "code_invalid") }
        lock.withLock { token = "mock" }
        return email
    }
    func me() async throws -> Me {
        try auth()
        return lock.withLock {
            Me(userId: "mock", email: "ios-test@example.com", lang: "en", gpsEnabled: false, creditBalance: 0, used: used,
               boxCount: boxes.count, itemCount: boxes.reduce(0) { $0 + $1.items.count })
        }
    }
    func updateMe(lang: String?, gpsEnabled: Bool?) async throws -> Me { try await me() }
    func deleteAccount() async throws { logout() }
    func boxes() async throws -> [Box] {
        try auth()
        return lock.withLock { boxes }
    }
    func box(id: String) async throws -> Box {
        guard let b = try await boxes().first(where: { $0.id == id }) else { throw APIError.http(status: 404, detail: "not found") }
        return b
    }
    func export(format: ExportFormat) async throws -> Data { Data("[]".utf8) }
    func mediaURL(_ path: String) -> URL { URL(string: "https://mock.invalid\(path)")! }

    // MARK: Entry

    func interpret(text: String, targetBoxId: String?) async throws -> InterpretResult {
        try auth()
        try await Task.sleep(for: .milliseconds(400))
        let low = text.lowercased()
        let next = lock.withLock { Self.nextLabel(boxes) }
        if low.hasSuffix("?") || ["where", "which", "how many", "what", "哪", "什么", "几"].contains(where: { low.contains($0) }) {
            return InterpretResult(intent: .query, boxLabel: nil, box: nil, items: [], locationText: nil, language: "en", nextLabel: next)
        }
        if ["delete", "rename", "move", "undo", "empty", "merge", "删除", "撤销", "改名"].contains(where: { low.hasPrefix($0) }) {
            return InterpretResult(intent: .operation, boxLabel: nil, box: nil, items: [], locationText: nil, language: "en", nextLabel: next)
        }
        var label: String?
        var rest = text
        if let m = text.range(of: #"(?i)^box\s+(\w+)\s+(also\s+)?(has|contains)\s+"#, options: .regularExpression) {
            let head = String(text[m])
            label = head.split(separator: " ")[1].description
            rest = String(text[m.upperBound...])
        }
        let items = rest.replacingOccurrences(of: ",", with: " and ")
            .components(separatedBy: " and ")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
            .map { Self.draft($0) }
        let existing = lock.withLock { boxes.first { $0.label == label } }
        return InterpretResult(intent: .ingest, boxLabel: label, box: existing, items: items, locationText: nil, language: "en", nextLabel: next)
    }

    func ingest(_ req: IngestRequest) async throws -> IngestResult {
        try auth()
        try await Task.sleep(for: .milliseconds(300))
        return lock.withLock {
            let now = Date()
            if let i = boxes.firstIndex(where: { $0.id == req.boxId || ($0.label == req.boxLabel && req.boxLabel != nil) }) {
                boxes[i].items += req.items.map { Item(id: UUID().uuidString, name: $0.name, qtyText: $0.qtyText, note: nil, createdAt: now) }
                boxes[i].updatedAt = now
                if let loc = req.locationText { boxes[i].locationText = loc }
                let b = boxes.remove(at: i)
                boxes.insert(b, at: 0)
                return IngestResult(box: b, created: false)
            }
            let label = req.boxLabel ?? Self.nextLabel(boxes)
            let b = Box(id: UUID().uuidString, label: label, name: "Box \(label)", barcode: nil, photoURL: nil, locationText: req.locationText,
                        gpsLat: req.gpsLat, gpsLng: req.gpsLng, colorA: "#9C7A52", colorB: "#7A5E3E", source: req.source, createdAt: now, updatedAt: now,
                        items: req.items.map { Item(id: UUID().uuidString, name: $0.name, qtyText: $0.qtyText, note: nil, createdAt: now) }, photos: [], audios: [])
            boxes.insert(b, at: 0)
            return IngestResult(box: b, created: true)
        }
    }

    func uploadAudio(boxId: String, clip: AudioClip) async throws -> String {
        lock.withLock {
            if let i = boxes.firstIndex(where: { $0.id == boxId }) { boxes[i].audios.append("/media/mock.m4a") }
        }
        return "/media/mock.m4a"
    }

    func transcribe(clip: AudioClip, language: String?) async throws -> String { "" }

    // MARK: Chat

    func askStream(question: String) -> AsyncThrowingStream<AskEvent, Error> {
        AsyncThrowingStream { c in
            Task {
                let hit = self.lock.withLock { self.boxes.first { b in b.items.contains { question.lowercased().contains($0.name.lowercased()) } } }
                let answer = hit.map { "The \(question.lowercased().contains("flashlight") ? "flashlight" : "item") is in **\($0.name)**, \($0.location ?? "location not set")." }
                    ?? "You have \(self.lock.withLock { self.boxes.count }) boxes."
                for word in answer.split(separator: " ", omittingEmptySubsequences: false) {
                    try? await Task.sleep(for: .milliseconds(60))
                    c.yield(.delta(String(word) + " "))
                }
                let refs = (hit.map { [$0] } ?? []).map {
                    BoxRef(id: $0.id, label: $0.label, name: $0.name, locationText: $0.locationText, colorA: $0.colorA, colorB: $0.colorB, gpsLat: $0.gpsLat, gpsLng: $0.gpsLng)
                }
                self.lock.withLock { self.used += 1 }
                c.yield(.done(boxes: refs, creditsLeft: -1))
                c.finish()
            }
        }
    }

    func agent(message: String, history: [AgentMessage], gps: GeoPoint?) async throws -> AgentResponse {
        try auth()
        try await Task.sleep(for: .milliseconds(500))
        let low = message.lowercased()
        if low.hasPrefix("delete box "), let label = low.split(separator: " ").last.map(String.init),
           let b = lock.withLock({ boxes.first { $0.label.lowercased() == label } }) {
            return AgentResponse(type: .confirm, text: "",
                                 actions: [AgentAction(tool: "delete_box", args: .object(["box": .string(b.label)]), summary: "Delete \(b.name) and its \(b.items.count) items")],
                                 executed: nil)
        }
        if low.hasPrefix("undo") {
            let restored: Box? = lock.withLock {
                guard let b = lastDeleted else { return nil }
                lastDeleted = nil
                boxes.append(b)
                return b
            }
            return AgentResponse(type: .message, text: restored.map { "Restored \($0.name)." } ?? "Nothing to undo.", actions: nil, executed: nil)
        }
        return AgentResponse(type: .message, text: "Done.", actions: nil, executed: nil)
    }

    func agentExecute(tool: String, args: JSONValue) async throws -> ExecuteResult {
        try auth()
        guard tool == "delete_box", case .object(let o) = args, case .string(let label)? = o["box"] else {
            return ExecuteResult(ok: false, error: "unsupported")
        }
        return lock.withLock {
            guard let i = boxes.firstIndex(where: { $0.label == label }) else { return ExecuteResult(ok: false, error: "box not found") }
            lastDeleted = boxes.remove(at: i)
            return ExecuteResult(ok: true, summary: "Deleted \(lastDeleted!.name)")
        }
    }

    func tts(text: String) async throws -> AudioClip { AudioClip(data: Data(), mimeType: "audio/wav", filename: "tts") }

    // MARK: Photo intake / scan / box editing

    func recognize(photo: PhotoClip) async throws -> RecogResult {
        try auth()
        try await Task.sleep(for: .milliseconds(700))
        let next = lock.withLock { Self.nextLabel(boxes) }
        return RecogResult(boxLabel: nil, boxExists: false, items: [
            RecogItem(name: "Backpack", qtyText: "×1", confidence: .high),
            RecogItem(name: "Camping stove", qtyText: "×1", confidence: .medium),
            RecogItem(name: "Gloves", qtyText: "some", confidence: .low),
        ], nextLabel: next)
    }

    func resolveCode(code: String?, label: String?, create: Bool) async throws -> ResolveResult {
        try auth()
        try await Task.sleep(for: .milliseconds(300))
        return try lock.withLock {
            if let code, let i = boxes.firstIndex(where: { $0.barcode == code }) { return ResolveResult(box: boxes[i], created: false) }
            if let label, let i = boxes.firstIndex(where: { $0.label.lowercased() == label.lowercased() }) {
                if let code, boxes[i].barcode == nil { boxes[i].barcode = code }
                return ResolveResult(box: boxes[i], created: false)
            }
            guard create, let name = label ?? code else { throw APIError.http(status: 404, detail: "box not found") }
            let now = Date()
            let b = Box(id: UUID().uuidString, label: name, name: "Box \(name)", barcode: code, colorA: "#A3835A", colorB: "#7D6241",
                        source: "scan", createdAt: now, updatedAt: now)
            boxes.insert(b, at: 0)
            return ResolveResult(box: b, created: true)
        }
    }

    func uploadPhoto(boxId: String, photo: PhotoClip, setCover: Bool) async throws -> String {
        try auth()
        return lock.withLock {
            photoSeq += 1
            let url = "/media/mock-\(photoSeq).jpg"
            if let i = boxes.firstIndex(where: { $0.id == boxId }) {
                boxes[i].photos.append(url)
                if setCover { boxes[i].photoURL = url }
            }
            return url
        }
    }

    func setCover(boxId: String, url: String) async throws -> Box {
        try auth()
        return try lock.withLock {
            guard let i = boxes.firstIndex(where: { $0.id == boxId }), boxes[i].photos.contains(url) else {
                throw APIError.http(status: 400, detail: "photo does not belong to this box")
            }
            boxes[i].photoURL = url
            return boxes[i]
        }
    }

    func addItem(boxId: String, name: String, qtyText: String?) async throws -> Item {
        try auth()
        return try lock.withLock {
            guard let i = boxes.firstIndex(where: { $0.id == boxId }) else { throw APIError.http(status: 404, detail: "box not found") }
            let item = Item(id: UUID().uuidString, name: name, qtyText: qtyText ?? "×1", note: nil, createdAt: Date())
            boxes[i].items.append(item)
            boxes[i].updatedAt = Date()
            return item
        }
    }

    func updateItem(boxId: String, itemId: String, name: String?, qtyText: String?) async throws -> Item {
        try auth()
        return try lock.withLock {
            guard let i = boxes.firstIndex(where: { $0.id == boxId }), let j = boxes[i].items.firstIndex(where: { $0.id == itemId }) else {
                throw APIError.http(status: 404, detail: "item not found")
            }
            if let name, !name.isEmpty { boxes[i].items[j].name = name }
            if let qtyText { boxes[i].items[j].qtyText = qtyText }
            return boxes[i].items[j]
        }
    }

    func deleteItem(boxId: String, itemId: String) async throws {
        try auth()
        try lock.withLock {
            guard let i = boxes.firstIndex(where: { $0.id == boxId }) else { throw APIError.http(status: 404, detail: "box not found") }
            boxes[i].items.removeAll { $0.id == itemId }
        }
    }

    // MARK: Helpers

    private func auth() throws {
        guard hasToken else { throw APIError.noAuth }
    }

    private static func nextLabel(_ boxes: [Box]) -> String {
        let used = Set(boxes.compactMap { Int($0.label) })
        var n = 1
        while used.contains(n) { n += 1 }
        return String(n)
    }

    private static func draft(_ phrase: String) -> ItemDraft {
        let words = phrase.split(separator: " ").map(String.init)
        let numbers = ["a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5]
        if let first = words.first?.lowercased(), let n = numbers[first] ?? Int(first), words.count > 1 {
            return ItemDraft(name: words.dropFirst().joined(separator: " "), qtyText: "×\(n)")
        }
        return ItemDraft(name: phrase, qtyText: "×1")
    }
}
#endif
