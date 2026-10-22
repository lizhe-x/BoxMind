// Press-and-hold driver shared by the home button and the Ask screen's mic.
import SwiftUI
import BoxMindKit

/// Owns one VoiceRecorder and the begin/end hand-off into the model. `onText` gets the final transcript.
@MainActor
@Observable
final class HoldToTalk {
    private(set) var recording = false
    private let recorder = VoiceRecorder()

    func begin(model: AppModel, onPartial: @escaping @MainActor (String) -> Void,
               onUnavailable: @escaping @MainActor () -> Void) {
        guard !recording else { return }
        recording = true
        Haptics.press()
        Task {
            let locales = await VoiceRecorder.candidateLocales(uiLocale: Locale(identifier: model.lang.speechLocale))
            let ok = await recorder.start(locales: locales, onPartial: onPartial)
            if !ok {
                recording = false
                onUnavailable()
            }
        }
    }

    func end(model: AppModel, onResult: @escaping @MainActor (String, AudioClip?) -> Void) {
        guard recording else { return }
        recording = false
        Haptics.release()
        Task {
            let (text, clip) = await recorder.stop(api: model.api, language: nil)
            onResult(text, clip)
        }
    }
}

/// Touch-down / touch-up gesture (a zero-distance drag) for hold-to-talk buttons.
struct HoldGesture: ViewModifier {
    let onBegin: () -> Void
    let onEnd: () -> Void
    @State private var down = false

    func body(content: Content) -> some View {
        content.gesture(
            DragGesture(minimumDistance: 0, coordinateSpace: .local)
                .onChanged { _ in
                    if !down {
                        down = true
                        onBegin()
                    }
                }
                .onEnded { _ in
                    down = false
                    onEnd()
                }
        )
    }
}

extension View {
    func holdToTalk(onBegin: @escaping () -> Void, onEnd: @escaping () -> Void) -> some View {
        modifier(HoldGesture(onBegin: onBegin, onEnd: onEnd))
    }
}
