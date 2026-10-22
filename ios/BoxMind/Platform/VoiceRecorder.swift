// Hold-to-talk capture. Port of frontend/src/voice.ts with native engines:
//  1. SpeechAnalyzer + SpeechTranscriber (iOS 26, on-device) gives the live transcript. A transcriber listens in
//     one language, so one runs per candidate language (the UI language plus the device's preferred languages,
//     at most two) on the same microphone tap, and the lane with the higher mean confidence wins.
//  2. The same microphone tap is written to an m4a file, saved on the box after the ingest.
//  3. No on-device text → the m4a goes to /api/transcribe (server ASR, when one is configured).
// Everything is best-effort: a failed engine never blocks the other, and the caller falls back to typing.
import AVFoundation
import Speech
import BoxMindKit

@MainActor
final class VoiceRecorder {
    private let engine = AVAudioEngine()
    private var sink: CaptureSink?
    private var lanes: [Lane] = []
    private var startTask: Task<Bool, Never>?
    private var fileURL: URL?
    private var preferredLocaleId = ""

    /// One transcriber listening in one language.
    @MainActor
    private final class Lane {
        let locale: Locale
        let analyzer: SpeechAnalyzer
        var task: Task<Void, Never>?
        var finalText = ""
        var volatileText = ""
        var confidenceSum = 0.0
        var confidenceCount = 0

        init(locale: Locale, analyzer: SpeechAnalyzer) {
            self.locale = locale
            self.analyzer = analyzer
        }

        var text: String { (finalText + volatileText).trimmingCharacters(in: .whitespaces) }
        var confidence: Double? { confidenceCount > 0 ? confidenceSum / Double(confidenceCount) : nil }
    }

    /// Languages worth listening in: the UI language first, then the device's preferred languages; at most two,
    /// one per language code, only those the on-device transcriber supports.
    static func candidateLocales(uiLocale: Locale) async -> [Locale] {
        var out: [Locale] = []
        guard SpeechTranscriber.isAvailable else { return out }
        for id in [uiLocale.identifier] + Locale.preferredLanguages {
            guard let supported = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: id)) else { continue }
            let code = supported.language.languageCode?.identifier
            if !out.contains(where: { $0.language.languageCode?.identifier == code }) { out.append(supported) }
            if out.count == 2 { break }
        }
        return out
    }

    /// Download the on-device models for the locales when missing. Cheap when already installed.
    static func prepareModels(for locales: [Locale]) async {
        for locale in locales { await prepareModel(for: locale) }
    }

    static func prepareModel(for locale: Locale) async {
        guard SpeechTranscriber.isAvailable,
              let supported = await SpeechTranscriber.supportedLocale(equivalentTo: locale),
              await !isInstalled(supported) else { return }
        let t = SpeechTranscriber(locale: supported, preset: .progressiveTranscription)
        if let req = try? await AssetInventory.assetInstallationRequest(supporting: [t]) {
            try? await req.downloadAndInstall()
        }
    }

    private static func isInstalled(_ locale: Locale) async -> Bool {
        await SpeechTranscriber.installedLocales.contains { $0.identifier(.bcp47) == locale.identifier(.bcp47) }
    }

    /// Start capturing. Returns false when the microphone is unavailable or denied.
    func start(locales: [Locale], onPartial: @escaping @MainActor (String) -> Void) async -> Bool {
        let task = Task { await self.begin(locales: locales, onPartial: onPartial) }
        startTask = task
        return await task.value
    }

    private func begin(locales: [Locale], onPartial: @escaping @MainActor (String) -> Void) async -> Bool {
        guard await AVAudioApplication.requestRecordPermission() else { return false }
        lanes = []
        preferredLocaleId = locales.first?.identifier(.bcp47) ?? ""
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetoothHFP])
        try? session.setActive(true)
        // No input device: touching inputNode aborts inside CoreAudio (RPC timeout), so bail out first.
        guard session.isInputAvailable, !(session.availableInputs ?? []).isEmpty else { return false }
        #if targetEnvironment(simulator)
        return false // the simulator reports an input yet still aborts when the host has no microphone
        #endif

        let input = engine.inputNode
        let hw = input.outputFormat(forBus: 0)
        guard hw.sampleRate > 0, hw.channelCount > 0 else { return false }

        // 1) on-device transcribers, one per installed candidate language (the download runs in the background)
        var targets: [CaptureSink.Target] = []
        if SpeechTranscriber.isAvailable {
            for locale in locales where await Self.isInstalled(locale) {
                let t = SpeechTranscriber(locale: locale, transcriptionOptions: [],
                                          reportingOptions: [.volatileResults, .fastResults],
                                          attributeOptions: [.transcriptionConfidence])
                guard let format = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [t]) else { continue }
                let (stream, continuation) = AsyncStream<AnalyzerInput>.makeStream()
                let lane = Lane(locale: locale, analyzer: SpeechAnalyzer(modules: [t]))
                lane.task = Task { [weak self, weak lane] in
                    do {
                        for try await r in t.results {
                            guard let self, let lane else { return }
                            let text = String(r.text.characters)
                            if r.isFinal {
                                lane.finalText += text
                                lane.volatileText = ""
                            } else {
                                lane.volatileText = text
                            }
                            for run in r.text.runs {
                                if let c = run.transcriptionConfidence {
                                    lane.confidenceSum += c
                                    lane.confidenceCount += 1
                                }
                            }
                            onPartial(self.bestText())
                        }
                    } catch { /* this transcriber gave up; the other lane, the file and server ASR remain */ }
                }
                do { try await lane.analyzer.start(inputSequence: stream) } catch {
                    lane.task?.cancel()
                    continuation.finish()
                    continue
                }
                lanes.append(lane)
                targets.append(.init(continuation: continuation, converter: AVAudioConverter(from: hw, to: format),
                                     format: format))
            }
        }

        // 2) m4a file for the voice note
        let url = FileManager.default.temporaryDirectory.appending(path: "bm-\(UUID().uuidString).m4a")
        let file = try? AVAudioFile(forWriting: url, settings: [
            AVFormatIDKey: kAudioFormatMPEG4AAC,
            AVSampleRateKey: hw.sampleRate,
            AVNumberOfChannelsKey: hw.channelCount,
            AVEncoderBitRateKey: 48_000,
        ], commonFormat: hw.commonFormat, interleaved: hw.isInterleaved)
        fileURL = file == nil ? nil : url

        let sink = CaptureSink(file: file, targets: targets)
        self.sink = sink
        // @Sendable: a plain closure here inherits the class's main-actor isolation and Swift 6 inserts a runtime
        // isolation check; CoreAudio calls the tap on its realtime queue, so that check trapped (TestFlight 1.0 (1)).
        input.installTap(onBus: 0, bufferSize: 4096, format: hw) { @Sendable buffer, _ in sink.handle(buffer) }
        engine.prepare()
        do { try engine.start() } catch {
            input.removeTap(onBus: 0)
            sink.finish()
            self.sink = nil
            return false // the transcribers hear nothing without the engine
        }
        return true
    }

    /// The lane with the higher mean confidence; with no confidence reported yet, the UI language's lane.
    private func bestText() -> String {
        let ranked = lanes.sorted { a, b in
            switch (a.confidence, b.confidence) {
            case let (x?, y?) where x != y: return x > y
            case (.some, .none): return true
            case (.none, .some): return false
            default: return a.locale.identifier(.bcp47) == preferredLocaleId
            }
        }
        return ranked.first(where: { !$0.text.isEmpty })?.text ?? ""
    }

    /// Stop, flush the transcribers, close the file; fall back to server ASR when nothing was understood.
    func stop(api: any BoxMindAPI, language: String?) async -> (text: String, audio: AudioClip?) {
        if let startTask { _ = await startTask.value } // a quick tap can release before start() returned
        startTask = nil
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        sink?.finish()
        sink = nil
        let analyzers = lanes.map(\.analyzer)
        let tasks = lanes.compactMap(\.task)
        await withTimeout(seconds: 3) {
            await withTaskGroup(of: Void.self) { group in
                for a in analyzers { group.addTask { try? await a.finalizeAndFinishThroughEndOfInput() } }
            }
        }
        await withTimeout(seconds: 2) {
            await withTaskGroup(of: Void.self) { group in
                for t in tasks { group.addTask { await t.value } }
            }
        }
        for lane in lanes { lane.task?.cancel() }
        var text = bestText()
        lanes = []
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)

        var clip: AudioClip?
        if let fileURL, let data = try? Data(contentsOf: fileURL), data.count > 1024 {
            clip = AudioClip(data: data)
            try? FileManager.default.removeItem(at: fileURL)
        }
        self.fileURL = nil
        if text.isEmpty, let clip {
            text = (try? await api.transcribe(clip: clip, language: language)) ?? ""
        }
        return (text, clip)
    }
}

/// Owned by the audio tap: writes the file and feeds every analyzer. Only the realtime thread touches it after start.
private final class CaptureSink: @unchecked Sendable {
    struct Target {
        let continuation: AsyncStream<AnalyzerInput>.Continuation
        let converter: AVAudioConverter?
        let format: AVAudioFormat
    }

    private let file: AVAudioFile?
    private let targets: [Target]
    private var finished = false

    init(file: AVAudioFile?, targets: [Target]) {
        self.file = file
        self.targets = targets
    }

    func handle(_ buffer: AVAudioPCMBuffer) {
        guard !finished else { return }
        try? file?.write(from: buffer)
        for target in targets {
            guard let converter = target.converter else {
                target.continuation.yield(AnalyzerInput(buffer: buffer))
                continue
            }
            let ratio = target.format.sampleRate / buffer.format.sampleRate
            let capacity = AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 32
            guard let out = AVAudioPCMBuffer(pcmFormat: target.format, frameCapacity: capacity) else { continue }
            var consumed = false
            var error: NSError?
            converter.convert(to: out, error: &error) { _, status in
                if consumed {
                    status.pointee = .noDataNow
                    return nil
                }
                consumed = true
                status.pointee = .haveData
                return buffer
            }
            if error == nil, out.frameLength > 0 { target.continuation.yield(AnalyzerInput(buffer: out)) }
        }
    }

    func finish() {
        finished = true
        for target in targets { target.continuation.finish() }
    }
}

/// Run `body`, returning after it finishes or after `seconds`, whichever comes first. The body keeps running in
/// the background when it overruns: a task group would wait for it (child tasks are always awaited, and the
/// analyzer's finalize does not observe cancellation), which is how hold-to-talk froze after a mixed-language
/// recording.
func withTimeout(seconds: Double, _ body: @escaping @Sendable () async -> Void) async {
    await withCheckedContinuation { (continuation: CheckedContinuation<Void, Never>) in
        let gate = ResumeOnce(continuation)
        Task {
            await body()
            gate.resume()
        }
        Task {
            try? await Task.sleep(for: .seconds(seconds))
            gate.resume()
        }
    }
}

/// Resumes a continuation exactly once, whichever racer gets there first.
private final class ResumeOnce: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<Void, Never>?

    init(_ continuation: CheckedContinuation<Void, Never>) { self.continuation = continuation }

    func resume() {
        lock.lock()
        let c = continuation
        continuation = nil
        lock.unlock()
        c?.resume()
    }
}
