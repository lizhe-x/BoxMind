import { useEffect, useState } from 'react'
import { api } from '../api'
import { useStore } from '../store'
import { T } from '../theme'

export function Login() {
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
    const t = setTimeout(() => setCooldown(cooldown - 1), 1000)
    return () => clearTimeout(t)
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
      if (r.dev_mode) showToast('开发模式:验证码已显示在下方')
    } catch (e) {
      setError((e as Error).message || '发送失败')
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
      setError((e as Error).message || '验证失败')
      setBusy(false)
    }
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '92px 30px 44px', position: 'relative', zIndex: 1, boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ fontFamily: T.fontNum, fontSize: 30, fontWeight: 700, background: 'linear-gradient(90deg,#AEC2FF,#CBB1FF)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', alignSelf: 'flex-start' }}>
          BoxMind
        </div>
        <div style={{ fontSize: 15, color: T.textSub55, lineHeight: 1.7 }}>
          {phase === 'email' ? '输入邮箱,用验证码登录或注册' : `验证码已发送至 ${email}`}
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
            {busy ? '发送中…' : '获取验证码'}
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {devCode && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(242,192,120,0.1)', border: '1px solid rgba(242,192,120,0.3)', borderRadius: 14, padding: '11px 14px' }}>
              <span style={{ fontSize: 12.5, color: T.amber }}>开发模式验证码</span>
              <span style={{ fontFamily: T.fontNum, fontSize: 18, fontWeight: 700, color: T.amber, letterSpacing: 3 }}>{devCode}</span>
            </div>
          )}
          <input
            inputMode="numeric"
            value={code}
            autoFocus
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            onKeyDown={(e) => { if (e.key === 'Enter') submit() }}
            placeholder="6 位验证码"
            style={{ ...inputStyle, fontFamily: T.fontNum, letterSpacing: 6, fontSize: 20, textAlign: 'center' }}
          />
          {error && <div style={{ fontSize: 13, color: T.red2 }}>{error}</div>}
          <div
            className="bm-press98"
            onClick={submit}
            style={{ ...btnStyle, opacity: code.trim().length >= 4 && !busy ? 1 : 0.5 }}
          >
            {busy ? '登录中…' : '登录'}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span onClick={() => { setPhase('email'); setCode(''); setError(null); setDevCode(null) }} style={{ color: T.textSub, cursor: 'pointer' }}>
              换个邮箱
            </span>
            <span
              onClick={sendCode}
              style={{ color: cooldown > 0 ? T.textWeak35 : T.blue2, cursor: cooldown > 0 ? 'default' : 'pointer' }}
            >
              {cooldown > 0 ? `重新发送 (${cooldown}s)` : '重新发送'}
            </span>
          </div>
        </div>
      )}

      <div style={{ marginTop: 20, fontSize: 11, color: 'rgba(235,240,250,0.3)', textAlign: 'center', lineHeight: 1.7 }}>
        登录即表示同意,数据归你所有,可随时导出或删除
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
