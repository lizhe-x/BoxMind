// Dependencies the app model needs from the platform. The app supplies real ones; tests supply fakes.
import Foundation

public struct CodeRequested: Decodable, Sendable {
    public var sent: Bool
    public var devMode: Bool?
    public var devCode: String?

    public init(sent: Bool, devMode: Bool? = nil, devCode: String? = nil) {
        self.sent = sent
        self.devMode = devMode
        self.devCode = devCode
    }

    enum CodingKeys: String, CodingKey {
        case sent
        case devMode = "dev_mode"
        case devCode = "dev_code"
    }
}

/// Everything the app model asks of the backend. `APIClient` is the real one; tests script it.
public protocol BoxMindAPI: Sendable {
    var hasToken: Bool { get }
    func logout()
    func requestCode(email: String) async throws -> CodeRequested
    func verifyCode(email: String, code: String) async throws -> String
    func me() async throws -> Me
    func updateMe(lang: String?, gpsEnabled: Bool?) async throws -> Me
    func deleteAccount() async throws
    func boxes() async throws -> [Box]
    func box(id: String) async throws -> Box
    func export(format: ExportFormat) async throws -> Data
    func mediaURL(_ path: String) -> URL

    // Entry
    func interpret(text: String, targetBoxId: String?) async throws -> InterpretResult
    func ingest(_ req: IngestRequest) async throws -> IngestResult
    func uploadAudio(boxId: String, clip: AudioClip) async throws -> String
    func transcribe(clip: AudioClip, language: String?) async throws -> String

    // Chat
    func askStream(question: String) -> AsyncThrowingStream<AskEvent, Error>
    func agent(message: String, history: [AgentMessage], gps: GeoPoint?) async throws -> AgentResponse
    func agentExecute(tool: String, args: JSONValue) async throws -> ExecuteResult
    /// Thumbs on a recorded run: 1 up, -1 down, 0 clears.
    func rateRun(id: String, value: Int) async throws
    func tts(text: String) async throws -> AudioClip

    // Photo intake / scan / box editing (M3)
    func recognize(photo: PhotoClip) async throws -> RecogResult
    func resolveCode(code: String?, label: String?, create: Bool) async throws -> ResolveResult
    /// Returns the `/media/...` path of the stored photo.
    func uploadPhoto(boxId: String, photo: PhotoClip, setCover: Bool) async throws -> String
    func setCover(boxId: String, url: String) async throws -> Box
    func addItem(boxId: String, name: String, qtyText: String?) async throws -> Item
    func updateItem(boxId: String, itemId: String, name: String?, qtyText: String?) async throws -> Item
    func deleteItem(boxId: String, itemId: String) async throws
}

public enum ExportFormat: String, Sendable {
    case json, csv
}

/// Small string key-value store (UserDefaults in the app, memory in tests). Replaces localStorage.
public protocol PreferenceStore: Sendable {
    func string(_ key: String) -> String?
    func set(_ value: String?, for key: String)
}

public final class MemoryPreferences: PreferenceStore, @unchecked Sendable {
    private let lock = NSLock()
    private var values: [String: String]

    public init(_ values: [String: String] = [:]) { self.values = values }

    public func string(_ key: String) -> String? { lock.withLock { values[key] } }
    public func set(_ value: String?, for key: String) { lock.withLock { values[key] = value } }
}

/// Outcome of a one-shot position lookup.
public enum LocationResult: Equatable, Sendable {
    case position(GeoPoint)
    /// The user refused (or the system restricts) location access.
    case denied
    /// No fix in time, no hardware, or the request failed.
    case unavailable
}

/// One-shot position lookup (asks for permission on first use). The app degrades silently except for `denied`,
/// which gets one hint when the user turns the GPS switch on.
public protocol LocationProvider: Sendable {
    func currentPosition() async -> LocationResult
}

public struct NoLocation: LocationProvider {
    public init() {}
    public func currentPosition() async -> LocationResult { .unavailable }
}
