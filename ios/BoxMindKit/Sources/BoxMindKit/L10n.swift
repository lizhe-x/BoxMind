// Language handling. Port of frontend/src/i18n.ts (the string tables live in L10nTable.swift, generated).
import Foundation

public enum Lang: String, Codable, Sendable, CaseIterable {
    case en, zh

    /// "zh", "zh-CN", "ZH-Hans" → .zh; anything else → .en.
    public static func norm(_ value: String?) -> Lang {
        (value ?? "").lowercased().hasPrefix("zh") ? .zh : .en
    }

    public var label: String {
        switch self {
        case .en: "English"
        case .zh: "中文"
        }
    }

    /// Speech-recognition locale for the UI language.
    public var speechLocale: String {
        switch self {
        case .en: "en-US"
        case .zh: "zh-CN"
        }
    }
}

public enum L10n {
    public static let storageKey = "bm_lang"

    /// Translate `key` in `lang`, substituting `{var}` placeholders.
    public static func tr(_ lang: Lang, _ key: L10nKey, _ vars: [String: any CustomStringConvertible] = [:]) -> String {
        var s = (lang == .zh ? zh[key] : en[key]) ?? en[key] ?? key.rawValue
        for (k, v) in vars {
            s = s.replacingOccurrences(of: "{\(k)}", with: String(describing: v))
        }
        return s
    }

    /// Default display name for a label the backend has not named yet ("4" → "Box 4" / "4号箱").
    public static func boxName(for label: String, lang: Lang) -> String {
        let trimmed = label.trimmingCharacters(in: .whitespaces)
        guard let m = trimmed.wholeMatch(of: /^(\d+)号?$/) else { return label }
        return lang == .zh ? "\(m.1)号箱" : "Box \(m.1)"
    }

    /// What the user should write on the box: the bare number for numeric labels.
    public static func markerText(_ label: String) -> String {
        label.hasSuffix("号") ? String(label.dropLast()) : label
    }

    /// Translate a backend auth error code; unknown detail strings are shown as-is.
    public static func authError(_ lang: Lang, detail: String?, fallback: L10nKey) -> String {
        let map: [String: L10nKey] = [
            "too_soon": .err_too_soon,
            "code_invalid": .err_code_invalid,
            "code_expired": .err_code_expired,
            "too_many": .err_too_many,
            "invalid_email": .err_invalid_email,
        ]
        guard let detail, !detail.isEmpty else { return tr(lang, fallback) }
        if let key = map[detail] { return tr(lang, key) }
        if detail.hasPrefix("send_failed") { return tr(lang, .err_send_failed) }
        return detail
    }
}
