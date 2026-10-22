import { useEffect, useState } from 'react'
import { api } from '../api'
import { LANGS, authError, makeT } from '../i18n'
import { useStore } from '../store'
import { T } from '../theme'

export function Login() {
  const lang = useStore((s) => s.lang)
  const t = makeT(lang)
  const setLang = useStore((s) => s.setLang)
  const login = useStore((s) => s.login)
  const showToast = useStore((s) => s.showToast)

  const [phase, setPhase] = useState<'email' | 'code'>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [devCode, setDevCode] = useState<string | null>(null)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setTimeout(() => setCooldown(cooldown - 1), 1000)
    return () => clearTimeout(timer)
  }, [cooldown])

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())

  const sendCode = async () => {
    if (!emailValid || busy || cooldown > 0) return
    setBusy(true)
    setError(null)
    try {
      const r = await api.requestCode(email.trim())
      setDevCode(r.dev_mode && r.dev_code ? r.dev_code : null)
      setPhase('code')
      setCooldown(60)
      if (r.dev_mode) showToast(t('dev_toast'))
    } catch (e) {
      setError(authError(lang, (e as Error).message, 'err_send_failed'))
    } finally {
      setBusy(false)
    }
  }

  const submit = async () => {
    if (code.trim().length < 4 || busy) return
    setBusy(true)
    setError(null)
    try {
      await login(email.trim(), code.trim())
    } catch (e) {
      setError(authError(lang, (e as Error).message, 'err_verify_failed'))
      setBusy(false)
    }
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '92px 30px 44px', position: 'relative', zIndex: 1, boxSizing: 'border-box' }}>
      {/* 登录前的语言切换:登录后同步到服务端 */}
      <div style={{ position: 'absolute', top: 64, right: 24, display: 'flex', gap: 4, background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.border8}`, borderRadius: 999, padding: 3 }}>
        {LANGS.map((l) => (
          <div
            key={l.code}
            onClick={() => void setLang(l.code)}
            style={{
              fontSize: 12, padding: '5px 10px', borderRadius: 999, cursor: 'pointer',
              background: lang === l.code ? 'rgba(124,140,255,0.2)' : 'transparent',
              color: lang === l.code ? T.blue2 : T.textWeak,
            }}
          >
            {l.label}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ fontFamily: T.fontNum, fontSize: 30, fontWeight: 700, background: 'linear-gradient(90deg,#AEC2FF,#CBB1FF)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', alignSelf: 'flex-start' }}>
          BoxMind
        </div>
        <div style={{ fontSize: 15, color: T.textSub55, lineHeight: 1.7 }}>
          {phase === 'email' ? t('login_email_prompt') : t('login_code_sent', { email })}
        </div>
      </div>

      <div style={{ flex: 1 }} />

      {phase === 'email' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <input
            type="email"
            inputMode="email"
            autoCapitalize="none"
            autoCorrect="off"
            value={email}
            autoFocus
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') sendCode() }}
            placeholder="you@example.com"
            style={inputStyle}
          />
          {error && <div style={{ fontSize: 13, color: T.red2 }}>{error}</div>}
          <div
            className="bm-press98"
            onClick={sendCode}
            style={{ ...btnStyle, opacity: emailValid && !busy ? 1 : 0.5 }}
          >
            {busy ? t('sending') : t('get_code')}
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {devCode && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(242,192,120,0.1)', border: '1px solid rgba(242,192,120,0.3)', borderRadius: 14, padding: '11px 14px' }}>
              <span style={{ fontSize: 12.5, color: T.amber }}>{t('dev_code')}</span>
              <span style={{ fontFamily: T.fontNum, fontSize: 18, fontWeight: 700, color: T.amber, letterSpacing: 3 }}>{devCode}</span>
            </div>
          )}
          <input
            inputMode="numeric"
            value={code}
            autoFocus
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            onKeyDown={(e) => { if (e.key === 'Enter') submit() }}
            placeholder={t('code_ph')}
            style={{ ...inputStyle, fontFamily: T.fontNum, letterSpacing: 6, fontSize: 20, textAlign: 'center' }}
          />
          {error && <div style={{ fontSize: 13, color: T.red2 }}>{error}</div>}
          <div
            className="bm-press98"
            onClick={submit}
            style={{ ...btnStyle, opacity: code.trim().length >= 4 && !busy ? 1 : 0.5 }}
          >
            {busy ? t('signing_in') : t('sign_in')}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span onClick={() => { setPhase('email'); setCode(''); setError(null); setDevCode(null) }} style={{ color: T.textSub, cursor: 'pointer' }}>
              {t('change_email')}
            </span>
            <span
              onClick={sendCode}
              style={{ color: cooldown > 0 ? T.textWeak35 : T.blue2, cursor: cooldown > 0 ? 'default' : 'pointer' }}
            >
              {cooldown > 0 ? t('resend_in', { s: cooldown }) : t('resend')}
            </span>
          </div>
        </div>
      )}

      <div style={{ marginTop: 20, fontSize: 11, color: 'rgba(235,240,250,0.3)', textAlign: 'center', lineHeight: 1.7 }}>
        {t('login_footer')}
      </div>
    </div>
  )
}

const inputStyle = {
  height: 54,
  background: T.card,
  border: '1px solid rgba(124,140,255,0.35)',
  borderRadius: 16,
  padding: '0 18px',
  fontSize: 16,
  color: T.text,
  fontFamily: T.font,
  boxSizing: 'border-box' as const,
  width: '100%',
}

const btnStyle = {
  height: 54,
  borderRadius: 999,
  background: T.grad,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: 16,
  fontWeight: 600,
  cursor: 'pointer',
  color: T.text,
  boxShadow: '0 10px 30px rgba(99,102,241,0.4)',
}
