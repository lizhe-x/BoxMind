// Read an answer aloud with the on-device synthesiser (plan §8.3: v1 stays on-device).
import AVFoundation
import Observation
import BoxMindKit

@MainActor
@Observable
final class Speaker: NSObject, AVSpeechSynthesizerDelegate {
    private(set) var speakingId: UUID?
    private let synth = AVSpeechSynthesizer()

    override init() {
        super.init()
        synth.delegate = self
    }

    /// Tap once to speak, tap again to stop.
    func toggle(id: UUID, text: String, lang: Lang) {
        if speakingId == id {
            synth.stopSpeaking(at: .immediate)
            speakingId = nil
            return
        }
        synth.stopSpeaking(at: .immediate)
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playback, mode: .spokenAudio, options: [])
        try? session.setActive(true)
        let u = AVSpeechUtterance(string: text)
        u.voice = AVSpeechSynthesisVoice(language: lang.speechLocale)
        u.rate = AVSpeechUtteranceDefaultSpeechRate
        speakingId = id
        synth.speak(u)
    }

    func stop() {
        synth.stopSpeaking(at: .immediate)
        speakingId = nil
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor in self.speakingId = nil }
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        Task { @MainActor in self.speakingId = nil }
    }
}
