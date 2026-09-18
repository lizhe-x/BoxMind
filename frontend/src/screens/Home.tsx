import { useMemo, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { T } from '../theme'
import { CameraIcon, CheckIcon, ChevronIcon, MicIcon, ScanIcon } from '../components/Icons'
import { makeT } from '../i18n'
import { fmtItems, fmtTime, useStore } from '../store'
import { useVoice } from '../voice'

export function Home() {
  const lang = useStore((s) => s.lang)
  const t = makeT(lang)
  const me = useStore((s) => s.me)
  const boxes = useStore((s) => s.boxes)
  const go = useStore((s) => s.go)
  const openBox = useStore((s) => s.openBox)
  const textEntry = useStore((s) => s.textEntry)
  const targetBox = useStore((s) => s.targetBox)
  const setTargetBox = useStore((s) => s.setTargetBox)
  const ask = useStore((s) => s.ask)
  const openAsk = useStore((s) => s.openAsk)
  const beginRecording = useStore((s) => s.beginRecording)
  const setLiveTranscript = useStore((s) => s.setLiveTranscript)
  const finishRecording = useStore((s) => s.finishRecording)

  const voice = useVoice()
  const recordingRef = useRef(false)

  const startTalk = (e: ReactPointerEvent) => {
    e.preventDefault()
    if (recordingRef.current) return
    recordingRef.current = true
    // 指针捕获:即使录音浮层弹出盖住手指,松手(up/cancel)仍由麦克风元素接收
    // (iOS 上浮层一出现会把后续事件变成 pointercancel,只听 window.pointerup 会丢失松手)
    const el = e.currentTarget
    const pid = e.pointerId
    try { el.setPointerCapture(pid) } catch { /* 不支持则忽略 */ }
    beginRecording()
    const end = () => {
      el.removeEventListener('pointerup', end)
      el.removeEventListener('pointercancel', end)
      try { el.releasePointerCapture(pid) } catch { /* noop */ }
      if (!recordingRef.current) return
      recordingRef.current = false
      void voice.stop().then(({ text, audio }) => finishRecording(text, audio))
    }
    el.addEventListener('pointerup', end)
    el.addEventListener('pointercancel', end)
    void voice.start(setLiveTranscript).then((ok) => {
      if (!ok) {
        el.removeEventListener('pointerup', end)
        el.removeEventListener('pointercancel', end)
        try { el.releasePointerCapture(pid) } catch { /* noop */ }
        recordingRef.current = false
        finishRecording('')
      }
    })
  }

  const [text, setText] = useState('')
  const submitInput = () => {
    const v = text.trim()
    if (!v) return
    setText('')
    void textEntry(v)
  }

  const itemCount = me?.item_count ?? 0
  const boxCount = me?.box_count ?? 0

  // 最近一次有物品的入库箱 → 绿色活动卡
  const lastBox = useMemo(() => boxes.find((b) => b.items.length > 0), [boxes])
  const everIngested = !!lastBox

  return (
    <div
      style={{
        height: '100%', display: 'flex', flexDirection: 'column',
        padding: '76px 22px 100px', position: 'relative', zIndex: 1, boxSizing: 'border-box',
      }}
    >
      {/* 顶部品牌 + 额度 */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div
            style={{
              fontFamily: T.fontNum, fontSize: 23, fontWeight: 700,
              background: 'linear-gradient(90deg,#AEC2FF,#CBB1FF)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}
          >
            BoxMind
          </div>
          <div style={{ fontSize: 12.5, color: T.textSub }}>
            {t('home_stats', { boxes: boxCount, items: itemCount })}
          </div>
        </div>
        <div
          onClick={() => go('settings')}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(124,140,255,0.1)',
            border: '1px solid rgba(124,140,255,0.25)', borderRadius: 999, padding: '7px 12px', cursor: 'pointer',
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: T.green, display: 'inline-block' }} />
          <span style={{ fontSize: 12.5, color: T.blue2, fontFamily: T.fontNum }}>{t('unlimited')}</span>
        </div>
      </div>

      {/* 教学卡 / 活动卡 */}
      {!everIngested && (
        <div
          style={{
            marginTop: 20, background: T.card, border: `1px solid ${T.border}`,
            borderRadius: 20, padding: 16, display: 'flex', alignItems: 'center', gap: 14,
          }}
        >
          <div
            style={{
              width: 54, height: 42, borderRadius: 8, background: 'linear-gradient(140deg,#9C7A52,#6E5638)',
              transform: 'rotate(-3deg)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, fontFamily: T.fontNum, fontWeight: 700, fontSize: 17, color: T.ink,
            }}
          >
            {t('label_sample')}
          </div>
          <div style={{ fontSize: 13.5, lineHeight: 1.7, color: 'rgba(235,240,250,0.65)', textWrap: 'pretty' }}>
            {t('home_tip')}
          </div>
        </div>
      )}
      {everIngested && lastBox && (
        <div
          onClick={() => openBox(lastBox.id)}
          style={{
            marginTop: 20, background: T.greenBg, border: '1px solid rgba(124,255,178,0.2)',
            borderRadius: 20, padding: '14px 16px', display: 'flex', alignItems: 'center',
            gap: 12, cursor: 'pointer', animation: 'bm-fadeUp 0.4s ease both',
          }}
        >
          <div
            style={{
              width: 34, height: 34, borderRadius: '50%', background: 'rgba(124,255,178,0.12)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}
          >
            <CheckIcon size={16} />
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>
              {t('home_last', { name: lastBox.name, time: fmtTime(lastBox.updated_at, lang) })}
            </div>
            <div
              style={{
                fontSize: 12, color: T.textSub, whiteSpace: 'nowrap',
                overflow: 'hidden', textOverflow: 'ellipsis',
              }}
            >
              {fmtItems(lastBox.items.slice(0, 3))}
            </div>
          </div>
          <ChevronIcon />
        </div>
      )}

      {/* 录入目标箱芯片 */}
      {targetBox && (
        <div
          style={{
            marginTop: 12, alignSelf: 'center', display: 'flex', alignItems: 'center', gap: 8,
            background: 'rgba(242,192,120,0.1)', border: '1px solid rgba(242,192,120,0.3)',
            borderRadius: 999, padding: '7px 8px 7px 14px',
          }}
        >
          <span style={{ fontSize: 12.5, color: T.amber }}>{t('home_target', { name: targetBox.name })}</span>
          <span
            onClick={() => setTargetBox(null)}
            style={{
              width: 18, height: 18, borderRadius: '50%', background: 'rgba(255,255,255,0.1)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', fontSize: 11, color: 'rgba(235,240,250,0.6)',
            }}
          >
            ✕
          </span>
        </div>
      )}

      <div style={{ flex: 1 }} />

      {/* 大麦克风按钮 */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {/* 按下事件挂在外层容器:整片区域的触摸都会冒泡到这里,光环/内圈即使被 iOS 命中也不影响 */}
        <div
          className="bm-press"
          onPointerDown={startTalk}
          onContextMenu={(e) => e.preventDefault()}
          draggable={false}
          style={{
            position: 'relative', width: 174, height: 174, display: 'flex',
            alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
            touchAction: 'none', userSelect: 'none', WebkitUserSelect: 'none',
          }}
        >
          <div style={{ position: 'absolute', inset: 12, borderRadius: '50%', border: '1px solid rgba(124,140,255,0.4)', animation: 'bm-pulse 2.6s ease-out infinite', pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', inset: 12, borderRadius: '50%', border: '1px solid rgba(139,92,246,0.3)', animation: 'bm-pulse 2.6s ease-out 0.9s infinite', pointerEvents: 'none' }} />
          <div
            style={{
              width: 150, height: 150, borderRadius: '50%',
              background: `radial-gradient(circle at 32% 28%,rgba(255,255,255,0.28),transparent 42%),${T.grad}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 18px 60px rgba(99,102,241,0.45),inset 0 -3px 12px rgba(0,0,0,0.2)',
              pointerEvents: 'none',
            }}
          >
            <MicIcon />
          </div>
        </div>
        <div style={{ marginTop: 14, fontSize: 17, fontWeight: 600, color: T.text }}>{t('hold_to_talk')}</div>
        <div style={{ marginTop: 5, fontSize: 13, color: targetBox ? T.amber : T.textWeak, textAlign: 'center', padding: '0 12px' }}>
          {targetBox ? t('home_hint_target', { name: targetBox.name }) : t('home_hint')}
        </div>
      </div>

      {/* 底部输入行 */}
      <div style={{ display: 'flex', gap: 10, marginTop: 28, alignItems: 'center' }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submitInput()
          }}
          placeholder={t('input_placeholder')}
          style={{
            flex: 1, height: 52, background: T.card, border: `1px solid ${T.border8}`,
            borderRadius: 999, padding: '0 18px', fontSize: 14.5, color: T.text,
            fontFamily: T.font, boxSizing: 'border-box', minWidth: 0,
          }}
        />
        {text.trim() ? (
          <div
            className="bm-press"
            onClick={submitInput}
            style={{
              width: 52, height: 52, borderRadius: 18, background: T.grad, display: 'flex',
              alignItems: 'center', justifyContent: 'center', cursor: 'pointer', flexShrink: 0,
              fontSize: 20, color: T.text, boxShadow: T.btnShadow,
            }}
          >
            ↑
          </div>
        ) : (
          <>
            <div
              onClick={() => go('camera')}
              style={{
                width: 52, height: 52, borderRadius: 18, background: T.card,
                border: `1px solid ${T.border8}`, display: 'flex', alignItems: 'center',
                justifyContent: 'center', cursor: 'pointer', flexShrink: 0,
              }}
            >
              <CameraIcon />
            </div>
            <div
              onClick={() => go('scan')}
              style={{
                width: 52, height: 52, borderRadius: 18, background: T.card,
                border: `1px solid ${T.border8}`, display: 'flex', alignItems: 'center',
                justifyContent: 'center', cursor: 'pointer', flexShrink: 0,
              }}
            >
              <ScanIcon />
            </div>
          </>
        )}
      </div>

      {/* 示例芯片 */}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 16, flexWrap: 'wrap' }}>
        {[t('chip_where_drill'), t('chip_how_many')].map((q) => (
          <div
            key={q}
            onClick={() => {
              openAsk()
              ask(q)
            }}
            style={{
              fontSize: 12.5, color: T.textSub55, background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.09)', borderRadius: 999,
              padding: '8px 14px', cursor: 'pointer',
            }}
          >
            {q}
          </div>
        ))}
      </div>
    </div>
  )
}
