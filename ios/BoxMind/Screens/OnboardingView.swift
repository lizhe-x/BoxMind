import SwiftUI
import BoxMindKit

/// Three-slide intro. Port of frontend/src/screens/Onboarding.tsx (text only; illustrations come in M4).
struct OnboardingView: View {
    @Environment(AppModel.self) private var model
    @State private var slide = 0

    private let slides: [(tag: L10nKey, title: L10nKey, desc: L10nKey)] = [
        (.ob1_tag, .ob1_title, .ob1_desc), (.ob2_tag, .ob2_title, .ob2_desc), (.ob3_tag, .ob3_title, .ob3_desc),
    ]

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Spacer()
                Button(model.t(.ob_skip)) { model.finishOnboarding() }
                    .font(.system(size: 14)).foregroundStyle(BM.textWeak).padding(6)
                    .accessibilityIdentifier("onboarding.skip")
            }
            Spacer()
            illustration.padding(.bottom, 40)
            VStack(alignment: .leading, spacing: 12) {
                Text(model.t(slides[slide].tag)).font(BM.num(12)).foregroundStyle(BM.blue2).tracking(1)
                Text(model.t(slides[slide].title)).font(.system(size: 26, weight: .bold)).foregroundStyle(BM.text)
                Text(model.t(slides[slide].desc)).font(.system(size: 15)).foregroundStyle(BM.textSub55).lineSpacing(5)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .id(slide)
            .transition(.opacity.combined(with: .move(edge: .trailing)))
            Spacer()
            HStack(spacing: 6) {
                ForEach(0..<3) { i in
                    Capsule().fill(i == slide ? BM.blue2 : Color.white.opacity(0.15)).frame(width: i == slide ? 18 : 6, height: 6)
                }
            }
            .padding(.bottom, 22)
            GradButton(height: 54) {
                withAnimation(.easeOut(duration: 0.3)) {
                    if slide >= 2 { model.finishOnboarding() } else { slide += 1 }
                }
            } label: {
                Text(slide >= 2 ? model.t(.ob_start) : model.t(.ob_continue)).font(.system(size: 16, weight: .semibold))
            }
        }
        .padding(.horizontal, 28)
        .padding(.bottom, 20)
    }

    @ViewBuilder private var illustration: some View {
        switch slide {
        case 0:
            ZStack(alignment: .top) {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(LinearGradient(colors: [Color(hex: 0x9C7A52), Color(hex: 0x6E5638)], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 172, height: 128)
                    .shadow(color: .black.opacity(0.45), radius: 25, y: 24)
                RoundedRectangle(cornerRadius: 2).fill(Color.white.opacity(0.22)).frame(width: 70, height: 16).rotationEffect(.degrees(-2)).offset(y: -7)
                Text(model.t(.label_sample)).font(BM.num(54, weight: .bold)).foregroundStyle(BM.ink).rotationEffect(.degrees(-2)).padding(.top, 30)
            }
            .rotationEffect(.degrees(-3))
        case 1:
            ZStack {
                Circle().fill(BM.grad).frame(width: 120, height: 120).shadow(color: BM.btnShadow, radius: 30, y: 10)
                Image(systemName: "mic.fill").font(.system(size: 44, weight: .medium)).foregroundStyle(.white)
            }
        default:
            VStack(alignment: .leading, spacing: 10) {
                Text(model.t(.ob_demo_q)).font(.system(size: 14)).foregroundStyle(BM.text)
                    .padding(.horizontal, 14).padding(.vertical, 10).background(BM.blueTint.opacity(0.2), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .frame(maxWidth: .infinity, alignment: .trailing)
                HStack(alignment: .top, spacing: 8) {
                    AiAvatar(size: 26)
                    Text(model.t(.ob_demo_a)).font(.system(size: 14)).foregroundStyle(BM.text)
                        .padding(.horizontal, 14).padding(.vertical, 10).card(radius: 16)
                }
            }
            .frame(width: 280)
        }
    }
}
