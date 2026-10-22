import SwiftUI
import BoxMindKit

/// Email + code sign-in. Port of frontend/src/screens/Login.tsx.
struct LoginView: View {
    @Environment(AppModel.self) private var model
    @State private var phase: Phase = .email
    @State private var email = ""
    @State private var code = ""
    @State private var busy = false
    @State private var error: String?
    @State private var devCode: String?
    @State private var cooldown = 0
    @FocusState private var focus: Field?

    enum Phase { case email, code }
    enum Field { case email, code }

    private var emailValid: Bool {
        email.trimmingCharacters(in: .whitespaces).wholeMatch(of: /[^\s@]+@[^\s@]+\.[^\s@]+/) != nil
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Spacer()
                langToggle
            }
            .padding(.top, 8)

            VStack(alignment: .leading, spacing: 10) {
                Text("BoxMind")
                    .font(BM.num(30, weight: .bold))
                    .foregroundStyle(LinearGradient(colors: [Color(hex: 0xAEC2FF), Color(hex: 0xCBB1FF)], startPoint: .leading, endPoint: .trailing))
                Text(phase == .email ? model.t(.login_email_prompt) : model.t(.login_code_sent, ["email": email]))
                    .font(.system(size: 15))
                    .foregroundStyle(BM.textSub55)
                    .lineSpacing(5)
            }
            .padding(.top, 20)

            Spacer()

            if phase == .email { emailForm } else { codeForm }

            Text(model.t(.login_footer))
                .font(.system(size: 11))
                .foregroundStyle(BM.textWeak30)
                .multilineTextAlignment(.center)
                .lineSpacing(4)
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        }
        .padding(.horizontal, 30)
        .padding(.bottom, 24)
        .onAppear { focus = .email }
        .task(id: cooldown) {
            guard cooldown > 0 else { return }
            try? await Task.sleep(for: .seconds(1))
            if !Task.isCancelled { cooldown -= 1 }
        }
    }

    private var langToggle: some View {
        HStack(spacing: 4) {
            ForEach(Lang.allCases, id: \.self) { l in
                Button { Task { await model.setLang(l) } } label: {
                    Text(l.label)
                        .font(.system(size: 12))
                        .foregroundStyle(model.lang == l ? BM.blue2 : BM.textWeak)
                        .padding(.horizontal, 10).padding(.vertical, 5)
                        .background(model.lang == l ? BM.blueTint.opacity(0.2) : .clear, in: Capsule())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(3)
        .background(Color.white.opacity(0.05), in: Capsule())
        .overlay(Capsule().strokeBorder(BM.border8, lineWidth: 1))
    }

    private var emailForm: some View {
        VStack(spacing: 14) {
            TextField("you@example.com", text: $email)
                .textContentType(.emailAddress)
                .keyboardType(.emailAddress)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.send)
                .onSubmit { Task { await sendCode() } }
                .focused($focus, equals: .email)
                .inputStyle()
                .accessibilityIdentifier("login.email")
            if let error { errorText(error) }
            GradButton(height: 54) { Task { await sendCode() } } label: {
                Text(busy ? model.t(.sending) : model.t(.get_code)).font(.system(size: 16, weight: .semibold))
            }
            .accessibilityIdentifier("login.getCode")
            .opacity(emailValid && !busy ? 1 : 0.5)
            .disabled(!emailValid || busy)
        }
    }

    private var codeForm: some View {
        VStack(spacing: 14) {
            if let devCode {
                HStack(spacing: 8) {
                    Text(model.t(.dev_code)).font(.system(size: 12.5)).foregroundStyle(BM.amber)
                    Text(devCode).font(BM.num(18, weight: .bold)).foregroundStyle(BM.amber).tracking(3)
                        .accessibilityIdentifier("login.devCode")
                }
                .padding(.horizontal, 14).padding(.vertical, 11)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(BM.amber.opacity(0.1), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(BM.amber.opacity(0.3), lineWidth: 1))
            }
            TextField(model.t(.code_ph), text: $code)
                .textContentType(.oneTimeCode)
                .keyboardType(.numberPad)
                .multilineTextAlignment(.center)
                .font(BM.num(20, weight: .medium))
                .focused($focus, equals: .code)
                .onChange(of: code) { _, v in
                    let digits = String(v.filter(\.isNumber).prefix(6))
                    if digits != v { code = digits }
                }
                .inputStyle()
                .accessibilityIdentifier("login.code")
            if let error { errorText(error) }
            GradButton(height: 54) { Task { await submit() } } label: {
                Text(busy ? model.t(.signing_in) : model.t(.sign_in)).font(.system(size: 16, weight: .semibold))
            }
            .accessibilityIdentifier("login.signIn")
            .opacity(code.count >= 4 && !busy ? 1 : 0.5)
            .disabled(code.count < 4 || busy)
            HStack {
                Button(model.t(.change_email)) {
                    phase = .email; code = ""; error = nil; devCode = nil; focus = .email
                }
                .foregroundStyle(BM.textSub)
                Spacer()
                Button(cooldown > 0 ? model.t(.resend_in, ["s": cooldown]) : model.t(.resend)) { Task { await sendCode() } }
                    .foregroundStyle(cooldown > 0 ? BM.textWeak35 : BM.blue2)
                    .disabled(cooldown > 0)
            }
            .font(.system(size: 13))
            .buttonStyle(.plain)
        }
    }

    private func errorText(_ s: String) -> some View {
        Text(s).font(.system(size: 13)).foregroundStyle(BM.red2).frame(maxWidth: .infinity, alignment: .leading)
    }

    private func sendCode() async {
        guard emailValid, !busy, cooldown == 0 else { return }
        busy = true
        error = nil
        defer { busy = false }
        do {
            let r = try await model.api.requestCode(email: email.trimmingCharacters(in: .whitespaces))
            devCode = (r.devMode == true) ? r.devCode : nil
            phase = .code
            cooldown = 60
            focus = .code
            if r.devMode == true { model.showToast(model.t(.dev_toast)) }
        } catch {
            self.error = L10n.authError(model.lang, detail: (error as? APIError)?.detail, fallback: .err_send_failed)
        }
    }

    private func submit() async {
        guard code.count >= 4, !busy else { return }
        busy = true
        error = nil
        do {
            try await model.login(email: email.trimmingCharacters(in: .whitespaces), code: code)
        } catch {
            self.error = L10n.authError(model.lang, detail: (error as? APIError)?.detail, fallback: .err_verify_failed)
            busy = false
        }
    }
}

extension APIError {
    /// The backend's `detail` string for HTTP errors; nil for transport/auth errors.
    var detail: String? {
        if case .http(_, let detail) = self { return detail }
        return nil
    }
}

private struct InputStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(.system(size: 16))
            .foregroundStyle(BM.text)
            .padding(.horizontal, 18)
            .frame(height: 54)
            .background(BM.card, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(BM.blueTint.opacity(0.35), lineWidth: 1))
    }
}

extension View {
    func inputStyle() -> some View { modifier(InputStyle()) }
}
