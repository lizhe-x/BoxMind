// Design tokens. Port of frontend/src/theme.ts / docs/design/README.md.
import SwiftUI
import BoxMindKit

enum BM {
    static let bgApp = Color(hex: 0x0A0D15)
    static let bgPage = Color(hex: 0x05070C)
    static let card = Color(hex: 0x11151F)
    static let card2 = Color(hex: 0x141A28)
    static let sheet = Color(hex: 0x0E1320)
    static let border = Color.white.opacity(0.07)
    static let border8 = Color.white.opacity(0.08)
    static let borderHi = Color(hex: 0x7C8CFF).opacity(0.25)
    static let text = Color(hex: 0xF2F5FA)
    static let textSub = Color(hex: 0xEBF0FA).opacity(0.5)
    static let textSub55 = Color(hex: 0xEBF0FA).opacity(0.55)
    static let textWeak = Color(hex: 0xEBF0FA).opacity(0.45)
    static let textWeak35 = Color(hex: 0xEBF0FA).opacity(0.35)
    static let textWeak30 = Color(hex: 0xEBF0FA).opacity(0.3)
    static let gradA = Color(hex: 0x4D7CFE)
    static let gradB = Color(hex: 0x8B5CF6)
    static let grad = LinearGradient(colors: [gradA, gradB], startPoint: .topLeading, endPoint: .bottomTrailing)
    static let gradGreen = LinearGradient(colors: [Color(hex: 0x34D399), Color(hex: 0x10B981)], startPoint: .topLeading, endPoint: .bottomTrailing)
    static let blue = Color(hex: 0x93A8FF)
    static let blue2 = Color(hex: 0xAAB8FF)
    static let blue3 = Color(hex: 0xC3CEFF)
    static let blueTint = Color(hex: 0x7C8CFF)
    static let amber = Color(hex: 0xF2C078)
    static let green = Color(hex: 0x7CFFB2)
    static let red = Color(hex: 0xFF5A5A)
    static let red2 = Color(hex: 0xFF8A8A)
    static let ink = Color(hex: 0x2B1F12) // handwritten marker colour
    static let btnShadow = Color(hex: 0x6366F1).opacity(0.35)

    /// Space Grotesk for numbers and labels; falls back to the rounded system face if the font is missing.
    static func num(_ size: CGFloat, weight: Font.Weight = .medium) -> Font {
        let name = weight == .bold ? "SpaceGrotesk-Bold" : "SpaceGrotesk-Medium"
        if UIFont(name: name, size: size) != nil { return .custom(name, size: size) }
        return .system(size: size, weight: weight, design: .rounded)
    }

    static func kraft(_ box: Box) -> LinearGradient {
        LinearGradient(colors: [Color(hexString: box.colorA), Color(hexString: box.colorB)],
                       startPoint: .topLeading, endPoint: .bottomTrailing)
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }

    /// "#9C7A52" → colour; anything unparsable → kraft default.
    init(hexString: String) {
        var s = hexString.trimmingCharacters(in: .whitespaces)
        if s.hasPrefix("#") { s.removeFirst() }
        guard s.count == 6, let v = UInt32(s, radix: 16) else {
            self.init(hex: 0x9C7A52)
            return
        }
        self.init(hex: v)
    }
}
