import { api } from '../api'
import { useStore } from '../store'
import { T } from '../theme'

const LANGS: { code: string; label: string }[] = [
  { code: 'zh', label: '中文' },
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Español' },
]

export function Settings() {
  const me = useStore((s) => s.me)
  const updateMe = useStore((s) => s.updateMe)
  const showToast = useStore((s) => s.showToast)
  const logout = useStore((s) => s.logout)

  const used = me?.used ?? 0
  const lang = me?.lang ?? 'zh'
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
      showToast('导出失败,请重试')
    }
  }

  return (
    <div
      style={{
        height: '100%', overflow: 'auto', padding: '76px 20px 110px', position: 'relative',
        zIndex: 1, boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 16,
      }}
    >
      <div style={{ fontSize: 28, fontWeight: 700, color: T.text }}>我的</div>

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
            <div style={{ fontSize: 12.5, color: T.textSub55 }}>使用额度</div>
            <div style={{ fontFamily: T.fontNum, fontSize: 30, fontWeight: 700, lineHeight: 1, color: T.text }}>无限制</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(124,255,178,0.1)', border: '1px solid rgba(124,255,178,0.25)', borderRadius: 999, padding: '7px 13px' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: T.green, display: 'inline-block' }} />
            <span style={{ fontSize: 12.5, color: T.green, fontFamily: T.fontNum }}>已用 {used} 次</span>
          </div>
        </div>
        <div style={{ fontSize: 11.5, color: T.textWeak }}>
          录入与 AI 查询不限次数,免费畅用 · 扫码与浏览不计次
        </div>
      </div>

      {/* 语言 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
        <div style={{ fontSize: 13, color: T.textWeak, paddingLeft: 4 }}>界面语言</div>
        <div style={{ display: 'flex', gap: 9 }}>
          {LANGS.map((l) => {
            const on = lang === l.code
            return (
              <div
                key={l.code}
                onClick={() => !on && updateMe({ lang: l.code })}
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
        <div style={{ fontSize: 11.5, color: T.textWeak35, paddingLeft: 4 }}>
          AI 对话语言自动识别:说中文答中文,说英文答英文
        </div>
      </div>

      {/* GPS 开关 */}
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 20, padding: '15px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <div style={{ fontSize: 15, fontWeight: 500, color: T.text }}>自动记录 GPS 位置</div>
          <div style={{ fontSize: 12, color: T.textWeak }}>区分家 / 仓库 / 父母家,仅你自己可见</div>
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
          <div style={{ fontSize: 15, color: T.text }}>导出我的数据 (JSON)</div>
          <div style={{ fontSize: 13, color: T.textWeak }}>下载</div>
        </div>
        <div
          onClick={() => exportData('csv')}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)', cursor: 'pointer' }}
        >
          <div style={{ fontSize: 15, color: T.text }}>导出我的数据 (CSV)</div>
          <div style={{ fontSize: 13, color: T.textWeak }}>下载</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 15, color: T.text }}>语音识别</div>
          <div style={{ fontSize: 13, color: T.textWeak }}>即将上线</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 16px' }}>
          <div style={{ fontSize: 15, color: T.text }}>关于 BoxMind</div>
          <div style={{ fontSize: 13, color: T.textWeak }}>v0.1 MVP</div>
        </div>
      </div>

      {/* 账户 */}
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 20, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 15, color: T.text }}>当前账户</div>
          <div style={{ fontSize: 13, color: T.textWeak, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {me?.email || '匿名'}
          </div>
        </div>
        <div onClick={logout} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '15px 16px', cursor: 'pointer' }}>
          <div style={{ fontSize: 15, color: T.red2 }}>退出登录</div>
        </div>
      </div>

      <div style={{ fontSize: 11, color: 'rgba(235,240,250,0.3)', textAlign: 'center', lineHeight: 1.7 }}>
        数据归你所有,可随时导出或删除
        <br />
        录入与 AI 查询计次,扫码与浏览永久免费
      </div>
    </div>
  )
}
