// HTTP client for the BoxMind backend. Port of frontend/src/api.ts.
import Foundation

public enum APIError: Error, Equatable, Sendable {
    /// No token stored: the app shows the login screen.
    case noAuth
    /// 401: the token was cleared, the app shows the login screen.
    case unauthorized
    /// Any other non-2xx; `detail` is the backend's `detail` field (often a stable code the UI translates).
    case http(status: Int, detail: String)
    case transport(String)
    case decoding(String)
}

public actor APIClient {
    public let baseURL: URL
    private let session: URLSession
    private let tokens: TokenStore

    public init(baseURL: URL, session: URLSession = .shared, tokens: TokenStore) {
        self.baseURL = baseURL
        self.session = session
        self.tokens = tokens
    }

    public nonisolated var hasToken: Bool { tokens.load() != nil }
    public nonisolated func logout() { tokens.clear() }

    // MARK: Public, unauthenticated

    public func health() async throws -> Bool {
        struct H: Decodable { let ok: Bool }
        let (data, _) = try await send(path: "/api/health", method: "GET", auth: false)
        return try decode(H.self, data).ok
    }

    public func requestCode(email: String) async throws -> CodeRequested {
        let (data, _) = try await send(path: "/api/auth/request-code", method: "POST",
                                       json: ["email": email], auth: false)
        return try decode(CodeRequested.self, data)
    }

    /// Verifies the code, stores the token, returns the account email.
    public func verifyCode(email: String, code: String) async throws -> String {
        struct T: Decodable { let token: String; let email: String? }
        let (data, _) = try await send(path: "/api/auth/verify-code", method: "POST",
                                       json: ["email": email, "code": code], auth: false)
        let t = try decode(T.self, data)
        tokens.save(t.token)
        return t.email ?? email
    }

    // MARK: Account

    public func me() async throws -> Me {
        try decode(Me.self, try await send(path: "/api/me", method: "GET").0)
    }

    public func updateMe(lang: String? = nil, gpsEnabled: Bool? = nil) async throws -> Me {
        var body: [String: Any] = [:]
        if let lang { body["lang"] = lang }
        if let gpsEnabled { body["gps_enabled"] = gpsEnabled }
        return try decode(Me.self, try await send(path: "/api/me", method: "PATCH", json: body).0)
    }

    public func deleteAccount() async throws {
        _ = try await send(path: "/api/me", method: "DELETE")
        tokens.clear()
    }

    // MARK: Boxes

    public func boxes() async throws -> [Box] {
        try decode([Box].self, try await send(path: "/api/boxes", method: "GET").0)
    }

    public func box(id: String) async throws -> Box {
        try decode(Box.self, try await send(path: "/api/boxes/\(id)", method: "GET").0)
    }

    /// Absolute URL for a `/media/...` path returned by the backend.
    public nonisolated func mediaURL(_ path: String) -> URL {
        URL(string: path, relativeTo: baseURL)?.absoluteURL ?? baseURL
    }

    // MARK: Plumbing

    func send(path: String, method: String, json: [String: Any]? = nil, body: Data? = nil, auth: Bool = true)
        async throws -> (Data, HTTPURLResponse) {
        var req = try request(path: path, method: method, auth: auth)
        if let json {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: json)
        } else if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = body
        }
        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await session.data(for: req)
        } catch {
            throw APIError.transport(error.localizedDescription)
        }
        return (data, try check(resp, data: data))
    }

    /// multipart/form-data upload of one file plus optional text fields (photo, audio, recognise, transcribe).
    func upload(path: String, clip: AudioClip, fields: [String: String], query: String? = nil)
        async throws -> (Data, HTTPURLResponse) {
        try await upload(path: path, fileData: clip.data, mimeType: clip.mimeType, filename: clip.filename,
                         fields: fields, query: query)
    }

    func upload(path: String, fileData: Data, mimeType: String, filename: String, fields: [String: String],
                query: String? = nil) async throws -> (Data, HTTPURLResponse) {
        var req = try request(path: path, method: "POST", auth: true, query: query)
        let boundary = "BoxMind-\(UUID().uuidString)"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.httpBody = Self.multipart(boundary: boundary, fileData: fileData, mimeType: mimeType,
                                      filename: filename, fields: fields)
        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await session.data(for: req)
        } catch {
            throw APIError.transport(error.localizedDescription)
        }
        return (data, try check(resp, data: data))
    }

    /// POST /api/ask and deliver decoded SSE events until the stream closes.
    func streamAsk(question: String, onEvent: @Sendable (AskEvent) -> Void) async throws {
        var req = try request(path: "/api/ask", method: "POST", auth: true)
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        req.httpBody = try JSONSerialization.data(withJSONObject: ["question": question])
        let bytes: URLSession.AsyncBytes
        let resp: URLResponse
        do {
            (bytes, resp) = try await session.bytes(for: req)
        } catch {
            throw APIError.transport(error.localizedDescription)
        }
        guard let http = resp as? HTTPURLResponse else { throw APIError.transport("not HTTP") }
        if http.statusCode == 401 {
            tokens.clear()
            throw APIError.unauthorized
        }
        guard (200..<300).contains(http.statusCode) else {
            var body = Data()
            for try await b in bytes { body.append(b) }
            throw APIError.http(status: http.statusCode, detail: Self.detail(from: body) ?? "HTTP \(http.statusCode)")
        }
        // Split on raw "\n" bytes ourselves: AsyncBytes.lines drops the blank lines that delimit SSE blocks.
        var parser = SSEParser()
        var line = Data()
        for try await byte in bytes {
            line.append(byte)
            if byte == UInt8(ascii: "\n") {
                for raw in parser.feed(String(decoding: line, as: UTF8.self)) {
                    if let ev = AskEvent(raw) { onEvent(ev) }
                }
                line.removeAll(keepingCapacity: true)
            }
        }
        for raw in parser.feed(String(decoding: line, as: UTF8.self) + "\n\n") { // flush an unterminated last block
            if let ev = AskEvent(raw) { onEvent(ev) }
        }
    }

    private func request(path: String, method: String, auth: Bool, query: String? = nil) throws -> URLRequest {
        var url = baseURL.appending(path: path)
        if let query { url = URL(string: url.absoluteString + "?" + query) ?? url }
        var req = URLRequest(url: url)
        req.httpMethod = method
        if auth {
            guard let token = tokens.load() else { throw APIError.noAuth }
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return req
    }

    private func check(_ resp: URLResponse, data: Data) throws -> HTTPURLResponse {
        guard let http = resp as? HTTPURLResponse else { throw APIError.transport("not HTTP") }
        if http.statusCode == 401 {
            tokens.clear()
            throw APIError.unauthorized
        }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError.http(status: http.statusCode, detail: Self.detail(from: data) ?? "HTTP \(http.statusCode)")
        }
        return http
    }

    nonisolated static func multipart(boundary: String, fileData: Data, mimeType: String, filename: String,
                                      fields: [String: String]) -> Data {
        var body = Data()
        func line(_ s: String) { body.append(Data(s.utf8)) }
        for (k, v) in fields.sorted(by: { $0.key < $1.key }) {
            line("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(k)\"\r\n\r\n\(v)\r\n")
        }
        line("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n")
        line("Content-Type: \(mimeType)\r\n\r\n")
        body.append(fileData)
        line("\r\n--\(boundary)--\r\n")
        return body
    }

    nonisolated func decode<T: Decodable>(_ type: T.Type, _ data: Data) throws -> T {
        do { return try JSON.decoder.decode(type, from: data) }
        catch { throw APIError.decoding(String(describing: error)) }
    }

    nonisolated static func detail(from data: Data) -> String? {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
        if let s = obj["detail"] as? String { return s }
        if let d = obj["detail"] { return String(describing: d) }
        return nil
    }
}
