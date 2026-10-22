import SwiftUI
import BoxMindKit

/// Scan a box's QR / barcode → box card; unknown code → handwritten-label fallback.
/// Port of frontend/src/screens/Scan.tsx.
struct ScanView: View {
    @Environment(AppModel.self) private var model
    @State private var manualOpen = false
    @State private var manualVal = ""
    @FocusState private var manualFocused: Bool

    var body: some View {
        ZStack {
            Color(hex: 0x04060A).ignoresSafeArea()
            VStack(spacing: 0) {
                viewfinder
                if model.scanPhase == .scanning { hintBar }
            }
            topBar
            if model.scanPhase == .found, let box = model.foundBox {
                VStack { Spacer(); foundSheet(box) }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
            if manualOpen { manualSheet }
        }
        .ignoresSafeArea(edges: .top)
        .animation(.easeOut(duration: 0.3), value: model.scanPhase)
        .animation(.easeOut(duration: 0.25), value: manualOpen)
        .onChange(of: model.scanPhase) { _, phase in if phase == .found { Haptics.success() } }
    }

    private var viewfinder: some View {
        ZStack {
            LinearGradient(colors: [Color(hex: 0x10141D), Color(hex: 0x080A10)], startPoint: .topLeading, endPoint: .bottomTrailing)
            if BarcodeScanner.isSupported {
                BarcodeScanner(active: model.scanPhase == .scanning) { code in
                    Task { await model.resolveScan(code) }
                }
            } else {
                Text(model.t(.cam_no_camera)).font(.system(size: 13)).foregroundStyle(BM.textWeak).offset(y: 150)
            }
            frame
        }
        .clipped()
    }

    /// Corner-bracket reticle with the sweeping line, or the green "found" border.
    private var frame: some View {
        ZStack {
            ForEach(0..<4, id: \.self) { i in
                Corner().stroke(Color(hex: 0x93A8FF), style: StrokeStyle(lineWidth: 3, lineCap: .round))
                    .frame(width: 34, height: 34)
                    .rotationEffect(.degrees(Double(i) * 90))
                    .offset(x: (i == 0 || i == 3) ? -101 : 101, y: i < 2 ? -101 : 101)
            }
            if model.scanPhase == .scanning {
                ScanLine().frame(width: 224, height: 224)
            } else {
                RoundedRectangle(cornerRadius: 10).strokeBorder(BM.green.opacity(0.7), lineWidth: 3)
                    .frame(width: 242, height: 242)
                    .shadow(color: BM.green.opacity(0.3), radius: 15)
            }
        }
        .frame(width: 236, height: 236)
        .offset(y: -30)
    }

    private var topBar: some View {
        VStack {
            HStack(spacing: 12) {
                Button { model.go(.home) } label: {
                    Image(systemName: "chevron.left").font(.system(size: 17, weight: .bold)).foregroundStyle(.white)
                        .frame(width: 38, height: 38).background(.ultraThinMaterial, in: Circle())
                }
                .accessibilityIdentifier("scan.back")
                Text(model.t(.scan_title)).font(.system(size: 16, weight: .semibold)).foregroundStyle(.white)
                Spacer()
            }
            .padding(.horizontal, 16).padding(.top, 64)
            Spacer()
        }
    }

    private var hintBar: some View {
        VStack(spacing: 14) {
            Text(model.t(.scan_hint)).font(.system(size: 14)).foregroundStyle(BM.textSub55)
            Button { manualOpen = true; manualFocused = true } label: {
                Text(model.t(.scan_manual_link)).font(.system(size: 13.5)).foregroundStyle(BM.blue)
                    .padding(.horizontal, 10).padding(.vertical, 6)
                    .overlay(alignment: .bottom) {
                        Line().stroke(BM.blue.opacity(0.4), style: StrokeStyle(lineWidth: 1, dash: [4, 3])).frame(height: 1)
                    }
            }
            .accessibilityIdentifier("scan.manualLink")
        }
        .padding(.top, 22).padding(.horizontal, 24).padding(.bottom, 48)
        .frame(maxWidth: .infinity)
        .background(Color(hex: 0x04060A))
    }

    // MARK: Found

    private func foundSheet(_ box: Box) -> some View {
        VStack(spacing: 16) {
            HStack(spacing: 8) {
                Image(systemName: "checkmark").font(.system(size: 12, weight: .heavy)).foregroundStyle(BM.green)
                Text(model.t(.scan_found, ["code": box.barcode ?? box.label])).font(BM.num(12.5)).foregroundStyle(BM.green)
            }
            .padding(.horizontal, 14).padding(.vertical, 6)
            .background(BM.green.opacity(0.1), in: Capsule())
            .overlay(Capsule().strokeBorder(BM.green.opacity(0.25), lineWidth: 1))
            .accessibilityIdentifier("scan.found")

            Button { model.openBox(box.id) } label: {
                HStack(spacing: 14) {
                    BoxBadge(box: box, width: 56, height: 48, fontSize: 18, radius: 10)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(box.name).font(.system(size: 16, weight: .semibold)).foregroundStyle(BM.text)
                        Text([box.location, Display.distText(userPos: model.userPos, lat: box.gpsLat, lng: box.gpsLng, lang: model.lang)]
                            .compactMap { $0 }.joined(separator: " · ").nonEmpty ?? model.t(.location_pending))
                            .font(.system(size: 12.5)).foregroundStyle(BM.textSub).lineLimit(1)
                        Text("\(model.t(.items_n, ["n": box.items.count])) · \(Display.fmtTime(box.updatedAt, lang: model.lang))")
                            .font(.system(size: 12)).foregroundStyle(BM.textWeak35)
                    }
                    Spacer()
                    Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(BM.textWeak)
                }
                .padding(14)
                .background(BM.card2, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(BM.border8, lineWidth: 1))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("scan.card")

            HStack(spacing: 10) {
                Button { model.recordToFound() } label: {
                    Text(model.t(.record_here)).font(.system(size: 15, weight: .semibold)).foregroundStyle(BM.blue2)
                        .multilineTextAlignment(.center).minimumScaleFactor(0.8)
                        .frame(maxWidth: .infinity).frame(height: 50).padding(.horizontal, 8)
                        .overlay(Capsule().strokeBorder(BM.blueTint.opacity(0.4), lineWidth: 1))
                        .contentShape(Capsule())
                }
                .buttonStyle(PressScale())
                .accessibilityIdentifier("scan.recordHere")
                GradButton(height: 50) { model.openBox(box.id) } label: { Text(model.t(.view_box)) }
                    .accessibilityIdentifier("scan.viewBox")
            }
            Button(model.t(.rescan)) { model.openScan() }
                .font(.system(size: 13)).foregroundStyle(BM.textWeak).padding(.horizontal, 8).padding(.vertical, 2)
                .accessibilityIdentifier("scan.rescan")
        }
        .padding(.horizontal, 22).padding(.top, 22).padding(.bottom, 46)
        .frame(maxWidth: .infinity)
        .background(BM.sheet, in: UnevenRoundedRectangle(topLeadingRadius: 28, topTrailingRadius: 28))
        .overlay(alignment: .top) { Rectangle().fill(BM.border8).frame(height: 1) }
    }

    // MARK: Handwritten-label fallback

    private var manualSheet: some View {
        ZStack(alignment: .bottom) {
            Color(red: 2 / 255, green: 4 / 255, blue: 8 / 255).opacity(0.6).ignoresSafeArea()
                .onTapGesture { manualOpen = false }
            VStack(alignment: .leading, spacing: 14) {
                Text(model.t(.manual_title)).font(.system(size: 17, weight: .bold)).foregroundStyle(BM.text)
                Text(model.t(.manual_desc)).font(.system(size: 13)).foregroundStyle(BM.textSub).lineSpacing(3)
                TextField(model.t(.manual_ph), text: $manualVal)
                    .font(.system(size: 17)).foregroundStyle(BM.text)
                    .focused($manualFocused)
                    .submitLabel(.done).onSubmit(submitManual)
                    .padding(.horizontal, 16).frame(height: 52)
                    .background(BM.card2, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(BM.blueTint.opacity(0.35), lineWidth: 1))
                    .accessibilityIdentifier("scan.manualField")
                GradButton(action: submitManual) { Text(model.t(.confirm)).font(.system(size: 16, weight: .semibold)) }
                    .accessibilityIdentifier("scan.manualConfirm")
            }
            .padding(.horizontal, 22).padding(.top, 24).padding(.bottom, 46)
            .frame(maxWidth: .infinity)
            .background(BM.sheet, in: UnevenRoundedRectangle(topLeadingRadius: 28, topTrailingRadius: 28))
            .overlay(alignment: .top) { Rectangle().fill(BM.border8).frame(height: 1) }
        }
    }

    private func submitManual() {
        let v = manualVal
        guard !v.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        manualOpen = false
        manualVal = ""
        Task { await model.scanManual(v) }
    }
}

/// One L-shaped reticle corner (top-left; rotate for the others).
struct Corner: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: rect.minX, y: rect.maxY))
        p.addLine(to: CGPoint(x: rect.minX, y: rect.minY + 8))
        p.addQuadCurve(to: CGPoint(x: rect.minX + 8, y: rect.minY), control: CGPoint(x: rect.minX, y: rect.minY))
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.minY))
        return p
    }
}

struct Line: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: rect.minX, y: rect.midY))
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.midY))
        return p
    }
}

extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}
