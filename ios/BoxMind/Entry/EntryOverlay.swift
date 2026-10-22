import SwiftUI
import BoxMindKit

/// Full-screen overlay for the entry pipeline: recording → parsing → confirm / askbox / edit → done.
/// Port of frontend/src/components/EntryOverlay.tsx.
struct EntryOverlay: View {
    @Environment(AppModel.self) private var model
    @State private var draft = ""

    var body: some View {
        ZStack(alignment: .top) {
            Color(hex: 0x06080E).opacity(0.92).background(.ultraThinMaterial).ignoresSafeArea()
            VStack(spacing: 0) {
                HStack {
                    Spacer()
                    Button { model.closeEntry() } label: {
                        Image(systemName: "xmark").font(.system(size: 13, weight: .semibold)).foregroundStyle(BM.textSub)
                            .frame(width: 34, height: 34)
                            .background(Color.white.opacity(0.07), in: Circle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("entry.close")
                    .opacity(model.entryPhase == .recording ? 0 : 1)
                }
                .padding(.horizontal, 24).padding(.top, 14)

                switch model.entryPhase {
                case .recording: recording
                case .parsing: parsing
                case .confirm: confirm
                case .askbox: askbox
                case .edit: edit
                case .done: done
                case .idle, .input: EmptyView()
                }
            }
        }
        .allowsHitTesting(model.entryPhase != .recording) // the finger stays on the home button underneath
        .animation(.easeOut(duration: 0.25), value: model.entryPhase)
    }

    private var items: [ItemDraft] { model.parsed?.items ?? [] }

    // MARK: Recording

    private var recording: some View {
        VStack(spacing: 30) {
            Spacer()
            HStack(spacing: 8) {
                BlinkDot(color: BM.red)
                Text(model.t(.listening)).font(.system(size: 13)).foregroundStyle(BM.red2)
            }
            .padding(.horizontal, 16).padding(.vertical, 7)
            .background(BM.red.opacity(0.1), in: Capsule())
            .overlay(Capsule().strokeBorder(BM.red.opacity(0.3), lineWidth: 1))
            WaveBars()
            Group {
                if model.liveTranscript.isEmpty {
                    Text(model.t(.rec_ph)).foregroundStyle(BM.textWeak)
                } else {
                    Text(model.liveTranscript).foregroundStyle(BM.text)
                }
            }
            .font(.system(size: 20)).lineSpacing(8).multilineTextAlignment(.center)
            .frame(minHeight: 120, alignment: .top)
            .padding(.horizontal, 28)
            Spacer()
            Text(model.t(.rec_release)).font(.system(size: 13)).foregroundStyle(BM.textWeak).padding(.bottom, 30)
        }
    }

    // MARK: Parsing

    private var parsing: some View {
        VStack(spacing: 26) {
            Spacer()
            Text("“\(model.rawText)”").font(.system(size: 16)).lineSpacing(6).foregroundStyle(BM.textWeak)
                .multilineTextAlignment(.center).padding(.horizontal, 32)
            HStack(spacing: 10) {
                AiAvatar(size: 28)
                Text(model.t(.parsing)).font(.system(size: 16, weight: .medium)).foregroundStyle(BM.blue2)
                ThinkingDots(size: 5)
            }
            Spacer()
        }
        .accessibilityIdentifier("entry.parsing")
    }

    // MARK: Confirm

    private var confirm: some View {
        let target = model.targetBox
        let matched = target ?? model.parsed?.box
        let label = matched?.label ?? model.parsed?.boxLabel ?? ""
        let name = matched?.name ?? (label.isEmpty ? model.t(.new_box_generic) : L10n.boxName(for: label, lang: model.lang))
        let location = model.parsed?.locationText ?? target?.location
        return ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 9) {
                    AiAvatar(size: 24)
                    Text(model.t(.confirm_title)).font(.system(size: 16, weight: .semibold)).foregroundStyle(BM.text)
                        .accessibilityIdentifier("entry.confirmTitle")
                }
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 12) {
                        LabelBadge(label: label.isEmpty ? "?" : label, colors: matched.map { ($0.colorA, $0.colorB) }, width: 48, height: 42, fontSize: 16, radius: 9)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(name).font(.system(size: 16, weight: .semibold)).foregroundStyle(BM.text)
                            Text(matched == nil ? model.t(.new_box_auto) : model.t(.existing_append))
                                .font(.system(size: 11.5)).foregroundStyle(matched == nil ? BM.green : BM.textSub)
                        }
                    }
                    Divider().overlay(Color.white.opacity(0.06))
                    ItemRows(items: items)
                    if let location, !location.isEmpty {
                        HStack(spacing: 8) {
                            PinIcon(size: 13)
                            Text(location).font(.system(size: 13.5)).foregroundStyle(Color(hex: 0xEBF0FA).opacity(0.7))
                        }
                    }
                }
                .padding(18)
                .card(radius: 22)
                Text(model.t(.original, ["text": model.rawText])).font(.system(size: 12)).lineSpacing(3)
                    .foregroundStyle(BM.textWeak35).padding(.horizontal, 4)
                HStack(spacing: 10) {
                    OutlineButton(title: model.t(.fix)) { model.toEdit() }
                        .frame(maxWidth: .infinity)
                        .accessibilityIdentifier("entry.edit")
                    GradButton { Task { await model.confirmEntry() } } label: {
                        Text(model.entryBusy ? model.t(.saving) : model.t(.confirm_save))
                    }
                    .frame(maxWidth: .infinity)
                    .layoutPriority(1)
                    .opacity(model.entryBusy ? 0.6 : 1)
                    .disabled(model.entryBusy)
                    .accessibilityIdentifier("entry.save")
                }
                .padding(.top, 4)
            }
            .padding(.horizontal, 24).padding(.top, 24).padding(.bottom, 40)
        }
    }

    // MARK: Ask which box

    private var askbox: some View {
        let next = model.parsed?.nextLabel ?? "1"
        return ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 9) {
                    AiAvatar(size: 24)
                    Text(model.t(.askbox_title, ["n": items.count])).font(.system(size: 16, weight: .semibold)).foregroundStyle(BM.text)
                }
                ItemRows(items: items, rowPadding: 10).padding(.horizontal, 16).padding(.vertical, 6).card(radius: 18)
                Text(model.t(.askbox_hint)).font(.system(size: 12.5)).foregroundStyle(BM.textWeak)
                VStack(spacing: 9) {
                    Button { Task { await model.pickNewBox() } } label: {
                        HStack(spacing: 12) {
                            LabelBadge(label: next, colors: ("#9C7A52", "#7A5E3E"))
                            VStack(alignment: .leading, spacing: 2) {
                                Text(model.t(.new_box_n, ["name": L10n.boxName(for: next, lang: model.lang)]))
                                    .font(.system(size: 14.5, weight: .semibold)).foregroundStyle(BM.amber)
                                Text(model.t(.new_box_desc)).font(.system(size: 11.5)).foregroundStyle(BM.textWeak)
                            }
                            Spacer(minLength: 0)
                            Text(model.t(.recommended)).font(.system(size: 10.5)).foregroundStyle(BM.amber)
                                .padding(.horizontal, 9).padding(.vertical, 3)
                                .background(BM.amber.opacity(0.12), in: Capsule())
                        }
                        .padding(.horizontal, 14).padding(.vertical, 12)
                        .background(BM.amber.opacity(0.08), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .strokeBorder(style: StrokeStyle(lineWidth: 1.5, dash: [5, 4])).foregroundStyle(BM.amber.opacity(0.45)))
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("entry.newBox")
                    ForEach(model.boxes.prefix(3)) { b in
                        Button { Task { await model.pickExisting(b.id) } } label: {
                            HStack(spacing: 12) {
                                BoxBadge(box: b)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(b.name).font(.system(size: 14.5, weight: .semibold)).foregroundStyle(BM.text)
                                    Text(b.location ?? model.t(.location_pending)).font(.system(size: 11.5)).foregroundStyle(BM.textWeak).lineLimit(1)
                                }
                                Spacer(minLength: 0)
                            }
                            .padding(.horizontal, 14).padding(.vertical, 11)
                            .card(radius: 16)
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("entry.pick.\(b.label)")
                    }
                }
                .opacity(model.entryBusy ? 0.6 : 1)
                .disabled(model.entryBusy)
                Button(model.t(.cancel)) { model.closeEntry() }
                    .font(.system(size: 13)).foregroundStyle(BM.textWeak)
                    .frame(maxWidth: .infinity).padding(.top, 2)
            }
            .padding(.horizontal, 24).padding(.top, 24).padding(.bottom, 40)
        }
    }

    // MARK: Edit

    private var edit: some View {
        VStack(alignment: .leading, spacing: 14) {
            Spacer()
            Text(model.t(.edit_title)).font(.system(size: 16, weight: .semibold)).foregroundStyle(BM.text)
            TextEditor(text: $draft)
                .font(.system(size: 16)).lineSpacing(5).foregroundStyle(BM.text)
                .scrollContentBackground(.hidden)
                .padding(.horizontal, 12).padding(.vertical, 8)
                .frame(minHeight: 130, maxHeight: 200)
                .background(BM.card, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(BM.blueTint.opacity(0.35), lineWidth: 1))
                .accessibilityIdentifier("entry.editor")
            HStack(spacing: 10) {
                OutlineButton(title: model.t(.cancel)) { model.cancelEdit() }.frame(maxWidth: .infinity)
                GradButton {
                    model.setRawText(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? model.rawText : draft)
                    Task { await model.reparse() }
                } label: { Text(model.t(.reparse)) }
                .frame(maxWidth: .infinity).layoutPriority(1)
                .accessibilityIdentifier("entry.reparse")
            }
            Spacer()
        }
        .padding(.horizontal, 24)
        .onAppear { draft = model.rawText }
    }

    // MARK: Done

    private var done: some View {
        VStack(spacing: 20) {
            Spacer()
            if let info = model.doneInfo {
                Image(systemName: "checkmark").font(.system(size: 40, weight: .bold)).foregroundStyle(.white)
                    .frame(width: 86, height: 86)
                    .background(BM.gradGreen, in: Circle())
                    .shadow(color: Color(hex: 0x10B981).opacity(0.4), radius: 25, y: 16)
                Text(info.title).font(.system(size: 21, weight: .bold)).foregroundStyle(BM.text).multilineTextAlignment(.center)
                    .accessibilityIdentifier("entry.doneTitle")
                VStack(spacing: 6) {
                    Text(info.line1)
                    Text(info.line2)
                }
                .font(.system(size: 13.5)).foregroundStyle(BM.textSub55).multilineTextAlignment(.center)
                if let tip = info.markerTip {
                    HStack(spacing: 11) {
                        Image(systemName: "pencil.line").font(.system(size: 16)).foregroundStyle(BM.amber)
                        Text(tip).font(.system(size: 13)).lineSpacing(3).foregroundStyle(BM.amber)
                    }
                    .padding(.horizontal, 15).padding(.vertical, 13)
                    .background(BM.amber.opacity(0.08), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(BM.amber.opacity(0.35), lineWidth: 1))
                }
                HStack(spacing: 10) {
                    Button {
                        model.openBox(info.boxId)
                        model.closeEntry()
                    } label: {
                        Text(model.t(.view_box)).font(.system(size: 15)).foregroundStyle(BM.blue2)
                            .frame(maxWidth: .infinity).frame(height: 52)
                            .overlay(Capsule().strokeBorder(BM.blueTint.opacity(0.4), lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("entry.viewBox")
                    GradButton { model.closeEntry() } label: { Text(model.t(.done)) }
                        .accessibilityIdentifier("entry.done")
                }
                .padding(.top, 10)
            }
            Spacer()
        }
        .padding(.horizontal, 24)
        .onAppear { Haptics.success() }
    }
}

// MARK: - Pieces

struct ItemRows: View {
    let items: [ItemDraft]
    var rowPadding: CGFloat = 11

    var body: some View {
        VStack(spacing: 0) {
            ForEach(Array(items.enumerated()), id: \.offset) { i, it in
                HStack {
                    Text(it.name).font(.system(size: 15)).foregroundStyle(BM.text)
                    Spacer()
                    Text(it.qtyText).font(BM.num(13.5)).foregroundStyle(BM.textSub)
                }
                .padding(.vertical, rowPadding).padding(.horizontal, 2)
                if i < items.count - 1 { Divider().overlay(Color.white.opacity(0.05)) }
            }
        }
    }
}

/// Badge for a label that may not belong to a saved box yet (confirm card, askbox suggestion).
struct LabelBadge: View {
    let label: String
    var colors: (String, String)? = nil
    var width: CGFloat = 44
    var height: CGFloat = 38
    var fontSize: CGFloat = 14
    var radius: CGFloat = 8

    var body: some View {
        let (a, b) = colors ?? ("#9C7A52", "#7A5E3E")
        Text(label)
            .font(BM.num(Display.badgeFontSize(label, base: fontSize), weight: .bold))
            .foregroundStyle(BM.ink).lineLimit(1).minimumScaleFactor(0.5)
            .padding(.horizontal, 3)
            .frame(width: width, height: height)
            .background(LinearGradient(colors: [Color(hexString: a), Color(hexString: b)], startPoint: .topLeading, endPoint: .bottomTrailing),
                        in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .rotationEffect(.degrees(-2))
    }
}

struct OutlineButton: View {
    let title: String
    var height: CGFloat = 52
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title).font(.system(size: 15)).foregroundStyle(Color(hex: 0xEBF0FA).opacity(0.7))
                .frame(maxWidth: .infinity).frame(height: height)
                .overlay(Capsule().strokeBorder(Color.white.opacity(0.15), lineWidth: 1))
                .contentShape(Capsule())
        }
        .buttonStyle(PressScale())
    }
}

struct ThinkingDots: View {
    var size: CGFloat = 6
    @State private var on = false

    var body: some View {
        HStack(spacing: 5) {
            ForEach(0..<3, id: \.self) { i in
                Circle().fill(BM.blue).frame(width: size, height: size)
                    .opacity(on ? 1 : 0.3)
                    .animation(.easeInOut(duration: 0.6).repeatForever().delay(Double(i) * 0.15), value: on)
            }
        }
        .onAppear { on = true }
    }
}

struct BlinkDot: View {
    var color: Color
    var size: CGFloat = 8
    @State private var on = true
    var body: some View {
        Circle().fill(color).frame(width: size, height: size)
            .opacity(on ? 1 : 0.2)
            .onAppear { withAnimation(.easeInOut(duration: 0.5).repeatForever()) { on = false } }
    }
}

/// Seven animated bars (`bm-wave`).
struct WaveBars: View {
    @State private var on = false
    private let bars: [(h: CGFloat, color: Color, d: Double)] = [
        (16, Color(hex: 0x7C9BFF), 0), (34, Color(hex: 0x93A8FF), 0.12), (24, Color(hex: 0xA78BFA), 0.24),
        (40, Color(hex: 0x8B5CF6), 0.36), (28, Color(hex: 0xA78BFA), 0.48), (36, Color(hex: 0x93A8FF), 0.6),
        (18, Color(hex: 0x7C9BFF), 0.72),
    ]

    var body: some View {
        HStack(spacing: 6) {
            ForEach(Array(bars.enumerated()), id: \.offset) { _, b in
                Capsule().fill(b.color).frame(width: 5, height: on ? b.h : b.h * 0.45)
                    .animation(.easeInOut(duration: 0.45).repeatForever().delay(b.d), value: on)
            }
        }
        .frame(height: 44)
        .onAppear { on = true }
    }
}
