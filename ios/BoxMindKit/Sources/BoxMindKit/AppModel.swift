// Application state. Port of frontend/src/store.ts; actions keep the same names so the
// frozen web client and its tests stay the behaviour spec.
import Foundation
import Observation

public enum Screen: String, Sendable {
    case onboarding, home, ask, boxes, boxdetail, settings, camera, scan

    public var isTab: Bool { self == .home || self == .boxes || self == .settings }
}

/// Where the entry overlay is. `idle` = hidden; `input` = hidden too, but the home input keeps focus.
public enum EntryPhase: String, Sendable {
    case idle, input, recording, parsing, confirm, askbox, edit, done

    public var showsOverlay: Bool { self != .idle && self != .input }
}

public enum EntrySource: String, Sendable { case text, voice, photo }

public enum CamPhase: String, Sendable { case live, recog, result }
public enum ScanPhase: String, Sendable { case scanning, found }

/// One chat bubble on the Ask screen.
public struct AskMsg: Identifiable, Equatable, Sendable {
    public enum Who: Sendable { case user, ai }
    public let id: UUID
    public var who: Who
    public var text: String
    public var streaming = false
    public var boxes: [BoxRef]?
    /// Destructive agent actions waiting for the user's confirmation.
    public var confirm: [AgentAction]?

    public init(id: UUID = UUID(), who: Who, text: String, streaming: Bool = false,
                boxes: [BoxRef]? = nil, confirm: [AgentAction]? = nil) {
        self.id = id
        self.who = who
        self.text = text
        self.streaming = streaming
        self.boxes = boxes
        self.confirm = confirm
    }
}

/// What the "done" card shows after an ingest.
public struct DoneInfo: Equatable, Sendable {
    public var boxId: String
    public var title: String
    public var line1: String
    public var line2: String
    public var markerTip: String?
}

@MainActor
@Observable
public final class AppModel {
    public static let onboardedKey = "bm_onboarded"

    public let api: any BoxMindAPI
    private let prefs: any PreferenceStore
    private let location: any LocationProvider

    public private(set) var lang: Lang
    public private(set) var authed = false
    public private(set) var authChecked = false
    public private(set) var screen: Screen
    public private(set) var backTo: Screen = .boxes
    public private(set) var activeBoxId: String?
    public internal(set) var me: Me?
    public internal(set) var boxes: [Box] = []
    public internal(set) var userPos: GeoPoint?
    public private(set) var toast: String?
    private var toastTask: Task<Void, Never>?

    // Entry overlay
    public internal(set) var entryPhase: EntryPhase = .idle
    public internal(set) var entrySource: EntrySource = .text
    public internal(set) var rawText = ""
    public internal(set) var liveTranscript = ""
    public internal(set) var parsed: InterpretResult?
    /// "Record into this box" lock (set from the scan screen).
    public internal(set) var targetBox: Box?
    public internal(set) var doneInfo: DoneInfo?
    public internal(set) var entryBusy = false
    /// Voice clip kept until the items are saved, then attached to the box best-effort.
    public internal(set) var pendingAudio: AudioClip?

    // Ask / agent
    public internal(set) var askMsgs: [AskMsg] = []
    public internal(set) var thinking = false

    // Photo intake
    public internal(set) var camPhase: CamPhase = .live
    public internal(set) var recog: RecogDraft?
    /// The shot kept until the items are saved, then stored as the box cover.
    public internal(set) var pendingPhoto: PhotoClip?

    // Scan
    public internal(set) var scanPhase: ScanPhase = .scanning
    public internal(set) var foundBox: Box?

    public init(api: any BoxMindAPI, prefs: any PreferenceStore, location: any LocationProvider = NoLocation()) {
        self.api = api
        self.prefs = prefs
        self.location = location
        lang = Lang.norm(prefs.string(L10n.storageKey))
        screen = prefs.string(Self.onboardedKey) != nil ? .home : .onboarding
    }

    // MARK: Strings

    public func t(_ key: L10nKey, _ vars: [String: any CustomStringConvertible] = [:]) -> String {
        L10n.tr(lang, key, vars)
    }

    public var activeBox: Box? { boxes.first { $0.id == activeBoxId } }

    private var onboardedScreen: Screen { prefs.string(Self.onboardedKey) != nil ? .home : .onboarding }

    // MARK: Session

    public func setLang(_ newLang: Lang) async {
        prefs.set(newLang.rawValue, for: L10n.storageKey)
        lang = newLang
        if authed { await updateMe(lang: newLang.rawValue) }
    }

    /// Restore the session on launch: no token → login screen; token → load profile and boxes.
    /// A rejected token means login; any other failure (offline, server down) keeps the session so the
    /// user is not asked for a code again — the screens show their empty states and a toast.
    public func start() async {
        guard api.hasToken else {
            authed = false
            authChecked = true
            return
        }
        do {
            try await refresh()
            authed = true
            authChecked = true
        } catch APIError.unauthorized {
            authed = false
            authChecked = true
            return
        } catch APIError.noAuth {
            authed = false
            authChecked = true
            return
        } catch {
            authed = true
            authChecked = true
            showToast(t(.toast_offline))
            return
        }
        if me?.gpsEnabled == true { await refreshPosition(announceDenied: false) }
    }

    /// After an offline start: retry loading the profile when the app comes back to the foreground.
    public func reconnectIfNeeded() async {
        guard authed, me == nil else { return }
        do {
            try await refresh()
            if me?.gpsEnabled == true { await refreshPosition(announceDenied: false) }
        } catch APIError.unauthorized {
            logout()
        } catch {
            showToast(t(.toast_offline))
        }
    }

    /// Ask the platform where we are. `announceDenied` shows the "allow it in Settings" hint once (used when
    /// the user flips the GPS switch on); the launch-time lookup stays silent, like the web client.
    public func refreshPosition(announceDenied: Bool) async {
        switch await location.currentPosition() {
        case .position(let p): userPos = p
        case .denied:
            userPos = nil
            if announceDenied { showToast(t(.gps_denied)) }
        case .unavailable: userPos = nil
        }
    }

    public func login(email: String, code: String) async throws {
        let chosen = lang // picked on the login screen before signing in
        _ = try await api.verifyCode(email: email, code: code)
        await start()
        if let me, Lang.norm(me.lang) != chosen {
            // New account or new device: push the local choice so the server generates names in it.
            lang = chosen
            prefs.set(chosen.rawValue, for: L10n.storageKey)
            await updateMe(lang: chosen.rawValue)
        }
        screen = onboardedScreen
    }

    public func logout() {
        api.logout()
        authed = false
        me = nil
        boxes = []
        activeBoxId = nil
        askMsgs = []
        targetBox = nil
        entryPhase = .idle
        recog = nil
        pendingPhoto = nil
        foundBox = nil
        screen = onboardedScreen
    }

    public func refresh() async throws {
        async let me = api.me()
        async let boxes = api.boxes()
        let (m, b) = try await (me, boxes)
        let serverLang = Lang.norm(m.lang) // once signed in the server owns the language
        prefs.set(serverLang.rawValue, for: L10n.storageKey)
        self.me = m
        self.boxes = b
        lang = serverLang
    }

    public func updateMe(lang: String? = nil, gpsEnabled: Bool? = nil) async {
        let prev = me
        if var optimistic = prev { // optimistic update so toggles respond immediately
            if let lang { optimistic.lang = lang }
            if let gpsEnabled { optimistic.gpsEnabled = gpsEnabled }
            me = optimistic
        }
        do {
            me = try await api.updateMe(lang: lang, gpsEnabled: gpsEnabled)
        } catch {
            if let prev { me = prev }
            showToast(t(.toast_settings_failed))
            return
        }
        if let gpsEnabled { // the switch also drives the position lookup
            if gpsEnabled { await refreshPosition(announceDenied: true) } else { userPos = nil }
        }
    }

    public func deleteAccount() async throws {
        try await api.deleteAccount()
        logout()
    }

    public func finishOnboarding() {
        prefs.set("1", for: Self.onboardedKey)
        screen = .home
    }

    // MARK: Navigation

    public func go(_ s: Screen) { screen = s }

    public func openBox(_ id: String) {
        backTo = screen == .boxdetail ? backTo : screen
        activeBoxId = id
        screen = .boxdetail
    }

    public func backFromDetail() {
        screen = backTo == .boxdetail ? .boxes : backTo
    }

    public func showToast(_ message: String) {
        toastTask?.cancel()
        toast = message
        toastTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(2.6))
            guard !Task.isCancelled else { return }
            self?.toast = nil
        }
    }

    public func setTargetBox(_ box: Box?) { targetBox = box }

    // MARK: Entry — text and voice into the same pipeline

    /// Typed on the home screen: no overlay until the parse comes back.
    public func textEntry(_ text: String) async {
        guard !text.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        entrySource = .text
        parsed = nil
        doneInfo = nil
        await submitText(text)
    }

    public func closeEntry() {
        entryPhase = .idle
        rawText = ""
        liveTranscript = ""
        parsed = nil
        entryBusy = false
    }

    public func setRawText(_ text: String) { rawText = text }

    public func beginRecording() {
        entryPhase = .recording
        entrySource = .voice
        rawText = ""
        liveTranscript = ""
        parsed = nil
        doneInfo = nil
        pendingAudio = nil
    }

    public func setLiveTranscript(_ text: String) { liveTranscript = text }

    /// Recording ended. Empty text → back home with a hint to type, so the loop never dead-ends.
    public func finishRecording(text: String, audio: AudioClip?) async {
        pendingAudio = audio
        let v = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if v.isEmpty {
            entryPhase = .idle
            liveTranscript = ""
            screen = .home
            showToast(t(.toast_not_heard))
        } else {
            await submitText(v)
        }
    }

    /// One sentence → interpret → ingest confirm card / ask which box / query chat / agent.
    public func submitText(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !entryBusy else { return }
        rawText = text
        entryPhase = .parsing
        entryBusy = true
        let target = targetBox
        do {
            let result = try await api.interpret(text: text, targetBoxId: target?.id)
            switch result.intent {
            case .query:
                entryPhase = .idle
                entryBusy = false
                openAsk()
                await ask(text)
            case .operation:
                entryPhase = .idle
                entryBusy = false
                liveTranscript = ""
                openAsk()
                await agentSend(text)
            case .ingest:
                if result.items.isEmpty {
                    entryPhase = .input
                    entryBusy = false
                    showToast(t(.toast_no_items))
                    return
                }
                parsed = result
                entryBusy = false
                entryPhase = (target != nil || result.boxLabel != nil) ? .confirm : .askbox
            }
        } catch {
            entryPhase = .input
            entryBusy = false
            showToast(t(.toast_parse_failed))
        }
    }

    public func toEdit() { entryPhase = .edit }
    public func cancelEdit() { entryPhase = .confirm }
    public func reparse() async { await submitText(rawText) }

    public func confirmEntry() async {
        guard let p = parsed, !entryBusy else { return }
        entryBusy = true
        do {
            let res = try await api.ingest(IngestRequest(
                boxId: targetBox?.id ?? p.box?.id, boxLabel: p.boxLabel, items: p.items,
                locationText: p.locationText, gpsLat: userPos?.lat, gpsLng: userPos?.lng,
                rawText: rawText, source: entrySource.rawValue))
            targetBox = nil
            let line2: String
            if let loc = res.box.location { line2 = t(.done_location, ["loc": loc]) }
            else if userPos != nil { line2 = t(.done_gps) }
            else { line2 = t(.done_no_location) }
            await finishIngest(res, items: p.items, line2: line2, markerTip: nil)
        } catch {
            entryBusy = false
            showToast(t(.toast_save_failed))
        }
    }

    public func pickNewBox() async {
        guard let p = parsed, !entryBusy else { return }
        entryBusy = true
        let label = p.nextLabel
        do {
            let res = try await api.ingest(IngestRequest(
                boxLabel: label, items: p.items, locationText: p.locationText,
                gpsLat: userPos?.lat, gpsLng: userPos?.lng, rawText: rawText, source: entrySource.rawValue))
            await finishIngest(res, items: p.items,
                               line2: userPos != nil ? t(.done_gps) : t(.done_no_location),
                               markerTip: t(.marker_tip, ["label": L10n.markerText(label)]),
                               title: t(.done_created, ["name": res.box.name]))
        } catch {
            entryBusy = false
            showToast(t(.toast_save_failed))
        }
    }

    public func pickExisting(_ boxId: String) async {
        guard let p = parsed, !entryBusy else { return }
        entryBusy = true
        do {
            let res = try await api.ingest(IngestRequest(
                boxId: boxId, items: p.items, locationText: p.locationText,
                gpsLat: userPos?.lat, gpsLng: userPos?.lng, rawText: rawText, source: entrySource.rawValue))
            await finishIngest(res, items: p.items,
                               line2: res.box.location.map { t(.done_location, ["loc": $0]) } ?? t(.done_no_location),
                               markerTip: nil, title: t(.done_saved, ["name": res.box.name]))
        } catch {
            entryBusy = false
            showToast(t(.toast_save_failed))
        }
    }

    /// Shared tail of every ingest: attach the voice clip (best-effort), refresh, show the done card.
    private func finishIngest(_ res: IngestResult, items: [ItemDraft], line2: String, markerTip: String?,
                              title: String? = nil) async {
        if let clip = pendingAudio {
            _ = try? await api.uploadAudio(boxId: res.box.id, clip: clip) // items are saved; a lost clip is fine
        }
        try? await refresh()
        pendingAudio = nil
        entryBusy = false
        doneInfo = DoneInfo(
            boxId: res.box.id,
            title: title ?? (res.created ? t(.done_created, ["name": res.box.name]) : t(.done_saved, ["name": res.box.name])),
            line1: Display.fmtItems(items), line2: line2, markerTip: markerTip)
        entryPhase = .done
    }

    // MARK: Ask / agent

    public func openAsk() {
        if askMsgs.isEmpty { askMsgs = [AskMsg(who: .ai, text: t(.greeting))] }
        screen = .ask
    }

    /// From the Ask screen: questions stream, everything else (operations, clarifications) goes to the agent.
    public func chatSend(_ text: String) async {
        let v = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !v.isEmpty, !thinking else { return }
        if let parsed = try? await api.interpret(text: v, targetBoxId: nil), parsed.intent != .query {
            await agentSend(v)
        } else {
            await ask(v) // parse failure → treat as a question
        }
    }

    public func ask(_ question: String) async {
        guard !thinking else { return }
        askMsgs.append(AskMsg(who: .user, text: question))
        thinking = true
        screen = .ask
        do {
            for try await event in api.askStream(question: question) {
                switch event {
                case .delta(let d):
                    if let i = askMsgs.indices.last, askMsgs[i].who == .ai, askMsgs[i].streaming {
                        askMsgs[i].text += d
                    } else {
                        askMsgs.append(AskMsg(who: .ai, text: d, streaming: true))
                    }
                    thinking = false
                case .done(let boxes, _):
                    if let i = askMsgs.indices.last, askMsgs[i].who == .ai {
                        askMsgs[i].streaming = false
                        askMsgs[i].boxes = boxes
                    }
                    thinking = false
                    me?.used += 1
                case .error(let message):
                    throw APIError.http(status: 500, detail: message)
                }
            }
            thinking = false
        } catch {
            thinking = false
            askMsgs.removeAll { $0.who == .ai && $0.streaming }
            askMsgs.append(AskMsg(who: .ai, text: t(.ask_error)))
        }
    }

    public func agentSend(_ message: String) async {
        guard !thinking else { return }
        let history = askMsgs
            .filter { !$0.text.isEmpty && $0.confirm == nil } // confirm cards are not history
            .map { AgentMessage(role: $0.who == .user ? "user" : "assistant", content: $0.text) }
        askMsgs.append(AskMsg(who: .user, text: message))
        thinking = true
        screen = .ask
        do {
            let resp = try await api.agent(message: message, history: history, gps: userPos)
            thinking = false
            if resp.type == .confirm {
                askMsgs.append(AskMsg(who: .ai, text: resp.text.isEmpty ? t(.agent_confirm_text) : resp.text,
                                      confirm: resp.actions ?? []))
                if !(resp.executed ?? []).isEmpty { try? await refresh() } // siblings already ran this turn
            } else {
                askMsgs.append(AskMsg(who: .ai, text: resp.text.isEmpty ? t(.agent_ok) : resp.text))
                try? await refresh() // the agent may have run tools (rename, move, undo…) before replying
            }
        } catch {
            thinking = false
            askMsgs.append(AskMsg(who: .ai, text: t(.agent_error)))
        }
    }

    public func agentConfirm(_ actions: [AgentAction]) async {
        thinking = true
        for i in askMsgs.indices where askMsgs[i].confirm != nil { askMsgs[i].confirm = nil }
        var results: [String] = []
        for a in actions {
            do {
                let r = try await api.agentExecute(tool: a.tool, args: a.args)
                results.append(r.summary ?? (r.ok ? t(.exec_done) : (r.error ?? t(.exec_incomplete))))
            } catch {
                results.append(t(.exec_failed))
            }
        }
        try? await refresh()
        thinking = false
        askMsgs.append(AskMsg(who: .ai, text: results.joined(separator: "; ")))
    }

    public func agentCancel() {
        for i in askMsgs.indices where askMsgs[i].confirm != nil { askMsgs[i].confirm = nil }
        askMsgs.append(AskMsg(who: .ai, text: t(.cancelled)))
    }

    // MARK: Photo intake

    public func openCamera() {
        camPhase = .live
        recog = nil
        screen = .camera
    }

    public func recognizePhoto(_ photo: PhotoClip) async {
        camPhase = .recog
        pendingPhoto = photo // kept for the cover once the items are saved
        do {
            let r = try await api.recognize(photo: photo)
            if r.items.isEmpty {
                camPhase = .live
                showToast(t(.recog_none))
                return
            }
            recog = RecogDraft(boxLabel: r.boxLabel, boxExists: r.boxExists, nextLabel: r.nextLabel,
                               items: r.items.map { .init(name: $0.name, qtyText: $0.qtyText, confidence: $0.confidence,
                                                          selected: $0.confidence != .low) })
            camPhase = .result
        } catch {
            camPhase = .live
            if case APIError.http(let status, _) = error, status == 502 { showToast(t(.recog_unavailable)) }
            else { showToast(t(.recog_failed)) }
        }
    }

    public func retakePhoto() {
        camPhase = .live
        recog = nil
    }

    public func toggleRecogItem(_ i: Int) {
        guard let r = recog, r.items.indices.contains(i) else { return }
        recog?.items[i].selected.toggle()
    }

    public func editRecogItem(_ i: Int, name: String? = nil, qtyText: String? = nil) {
        guard let r = recog, r.items.indices.contains(i) else { return }
        if let name { recog?.items[i].name = name }
        if let qtyText { recog?.items[i].qtyText = qtyText }
    }

    public func addRecogItem(_ name: String) {
        let n = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard recog != nil, !n.isEmpty else { return }
        recog?.items.append(.init(name: n, qtyText: "×1", confidence: .high, selected: true))
    }

    /// Save the selected items into the handwritten (or next free) box and attach the photo as cover.
    public func confirmPhoto() async {
        guard let r = recog, !entryBusy else { return }
        let chosen = r.items.filter(\.selected).map { ItemDraft(name: $0.name, qtyText: $0.qtyText) }
        if chosen.isEmpty {
            showToast(t(.select_one))
            return
        }
        entryBusy = true
        let label = r.targetLabel
        do {
            let res = try await api.ingest(IngestRequest(boxLabel: label, items: chosen, gpsLat: userPos?.lat,
                                                         gpsLng: userPos?.lng, source: "photo"))
            if let photo = pendingPhoto {
                _ = try? await api.uploadPhoto(boxId: res.box.id, photo: photo, setCover: true) // items are saved; a lost photo is fine
            }
            try? await refresh()
            screen = .home
            camPhase = .live
            recog = nil
            pendingPhoto = nil
            entryBusy = false
            doneInfo = DoneInfo(
                boxId: res.box.id,
                title: res.created ? t(.done_created, ["name": res.box.name]) : t(.done_saved, ["name": res.box.name]),
                line1: Display.fmtItems(chosen), line2: t(.photo_line2),
                markerTip: res.created ? t(.marker_tip_short, ["label": L10n.markerText(label)]) : nil)
            entryPhase = .done
        } catch {
            entryBusy = false
            showToast(t(.toast_save_failed))
        }
    }

    // MARK: Scan

    public func openScan() {
        scanPhase = .scanning
        foundBox = nil
        screen = .scan
    }

    public func resolveScan(_ code: String) async {
        do {
            let r = try await api.resolveCode(code: code, label: nil, create: false)
            foundBox = r.box
            scanPhase = .found
        } catch {
            if case APIError.http(let status, _) = error, status == 404 { showToast(t(.scan_unknown)) }
            else { showToast(t(.scan_failed)) }
        }
    }

    /// Handwritten-label fallback: finds the box, or creates it.
    public func scanManual(_ label: String) async {
        let v = label.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !v.isEmpty else { return }
        do {
            let r = try await api.resolveCode(code: nil, label: v, create: true)
            foundBox = r.box
            scanPhase = .found
        } catch {
            showToast(t(.op_failed))
        }
    }

    /// "Record into this box": lock the found box as the entry target and go home.
    public func recordToFound() {
        guard let b = foundBox else { return }
        targetBox = b
        screen = .home
    }

    // MARK: Box editing (detail screen)

    public func addBoxPhoto(boxId: String, photo: PhotoClip, setCover: Bool) async {
        do {
            _ = try await api.uploadPhoto(boxId: boxId, photo: photo, setCover: setCover)
            try await refresh()
        } catch {
            showToast(t(.toast_photo_failed))
        }
    }

    public func setBoxCover(boxId: String, url: String) async {
        do {
            _ = try await api.setCover(boxId: boxId, url: url)
            try await refresh()
            showToast(t(.toast_cover_set))
        } catch {
            showToast(t(.toast_cover_failed))
        }
    }

    public func addBoxItem(boxId: String, name: String) async {
        let n = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !n.isEmpty else { return }
        do {
            _ = try await api.addItem(boxId: boxId, name: n, qtyText: nil)
            try await refresh()
        } catch {
            showToast(t(.toast_add_failed))
        }
    }

    public func updateBoxItem(boxId: String, itemId: String, name: String? = nil, qtyText: String? = nil) async {
        do {
            _ = try await api.updateItem(boxId: boxId, itemId: itemId, name: name, qtyText: qtyText)
            try await refresh()
        } catch {
            showToast(t(.toast_save_item_failed))
        }
    }

    public func deleteBoxItem(boxId: String, itemId: String) async {
        do {
            try await api.deleteItem(boxId: boxId, itemId: itemId)
            try await refresh()
        } catch {
            showToast(t(.toast_delete_failed))
        }
    }
}
