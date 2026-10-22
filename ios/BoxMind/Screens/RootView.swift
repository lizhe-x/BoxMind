import SwiftUI
import BoxMindKit

/// Screen router. Port of frontend/src/App.tsx.
struct RootView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.scenePhase) private var scenePhase
    @State private var talk = HoldToTalk()
    @State private var speaker = Speaker()

    var body: some View {
        ZStack {
            AppBackground()
            if !model.authChecked {
                Color.clear
            } else if !model.authed {
                LoginView()
            } else {
                screen
                    .safeAreaInset(edge: .bottom, spacing: 0) {
                        if model.screen.isTab { TabBar() }
                    }
                if model.entryPhase.showsOverlay {
                    EntryOverlay().transition(.opacity)
                }
            }
            if let toast = model.toast {
                VStack {
                    ToastView(text: toast).padding(.top, 10)
                    Spacer()
                }
                .allowsHitTesting(false)
            }
        }
        .environment(talk)
        .environment(speaker)
        .animation(.easeOut(duration: 0.25), value: model.toast)
        .animation(.easeOut(duration: 0.2), value: model.entryPhase.showsOverlay)
        .task { await model.start() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await model.reconnectIfNeeded() } } // offline launch → retry on return
        }
        .task(id: model.lang) {
            let locales = await VoiceRecorder.candidateLocales(uiLocale: Locale(identifier: model.lang.speechLocale))
            await VoiceRecorder.prepareModels(for: locales)
        }
    }

    @ViewBuilder private var screen: some View {
        switch model.screen {
        case .onboarding: OnboardingView()
        case .home: HomeView()
        case .boxes: BoxesView()
        case .boxdetail: BoxDetailView()
        case .settings: SettingsView()
        case .ask: AskView()
        case .camera: CameraView()
        case .scan: ScanView()
        }
    }
}
