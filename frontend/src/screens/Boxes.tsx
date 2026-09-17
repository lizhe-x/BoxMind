import { api } from '../api'
import { PinIcon } from '../components/Icons'
import { fmtTime, isNewBox, useStore } from '../store'
import { T } from '../theme'

export function Boxes() {
  const boxes = useStore((s) => s.boxes)
  const openBox = useStore((s) => s.openBox)
  const go = useStore((s) => s.go)
  const showToast = useStore((s) => s.showToast)

  const newBoxHint = () => {
    go('home')
    showToast('回到主页,说一句「N号箱放了…」就能建箱')
  }

  return (
    <div
      style={{
        height: '100%', overflow: 'auto', padding: '76px 20px 110px',
        position: 'relative', zIndex: 1, boxSizing: 'border-box',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 18 }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: T.text }}>我的箱子</div>
        <div style={{ fontSize: 14, color: T.blue, fontFamily: T.fontNum }}>{boxes.length}</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {boxes.map((b) => {
          const cover = b.photo_url || b.photos[0]
          return (
          <div
            key={b.id}
            onClick={() => openBox(b.id)}
            style={{
              background: T.card, border: `1px solid ${T.border}`, borderRadius: 20,
              overflow: 'hidden', cursor: 'pointer',
            }}
          >
            <div
              style={{
                height: 92,
                background: `linear-gradient(140deg,${b.color_a},${b.color_b})`,
                ...(cover
                  ? { backgroundImage: `url(${api.mediaUrl(cover)})`, backgroundSize: 'cover', backgroundPosition: 'center' }
                  : {}),
                display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative',
              }}
            >
              {!cover && (
                <div
                  style={{
                    position: 'absolute', top: -5, left: '50%', transform: 'translateX(-50%) rotate(-2deg)',
                    width: 52, height: 14, background: 'rgba(255,255,255,0.22)', borderRadius: 2,
                  }}
                />
              )}
              <div
                style={{
                  fontFamily: T.fontNum, fontSize: 26, fontWeight: 700, color: T.ink, transform: 'rotate(-2deg)',
                  ...(cover
                    ? { position: 'absolute', left: 8, bottom: 6, fontSize: 18, color: '#fff', textShadow: '0 1px 6px rgba(0,0,0,0.7)' }
                    : {}),
                }}
              >
                {b.label}
              </div>
              {isNewBox(b) && (
                <div
                  style={{
                    position: 'absolute', top: 8, right: 8, background: 'rgba(124,255,178,0.9)',
                    color: '#0A2C18', fontSize: 10, fontWeight: 700, borderRadius: 999, padding: '3px 8px',
                  }}
                >
                  新
                </div>
              )}
            </div>
            <div style={{ padding: '12px 13px 13px', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ fontSize: 14.5, fontWeight: 600, color: T.text }}>{b.name}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5, minWidth: 0 }}>
                <PinIcon />
                <span
                  style={{
                    fontSize: 11.5, color: T.textSub, whiteSpace: 'nowrap',
                    overflow: 'hidden', textOverflow: 'ellipsis',
                  }}
                >
                  {b.location_text || '位置待补充'}
                </span>
              </div>
              <div style={{ fontSize: 11, color: T.textWeak35 }}>
                {b.items.length > 0 ? `${b.items.length} 类物品` : '空箱'} · {fmtTime(b.updated_at)}
              </div>
            </div>
          </div>
          )
        })}

        <div
          onClick={newBoxHint}
          style={{
            border: '1.5px dashed rgba(124,140,255,0.3)', borderRadius: 20, minHeight: 170,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            gap: 10, cursor: 'pointer',
          }}
        >
          <div
            style={{
              width: 38, height: 38, borderRadius: '50%', background: 'rgba(124,140,255,0.1)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
              color: T.blue, fontWeight: 300,
            }}
          >
            +
          </div>
          <div style={{ fontSize: 12.5, color: T.textWeak, textAlign: 'center', lineHeight: 1.6, padding: '0 12px' }}>
            写个编号
            <br />
            开口即建
          </div>
        </div>
      </div>

      {boxes.length === 0 && (
        <div style={{ marginTop: 18, fontSize: 13, color: T.textWeak, textAlign: 'center', lineHeight: 1.8 }}>
          还没有箱子 — 回主页说一句「1号箱放了…」即可建第一个箱子
        </div>
      )}
    </div>
  )
}
