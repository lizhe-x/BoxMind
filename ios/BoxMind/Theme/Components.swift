// Shared building blocks. Port of frontend/src/components/common.tsx.
import SwiftUI
import BoxMindKit

/// Card surface: #11151F with a 1 px hairline, 20 pt corners.
struct CardStyle: ViewModifier {
    var radius: CGFloat = 20
    func body(content: Content) -> some View {
        content
            .background(BM.card, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: radius, style: .continuous).strokeBorder(BM.border, lineWidth: 1))
    }
}

extension View {
    func card(radius: CGFloat = 20) -> some View { modifier(CardStyle(radius: radius)) }
}

/// Kraft gradient badge with the rotated handwritten label.
struct BoxBadge: View {
    let box: Box
    var width: CGFloat = 44
    var height: CGFloat = 38
    var fontSize: CGFloat = 14
    var radius: CGFloat = 8

    var body: some View {
        Text(box.label)
            .font(BM.num(Display.badgeFontSize(box.label, base: fontSize), weight: .bold))
            .foregroundStyle(BM.ink)
            .lineLimit(1)
            .minimumScaleFactor(0.5)
            .padding(.horizontal, 3)
            .frame(width: width, height: height)
            .background(BM.kraft(box), in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .rotationEffect(.degrees(-2))
    }
}

/// Gradient capsule button (52–56 pt) with the indigo glow.
struct GradButton<Label: View>: View {
    var height: CGFloat = 52
    let action: () -> Void
    @ViewBuilder let label: () -> Label

    var body: some View {
        Button(action: action) {
            HStack(spacing: 9) { label() }
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(BM.text)
                .frame(maxWidth: .infinity)
                .frame(height: height)
                .background(BM.grad, in: Capsule())
                .shadow(color: BM.btnShadow, radius: 13, y: 8)
        }
        .buttonStyle(PressScale())
    }
}

struct PressScale: ButtonStyle {
    var scale: CGFloat = 0.98
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? scale : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

/// Small pill chip: amber (label), blue (barcode) or neutral.
struct Chip: View {
    enum Tone { case amber, blue, neutral, green }
    let text: String
    var tone: Tone = .neutral

    private var fg: Color {
        switch tone {
        case .amber: BM.amber
        case .blue: BM.blue2
        case .neutral: BM.textSub
        case .green: BM.green
        }
    }
    private var bg: Color {
        switch tone {
        case .amber: BM.amber.opacity(0.1)
        case .blue: BM.blueTint.opacity(0.1)
        case .neutral: Color.white.opacity(0.05)
        case .green: BM.green.opacity(0.12)
        }
    }
    private var stroke: Color {
        switch tone {
        case .amber: BM.amber.opacity(0.3)
        case .blue: BM.blueTint.opacity(0.3)
        case .neutral: Color.white.opacity(0.09)
        case .green: .clear
        }
    }

    var body: some View {
        Text(text)
            .font(.system(size: 12, weight: tone == .green ? .semibold : .regular))
            .foregroundStyle(fg)
            .padding(.horizontal, 12).padding(.vertical, 6)
            .background(bg, in: Capsule())
            .overlay(Capsule().strokeBorder(stroke, lineWidth: 1))
    }
}

/// Sparkle-on-gradient avatar used for AI messages and "organised by AI" footnotes.
struct AiAvatar: View {
    var size: CGFloat = 26
    var body: some View {
        Image(systemName: "sparkle")
            .font(.system(size: size / 2.2, weight: .bold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(BM.grad, in: Circle())
    }
}

struct PinIcon: View {
    var size: CGFloat = 11
    var body: some View {
        Image(systemName: "mappin.and.ellipse")
            .font(.system(size: size, weight: .medium))
            .foregroundStyle(BM.blue)
    }
}

/// Bottom tab bar: Home / Boxes / Me.
struct TabBar: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        let on = BM.blue3
        let off = Color(hex: 0xEBF0FA).opacity(0.4)
        HStack(spacing: 0) {
            tab(.home, label: model.t(.tab_home), icon: "house", on: on, off: off)
            tab(.boxes, label: model.t(.tab_boxes), icon: "shippingbox", on: on, off: off)
            tab(.settings, label: model.t(.tab_me), icon: "gearshape", on: on, off: off)
        }
        .frame(height: 64)
        .background(Color(hex: 0x090C13).opacity(0.82).background(.ultraThinMaterial))
        .overlay(alignment: .top) { Rectangle().fill(Color.white.opacity(0.06)).frame(height: 1) }
    }

    private func tab(_ s: Screen, label: String, icon: String, on: Color, off: Color) -> some View {
        let c = model.screen == s ? on : off
        return Button { model.go(s) } label: {
            VStack(spacing: 4) {
                Image(systemName: icon).font(.system(size: 22, weight: .regular))
                Text(label).font(.system(size: 10.5))
            }
            .foregroundStyle(c)
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("tab.\(s.rawValue)")
    }
}

struct ToastView: View {
    let text: String
    var body: some View {
        Text(text)
            .font(.system(size: 13))
            .foregroundStyle(BM.text)
            .multilineTextAlignment(.center)
            .padding(.horizontal, 18).padding(.vertical, 10)
            .frame(maxWidth: 320)
            .background(Color(hex: 0x161C2C).opacity(0.95), in: Capsule())
            .overlay(Capsule().strokeBorder(BM.blueTint.opacity(0.3), lineWidth: 1))
            .shadow(color: .black.opacity(0.5), radius: 17, y: 10)
            .transition(.scale(scale: 0.94).combined(with: .opacity))
    }
}

/// Dark app background with the brand glow at the top (`.bm-frame::before`).
/// The glow is an overlay so its fixed size never widens the layout.
struct AppBackground: View {
    var body: some View {
        BM.bgApp
            .overlay(alignment: .top) {
                RadialGradient(colors: [Color(hex: 0x5D6CFF).opacity(0.18), .clear], center: .center, startRadius: 0, endRadius: 280)
                    .frame(width: 560, height: 440)
                    .offset(y: -220)
            }
            .clipped()
            .ignoresSafeArea()
    }
}

/// Kraft cover: the gradient, a tape strip and the handwritten label; or the cover photo when there is one.
struct KraftCover: View {
    @Environment(AppModel.self) private var model
    let box: Box
    let height: CGFloat
    var labelSize: CGFloat = 26
    var tapeWidth: CGFloat = 52

    var body: some View {
        let cover = box.cover
        ZStack {
            BM.kraft(box)
            if let cover {
                AsyncImage(url: model.api.mediaURL(cover)) { image in
                    image.resizable().scaledToFill()
                } placeholder: { Color.clear }
                .frame(height: height)
                .clipped()
            } else {
                VStack(spacing: 0) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.white.opacity(0.22))
                        .frame(width: tapeWidth, height: tapeWidth * 0.27)
                        .rotationEffect(.degrees(-2))
                        .offset(y: -5)
                    Spacer()
                }
                Text(box.label)
                    .font(BM.num(Display.badgeFontSize(box.label, base: labelSize), weight: .bold))
                    .foregroundStyle(BM.ink)
                    .lineLimit(1)
                    .rotationEffect(.degrees(-2))
            }
        }
        .frame(height: height)
        .clipped()
    }
}
