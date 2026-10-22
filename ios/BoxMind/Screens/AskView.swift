import SwiftUI
import BoxMindKit

/// Chat with the inventory: streamed answers with box cards, agent confirm cards, read-aloud, hold-to-talk.
/// Port of frontend/src/screens/Ask.tsx.
struct AskView: View {
    @Environment(AppModel.self) private var model
    @Environment(HoldToTalk.self) private var talk
    @Environment(Speaker.self) private var speaker
    @State private var text = ""
    @FocusState private var focused: Bool

    private var chips: [String] {
        let asked = Set(model.askMsgs.filter { $0.who == .user }.map(\.text))
        return [model.t(.chip_where_drill), model.t(.chip_how_many), model.t(.chip_no_location)].filter { !asked.contains($0) }
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            messages
            footer
        }
        .onDisappear { speaker.stop() }
    }

    private var header: some View {
        HStack(spacing: 12) {
            Button { model.go(.home) } label: {
                Image(systemName: "chevron.left").font(.system(size: 15, weight: .semibold)).foregroundStyle(BM.text)
                    .frame(width: 38, height: 38)
                    .background(Color.white.opacity(0.06), in: Circle())
                    .overlay(Circle().strokeBorder(BM.border8, lineWidth: 1))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("ask.back")
            VStack(alignment: .leading, spacing: 1) {
                Text(model.t(.ask_title)).font(.system(size: 16, weight: .semibold)).foregroundStyle(BM.text)
                Text(model.t(.ask_sub)).font(.system(size: 11.5)).foregroundStyle(BM.textWeak)
            }
            Spacer()
        }
        .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 12)
    }

    private var messages: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 14) {
                    ForEach(model.askMsgs) { m in
                        if m.who == .user { userBubble(m) } else { aiBubble(m) }
                    }
                    if model.thinking {
                        HStack(alignment: .top, spacing: 10) {
                            AiAvatar()
                            ThinkingDots().padding(.horizontal, 16).padding(.vertical, 15)
                                .background(BM.card2, in: BubbleShape(tail: .leading))
                                .overlay(BubbleShape(tail: .leading).strokeBorder(BM.border, lineWidth: 1))
                        }
                        .id("thinking")
                    }
                    Color.clear.frame(height: 6).id("bottom")
                }
                .padding(.horizontal, 20).padding(.vertical, 10)
            }
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: model.askMsgs) { _, _ in withAnimation { proxy.scrollTo("bottom", anchor: .bottom) } }
            .onChange(of: model.thinking) { _, _ in withAnimation { proxy.scrollTo("bottom", anchor: .bottom) } }
            .onAppear { proxy.scrollTo("bottom", anchor: .bottom) }
        }
    }

    private func userBubble(_ m: AskMsg) -> some View {
        HStack {
            Spacer(minLength: 60)
            Text(m.text).font(.system(size: 15)).lineSpacing(4).foregroundStyle(BM.text)
                .padding(.horizontal, 15).padding(.vertical, 11)
                .background(Color(hex: 0x273048), in: BubbleShape(tail: .trailing))
        }
    }

    private func aiBubble(_ m: AskMsg) -> some View {
        HStack(alignment: .top, spacing: 10) {
            AiAvatar().padding(.top, 2)
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .bottom, spacing: 0) {
                    Text(Display.plainText(m.text)).font(.system(size: 15)).lineSpacing(5).foregroundStyle(BM.text)
                    if m.streaming { Cursor() }
                }
                .padding(.horizontal, 15).padding(.vertical, 12)
                .background(BM.card2, in: BubbleShape(tail: .leading))
                .overlay(BubbleShape(tail: .leading).strokeBorder(BM.border, lineWidth: 1))
                if !m.streaming, !m.text.isEmpty { speakButton(m) }
                ForEach(m.boxes ?? []) { box in boxCard(box) }
                if let actions = m.confirm, !actions.isEmpty { confirmCard(actions) }
            }
            Spacer(minLength: 40)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func speakButton(_ m: AskMsg) -> some View {
        let on = speaker.speakingId == m.id
        return Button { speaker.toggle(id: m.id, text: Display.plainText(m.text), lang: model.lang) } label: {
            HStack(spacing: 6) {
                Image(systemName: on ? "speaker.wave.2.fill" : "speaker.wave.2").font(.system(size: 12))
                Text(on ? model.t(.playing) : model.t(.read_aloud)).font(.system(size: 12))
            }
            .foregroundStyle(on ? BM.blue2 : BM.textSub)
            .padding(.horizontal, 11).padding(.vertical, 5)
            .background(on ? BM.blueTint.opacity(0.12) : Color.white.opacity(0.04), in: Capsule())
            .overlay(Capsule().strokeBorder(on ? BM.blueTint.opacity(0.35) : BM.border8, lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

    private func boxCard(_ box: BoxRef) -> some View {
        let dist = Display.distText(userPos: model.userPos, lat: box.gpsLat, lng: box.gpsLng, lang: model.lang)
        let sub = [box.locationText, dist].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · ")
        return Button { model.openBox(box.id) } label: {
            HStack(spacing: 12) {
                LabelBadge(label: box.label, colors: (box.colorA, box.colorB), width: 46, height: 40, fontSize: 15)
                VStack(alignment: .leading, spacing: 2) {
                    Text(box.name).font(.system(size: 14.5, weight: .semibold)).foregroundStyle(BM.text)
                    Text(sub.isEmpty ? model.t(.location_pending) : sub).font(.system(size: 12)).foregroundStyle(BM.textSub).lineLimit(1)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(BM.textWeak35)
            }
            .padding(.horizontal, 13).padding(.vertical, 11)
            .background(BM.card, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(BM.blueTint.opacity(0.25), lineWidth: 1))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("ask.box.\(box.label)")
    }

    private func confirmCard(_ actions: [AgentAction]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(model.t(.confirm_needed)).font(.system(size: 12.5)).foregroundStyle(BM.red2)
            ForEach(Array(actions.enumerated()), id: \.offset) { _, a in
                Text("· \(a.summary)").font(.system(size: 14)).lineSpacing(3).foregroundStyle(BM.text)
            }
            HStack(spacing: 10) {
                OutlineButton(title: model.t(.cancel), height: 42) { model.agentCancel() }
                    .accessibilityIdentifier("ask.cancelActions")
                Button { Task { await model.agentConfirm(actions) } } label: {
                    Text(model.t(.confirm_run)).font(.system(size: 14, weight: .semibold)).foregroundStyle(.white)
                        .frame(maxWidth: .infinity).frame(height: 42)
                        .background(LinearGradient(colors: [BM.red, BM.red2], startPoint: .topLeading, endPoint: .bottomTrailing), in: Capsule())
                }
                .buttonStyle(PressScale())
                .accessibilityIdentifier("ask.confirmActions")
            }
            .padding(.top, 2)
        }
        .padding(.horizontal, 15).padding(.vertical, 13)
        .background(BM.card, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(BM.red.opacity(0.3), lineWidth: 1))
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: 12) {
            if !chips.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(chips, id: \.self) { c in
                            Button { send(c) } label: {
                                Text(c).font(.system(size: 13)).foregroundStyle(BM.blue2)
                                    .padding(.horizontal, 14).padding(.vertical, 9)
                                    .background(BM.blueTint.opacity(0.1), in: Capsule())
                                    .overlay(Capsule().strokeBorder(BM.blueTint.opacity(0.3), lineWidth: 1))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, 20)
                }
            }
            HStack(spacing: 10) {
                TextField(talk.recording ? model.t(.listening) : model.t(.ask_ph), text: $text)
                    .font(.system(size: 14)).foregroundStyle(BM.text)
                    .focused($focused)
                    .submitLabel(.send)
                    .onSubmit { send(text) }
                    .padding(.horizontal, 18)
                    .frame(height: 46)
                    .background(BM.card, in: Capsule())
                    .overlay(Capsule().strokeBorder(talk.recording ? BM.red.opacity(0.4) : BM.border8, lineWidth: 1))
                    .accessibilityIdentifier("ask.input")
                if !text.trimmingCharacters(in: .whitespaces).isEmpty {
                    Button { send(text) } label: {
                        Image(systemName: "arrow.up").font(.system(size: 17, weight: .semibold)).foregroundStyle(BM.text)
                            .frame(width: 46, height: 46)
                            .background(BM.grad, in: Circle())
                            .shadow(color: BM.btnShadow, radius: 10, y: 6)
                    }
                    .buttonStyle(PressScale(scale: 0.94))
                    .accessibilityIdentifier("ask.send")
                } else {
                    Image(systemName: "mic.fill").font(.system(size: 18, weight: .medium)).foregroundStyle(.white)
                        .frame(width: 46, height: 46)
                        .background(talk.recording ? LinearGradient(colors: [BM.red, BM.red2], startPoint: .topLeading, endPoint: .bottomTrailing) : BM.grad, in: Circle())
                        .shadow(color: BM.btnShadow, radius: 10, y: 6)
                        .contentShape(Circle())
                        .holdToTalk(onBegin: beginTalk, onEnd: endTalk)
                        .accessibilityIdentifier("ask.talk")
                }
            }
            .padding(.horizontal, 20)
        }
        .padding(.top, 10).padding(.bottom, 12)
    }

    // MARK: Actions

    private func send(_ q: String) {
        let v = q.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !v.isEmpty, !model.thinking else { return }
        text = ""
        Task { await model.chatSend(v) }
    }

    private func beginTalk() {
        guard !model.thinking else { return }
        focused = false
        text = ""
        talk.begin(model: model, onPartial: { text = $0 }, onUnavailable: { model.showToast(model.t(.mic_unavailable)) })
    }

    private func endTalk() {
        talk.end(model: model) { heard, _ in
            text = ""
            if heard.trimmingCharacters(in: .whitespaces).isEmpty { model.showToast(model.t(.not_heard_type)) } else { send(heard) }
        }
    }
}

/// Chat bubble: 18 pt corners with one 4 pt corner on the tail side.
struct BubbleShape: InsettableShape {
    enum Tail { case leading, trailing }
    var tail: Tail
    var inset: CGFloat = 0

    func inset(by amount: CGFloat) -> BubbleShape {
        var s = self
        s.inset += amount
        return s
    }

    func path(in rect: CGRect) -> Path {
        let r = rect.insetBy(dx: inset, dy: inset)
        let big: CGFloat = 18, small: CGFloat = 4
        let tl = tail == .leading ? small : big
        let tr = tail == .trailing ? small : big
        return Path(roundedRect: r, cornerRadii: RectangleCornerRadii(topLeading: tl, bottomLeading: big, bottomTrailing: big, topTrailing: tr), style: .continuous)
    }
}

struct Cursor: View {
    @State private var on = true
    var body: some View {
        Rectangle().fill(BM.blue).frame(width: 2, height: 15)
            .opacity(on ? 1 : 0)
            .padding(.leading, 3).padding(.bottom, 2)
            .onAppear { withAnimation(.easeInOut(duration: 0.4).repeatForever()) { on = false } }
    }
}
