import SwiftUI
import AVFoundation
import PhotosUI
import BoxMindKit

/// Box detail: cover, location card, editable items, photos (add / set cover), voice notes, "record into this box".
/// Port of frontend/src/screens/BoxDetail.tsx.
struct BoxDetailView: View {
    @Environment(AppModel.self) private var model
    @State private var newItem = ""
    @State private var picks: [PhotosPickerItem] = []
    @State private var uploading = false

    var body: some View {
        if let box = model.activeBox {
            content(box)
        } else {
            Text(model.t(.box_missing)).foregroundStyle(BM.textSub)
        }
    }

    private func content(_ box: Box) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                cover(box)
                header(box)
                locationCard(box)
                itemsSection(box)
                if (box.source == "text" || box.source == "voice") && !box.items.isEmpty {
                    HStack(spacing: 7) {
                        AiAvatar(size: 16)
                        Text(model.t(.from_source, ["source": model.t(box.source == "voice" ? .source_voice : .source_text)]))
                    }
                    .font(.system(size: 12)).foregroundStyle(BM.textWeak).padding(.horizontal, 20).padding(.top, -4)
                }
                photosSection(box)
                if !box.audios.isEmpty { audiosSection(box) }
                GradButton(height: 54) {
                    model.setTargetBox(box)
                    model.go(.home)
                } label: {
                    Image(systemName: "mic.fill").font(.system(size: 16, weight: .semibold))
                    Text(model.t(.record_here)).font(.system(size: 16, weight: .semibold))
                }
                .padding(.horizontal, 20).padding(.top, 4).padding(.bottom, 40)
                .accessibilityIdentifier("detail.recordHere")
            }
        }
        .scrollDismissesKeyboard(.interactively)
        .ignoresSafeArea(edges: .top)
        .overlay(alignment: .topLeading) {
            Button { model.backFromDetail() } label: {
                Image(systemName: "chevron.left").font(.system(size: 17, weight: .bold)).foregroundStyle(.white)
                    .frame(width: 38, height: 38).background(.ultraThinMaterial, in: Circle())
            }
            .accessibilityIdentifier("detail.back")
            .padding(.leading, 16).padding(.top, 8)
        }
    }

    private func cover(_ box: Box) -> some View {
        KraftCover(box: box, height: 240, labelSize: 54, tapeWidth: 110)
            .overlay(alignment: .bottom) {
                LinearGradient(colors: [.clear, BM.bgApp], startPoint: .top, endPoint: .bottom).frame(height: 80)
            }
            .overlay(alignment: .topTrailing) {
                Text(box.cover != nil ? model.t(.cover_photo) : model.t(.cover_placeholder))
                    .font(.system(size: 11)).foregroundStyle(.white.opacity(0.75))
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(.trailing, 16).padding(.top, 64)
            }
    }

    private func header(_ box: Box) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Text(box.name).font(.system(size: 24, weight: .bold)).foregroundStyle(BM.text)
                if Display.isNewBox(box) { Chip(text: model.t(.new_box_badge), tone: .green) }
            }
            HStack(spacing: 8) {
                Chip(text: model.t(.handwritten, ["label": box.label]), tone: .amber)
                if let code = box.barcode { Chip(text: code, tone: .blue) }
                Chip(text: model.t(.updated_at, ["time": Display.fmtTime(box.updatedAt, lang: model.lang)]))
            }
        }
        .padding(.horizontal, 20).padding(.top, -12)
    }

    private func locationCard(_ box: Box) -> some View {
        VStack(spacing: 0) {
            ZStack {
                Color(hex: 0x0D1119)
                GridPattern().stroke(Color.white.opacity(0.035), lineWidth: 1)
                Rectangle().fill(BM.blueTint.opacity(0.1)).frame(width: 60).rotationEffect(.degrees(25))
                Circle().strokeBorder(BM.blueTint.opacity(0.5), lineWidth: 1).frame(width: 36, height: 36).offset(x: 20, y: 18)
                Circle().fill(BM.grad).frame(width: 13, height: 13).shadow(color: Color(hex: 0x6366F1).opacity(0.8), radius: 7)
                if let dist = Display.distText(userPos: model.userPos, lat: box.gpsLat, lng: box.gpsLng, lang: model.lang) {
                    VStack { HStack { Spacer()
                        Text(dist).font(BM.num(11)).foregroundStyle(BM.blue2).padding(.horizontal, 11).padding(.vertical, 5)
                            .background(.ultraThinMaterial, in: Capsule()).padding(10)
                    }; Spacer() }
                }
            }
            .frame(height: 106).clipped()
            HStack(spacing: 10) {
                PinIcon(size: 14)
                VStack(alignment: .leading, spacing: 2) {
                    Text(box.location ?? model.t(.location_pending)).font(.system(size: 14, weight: .medium)).foregroundStyle(BM.text)
                    Text(box.gpsLat != nil ? model.t(.gps_recorded) : model.t(.gps_none)).font(.system(size: 11.5)).foregroundStyle(BM.textWeak)
                }
                Spacer()
            }
            .padding(.horizontal, 15).padding(.vertical, 13)
        }
        .card()
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .padding(.horizontal, 20)
    }

    private func itemsSection(_ box: Box) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(model.t(.items_title)).font(.system(size: 16, weight: .semibold)).foregroundStyle(BM.text)
                Spacer()
                Text(model.t(.items_count, ["n": box.items.count])).font(.system(size: 12.5)).foregroundStyle(BM.textWeak)
            }
            VStack(spacing: 0) {
                ForEach(box.items) { item in
                    ItemEditRow(item: item) { name, qty in
                        Task { await model.updateBoxItem(boxId: box.id, itemId: item.id, name: name, qtyText: qty) }
                    } onDelete: {
                        Task { await model.deleteBoxItem(boxId: box.id, itemId: item.id) }
                    }
                    Rectangle().fill(Color.white.opacity(0.05)).frame(height: 1)
                }
                HStack(spacing: 8) {
                    Text("+").font(.system(size: 17)).foregroundStyle(BM.blue).frame(width: 16)
                    TextField(model.t(.add_item_ph), text: $newItem)
                        .font(.system(size: 15)).foregroundStyle(BM.text)
                        .submitLabel(.done).onSubmit(addItem)
                        .accessibilityIdentifier("detail.addField")
                    if !newItem.trimmingCharacters(in: .whitespaces).isEmpty {
                        Button(model.t(.add), action: addItem)
                            .font(.system(size: 13)).foregroundStyle(BM.blue2).padding(.horizontal, 8).padding(.vertical, 4)
                            .accessibilityIdentifier("detail.add")
                    }
                }
                .padding(.leading, 16).padding(.trailing, 12).padding(.vertical, 8)
            }
            .card()
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        }
        .padding(.horizontal, 20)
    }

    private func addItem() {
        guard let box = model.activeBox else { return }
        let v = newItem
        newItem = ""
        Task { await model.addBoxItem(boxId: box.id, name: v) }
    }

    private func photosSection(_ box: Box) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(model.t(.photos_title)).font(.system(size: 16, weight: .semibold)).foregroundStyle(BM.text)
                Spacer()
                if !box.photos.isEmpty { Text(model.t(.tap_cover)).font(.system(size: 12)).foregroundStyle(BM.textWeak) }
            }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(Array(box.photos.enumerated()), id: \.element) { i, p in
                        let isCover = p == box.photoURL
                        Button { Task { await model.setBoxCover(boxId: box.id, url: p) } } label: {
                            AsyncImage(url: model.api.mediaURL(p)) { img in img.resizable().scaledToFill() } placeholder: { BM.card2 }
                                .frame(width: 92, height: 92)
                                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                                .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(isCover ? BM.blue : BM.border, lineWidth: 2))
                                .overlay(alignment: .bottomLeading) {
                                    if isCover {
                                        Text(model.t(.cover_badge)).font(.system(size: 10, weight: .semibold)).foregroundStyle(.white)
                                            .padding(.horizontal, 6).padding(.vertical, 2).background(BM.grad, in: RoundedRectangle(cornerRadius: 6)).padding(5)
                                    }
                                }
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("detail.photo.\(i)")
                    }
                    PhotosPicker(selection: $picks, maxSelectionCount: 10, matching: .images) {
                        VStack(spacing: 3) {
                            if uploading {
                                ProgressView().tint(BM.blue)
                            } else {
                                Text("+").font(.system(size: 22, weight: .light))
                                Text(model.t(.add_photo)).font(.system(size: 11))
                            }
                        }
                        .foregroundStyle(BM.blue).frame(width: 92, height: 92)
                        .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(BM.blueTint.opacity(0.4), style: StrokeStyle(lineWidth: 1.5, dash: [5, 4])))
                    }
                    .disabled(uploading)
                    .accessibilityIdentifier("detail.addPhoto")
                }
            }
        }
        .padding(.horizontal, 20)
        .onChange(of: picks) { _, items in
            guard !items.isEmpty else { return }
            picks = []
            Task { await upload(items, to: box) }
        }
    }

    /// Library photos: downscale, upload one by one; the first becomes the cover when the box has none.
    private func upload(_ items: [PhotosPickerItem], to box: Box) async {
        uploading = true
        defer { uploading = false }
        var setCover = box.photoURL == nil
        for item in items {
            guard let raw = try? await item.loadTransferable(type: Data.self), let clip = ImageResize.clip(raw) else {
                model.showToast(model.t(.toast_photo_failed))
                continue
            }
            await model.addBoxPhoto(boxId: box.id, photo: clip, setCover: setCover)
            setCover = false
        }
    }

    private func audiosSection(_ box: Box) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(model.t(.voice_notes)).font(.system(size: 16, weight: .semibold)).foregroundStyle(BM.text)
            ForEach(Array(box.audios.enumerated()), id: \.offset) { i, a in
                AudioRow(url: model.api.mediaURL(a), index: i)
            }
        }
        .padding(.horizontal, 20)
    }
}

/// One editable item line: name and quantity commit when editing ends; ✕ deletes.
struct ItemEditRow: View {
    let item: Item
    let onCommit: (_ name: String?, _ qty: String?) -> Void
    let onDelete: () -> Void
    @State private var name = ""
    @State private var qty = ""
    @FocusState private var focus: Field?
    enum Field { case name, qty }

    var body: some View {
        HStack(spacing: 8) {
            TextField("", text: $name)
                .font(.system(size: 15)).foregroundStyle(BM.text)
                .focused($focus, equals: .name)
                .submitLabel(.done).onSubmit { focus = nil }
                .accessibilityIdentifier("detail.itemName.\(item.name)")
            TextField("", text: $qty)
                .font(BM.num(13)).foregroundStyle(BM.textSub).multilineTextAlignment(.center)
                .focused($focus, equals: .qty)
                .submitLabel(.done).onSubmit { focus = nil }
                .frame(width: 64).padding(.vertical, 6)
                .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(BM.border8, lineWidth: 1))
                .accessibilityIdentifier("detail.itemQty.\(item.name)")
            Button(action: onDelete) {
                Image(systemName: "xmark").font(.system(size: 12, weight: .semibold)).foregroundStyle(BM.textWeak)
                    .frame(width: 28, height: 28)
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("detail.deleteItem.\(item.name)")
        }
        .padding(.leading, 16).padding(.trailing, 10).padding(.vertical, 6)
        .onAppear { name = item.name; qty = item.qtyText }
        .onChange(of: item) { _, new in name = new.name; qty = new.qtyText } // refreshed from the server
        .onChange(of: focus) { old, new in
            guard new == nil, let old else { return }
            commit(old)
        }
    }

    private func commit(_ field: Field) {
        switch field {
        case .name:
            let v = name.trimmingCharacters(in: .whitespacesAndNewlines)
            if v.isEmpty { name = item.name } else if v != item.name { onCommit(v, nil) }
        case .qty:
            if qty != item.qtyText { onCommit(nil, qty) }
        }
    }
}

/// Tap to play / pause a voice note.
struct AudioRow: View {
    @Environment(AppModel.self) private var model
    let url: URL
    let index: Int
    @State private var player = AudioPlayer()

    var body: some View {
        Button {
            player.toggle(url)
        } label: {
            HStack(spacing: 10) {
                Image(systemName: player.playing ? "pause.fill" : "speaker.wave.2.fill")
                    .font(.system(size: 14, weight: .semibold)).foregroundStyle(.white)
                    .frame(width: 34, height: 34).background(BM.grad, in: Circle())
                Text(player.playing ? model.t(.playing) : model.t(.voice_note_n, ["n": index + 1]))
                    .font(.system(size: 14)).foregroundStyle(BM.text)
                Spacer()
            }
            .padding(.horizontal, 14).padding(.vertical, 11)
            .card(radius: 14)
        }
        .buttonStyle(.plain)
    }
}

/// Streams a remote audio file with AVPlayer.
@Observable
@MainActor
final class AudioPlayer {
    private(set) var playing = false
    private var player: AVPlayer?
    private var observer: NSObjectProtocol?

    func toggle(_ url: URL) {
        if playing {
            player?.pause()
            playing = false
            return
        }
        if player == nil {
            try? AVAudioSession.sharedInstance().setCategory(.playback)
            let item = AVPlayerItem(url: url)
            player = AVPlayer(playerItem: item)
            observer = NotificationCenter.default.addObserver(forName: .AVPlayerItemDidPlayToEndTime, object: item, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated {
                    self?.playing = false
                    self?.player?.seek(to: .zero)
                }
            }
        }
        player?.play()
        playing = true
    }
}

struct GridPattern: Shape {
    var step: CGFloat = 22
    func path(in rect: CGRect) -> Path {
        var p = Path()
        var x = rect.minX
        while x <= rect.maxX { p.move(to: CGPoint(x: x, y: rect.minY)); p.addLine(to: CGPoint(x: x, y: rect.maxY)); x += step }
        var y = rect.minY
        while y <= rect.maxY { p.move(to: CGPoint(x: rect.minX, y: y)); p.addLine(to: CGPoint(x: rect.maxX, y: y)); y += step }
        return p
    }
}
