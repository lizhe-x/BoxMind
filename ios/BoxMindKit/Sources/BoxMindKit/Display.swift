// Display helpers. Port of the bottom of frontend/src/store.ts and theme.ts.
import Foundation

public struct GeoPoint: Hashable, Sendable {
    public var lat: Double
    public var lng: Double
    public init(lat: Double, lng: Double) {
        self.lat = lat
        self.lng = lng
    }
}

public enum Display {
    /// The answer prompt says "no markdown", but models still leak **bold** / `code`; strip before showing or reading aloud.
    public static func plainText(_ text: String) -> String {
        text.replacing(/\*\*(.+?)\*\*/) { String($0.1) }
            .replacing(/`([^`]+)`/) { String($0.1) }
    }

    public static func fmtItems(_ items: [ItemDraft]) -> String {
        items.map { "\($0.name) \($0.qtyText)" }.joined(separator: " · ")
    }

    private static let monthsEN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    /// "just now" / "5 min ago" / "today" / "Oct 20" / "Oct 20, 2025" (zh: "10月20日" / "2025年10月20日").
    public static func fmtTime(_ date: Date, lang: Lang = .en, now: Date = Date(), calendar: Calendar = .current) -> String {
        let diff = now.timeIntervalSince(date)
        if diff < 90 { return L10n.tr(lang, .just_now) }
        if diff < 3600 { return L10n.tr(lang, .minutes_ago, ["n": Int(diff / 60)]) }
        if calendar.isDate(date, inSameDayAs: now) { return L10n.tr(lang, .today) }
        let c = calendar.dateComponents([.year, .month, .day], from: date)
        let sameYear = c.year == calendar.component(.year, from: now)
        let (y, m, d) = (c.year!, c.month!, c.day!)
        if lang == .zh {
            return sameYear ? "\(m)月\(d)日" : "\(y)年\(m)月\(d)日"
        }
        let md = "\(monthsEN[m - 1]) \(d)"
        return sameYear ? md : "\(md), \(y)"
    }

    /// A box is "new" for 24 h after creation.
    public static func isNewBox(_ box: Box, now: Date = Date()) -> Bool {
        now.timeIntervalSince(box.createdAt) < 86_400
    }

    /// Haversine distance text, or nil without a user position / box coordinates.
    public static func distText(userPos: GeoPoint?, lat: Double?, lng: Double?, lang: Lang = .en) -> String? {
        guard let userPos, let lat, let lng else { return nil }
        let r = 6371.0
        let dLat = (lat - userPos.lat) * .pi / 180
        let dLng = (lng - userPos.lng) * .pi / 180
        let a = pow(sin(dLat / 2), 2)
            + cos(userPos.lat * .pi / 180) * cos(lat * .pi / 180) * pow(sin(dLng / 2), 2)
        let km = 2 * r * asin(sqrt(a))
        if km < 0.2 { return L10n.tr(lang, .nearby) }
        let text = km < 10 ? String(format: "%.1f", km) : String(Int(km.rounded()))
        return L10n.tr(lang, .km_away, ["km": text])
    }

    /// Font size for a handwritten label inside a badge: short labels keep the base size, long ones shrink.
    public static func badgeFontSize(_ label: String, base: Double) -> Double {
        let n = label.count
        return n <= 2 ? base : n <= 4 ? (base * 0.78).rounded() : (base * 0.5).rounded()
    }
}
