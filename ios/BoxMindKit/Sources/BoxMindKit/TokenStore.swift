import Foundation

/// Where the bearer token lives. The app uses the Keychain; tests use memory.
public protocol TokenStore: Sendable {
    func load() -> String?
    func save(_ token: String)
    func clear()
}

public final class MemoryTokenStore: TokenStore, @unchecked Sendable {
    private let lock = NSLock()
    private var token: String?

    public init(_ token: String? = nil) { self.token = token }

    public func load() -> String? { lock.withLock { token } }
    public func save(_ token: String) { lock.withLock { self.token = token } }
    public func clear() { lock.withLock { token = nil } }
}
