// Wire types. Mirror backend/app/schemas.py (and frontend/src/types.ts, the frozen web client).
import Foundation

public struct Item: Codable, Hashable, Identifiable, Sendable {
    public var id: String
    public var name: String
    public var qtyText: String
    public var note: String?
    public var createdAt: Date

    public init(id: String, name: String, qtyText: String, note: String? = nil, createdAt: Date) {
        self.id = id
        self.name = name
        self.qtyText = qtyText
        self.note = note
        self.createdAt = createdAt
    }

    enum CodingKeys: String, CodingKey {
        case id, name, note
        case qtyText = "qty_text"
        case createdAt = "created_at"
    }
}

public struct Box: Codable, Hashable, Identifiable, Sendable {
    public var id: String
    public var label: String
    public var name: String
    public var barcode: String?
    public var photoURL: String?
    public var locationText: String?
    public var gpsLat: Double?
    public var gpsLng: Double?
    public var colorA: String
    public var colorB: String
    public var source: String
    public var createdAt: Date
    public var updatedAt: Date
    public var items: [Item]
    public var photos: [String]
    public var audios: [String]

    public init(id: String, label: String, name: String, barcode: String? = nil, photoURL: String? = nil, locationText: String? = nil,
                gpsLat: Double? = nil, gpsLng: Double? = nil, colorA: String, colorB: String, source: String = "text",
                createdAt: Date, updatedAt: Date, items: [Item] = [], photos: [String] = [], audios: [String] = []) {
        self.id = id
        self.label = label
        self.name = name
        self.barcode = barcode
        self.photoURL = photoURL
        self.locationText = locationText
        self.gpsLat = gpsLat
        self.gpsLng = gpsLng
        self.colorA = colorA
        self.colorB = colorB
        self.source = source
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.items = items
        self.photos = photos
        self.audios = audios
    }

    /// Location text with blanks treated as unset (the backend stores "" for some sources).
    public var location: String? {
        let t = (locationText ?? "").trimmingCharacters(in: .whitespaces)
        return t.isEmpty ? nil : t
    }

    /// Cover photo URL path, or the first photo when no cover is set.
    public var cover: String? { photoURL ?? photos.first }

    enum CodingKeys: String, CodingKey {
        case id, label, name, barcode, source, items, photos, audios
        case photoURL = "photo_url"
        case locationText = "location_text"
        case gpsLat = "gps_lat"
        case gpsLng = "gps_lng"
        case colorA = "color_a"
        case colorB = "color_b"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

/// Compact box reference returned with a streamed answer.
public struct BoxRef: Codable, Hashable, Identifiable, Sendable {
    public var id: String
    public var label: String
    public var name: String
    public var locationText: String?
    public var colorA: String
    public var colorB: String
    public var gpsLat: Double?
    public var gpsLng: Double?

    public init(id: String, label: String, name: String, locationText: String? = nil, colorA: String, colorB: String,
                gpsLat: Double? = nil, gpsLng: Double? = nil) {
        self.id = id
        self.label = label
        self.name = name
        self.locationText = locationText
        self.colorA = colorA
        self.colorB = colorB
        self.gpsLat = gpsLat
        self.gpsLng = gpsLng
    }

    enum CodingKeys: String, CodingKey {
        case id, label, name
        case locationText = "location_text"
        case colorA = "color_a"
        case colorB = "color_b"
        case gpsLat = "gps_lat"
        case gpsLng = "gps_lng"
    }
}

public struct Me: Codable, Hashable, Sendable {
    public var userId: String
    public var email: String?
    public var lang: String
    public var gpsEnabled: Bool
    public var creditBalance: Int
    public var used: Int
    public var boxCount: Int
    public var itemCount: Int

    public init(userId: String, email: String? = nil, lang: String, gpsEnabled: Bool, creditBalance: Int = 0, used: Int = 0,
                boxCount: Int = 0, itemCount: Int = 0) {
        self.userId = userId
        self.email = email
        self.lang = lang
        self.gpsEnabled = gpsEnabled
        self.creditBalance = creditBalance
        self.used = used
        self.boxCount = boxCount
        self.itemCount = itemCount
    }

    enum CodingKeys: String, CodingKey {
        case email, lang, used
        case userId = "user_id"
        case gpsEnabled = "gps_enabled"
        case creditBalance = "credit_balance"
        case boxCount = "box_count"
        case itemCount = "item_count"
    }
}

public struct ItemDraft: Codable, Hashable, Sendable {
    public var name: String
    public var qtyText: String

    public init(name: String, qtyText: String) {
        self.name = name
        self.qtyText = qtyText
    }

    enum CodingKeys: String, CodingKey {
        case name
        case qtyText = "qty_text"
    }
}

public enum Intent: String, Codable, Sendable {
    case ingest, query, operation
}

public struct InterpretResult: Codable, Hashable, Sendable {
    public var intent: Intent
    public var boxLabel: String?
    public var box: Box?
    public var items: [ItemDraft]
    public var locationText: String?
    public var language: String
    public var nextLabel: String

    public init(intent: Intent, boxLabel: String? = nil, box: Box? = nil, items: [ItemDraft], locationText: String? = nil,
                language: String = "en", nextLabel: String) {
        self.intent = intent
        self.boxLabel = boxLabel
        self.box = box
        self.items = items
        self.locationText = locationText
        self.language = language
        self.nextLabel = nextLabel
    }

    enum CodingKeys: String, CodingKey {
        case intent, box, items, language
        case boxLabel = "box_label"
        case locationText = "location_text"
        case nextLabel = "next_label"
    }
}

public struct AgentAction: Codable, Hashable, Sendable {
    public var tool: String
    public var args: JSONValue
    public var summary: String

    public init(tool: String, args: JSONValue, summary: String) {
        self.tool = tool
        self.args = args
        self.summary = summary
    }
}

public struct AgentResponse: Codable, Hashable, Sendable {
    public enum Kind: String, Codable, Sendable { case message, confirm }
    public var type: Kind
    public var text: String
    public var actions: [AgentAction]?
    /// Non-destructive calls the agent already ran in this turn.
    public var executed: [Executed]?
    /// The recorded production trace; thumbs feedback goes to `POST /api/runs/{id}/feedback`.
    public var runId: String?

    public init(type: Kind, text: String, actions: [AgentAction]? = nil, executed: [Executed]? = nil,
                runId: String? = nil) {
        self.type = type
        self.text = text
        self.actions = actions
        self.executed = executed
        self.runId = runId
    }

    enum CodingKeys: String, CodingKey {
        case type, text, actions, executed
        case runId = "run_id"
    }

    public struct Executed: Codable, Hashable, Sendable {
        public var tool: String
        public var result: JSONValue

        public init(tool: String, result: JSONValue) {
            self.tool = tool
            self.result = result
        }
    }
}

/// Untyped JSON for tool arguments / results the model produces.
public enum JSONValue: Codable, Hashable, Sendable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case null
    case array([JSONValue])
    case object([String: JSONValue])

    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let b = try? c.decode(Bool.self) { self = .bool(b) }
        else if let n = try? c.decode(Double.self) { self = .number(n) }
        else if let s = try? c.decode(String.self) { self = .string(s) }
        else if let a = try? c.decode([JSONValue].self) { self = .array(a) }
        else if let o = try? c.decode([String: JSONValue].self) { self = .object(o) }
        else { throw DecodingError.dataCorruptedError(in: c, debugDescription: "unsupported JSON value") }
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let s): try c.encode(s)
        case .number(let n): try c.encode(n)
        case .bool(let b): try c.encode(b)
        case .null: try c.encodeNil()
        case .array(let a): try c.encode(a)
        case .object(let o): try c.encode(o)
        }
    }
}

public enum JSON {
    /// The backend emits ISO-8601 with fractional seconds and a +00:00 offset.
    public static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        let withFraction = Date.ISO8601FormatStyle(includingFractionalSeconds: true)
        let plain = Date.ISO8601FormatStyle()
        d.dateDecodingStrategy = .custom { decoder in
            let c = try decoder.singleValueContainer()
            let s = try c.decode(String.self)
            if let date = try? withFraction.parse(s) { return date }
            if let date = try? plain.parse(s) { return date }
            throw DecodingError.dataCorruptedError(in: c, debugDescription: "bad date \(s)")
        }
        return d
    }()

    public static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        return e
    }()
}

// MARK: - Request / response shapes added in M2

/// Body of POST /api/ingest (IngestIn).
public struct IngestRequest: Codable, Hashable, Sendable {
    public var boxId: String?
    public var boxLabel: String?
    public var items: [ItemDraft]
    public var locationText: String?
    public var gpsLat: Double?
    public var gpsLng: Double?
    public var rawText: String?
    public var source: String

    public init(boxId: String? = nil, boxLabel: String? = nil, items: [ItemDraft], locationText: String? = nil,
                gpsLat: Double? = nil, gpsLng: Double? = nil, rawText: String? = nil, source: String = "text") {
        self.boxId = boxId
        self.boxLabel = boxLabel
        self.items = items
        self.locationText = locationText
        self.gpsLat = gpsLat
        self.gpsLng = gpsLng
        self.rawText = rawText
        self.source = source
    }

    enum CodingKeys: String, CodingKey {
        case items, source
        case boxId = "box_id"
        case boxLabel = "box_label"
        case locationText = "location_text"
        case gpsLat = "gps_lat"
        case gpsLng = "gps_lng"
        case rawText = "raw_text"
    }
}

public struct IngestResult: Codable, Hashable, Sendable {
    public var box: Box
    public var created: Bool
    public var creditsLeft: Int

    public init(box: Box, created: Bool, creditsLeft: Int = -1) {
        self.box = box
        self.created = created
        self.creditsLeft = creditsLeft
    }

    enum CodingKeys: String, CodingKey {
        case box, created
        case creditsLeft = "credits_left"
    }
}

/// One turn of chat history sent to the agent.
public struct AgentMessage: Codable, Hashable, Sendable {
    public var role: String
    public var content: String

    public init(role: String, content: String) {
        self.role = role
        self.content = content
    }
}

/// Response of POST /api/agent/execute.
public struct ExecuteResult: Codable, Hashable, Sendable {
    public var ok: Bool
    public var summary: String?
    public var error: String?

    public init(ok: Bool, summary: String? = nil, error: String? = nil) {
        self.ok = ok
        self.summary = summary
        self.error = error
    }
}

/// A recorded or synthesised audio payload with the MIME type the backend stores it under.
public struct AudioClip: Hashable, Sendable {
    public var data: Data
    public var mimeType: String
    public var filename: String

    public init(data: Data, mimeType: String = "audio/mp4", filename: String = "audio.m4a") {
        self.data = data
        self.mimeType = mimeType
        self.filename = filename
    }
}

extension JSONValue {
    /// Foundation object for `JSONSerialization` (tool args are echoed back to the backend as-is).
    public var foundationObject: Any {
        switch self {
        case .string(let s): s
        case .number(let n): n
        case .bool(let b): b
        case .null: NSNull()
        case .array(let a): a.map(\.foundationObject)
        case .object(let o): o.mapValues(\.foundationObject)
        }
    }
}

// MARK: - Request / response shapes added in M3 (photo intake, scan, box editing)

public enum Confidence: String, Codable, Hashable, Sendable {
    case high, medium, low
}

/// One item the vision model saw in a photo (`/api/recognize`).
public struct RecogItem: Codable, Hashable, Sendable {
    public var name: String
    public var qtyText: String
    public var confidence: Confidence

    public init(name: String, qtyText: String, confidence: Confidence) {
        self.name = name
        self.qtyText = qtyText
        self.confidence = confidence
    }

    enum CodingKeys: String, CodingKey {
        case name, confidence
        case qtyText = "qty_text"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = try c.decode(String.self, forKey: .name)
        qtyText = try c.decode(String.self, forKey: .qtyText)
        confidence = (try? c.decode(Confidence.self, forKey: .confidence)) ?? .medium // unknown strings degrade
    }
}

public struct RecogResult: Codable, Hashable, Sendable {
    public var boxLabel: String?
    public var boxExists: Bool
    public var items: [RecogItem]
    public var nextLabel: String

    public init(boxLabel: String? = nil, boxExists: Bool = false, items: [RecogItem], nextLabel: String) {
        self.boxLabel = boxLabel
        self.boxExists = boxExists
        self.items = items
        self.nextLabel = nextLabel
    }

    enum CodingKeys: String, CodingKey {
        case items
        case boxLabel = "box_label"
        case boxExists = "box_exists"
        case nextLabel = "next_label"
    }
}

/// The editable recognition result on the camera screen (web `RecogDraft`).
public struct RecogDraft: Hashable, Sendable {
    public struct Item: Hashable, Sendable {
        public var name: String
        public var qtyText: String
        public var confidence: Confidence
        public var selected: Bool

        public init(name: String, qtyText: String, confidence: Confidence, selected: Bool) {
            self.name = name
            self.qtyText = qtyText
            self.confidence = confidence
            self.selected = selected
        }
    }

    public var boxLabel: String?
    public var boxExists: Bool
    public var nextLabel: String
    public var items: [Item]

    public init(boxLabel: String?, boxExists: Bool, nextLabel: String, items: [Item]) {
        self.boxLabel = boxLabel
        self.boxExists = boxExists
        self.nextLabel = nextLabel
        self.items = items
    }

    /// Label the items go into: the handwritten one when seen, else the next free number.
    public var targetLabel: String { boxLabel ?? nextLabel }
    public var selectedCount: Int { items.filter(\.selected).count }
}

/// `/api/boxes/resolve` answer.
public struct ResolveResult: Codable, Hashable, Sendable {
    public var box: Box
    public var created: Bool

    public init(box: Box, created: Bool) {
        self.box = box
        self.created = created
    }
}

/// A JPEG ready for upload (already downscaled on the device).
public struct PhotoClip: Hashable, Sendable {
    public var data: Data
    public var mimeType: String
    public var filename: String

    public init(data: Data, mimeType: String = "image/jpeg", filename: String = "photo.jpg") {
        self.data = data
        self.mimeType = mimeType
        self.filename = filename
    }
}
