import SwiftUI
import BoxMindKit

/// Home: brand header, tip / last-activity card, the hold-to-talk button and the text input row.
/// Port of frontend/src/screens/Home.tsx.
struct HomeView: View {
    @Environment(AppModel.self) private var model
    @Environment(HoldToTalk.self) private var talk
    @State private var text = ""
    @FocusState private var focused: Bool

    private var lastBox: Box? { model.boxes.first { !$0.items.isEmpty } }

    var body: some View {
        VStack(spacing: 0) {
            header.padding(.horizontal, 22).padding(.top, 12)

            if let lastBox {
                activityCard(lastBox).padding(.horizontal, 22).padding(.top, 20)
            } else {
                tipCard.padding(.horizontal, 22).padding(.top, 20)
            }

            if let target = model.targetBox { targetChip(target).padding(.top, 12) }

            Spacer(minLength: 12)
            talkButton
            Spacer(minLength: 12)

            inputRow.padding(.horizontal, 22).padding(.top, 20)
            chips.padding(.top, 14).padding(.bottom, 10)
        }
        .onChange(of: model.entryPhase) { _, phase in
            if phase == .input { focused = true } // "couldn't parse that" → cursor back in the box
        }
    }

    // MARK: Pieces

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 5) {
                Text("BoxMind").font(BM.num(23, weight: .bold)).foregroundStyle(BM.blue3)
                Text(model.t(.home_stats, ["boxes": model.me?.boxCount ?? model.boxes.count, "items": model.me?.itemCount ?? 0]))
                    .font(.system(size: 12.5)).foregroundStyle(BM.textSub)
            }
            Spacer()
            Button { model.go(.settings) } label: {
                HStack(spacing: 6) {
                    Circle().fill(BM.green).frame(width: 6, height: 6)
                    Text(model.t(.unlimited)).font(BM.num(12.5)).foregroundStyle(BM.blue2)
                }
                .padding(.horizontal, 12).padding(.vertical, 7)
                .background(BM.blueTint.opacity(0.1), in: Capsule())
                .overlay(Capsule().strokeBorder(BM.blueTint.opacity(0.25), lineWidth: 1))
            }
            .buttonStyle(.plain)
        }
    }

    private var tipCard: some View {
        HStack(spacing: 14) {
            Text(model.t(.label_sample))
                .font(BM.num(17, weight: .bold)).foregroundStyle(BM.ink)
                .frame(width: 54, height: 42)
                .background(LinearGradient(colors: [Color(hex: 0x9C7A52), Color(hex: 0x6E5638)], startPoint: .topLeading, endPoint: .bottomTrailing),
                            in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                .rotationEffect(.degrees(-3))
            Text(model.t(.home_tip))
                .font(.system(size: 13.5)).lineSpacing(4)
                .foregroundStyle(Color(hex: 0xEBF0FA).opacity(0.65))
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }

    private func activityCard(_ box: Box) -> some View {
        Button { model.openBox(box.id) } label: {
            HStack(spacing: 12) {
                Image(systemName: "checkmark")
                    .font(.system(size: 14, weight: .bold)).foregroundStyle(BM.green)
                    .frame(width: 34, height: 34)
                    .background(BM.green.opacity(0.12), in: Circle())
                VStack(alignment: .leading, spacing: 3) {
                    Text(model.t(.home_last, ["name": box.name, "time": Display.fmtTime(box.updatedAt, lang: model.lang)]))
                        .font(.system(size: 14, weight: .semibold)).foregroundStyle(BM.text).lineLimit(1)
                    Text(Display.fmtItems(Array(box.items.prefix(3)).map { ItemDraft(name: $0.name, qtyText: $0.qtyText) }))
                        .font(.system(size: 12)).foregroundStyle(BM.textSub).lineLimit(1)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(BM.textWeak35)
            }
            .padding(.horizontal, 16).padding(.vertical, 14)
            .background(BM.green.opacity(0.07), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(BM.green.opacity(0.2), lineWidth: 1))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("home.lastBox")
    }

    private func targetChip(_ box: Box) -> some View {
        HStack(spacing: 8) {
            Text(model.t(.home_target, ["name": box.name])).font(.system(size: 12.5)).foregroundStyle(BM.amber)
            Button { model.setTargetBox(nil) } label: {
                Image(systemName: "xmark").font(.system(size: 9, weight: .bold))
                    .foregroundStyle(Color(hex: 0xEBF0FA).opacity(0.6))
                    .frame(width: 18, height: 18)
                    .background(Color.white.opacity(0.1), in: Circle())
            }
            .buttonStyle(.plain)
        }
        .padding(.leading, 14).padding(.trailing, 8).padding(.vertical, 7)
        .background(BM.amber.opacity(0.1), in: Capsule())
        .overlay(Capsule().strokeBorder(BM.amber.opacity(0.3), lineWidth: 1))
        .accessibilityIdentifier("home.target")
    }

    private var talkButton: some View {
        VStack(spacing: 0) {
            ZStack {
                PulseRing(delay: 0)
                PulseRing(delay: 0.9, color: BM.gradB.opacity(0.3))
                Circle()
                    .fill(BM.grad)
                    .overlay(
                        RadialGradient(colors: [Color.white.opacity(0.28), .clear], center: UnitPoint(x: 0.32, y: 0.28), startRadius: 0, endRadius: 64)
                            .clipShape(Circle())
                    )
                    .frame(width: 150, height: 150)
                    .shadow(color: Color(hex: 0x6366F1).opacity(0.45), radius: 30, y: 18)
                    .scaleEffect(talk.recording ? 0.95 : 1)
                    .animation(.easeOut(duration: 0.15), value: talk.recording)
                Image(systemName: "mic.fill").font(.system(size: 44, weight: .medium)).foregroundStyle(.white)
            }
            .frame(width: 174, height: 174)
            .contentShape(Circle())
            .holdToTalk(onBegin: beginTalk, onEnd: endTalk)
            .accessibilityIdentifier("home.talk")

            Text(model.t(.hold_to_talk)).font(.system(size: 17, weight: .semibold)).foregroundStyle(BM.text).padding(.top, 14)
            Text(model.targetBox.map { model.t(.home_hint_target, ["name": $0.name]) } ?? model.t(.home_hint))
                .font(.system(size: 13)).foregroundStyle(model.targetBox == nil ? BM.textWeak : BM.amber)
                .multilineTextAlignment(.center).padding(.horizontal, 34).padding(.top, 5)
        }
    }

    private var inputRow: some View {
        HStack(spacing: 10) {
            TextField(model.t(.input_placeholder), text: $text)
                .font(.system(size: 14.5)).foregroundStyle(BM.text)
                .focused($focused)
                .submitLabel(.send)
                .onSubmit(submit)
                .padding(.horizontal, 18)
                .frame(height: 52)
                .background(BM.card, in: Capsule())
                .overlay(Capsule().strokeBorder(BM.border8, lineWidth: 1))
                .accessibilityIdentifier("home.input")
            if !text.trimmingCharacters(in: .whitespaces).isEmpty {
                Button(action: submit) {
                    Image(systemName: "arrow.up").font(.system(size: 18, weight: .semibold)).foregroundStyle(BM.text)
                        .frame(width: 52, height: 52)
                        .background(BM.grad, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                        .shadow(color: BM.btnShadow, radius: 13, y: 8)
                }
                .buttonStyle(PressScale(scale: 0.94))
                .accessibilityIdentifier("home.send")
            } else {
                squareButton("camera") { model.openCamera() }.accessibilityIdentifier("home.camera")
                squareButton("qrcode.viewfinder") { model.openScan() }.accessibilityIdentifier("home.scan")
            }
        }
    }

    private func squareButton(_ icon: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon).font(.system(size: 20, weight: .regular)).foregroundStyle(BM.text.opacity(0.85))
                .frame(width: 52, height: 52)
                .background(BM.card, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(BM.border8, lineWidth: 1))
        }
        .buttonStyle(PressScale(scale: 0.94))
    }

    private var chips: some View {
        HStack(spacing: 8) {
            ForEach([model.t(.chip_where_drill), model.t(.chip_how_many)], id: \.self) { q in
                Button {
                    model.openAsk()
                    Task { await model.ask(q) }
                } label: {
                    Text(q).font(.system(size: 12.5)).foregroundStyle(BM.textSub55)
                        .padding(.horizontal, 14).padding(.vertical, 8)
                        .background(Color.white.opacity(0.04), in: Capsule())
                        .overlay(Capsule().strokeBorder(Color.white.opacity(0.09), lineWidth: 1))
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: Actions

    private func submit() {
        let v = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !v.isEmpty else { return }
        text = ""
        focused = false
        Task { await model.textEntry(v) }
    }

    private func beginTalk() {
        focused = false
        model.beginRecording()
        talk.begin(model: model, onPartial: { model.setLiveTranscript($0) },
                   onUnavailable: { Task { await model.finishRecording(text: "", audio: nil) } })
    }

    private func endTalk() {
        talk.end(model: model) { text, clip in Task { await model.finishRecording(text: text, audio: clip) } }
    }
}

/// Expanding ring around the talk button (`bm-pulse`).
struct PulseRing: View {
    let delay: Double
    var color: Color = BM.blueTint.opacity(0.4)
    @State private var on = false

    var body: some View {
        Circle()
            .strokeBorder(color, lineWidth: 1)
            .frame(width: 150, height: 150)
            .scaleEffect(on ? 1.32 : 1)
            .opacity(on ? 0 : 0.8)
            .onAppear {
                withAnimation(.easeOut(duration: 2.6).repeatForever(autoreverses: false).delay(delay)) { on = true }
            }
    }
}
