// Server-Sent Events parser for /api/ask. Port of the loop in frontend/src/api.ts (askStream):
// blocks are separated by a blank line, each carries one `event:` and one `data:` line.
import Foundation

public struct SSEEvent: Equatable, Sendable {
    public var event: String
    public var data: String
}

public struct SSEParser: Sendable {
    private var buffer = ""

    public init() {}

    /// Feed any chunk of text (it may split a line or a block anywhere) and get the complete events.
    public mutating func feed(_ chunk: String) -> [SSEEvent] {
        buffer += chunk
        var out: [SSEEvent] = []
        while let range = buffer.range(of: "\n\n") {
            let block = String(buffer[buffer.startIndex..<range.lowerBound])
            buffer.removeSubrange(buffer.startIndex..<range.upperBound)
            if let ev = Self.parseBlock(block) { out.append(ev) }
        }
        return out
    }

    private static func parseBlock(_ block: String) -> SSEEvent? {
        var event: String?
        var data: String?
        for line in block.split(separator: "\n", omittingEmptySubsequences: false) {
            if event == nil, line.hasPrefix("event: ") {
                event = String(line.dropFirst(7))
            } else if data == nil, line.hasPrefix("data: ") {
                data = String(line.dropFirst(6))
            }
        }
        guard let event, let data else { return nil }
        return SSEEvent(event: event, data: data)
    }
}

/// Decoded /api/ask events.
public enum AskEvent: Equatable, Sendable {
    case delta(String)
    case done(boxes: [BoxRef], creditsLeft: Int, runId: String? = nil)
    case error(String)

    public init?(_ raw: SSEEvent) {
        guard let data = raw.data.data(using: .utf8) else { return nil }
        switch raw.event {
        case "delta":
            struct D: Decodable { let t: String }
            guard let d = try? JSON.decoder.decode(D.self, from: data) else { return nil }
            self = .delta(d.t)
        case "done":
            struct D: Decodable { let boxes: [BoxRef]; let credits_left: Int; let run_id: String? }
            guard let d = try? JSON.decoder.decode(D.self, from: data) else { return nil }
            self = .done(boxes: d.boxes, creditsLeft: d.credits_left, runId: d.run_id)
        case "error":
            struct D: Decodable { let message: String }
            guard let d = try? JSON.decoder.decode(D.self, from: data) else { return nil }
            self = .error(d.message)
        default:
            return nil
        }
    }
}
