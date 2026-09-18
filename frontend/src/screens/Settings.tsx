import { api } from '../api'
import { LANGS, makeT } from '../i18n'
import { useStore } from '../store'
import { T } from '../theme'

export function Settings() {
  const lang = useStore((s) => s.lang)
  const t = makeT(lang)
  const me = useStore((s) => s.me)
  const setLang = useStore((s) => s.setLang)
  const updateMe = useStore((s) => s.updateMe)
  const showToast = useStore((s) => s.showToast)
  const logout = useStore((s) => s.logout)

  const used = me?.used ?? 0
  const gpsOn = me?.gps_enabled ?? false

  const exportData = async (fmt: 'json' | 'csv') => {
    try {
      const r = await fetch(api.exportUrl(fmt), { headers: { Authorization: `Bearer ${api.authToken()}` } })
      if (!r.ok) throw new Error()
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `boxmind-export.${fmt}`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      showToast(t('export_failed'))
    }
  }

  return (
    <div
      style={{
        height: '100%', overflow: 'auto', padding: '76px 20px 110px', position: 'relative',
        zIndex: 1, boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 16,
      }}
    >
      <div style={{ fontSize: 28, fontWeight: 700, color: T.text }}>{t('me_title')}</div>

      {/* 用量卡(无限制使用) */}
      <div
        style={{
          background: 'linear-gradient(135deg,rgba(77,124,254,0.14),rgba(139,92,246,0.1))',
          border: '1px solid rgba(124,140,255,0.3)', borderRadius: 20, padding: 18,
          display: 'flex', flexDirection: 'column', gap: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ fontSize: 12.5, color: T.textSub55 }}>{t('quota')}</div>
            <div style={{ fontFamily: T.fontNum, fontSize: 30, fontWeight: 700, lineHeight: 1, color: T.text }}>{t('unlimited_big')}</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(124,255,178,0.1)', border: '1px solid rgba(124,255,178,0.25)', borderRadius: 999, padding: '7px 13px' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: T.green, display: 'inline-block' }} />
            <span style={{ fontSize: 12.5, color: T.green, fontFamily: T.fontNum }}>{t('used_n', { n: used })}</span>
          </div>
        </div>
        <div style={{ fontSize: 11.5, color: T.textWeak }}>{t('quota_note')}</div>
      </div>

      {/* 语言 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
        <div style={{ fontSize: 13, color: T.textWeak, paddingLeft: 4 }}>{t('ui_lang')}</div>
        <div style={{ display: 'flex', gap: 9 }}>
          {LANGS.map((l) => {
            const on = lang === l.code
            return (
              <div
                key={l.code}
                onClick={() => !on && void setLang(l.code)}
                style={{
                  flex: 1, height: 44, borderRadius: 14,
                  background: on ? 'rgba(124,140,255,0.15)' : T.card,
                  border: `1px solid ${on ? 'rgba(124,140,255,0.5)' : T.border8}`,
                  color: on ? T.blue2 : T.textSub, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 14, fontWeight: 500, cursor: 'pointer',
                }}
              >
                {l.label}
              </div>
            )
          })}
        </div>
        <div style={{ fontSize: 11.5, color: T.textWeak35, paddingLeft: 4 }}>{t('lang_note')}</div>
      </div>

      {/* GPS 开关 */}
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 20, padding: '15px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <div style={{ fontSize: 15, fontWeight: 500, color: T.text }}>{t('gps_auto')}</div>
          <div style={{ fontSize: 12, color: T.textWeak }}>{t('gps_desc')}</div>
        </div>
        <div
          onClick={() => updateMe({ gps_enabled: !gpsOn })}
          style={{
            width: 48, height: 29, borderRadius: 999, background: gpsOn ? T.grad : 'rgba(255,255,255,0.12)',
            position: 'relative', cursor: 'pointer', transition: 'background 0.25s', flexShrink: 0,
          }}
        >
          <div
            style={{
              position: 'absolute', top: 2.5, left: 2.5, width: 24, height: 24, borderRadius: '50%',
              background: '#fff', boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
              transform: gpsOn ? 'translateX(19px)' : 'translateX(0)', transition: 'transform 0.25s',
            }}
          />
        </div>
      </div>

      {/* 列表 */}
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 20, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div
          onClick={() => exportData('json')}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)', cursor: 'pointer' }}
        >
          <div style={{ fontSize: 15, color: T.text }}>{t('export_json')}</div>
          <div style={{ fontSize: 13, color: T.textWeak }}>{t('download')}</div>
        </div>
        <div
          onClick={() => exportData('csv')}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)', cursor: 'pointer' }}
        >
          <div style={{ fontSize: 15, color: T.text }}>{t('export_csv')}</div>
          <div style={{ fontSize: 13, color: T.textWeak }}>{t('download')}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 16px' }}>
          <div style={{ fontSize: 15, color: T.text }}>{t('about')}</div>
          <div style={{ fontSize: 13, color: T.textWeak }}>v0.1 MVP</div>
        </div>
      </div>

      {/* 账户 */}
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 20, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 15, color: T.text }}>{t('account')}</div>
          <div style={{ fontSize: 13, color: T.textWeak, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {me?.email || t('anonymous')}
          </div>
        </div>
        <div onClick={logout} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '15px 16px', cursor: 'pointer' }}>
          <div style={{ fontSize: 15, color: T.red2 }}>{t('sign_out')}</div>
        </div>
      </div>

      <div style={{ fontSize: 11, color: 'rgba(235,240,250,0.3)', textAlign: 'center', lineHeight: 1.7 }}>
        {t('footer_yours')}
      </div>
    </div>
  )
}
