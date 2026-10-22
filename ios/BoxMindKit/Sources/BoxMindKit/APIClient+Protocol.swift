import Foundation

extension APIClient: BoxMindAPI {
    public func export(format: ExportFormat) async throws -> Data {
        try await send(path: "/api/me/export.\(format.rawValue)", method: "GET").0
    }

    // MARK: Entry

    public func interpret(text: String, targetBoxId: String?) async throws -> InterpretResult {
        var body: [String: Any] = ["text": text]
        body["target_box_id"] = targetBoxId ?? NSNull()
        return try decode(InterpretResult.self, try await send(path: "/api/interpret", method: "POST", json: body).0)
    }

    public func ingest(_ req: IngestRequest) async throws -> IngestResult {
        let data = try JSON.encoder.encode(req)
        return try decode(IngestResult.self, try await send(path: "/api/ingest", method: "POST", body: data).0)
    }

    /// Returns the `/media/...` path of the stored clip.
    public func uploadAudio(boxId: String, clip: AudioClip) async throws -> String {
        struct U: Decodable { let url: String }
        let data = try await upload(path: "/api/boxes/\(boxId)/audio", clip: clip, fields: [:]).0
        return try decode(U.self, data).url
    }

    public func transcribe(clip: AudioClip, language: String?) async throws -> String {
        struct T: Decodable { let text: String? }
        var fields: [String: String] = [:]
        if let language { fields["language"] = language }
        let data = try await upload(path: "/api/transcribe", clip: clip, fields: fields).0
        return try decode(T.self, data).text ?? ""
    }

    // MARK: Chat

    public nonisolated func askStream(question: String) -> AsyncThrowingStream<AskEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    try await self.streamAsk(question: question) { continuation.yield($0) }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    public func agent(message: String, history: [AgentMessage], gps: GeoPoint?) async throws -> AgentResponse {
        var body: [String: Any] = [
            "message": message,
            "history": history.map { ["role": $0.role, "content": $0.content] },
        ]
        body["gps"] = gps.map { ["lat": $0.lat, "lng": $0.lng] as [String: Any] } ?? NSNull()
        return try decode(AgentResponse.self, try await send(path: "/api/agent", method: "POST", json: body).0)
    }

    public func agentExecute(tool: String, args: JSONValue) async throws -> ExecuteResult {
        let body: [String: Any] = ["tool": tool, "args": args.foundationObject]
        return try decode(ExecuteResult.self, try await send(path: "/api/agent/execute", method: "POST", json: body).0)
    }

    public func rateRun(id: String, value: Int) async throws {
        _ = try await send(path: "/api/runs/\(id)/feedback", method: "POST", json: ["value": value])
    }

    public func tts(text: String) async throws -> AudioClip {
        let (data, http) = try await send(path: "/api/tts", method: "POST", json: ["text": text])
        let mime = http.value(forHTTPHeaderField: "Content-Type") ?? "audio/wav"
        return AudioClip(data: data, mimeType: mime, filename: "tts")
    }

    // MARK: Photo intake / scan / box editing

    public func recognize(photo: PhotoClip) async throws -> RecogResult {
        let data = try await upload(path: "/api/recognize", fileData: photo.data, mimeType: photo.mimeType,
                                    filename: photo.filename, fields: [:]).0
        return try decode(RecogResult.self, data)
    }

    public func resolveCode(code: String?, label: String?, create: Bool) async throws -> ResolveResult {
        var body: [String: Any] = ["create": create] // absent keys stay absent, like the web client
        if let code { body["code"] = code }
        if let label { body["label"] = label }
        return try decode(ResolveResult.self, try await send(path: "/api/boxes/resolve", method: "POST", json: body).0)
    }

    public func uploadPhoto(boxId: String, photo: PhotoClip, setCover: Bool) async throws -> String {
        struct U: Decodable { let url: String }
        let data = try await upload(path: "/api/boxes/\(boxId)/photo", fileData: photo.data, mimeType: photo.mimeType,
                                    filename: photo.filename, fields: [:], query: "set_cover=\(setCover)").0
        return try decode(U.self, data).url
    }

    public func setCover(boxId: String, url: String) async throws -> Box {
        try decode(Box.self, try await send(path: "/api/boxes/\(boxId)/cover", method: "POST", json: ["url": url]).0)
    }

    public func addItem(boxId: String, name: String, qtyText: String?) async throws -> Item {
        var body: [String: Any] = ["name": name]
        if let qtyText { body["qty_text"] = qtyText }
        return try decode(Item.self, try await send(path: "/api/boxes/\(boxId)/items", method: "POST", json: body).0)
    }

    public func updateItem(boxId: String, itemId: String, name: String?, qtyText: String?) async throws -> Item {
        var body: [String: Any] = [:]
        if let name { body["name"] = name }
        if let qtyText { body["qty_text"] = qtyText }
        return try decode(Item.self, try await send(path: "/api/boxes/\(boxId)/items/\(itemId)", method: "PATCH", json: body).0)
    }

    public func deleteItem(boxId: String, itemId: String) async throws {
        _ = try await send(path: "/api/boxes/\(boxId)/items/\(itemId)", method: "DELETE")
    }
}
