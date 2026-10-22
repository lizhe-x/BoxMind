import SwiftUI
import BoxMindKit

/// Two-column box grid. Port of frontend/src/screens/Boxes.tsx.
struct BoxesView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(model.t(.my_boxes)).font(.system(size: 28, weight: .bold)).foregroundStyle(BM.text)
                    Text("\(model.boxes.count)").font(BM.num(14)).foregroundStyle(BM.blue)
                }
                LazyVGrid(columns: [GridItem(.flexible(), spacing: 14), GridItem(.flexible(), spacing: 14)], spacing: 14) {
                    ForEach(model.boxes) { box in
                        Button { model.openBox(box.id) } label: { BoxCard(box: box) }
                            .buttonStyle(PressScale())
                            .accessibilityIdentifier("box.\(box.label)")
                    }
                    newBoxTile
                }
                if model.boxes.isEmpty {
                    Text(model.t(.no_boxes))
                        .font(.system(size: 13)).foregroundStyle(BM.textWeak)
                        .multilineTextAlignment(.center).lineSpacing(5)
                        .frame(maxWidth: .infinity).padding(.top, 4)
                }
            }
            .padding(.horizontal, 20).padding(.top, 12).padding(.bottom, 30)
        }
        .refreshable { try? await model.refresh() }
    }

    private var newBoxTile: some View {
        Button {
            model.go(.home)
            model.showToast(model.t(.new_box_hint))
        } label: {
            VStack(spacing: 10) {
                Text("+").font(.system(size: 20, weight: .light)).foregroundStyle(BM.blue)
                    .frame(width: 38, height: 38).background(BM.blueTint.opacity(0.1), in: Circle())
                Text("\(model.t(.new_box_l1))\n\(model.t(.new_box_l2))")
                    .font(.system(size: 12.5)).foregroundStyle(BM.textWeak).multilineTextAlignment(.center).lineSpacing(4)
            }
            .frame(maxWidth: .infinity, minHeight: 170)
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous)
                .strokeBorder(BM.blueTint.opacity(0.3), style: StrokeStyle(lineWidth: 1.5, dash: [5, 4])))
        }
        .buttonStyle(.plain)
    }
}

struct BoxCard: View {
    @Environment(AppModel.self) private var model
    let box: Box

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            KraftCover(box: box, height: 92)
                .overlay(alignment: .topTrailing) {
                    if Display.isNewBox(box) {
                        Text(model.t(.new_badge))
                            .font(.system(size: 10, weight: .bold)).foregroundStyle(Color(hex: 0x0A2C18))
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(BM.green.opacity(0.9), in: Capsule())
                            .padding(8)
                    }
                }
            VStack(alignment: .leading, spacing: 6) {
                Text(box.name).font(.system(size: 14.5, weight: .semibold)).foregroundStyle(BM.text).lineLimit(1)
                HStack(spacing: 5) {
                    PinIcon()
                    Text(box.location ?? model.t(.location_pending)).font(.system(size: 11.5)).foregroundStyle(BM.textSub).lineLimit(1)
                }
                Text("\(box.items.isEmpty ? model.t(.empty_box) : model.t(.items_n, ["n": box.items.count])) · \(Display.fmtTime(box.updatedAt, lang: model.lang))")
                    .font(.system(size: 11)).foregroundStyle(BM.textWeak35).lineLimit(1)
            }
            .padding(.horizontal, 13).padding(.top, 12).padding(.bottom, 13)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .card()
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}
