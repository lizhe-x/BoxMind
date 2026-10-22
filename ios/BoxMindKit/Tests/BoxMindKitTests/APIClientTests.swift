import XCTest
@testable import BoxMindKit

/// Scripted transport: records requests, replays canned responses (the Swift twin of the vitest fetch mock).
final class StubProtocol: URLProtocol {
    nonisolated(unsafe) static var handler: (@Sendable (URLRequest) -> (Int, Data))?
    nonisolated(unsafe) static var requests: [URLRequest] = []

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    /// URLProtocol sees POST bodies only as a stream; drain it so tests can assert on it.
    static func body(of request: URLRequest) -> Data {
        if let b = request.httpBody { return b }
        guard let stream = request.httpBodyStream else { return Data() }
        stream.open()
        defer { stream.close() }
        var out = Data()
        var buf = [UInt8](repeating: 0, count: 4096)
        while stream.hasBytesAvailable {
            let n = stream.read(&buf, maxLength: buf.count)
            if n <= 0 { break }
            out.append(buf, count: n)
        }
        return out
    }

    override func startLoading() {
        var req = request
        req.httpBody = Self.body(of: request)
        Self.requests.append(req)
        let (status, body) = Self.handler!(request)
        let resp = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

final class APIClientTests: XCTestCase {
    private var tokens: MemoryTokenStore!
    private var client: APIClient!

    override func setUp() {
        StubProtocol.requests = []
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [StubProtocol.self]
        tokens = MemoryTokenStore("tok-1")
        client = APIClient(baseURL: URL(string: "https://api.test")!, session: URLSession(configuration: cfg), tokens: tokens)
    }

    private static let meJSON = Data("""
    {"user_id":"u1","email":"a@b.co","lang":"en","gps_enabled":true,"credit_balance":50,"used":0,"box_count":2,"item_count":5}
    """.utf8)

    func testSendsBearerTokenAndParsesJSON() async throws {
        StubProtocol.handler = { _ in (200, Self.meJSON) }
        let me = try await client.me()
        XCTAssertEqual(me.boxCount, 2)
        XCTAssertEqual(StubProtocol.requests.first?.value(forHTTPHeaderField: "Authorization"), "Bearer tok-1")
        XCTAssertEqual(StubProtocol.requests.first?.url?.path, "/api/me")
    }

    func testRefusesToCallTheNetworkWithoutAToken() async {
        tokens.clear()
        StubProtocol.handler = { _ in (200, Self.meJSON) }
        do { _ = try await client.me(); XCTFail("expected noAuth") }
        catch let e as APIError { XCTAssertEqual(e, .noAuth) }
        catch { XCTFail("\(error)") }
        XCTAssertTrue(StubProtocol.requests.isEmpty)
    }

    func testA401ClearsTheStoredToken() async {
        StubProtocol.handler = { _ in (401, Data("{\"detail\":\"invalid token\"}".utf8)) }
        do { _ = try await client.me(); XCTFail("expected unauthorized") }
        catch let e as APIError { XCTAssertEqual(e, .unauthorized) }
        catch { XCTFail("\(error)") }
        XCTAssertNil(tokens.load())
        XCTAssertFalse(client.hasToken)
    }

    func testSurfacesTheBackendDetailAndStatusOnOtherErrors() async {
        StubProtocol.handler = { _ in (429, Data("{\"detail\":\"too_soon\"}".utf8)) }
        do { _ = try await client.requestCode(email: "a@b.co"); XCTFail("expected http error") }
        catch let e as APIError { XCTAssertEqual(e, .http(status: 429, detail: "too_soon")) }
        catch { XCTFail("\(error)") }
    }

    func testVerifyCodeStoresTheTokenAndLogoutRemovesIt() async throws {
        tokens.clear()
        StubProtocol.handler = { _ in (200, Data("{\"token\":\"tok-2\",\"user_id\":\"u1\",\"email\":\"a@b.co\"}".utf8)) }
        let email = try await client.verifyCode(email: "a@b.co", code: "123456")
        XCTAssertEqual(email, "a@b.co")
        XCTAssertEqual(tokens.load(), "tok-2")
        XCTAssertNil(StubProtocol.requests.first?.value(forHTTPHeaderField: "Authorization"))
        client.logout()
        XCTAssertNil(tokens.load())
    }

    func testDecodesBoxesWithBackendDates() async throws {
        let body = Data("""
        [{"id":"b1","label":"5","name":"Box 5","barcode":null,"photo_url":"/media/x.jpg","location_text":"garage",
          "gps_lat":null,"gps_lng":null,"color_a":"#9C7A52","color_b":"#7A5E3E","source":"voice",
          "created_at":"2026-10-20T08:00:00.123456+00:00","updated_at":"2026-10-20T08:00:00+00:00",
          "items":[{"id":"i1","name":"tent","qty_text":"×1","note":null,"created_at":"2026-10-20T08:00:00.1+00:00"}],
          "photos":["/media/x.jpg"],"audios":[]}]
        """.utf8)
        StubProtocol.handler = { _ in (200, body) }
        let boxes = try await client.boxes()
        XCTAssertEqual(boxes.count, 1)
        XCTAssertEqual(boxes[0].items.first?.qtyText, "×1")
        XCTAssertEqual(client.mediaURL(boxes[0].photoURL!).absoluteString, "https://api.test/media/x.jpg")
    }

    // MARK: M2 endpoints

    func testIngestSendsSnakeCaseBodyAndDecodesTheResult() async throws {
        StubProtocol.handler = { _ in (200, Data("""
        {"box":{"id":"b1","label":"5","name":"Box 5","barcode":null,"photo_url":null,"location_text":"garage","gps_lat":null,"gps_lng":null,"color_a":"#9C7A52","color_b":"#7A5E3E","source":"text","created_at":"2026-10-20T10:00:00.123456+00:00","updated_at":"2026-10-20T10:00:00+00:00","items":[],"photos":[],"audios":[]},"created":true,"credits_left":-1}
        """.utf8)) }
        let res = try await client.ingest(IngestRequest(boxLabel: "5", items: [ItemDraft(name: "headlamp", qtyText: "×1")],
                                                        gpsLat: 1, rawText: "raw", source: "voice"))
        XCTAssertTrue(res.created)
        XCTAssertEqual(res.box.location, "garage")
        let sent = try JSONSerialization.jsonObject(with: StubProtocol.requests[0].httpBody!) as! [String: Any]
        XCTAssertEqual(sent["box_label"] as? String, "5")
        XCTAssertEqual(sent["source"] as? String, "voice")
        XCTAssertEqual(sent["gps_lat"] as? Double, 1)
        XCTAssertEqual((sent["items"] as? [[String: Any]])?.first?["qty_text"] as? String, "×1")
        XCTAssertNil(sent["box_id"]) // absent, not null — matches the web client
    }

    func testUploadAudioIsMultipartWithTheClipsMimeType() async throws {
        StubProtocol.handler = { _ in (200, Data("{\"url\":\"/media/x.m4a\"}".utf8)) }
        let url = try await client.uploadAudio(boxId: "b1", clip: AudioClip(data: Data([1, 2, 3])))
        XCTAssertEqual(url, "/media/x.m4a")
        let req = StubProtocol.requests[0]
        XCTAssertEqual(req.url?.path, "/api/boxes/b1/audio")
        let ct = req.value(forHTTPHeaderField: "Content-Type") ?? ""
        XCTAssertTrue(ct.hasPrefix("multipart/form-data; boundary="))
        let body = String(decoding: req.httpBody!, as: UTF8.self)
        XCTAssertTrue(body.contains("name=\"file\"; filename=\"audio.m4a\""))
        XCTAssertTrue(body.contains("Content-Type: audio/mp4"))
    }

    func testTranscribeSendsTheLanguageField() async throws {
        StubProtocol.handler = { _ in (200, Data("{\"text\":\"box 5 has a lamp\"}".utf8)) }
        let text = try await client.transcribe(clip: AudioClip(data: Data([1])), language: "zh")
        XCTAssertEqual(text, "box 5 has a lamp")
        let body = String(decoding: StubProtocol.requests[0].httpBody!, as: UTF8.self)
        XCTAssertTrue(body.contains("name=\"language\"\r\n\r\nzh\r\n"))
    }

    func testAskStreamDecodesEventsAcrossTheWholeResponse() async throws {
        StubProtocol.handler = { _ in (200, Data("""
        event: delta
        data: {"t":"In "}

        event: delta
        data: {"t":"box 1"}

        event: done
        data: {"boxes":[{"id":"b1","label":"1","name":"Box 1","location_text":null,"color_a":"#000","color_b":"#111","gps_lat":null,"gps_lng":null}],"credits_left":-1}

        """.utf8)) }
        var events: [AskEvent] = []
        for try await e in client.askStream(question: "where") { events.append(e) }
        guard events.count == 3, !StubProtocol.requests.isEmpty else { return XCTFail("events \(events)") }
        XCTAssertEqual(events[0], .delta("In "))
        XCTAssertEqual(events[1], .delta("box 1"))
        if case .done(let boxes, _) = events[2] { XCTAssertEqual(boxes.first?.name, "Box 1") } else { XCTFail("\(events[2])") }
        let sent = try JSONSerialization.jsonObject(with: StubProtocol.requests[0].httpBody!) as! [String: Any]
        XCTAssertEqual(sent["question"] as? String, "where")
    }

    func testAskStreamSurfacesHTTPErrors() async {
        StubProtocol.handler = { _ in (502, Data("{\"detail\":\"llm_down\"}".utf8)) }
        do {
            for try await _ in client.askStream(question: "q") {}
            XCTFail("expected an error")
        } catch let e as APIError {
            XCTAssertEqual(e, .http(status: 502, detail: "llm_down"))
        } catch { XCTFail("\(error)") }
    }

    // MARK: M3 endpoints

    func testRecognizeIsMultipartAndDecodesConfidence() async throws {
        StubProtocol.handler = { _ in (200, Data("""
        {"box_label":"2","box_exists":true,"next_label":"5","items":[{"name":"tent","qty_text":"×1","confidence":"high"},{"name":"bag","qty_text":"some","confidence":"weird"}]}
        """.utf8)) }
        let r = try await client.recognize(photo: PhotoClip(data: Data([0xFF, 0xD8])))
        XCTAssertEqual(r.boxLabel, "2")
        XCTAssertTrue(r.boxExists)
        XCTAssertEqual(r.items.map(\.confidence), [.high, .medium]) // unknown confidence degrades to medium
        let req = StubProtocol.requests[0]
        XCTAssertEqual(req.url?.path, "/api/recognize")
        let body = String(decoding: req.httpBody!, as: UTF8.self)
        XCTAssertTrue(body.contains("name=\"file\"; filename=\"photo.jpg\""))
        XCTAssertTrue(body.contains("Content-Type: image/jpeg"))
    }

    func testResolveCodeOmitsAbsentKeys() async throws {
        let box = """
        {"id":"b7","label":"7","name":"Box 7","barcode":"BX-7","photo_url":null,"location_text":null,"gps_lat":null,"gps_lng":null,"color_a":"#000","color_b":"#111","source":"scan","created_at":"2026-10-20T10:00:00+00:00","updated_at":"2026-10-20T10:00:00+00:00","items":[],"photos":[],"audios":[]}
        """
        StubProtocol.handler = { _ in (200, Data("{\"box\":\(box),\"created\":true}".utf8)) }
        let r = try await client.resolveCode(code: nil, label: "7", create: true)
        XCTAssertTrue(r.created)
        XCTAssertEqual(r.box.barcode, "BX-7")
        let sent = try JSONSerialization.jsonObject(with: StubProtocol.requests[0].httpBody!) as! [String: Any]
        XCTAssertEqual(sent["label"] as? String, "7")
        XCTAssertEqual(sent["create"] as? Bool, true)
        XCTAssertNil(sent["code"])
    }

    func testUploadPhotoPassesSetCoverAsAQuery() async throws {
        StubProtocol.handler = { _ in (200, Data("{\"url\":\"/media/p.jpg\"}".utf8)) }
        let url = try await client.uploadPhoto(boxId: "b1", photo: PhotoClip(data: Data([1])), setCover: false)
        XCTAssertEqual(url, "/media/p.jpg")
        let req = StubProtocol.requests[0]
        XCTAssertEqual(req.url?.path, "/api/boxes/b1/photo")
        XCTAssertEqual(req.url?.query, "set_cover=false")
    }

    func testItemEndpointsUseTheRightVerbsAndBodies() async throws {
        let item = Data("""
        {"id":"i1","name":"lamp","qty_text":"×2","note":null,"created_at":"2026-10-20T10:00:00+00:00"}
        """.utf8)
        let box = Data("""
        {"id":"b1","label":"1","name":"Box 1","barcode":null,"photo_url":"/media/p.jpg","location_text":null,"gps_lat":null,"gps_lng":null,"color_a":"#000","color_b":"#111","source":"text","created_at":"2026-10-20T10:00:00+00:00","updated_at":"2026-10-20T10:00:00+00:00","items":[],"photos":["/media/p.jpg"],"audios":[]}
        """.utf8)
        StubProtocol.handler = { req in
            if req.httpMethod == "DELETE" { return (200, Data("{\"ok\":true}".utf8)) }
            return (200, req.url!.path.hasSuffix("/cover") ? box : item)
        }
        _ = try await client.addItem(boxId: "b1", name: "lamp", qtyText: nil)
        let updated = try await client.updateItem(boxId: "b1", itemId: "i1", name: nil, qtyText: "×2")
        try await client.deleteItem(boxId: "b1", itemId: "i1")
        let cover = try await client.setCover(boxId: "b1", url: "/media/p.jpg")
        XCTAssertEqual(cover.photoURL, "/media/p.jpg")
        XCTAssertEqual(updated.qtyText, "×2")
        let reqs = StubProtocol.requests
        XCTAssertEqual(reqs.map(\.httpMethod), ["POST", "PATCH", "DELETE", "POST"])
        XCTAssertEqual(reqs[0].url?.path, "/api/boxes/b1/items")
        XCTAssertEqual(reqs[1].url?.path, "/api/boxes/b1/items/i1")
        XCTAssertEqual(reqs[3].url?.path, "/api/boxes/b1/cover")
        let add = try JSONSerialization.jsonObject(with: reqs[0].httpBody!) as! [String: Any]
        XCTAssertEqual(add["name"] as? String, "lamp")
        XCTAssertNil(add["qty_text"])
        let patch = try JSONSerialization.jsonObject(with: reqs[1].httpBody!) as! [String: Any]
        XCTAssertEqual(patch["qty_text"] as? String, "×2")
        XCTAssertNil(patch["name"])
    }
}
