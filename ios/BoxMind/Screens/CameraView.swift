import SwiftUI
import BoxMindKit

/// Photo intake: viewfinder → shutter → "AI is looking…" → editable result sheet → save.
/// Port of frontend/src/screens/Camera.tsx.
struct CameraView: View {
    @Environment(AppModel.self) private var model
    @State private var camera = CameraController()
    @State private var newName = ""
    @State private var shutterBusy = false

    var body: some View {
        ZStack {
            Color(hex: 0x04060A).ignoresSafeArea()
            VStack(spacing: 0) {
                viewfinder
                if model.camPhase == .live { shutterBar }
            }
            topBar
            if model.camPhase == .result, let recog = model.recog {
                VStack { Spacer(); resultSheet(recog) }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .ignoresSafeArea(edges: .top)
        .animation(.easeOut(duration: 0.3), value: model.camPhase)
        .task { await camera.start() }
        .onDisappear { camera.stop() }
    }

    // MARK: Viewfinder

    private var viewfinder: some View {
        ZStack {
            Color(hex: 0x0A0D15)
            if camera.ready {
                CameraPreview(session: camera.session)
            } else if camera.unavailable {
                Text(model.t(.cam_no_camera)).font(.system(size: 13)).foregroundStyle(BM.textWeak)
            }
            if model.camPhase == .live {
                GeometryReader { g in
                    let w = g.size.width, h = g.size.height
                    Path { p in
                        for f in [0.33, 0.66] {
                            p.move(to: CGPoint(x: 0, y: h * f)); p.addLine(to: CGPoint(x: w, y: h * f))
                            p.move(to: CGPoint(x: w * f, y: 0)); p.addLine(to: CGPoint(x: w * f, y: h))
                        }
                    }
                    .stroke(Color.white.opacity(0.12), lineWidth: 1)
                }
            }
            if model.camPhase == .recog {
                Color(red: 3 / 255, green: 5 / 255, blue: 9 / 255).opacity(0.45)
                ScanLine()
                HStack(spacing: 10) {
                    AiAvatar(size: 22).modifier(Glow())
                    Text(model.t(.cam_recognizing)).font(.system(size: 14, weight: .medium)).foregroundStyle(BM.blue3)
                }
                .padding(.horizontal, 20).padding(.vertical, 11)
                .background(Color(red: 14 / 255, green: 19 / 255, blue: 32 / 255).opacity(0.9), in: Capsule())
                .overlay(Capsule().strokeBorder(BM.blueTint.opacity(0.3), lineWidth: 1))
                .accessibilityIdentifier("cam.recognizing")
            }
            if model.camPhase == .result {
                Color(red: 3 / 255, green: 5 / 255, blue: 9 / 255).opacity(0.55)
            }
        }
        .clipped()
    }

    private var topBar: some View {
        VStack {
            HStack(spacing: 12) {
                Button { model.go(.home) } label: {
                    Image(systemName: "chevron.left").font(.system(size: 17, weight: .bold)).foregroundStyle(.white)
                        .frame(width: 38, height: 38).background(.ultraThinMaterial, in: Circle())
                }
                .accessibilityIdentifier("cam.back")
                Text(model.t(.cam_title)).font(.system(size: 16, weight: .semibold)).foregroundStyle(.white)
                Spacer()
            }
            .padding(.horizontal, 16).padding(.top, 64)
            Spacer()
        }
    }

    private var shutterBar: some View {
        VStack(spacing: 18) {
            Text(model.t(.cam_hint)).font(.system(size: 13.5)).foregroundStyle(BM.textSub55)
                .multilineTextAlignment(.center).padding(.horizontal, 10)
            Button(action: shutter) {
                ZStack {
                    Circle().strokeBorder(Color.white.opacity(0.9), lineWidth: 4).frame(width: 74, height: 74)
                    Circle().fill(.white).frame(width: 58, height: 58)
                }
            }
            .buttonStyle(PressScale(scale: 0.92))
            .disabled(shutterBusy)
            .accessibilityIdentifier("cam.shutter")
        }
        .padding(.top, 18).padding(.horizontal, 24).padding(.bottom, 44)
        .background(Color(hex: 0x04060A))
    }

    private func shutter() {
        guard !shutterBusy else { return }
        shutterBusy = true
        Haptics.press()
        Task {
            defer { shutterBusy = false }
            var clip: PhotoClip?
            if let raw = await camera.capture() { clip = ImageResize.clip(raw) }
            #if DEBUG && targetEnvironment(simulator)
            if clip == nil { clip = ImageResize.placeholderClip() } // no camera: let the flow be exercised
            #endif
            guard let clip else {
                model.showToast(model.t(.cam_not_ready))
                return
            }
            await model.recognizePhoto(clip)
        }
    }

    // MARK: Result sheet

    private func resultSheet(_ recog: RecogDraft) -> some View {
        let target = recog.targetLabel
        return VStack(alignment: .leading, spacing: 14) {
            HStack {
                HStack(spacing: 9) {
                    AiAvatar(size: 24)
                    Text(model.t(.cam_result)).font(.system(size: 16, weight: .semibold)).foregroundStyle(BM.text)
                        .accessibilityIdentifier("cam.result")
                }
                Spacer()
                Button(model.t(.retake)) { model.retakePhoto() }
                    .font(.system(size: 13)).foregroundStyle(BM.textSub).padding(.horizontal, 8).padding(.vertical, 4)
                    .accessibilityIdentifier("cam.retake")
            }

            HStack(spacing: 12) {
                LabelBadge(label: target, colors: ("#94714B", "#6F5639"))
                VStack(alignment: .leading, spacing: 2) {
                    Text(model.t(.cam_into, ["box": L10n.boxName(for: target, lang: model.lang),
                                             "status": model.t(recog.boxExists ? .cam_existing : .cam_new)]))
                        .font(.system(size: 14, weight: .semibold)).foregroundStyle(BM.text)
                    Text(recog.boxLabel.map { model.t(.cam_label_found, ["label": $0]) } ?? model.t(.cam_label_none))
                        .font(.system(size: 11.5)).foregroundStyle(BM.textWeak)
                }
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
            .background(BM.card2, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(BM.border, lineWidth: 1))

            ScrollView {
                VStack(spacing: 0) {
                    ForEach(Array(recog.items.enumerated()), id: \.offset) { i, it in
                        itemRow(i, it)
                    }
                    addRow
                }
            }
            .fixedSize(horizontal: false, vertical: true) // size to the rows…
            .frame(maxHeight: 280)                         // …but never taller than this

            Text(model.t(.cam_footnote)).font(.system(size: 11.5)).foregroundStyle(BM.textWeak35)

            GradButton { Task { await model.confirmPhoto() } } label: {
                Text(model.entryBusy ? model.t(.cam_saving) : model.t(.cam_confirm, ["n": recog.selectedCount]))
            }
            .opacity(model.entryBusy || recog.selectedCount == 0 ? 0.6 : 1)
            .accessibilityIdentifier("cam.confirm")
        }
        .padding(.horizontal, 22).padding(.top, 22).padding(.bottom, 44)
        .frame(maxWidth: .infinity)
        .background(BM.sheet, in: UnevenRoundedRectangle(topLeadingRadius: 28, topTrailingRadius: 28))
        .overlay(alignment: .top) { Rectangle().fill(BM.border8).frame(height: 1) }
    }

    private func itemRow(_ i: Int, _ it: RecogDraft.Item) -> some View {
        HStack(spacing: 10) {
            Button { Haptics.tick(); model.toggleRecogItem(i) } label: {
                ZStack {
                    if it.selected {
                        Circle().fill(BM.grad)
                        Image(systemName: "checkmark").font(.system(size: 11, weight: .heavy)).foregroundStyle(.white)
                    } else {
                        Circle().strokeBorder(Color.white.opacity(0.25), lineWidth: 1.5)
                    }
                }
                .frame(width: 22, height: 22)
                .contentShape(Circle()) // the unselected ring alone would only be hittable on its stroke
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("cam.toggle.\(i)")
            TextField("", text: Binding(get: { it.name }, set: { model.editRecogItem(i, name: $0) }))
                .font(.system(size: 15)).foregroundStyle(it.selected ? BM.text : BM.textWeak)
                .accessibilityIdentifier("cam.name.\(i)")
            TextField("", text: Binding(get: { it.qtyText }, set: { model.editRecogItem(i, qtyText: $0) }))
                .font(BM.num(13)).foregroundStyle(BM.textSub).multilineTextAlignment(.center)
                .frame(width: 56).padding(.vertical, 5)
                .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(BM.border8, lineWidth: 1))
                .accessibilityIdentifier("cam.qty.\(i)")
            ConfidencePill(confidence: it.confidence)
        }
        .padding(.vertical, 8).padding(.horizontal, 2)
        .overlay(alignment: .bottom) { Rectangle().fill(Color.white.opacity(0.05)).frame(height: 1) }
    }

    private var addRow: some View {
        HStack(spacing: 10) {
            Text("+").font(.system(size: 15)).foregroundStyle(BM.blue)
                .frame(width: 22, height: 22)
                .overlay(Circle().strokeBorder(BM.blueTint.opacity(0.5), style: StrokeStyle(lineWidth: 1.5, dash: [3, 3])))
            TextField(model.t(.cam_add_ph), text: $newName)
                .font(.system(size: 15)).foregroundStyle(BM.text)
                .submitLabel(.done).onSubmit(addItem)
                .accessibilityIdentifier("cam.addField")
            if !newName.trimmingCharacters(in: .whitespaces).isEmpty {
                Button(model.t(.add), action: addItem)
                    .font(.system(size: 13)).foregroundStyle(BM.blue2).padding(.horizontal, 8).padding(.vertical, 4)
                    .accessibilityIdentifier("cam.add")
            }
        }
        .padding(.top, 10).padding(.bottom, 2).padding(.horizontal, 2)
    }

    private func addItem() {
        model.addRecogItem(newName)
        newName = ""
    }
}

struct ConfidencePill: View {
    @Environment(AppModel.self) private var model
    let confidence: Confidence

    var body: some View {
        let (key, color, bg): (L10nKey, Color, Color) = switch confidence {
        case .high: (.conf_high, BM.green, BM.green.opacity(0.12))
        case .medium: (.conf_medium, BM.amber, BM.amber.opacity(0.12))
        case .low: (.conf_low, BM.textWeak, Color.white.opacity(0.06))
        }
        Text(model.t(key)).font(.system(size: 10.5)).foregroundStyle(color)
            .padding(.horizontal, 8).padding(.vertical, 3).background(bg, in: Capsule())
    }
}

/// The sweeping line shown while the model looks at the photo (`bm-scan` keyframes).
struct ScanLine: View {
    @State private var down = false
    var body: some View {
        GeometryReader { g in
            Rectangle()
                .fill(LinearGradient(colors: [.clear, Color(hex: 0x7C9BFF), Color(hex: 0xA78BFA), .clear], startPoint: .leading, endPoint: .trailing))
                .frame(height: 2)
                .shadow(color: Color(hex: 0x7C9BFF).opacity(0.8), radius: 9)
                .padding(.horizontal, 24)
                .offset(y: down ? g.size.height * 0.8 : g.size.height * 0.2)
                .animation(.easeInOut(duration: 1.8).repeatForever(autoreverses: true), value: down)
                .onAppear { down = true }
        }
    }
}

struct Glow: ViewModifier {
    @State private var on = false
    func body(content: Content) -> some View {
        content.shadow(color: BM.gradA.opacity(on ? 0.9 : 0.2), radius: on ? 10 : 2)
            .animation(.easeInOut(duration: 0.55).repeatForever(autoreverses: true), value: on)
            .onAppear { on = true }
    }
}
