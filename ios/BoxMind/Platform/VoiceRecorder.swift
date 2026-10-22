// Hold-to-talk capture. Port of frontend/src/voice.ts with native engines:
//  1. SpeechAnalyzer + SpeechTranscriber (iOS 26, on-device) gives the live transcript.
//  2. The same microphone tap is written to an m4a file, saved on the box after the ingest.
//  3. No on-device text → the m4a goes to /api/transcribe (gateway ASR).
// Everything is best-effort: a failed engine never blocks the other, and the caller falls back to typing.
import AVFoundation
import Speech
import BoxMindKit

@MainActor
final class VoiceRecorder {
    private let engine = AVAudioEngine()
    private var sink: CaptureSink?
    private var analyzer: SpeechAnalyzer?
    private var resultsTask: Task<Void, Never>?
    private var startTask: Task<Bool, Never>?
    private var fileURL: URL?
    private var finalText = ""
    private var volatileText = ""

    /// Download the on-device model for the locale when it is missing. Cheap when already installed.
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
    func start(locale: Locale, onPartial: @escaping @MainActor (String) -> Void) async -> Bool {
        let task = Task { await self.begin(locale: locale, onPartial: onPartial) }
        startTask = task
        return await task.value
    }

    private func begin(locale: Locale, onPartial: @escaping @MainActor (String) -> Void) async -> Bool {
        guard await AVAudioApplication.requestRecordPermission() else { return false }
        finalText = ""
        volatileText = ""
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

        // 1) on-device transcriber, only when its model is installed (the download runs in the background)
        var analyzerFormat: AVAudioFormat?
        var inputContinuation: AsyncStream<AnalyzerInput>.Continuation?
        if SpeechTranscriber.isAvailable,
           let supported = await SpeechTranscriber.supportedLocale(equivalentTo: locale),
           await Self.isInstalled(supported) {
            let t = SpeechTranscriber(locale: supported, transcriptionOptions: [],
                                      reportingOptions: [.volatileResults, .fastResults], attributeOptions: [])
            analyzerFormat = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [t])
            let (stream, cont) = AsyncStream<AnalyzerInput>.makeStream()
            inputContinuation = cont
            let a = SpeechAnalyzer(modules: [t])
            analyzer = a
            resultsTask = Task { [weak self] in
                do {
                    for try await r in t.results {
                        let text = String(r.text.characters)
                        guard let self else { return }
                        if r.isFinal {
                            self.finalText += text
                            self.volatileText = ""
                        } else {
                            self.volatileText = text
                        }
                        onPartial((self.finalText + self.volatileText).trimmingCharacters(in: .whitespaces))
                    }
                } catch { /* transcriber gave up; the file + server ASR remain */ }
            }
            do { try await a.start(inputSequence: stream) } catch {
                analyzer = nil
                analyzerFormat = nil
                inputContinuation = nil
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

        let sink = CaptureSink(file: file, continuation: inputContinuation,
                               converter: analyzerFormat.flatMap { AVAudioConverter(from: hw, to: $0) },
                               targetFormat: analyzerFormat)
        self.sink = sink
        // @Sendable: a plain closure here inherits the class's main-actor isolation and Swift 6 inserts a runtime
        // isolation check; CoreAudio calls the tap on its realtime queue, so that check trapped (TestFlight 1.0 (1)).
        input.installTap(onBus: 0, bufferSize: 4096, format: hw) { @Sendable buffer, _ in sink.handle(buffer) }
        engine.prepare()
        do { try engine.start() } catch {
            input.removeTap(onBus: 0)
            sink.finish()
            self.sink = nil
            return false // the transcriber hears nothing without the engine
        }
        return true
    }

    /// Stop, flush the transcriber, close the file; fall back to server ASR when nothing was understood.
    func stop(api: any BoxMindAPI, language: String?) async -> (text: String, audio: AudioClip?) {
        if let startTask { _ = await startTask.value } // a quick tap can release before start() returned
        startTask = nil
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        sink?.finish()
        sink = nil
        if let analyzer {
            await withTimeout(seconds: 3) { try? await analyzer.finalizeAndFinishThroughEndOfInput() }
            await withTimeout(seconds: 2) { await self.resultsTask?.value }
        }
        resultsTask?.cancel()
        resultsTask = nil
        analyzer = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)

        var text = (finalText + volatileText).trimmingCharacters(in: .whitespacesAndNewlines)
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

/// Owned by the audio tap: writes the file and feeds the analyzer. Only the realtime thread touches it after start.
private final class CaptureSink: @unchecked Sendable {
    private let file: AVAudioFile?
    private let continuation: AsyncStream<AnalyzerInput>.Continuation?
    private let converter: AVAudioConverter?
    private let targetFormat: AVAudioFormat?
    private var finished = false

    init(file: AVAudioFile?, continuation: AsyncStream<AnalyzerInput>.Continuation?,
         converter: AVAudioConverter?, targetFormat: AVAudioFormat?) {
        self.file = file
        self.continuation = continuation
        self.converter = converter
        self.targetFormat = targetFormat
    }

    func handle(_ buffer: AVAudioPCMBuffer) {
        guard !finished else { return }
        try? file?.write(from: buffer)
        guard let continuation else { return }
        if let converter, let targetFormat {
            let ratio = targetFormat.sampleRate / buffer.format.sampleRate
            let capacity = AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 32
            guard let out = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: capacity) else { return }
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
            if error == nil, out.frameLength > 0 { continuation.yield(AnalyzerInput(buffer: out)) }
        } else {
            continuation.yield(AnalyzerInput(buffer: buffer))
        }
    }

    func finish() {
        finished = true
        continuation?.finish()
    }
}

/// Run `body`, giving up (not cancelling) after `seconds`.
func withTimeout(seconds: Double, _ body: @escaping @Sendable () async -> Void) async {
    await withTaskGroup(of: Void.self) { group in
        group.addTask { await body() }
        group.addTask { try? await Task.sleep(for: .seconds(seconds)) }
        await group.next()
        group.cancelAll()
    }
}
