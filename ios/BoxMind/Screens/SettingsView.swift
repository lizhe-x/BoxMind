import SwiftUI
import BoxMindKit

/// "Me": usage, language, GPS, export, account. Port of frontend/src/screens/Settings.tsx plus account deletion.
struct SettingsView: View {
    @Environment(AppModel.self) private var model
    @State private var exportURL: URL?
    @State private var confirmDelete = false
    @State private var deleting = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(model.t(.me_title)).font(.system(size: 28, weight: .bold)).foregroundStyle(BM.text)
                usageCard
                languageSection
                gpsCard
                listCard {
                    row(model.t(.export_json), trailing: model.t(.download)) { Task { await export(.json) } }
                    divider
                    row(model.t(.export_csv), trailing: model.t(.download)) { Task { await export(.csv) } }
                    divider
                    row(model.t(.about), trailing: "v\(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")") {}
                }
                listCard {
                    HStack {
                        Text(model.t(.account)).font(.system(size: 15)).foregroundStyle(BM.text)
                        Spacer()
                        Text(model.me?.email ?? model.t(.anonymous)).font(.system(size: 13)).foregroundStyle(BM.textWeak).lineLimit(1).frame(maxWidth: 200, alignment: .trailing)
                    }
                    .padding(.horizontal, 16).padding(.vertical, 15)
                    divider
                    Button { model.logout() } label: {
                        Text(model.t(.sign_out)).font(.system(size: 15)).foregroundStyle(BM.red2).frame(maxWidth: .infinity).padding(.vertical, 15)
                    }
                    .buttonStyle(.plain)
                    divider
                    Button { confirmDelete = true } label: {
                        Text(model.lang == .zh ? "删除账号及全部数据" : "Delete account and all data")
                            .font(.system(size: 15)).foregroundStyle(BM.textWeak).frame(maxWidth: .infinity).padding(.vertical, 15)
                    }
                    .buttonStyle(.plain)
                    .disabled(deleting)
                }
                Text(model.t(.footer_yours)).font(.system(size: 11)).foregroundStyle(BM.textWeak30).frame(maxWidth: .infinity).multilineTextAlignment(.center)
            }
            .padding(.horizontal, 20).padding(.top, 12).padding(.bottom, 30)
        }
        .sheet(item: $exportURL) { url in ShareSheet(items: [url]) }
        .confirmationDialog(
            model.lang == .zh ? "删除账号?所有箱子、物品、照片和语音都会被永久删除,无法恢复。" : "Delete your account? Every box, item, photo and voice note is erased permanently.",
            isPresented: $confirmDelete, titleVisibility: .visible
        ) {
            Button(model.lang == .zh ? "永久删除" : "Delete permanently", role: .destructive) { Task { await deleteAccount() } }
            Button(model.t(.cancel), role: .cancel) {}
        }
    }

    private var usageCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(model.t(.quota)).font(.system(size: 12.5)).foregroundStyle(BM.textSub55)
                    Text(model.t(.unlimited_big)).font(BM.num(30, weight: .bold)).foregroundStyle(BM.text)
                }
                Spacer()
                HStack(spacing: 6) {
                    Circle().fill(BM.green).frame(width: 6, height: 6)
                    Text(model.t(.used_n, ["n": model.me?.used ?? 0])).font(BM.num(12.5)).foregroundStyle(BM.green)
                }
                .padding(.horizontal, 13).padding(.vertical, 7)
                .background(BM.green.opacity(0.1), in: Capsule())
                .overlay(Capsule().strokeBorder(BM.green.opacity(0.25), lineWidth: 1))
            }
            Text(model.t(.quota_note)).font(.system(size: 11.5)).foregroundStyle(BM.textWeak)
        }
        .padding(18)
        .background(LinearGradient(colors: [BM.gradA.opacity(0.14), BM.gradB.opacity(0.1)], startPoint: .topLeading, endPoint: .bottomTrailing),
                    in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(BM.blueTint.opacity(0.3), lineWidth: 1))
    }

    private var languageSection: some View {
        VStack(alignment: .leading, spacing: 9) {
            Text(model.t(.ui_lang)).font(.system(size: 13)).foregroundStyle(BM.textWeak).padding(.leading, 4)
            HStack(spacing: 9) {
                ForEach(Lang.allCases, id: \.self) { l in
                    let on = model.lang == l
                    Button { if !on { Task { await model.setLang(l) } } } label: {
                        Text(l.label).font(.system(size: 14, weight: .medium))
                            .foregroundStyle(on ? BM.blue2 : BM.textSub)
                            .frame(maxWidth: .infinity).frame(height: 44)
                            .background(on ? BM.blueTint.opacity(0.15) : BM.card, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(on ? BM.blueTint.opacity(0.5) : BM.border8, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                }
            }
            Text(model.t(.lang_note)).font(.system(size: 11.5)).foregroundStyle(BM.textWeak35).padding(.leading, 4)
        }
    }

    private var gpsCard: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                Text(model.t(.gps_auto)).font(.system(size: 15, weight: .medium)).foregroundStyle(BM.text)
                Text(model.t(.gps_desc)).font(.system(size: 12)).foregroundStyle(BM.textWeak)
            }
            Spacer()
            Toggle("", isOn: Binding(
                get: { model.me?.gpsEnabled ?? false },
                set: { v in Task { await model.updateMe(gpsEnabled: v) } }
            ))
            .labelsHidden()
            .tint(BM.gradA)
        }
        .padding(.horizontal, 16).padding(.vertical, 15)
        .card()
    }

    private func listCard<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        VStack(spacing: 0) { content() }
            .card()
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private var divider: some View { Rectangle().fill(Color.white.opacity(0.05)).frame(height: 1) }

    private func row(_ title: String, trailing: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(title).font(.system(size: 15)).foregroundStyle(BM.text)
                Spacer()
                Text(trailing).font(.system(size: 13)).foregroundStyle(BM.textWeak)
            }
            .padding(.horizontal, 16).padding(.vertical, 15)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func export(_ format: ExportFormat) async {
        do {
            let data = try await model.api.export(format: format)
            let url = FileManager.default.temporaryDirectory.appending(path: "boxmind-export.\(format.rawValue)")
            try data.write(to: url, options: .atomic)
            exportURL = url
        } catch {
            model.showToast(model.t(.export_failed))
        }
    }

    private func deleteAccount() async {
        deleting = true
        defer { deleting = false }
        do { try await model.deleteAccount() } catch { model.showToast(model.t(.op_failed)) }
    }
}

extension URL: @retroactive Identifiable {
    public var id: String { absoluteString }
}

/// UIActivityViewController wrapper for exporting files.
struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: items, applicationActivities: nil) }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}
