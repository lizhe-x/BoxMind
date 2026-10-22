import UIKit

/// Small haptic vocabulary: press = hold-to-talk / shutter, success = saved or found, tick = toggles.
@MainActor
enum Haptics {
    static func press() { UIImpactFeedbackGenerator(style: .medium).impactOccurred() }
    static func release() { UIImpactFeedbackGenerator(style: .light).impactOccurred() }
    static func success() { UINotificationFeedbackGenerator().notificationOccurred(.success) }
    static func warning() { UINotificationFeedbackGenerator().notificationOccurred(.warning) }
    static func tick() { UISelectionFeedbackGenerator().selectionChanged() }
}
