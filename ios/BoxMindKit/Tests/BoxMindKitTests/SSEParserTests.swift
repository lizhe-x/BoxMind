import XCTest
@testable import BoxMindKit

final class SSEParserTests: XCTestCase {
    private let stream = "event: delta\ndata: {\"t\":\"The \"}\n\nevent: delta\ndata: {\"t\":\"tent\"}\n\n"
        + "event: done\ndata: {\"boxes\":[{\"id\":\"b1\",\"label\":\"5\",\"name\":\"Box 5\",\"location_text\":null,"
        + "\"color_a\":\"#9C7A52\",\"color_b\":\"#7A5E3E\",\"gps_lat\":null,\"gps_lng\":null}],\"credits_left\":49}\n\n"

    /// Mirrors "reassembles events split across arbitrary chunk boundaries" in frontend/tests/api.test.ts.
    func testReassemblesAcrossArbitraryChunkBoundaries() {
        let expected: [AskEvent] = [
            .delta("The "), .delta("tent"),
            .done(boxes: [BoxRef(id: "b1", label: "5", name: "Box 5", locationText: nil,
                                 colorA: "#9C7A52", colorB: "#7A5E3E", gpsLat: nil, gpsLng: nil)],
                  creditsLeft: 49),
        ]
        for size in [1, 3, 7, 16, 64, 1000] {
            var parser = SSEParser()
            var got: [AskEvent] = []
            var rest = Substring(stream)
            while !rest.isEmpty {
                let chunk = rest.prefix(size)
                rest = rest.dropFirst(size)
                got += parser.feed(String(chunk)).compactMap(AskEvent.init)
            }
            XCTAssertEqual(got, expected, "chunk size \(size)")
        }
    }

    func testForwardsServerSideErrorEvents() {
        var parser = SSEParser()
        let events = parser.feed("event: error\ndata: {\"message\":\"gateway down\"}\n\n").compactMap(AskEvent.init)
        XCTAssertEqual(events, [.error("gateway down")])
    }

    func testIgnoresBlocksWithoutEventOrData() {
        var parser = SSEParser()
        XCTAssertEqual(parser.feed(": keep-alive\n\nevent: delta\n\n"), [])
    }


    func testDoneCarriesTheRunIdWhenPresent() {
        let raw = SSEEvent(event: "done", data: #"{"boxes": [], "credits_left": -1, "run_id": "abc123"}"#)
        XCTAssertEqual(AskEvent(raw), .done(boxes: [], creditsLeft: -1, runId: "abc123"))
        let old = SSEEvent(event: "done", data: #"{"boxes": [], "credits_left": -1}"#)
        XCTAssertEqual(AskEvent(old), .done(boxes: [], creditsLeft: -1, runId: nil))
    }
}
