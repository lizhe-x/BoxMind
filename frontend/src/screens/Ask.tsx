import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { AiAvatar, Cursor, ThinkingDots } from '../components/common'
import { BackIcon, CameraIcon, ChevronIcon, MicIcon, ScanIcon, SpeakerIcon } from '../components/Icons'
import { api } from '../api'
import { distText, useStore } from '../store'
import { T } from '../theme'
import { useVoice } from '../voice'

const SUGGESTED = ['电钻在哪个箱子?', '我一共有几个箱子?', '哪些箱子还没记位置?']

export function Ask() {
  const askMsgs = useStore((s) => s.askMsgs)
  const thinking = useStore((s) => s.thinking)
  const ask = useStore((s) => s.ask)
  const agentSend = useStore((s) => s.agentSend)
  const agentConfirm = useStore((s) => s.agentConfirm)
  const agentCancel = useStore((s) => s.agentCancel)
  const go = useStore((s) => s.go)
  const openBox = useStore((s) => s.openBox)
  const userPos = useStore((s) => s.userPos)
  const showToast = useStore((s) => s.showToast)

  const [text, setText] = useState('')
  const [listening, setListening] = useState(false)
  const [speakingIdx, setSpeakingIdx] = useState<number | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const voice = useVoice()
  const recordingRef = useRef(false)

  const speak = async (idx: number, t: string) => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    if (speakingIdx === idx) {
      setSpeakingIdx(null)
      return
    }
    setSpeakingIdx(idx)
    try {
      const blob = await api.tts(t)
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = () => {
        setSpeakingIdx(null)
        URL.revokeObjectURL(url)
        audioRef.current = null
      }
      await audio.play()
    } catch {
      setSpeakingIdx(null)
      showToast('语音合成失败')
    }
  }

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [askMsgs, thinking])

  const asked = new Set(askMsgs.filter((m) => m.who === 'user').map((m) => m.text))
  const chips = SUGGESTED.filter((q) => !asked.has(q))

  const send = async (q: string) => {
    const v = q.trim()
    if (!v || thinking) return
    setText('')
    // 路由:提问走流式 RAG;其它(操作/录入/澄清回复)走 agent
    try {
      const parsed = await api.interpret(v)
      if (parsed.intent !== 'query') {
        agentSend(v)
        return
      }
    } catch {
      /* 解析失败 → 当作提问 */
    }
    ask(v)
  }

  const startTalk = (e: ReactPointerEvent) => {
    e.preventDefault()
    if (recordingRef.current || thinking) return
    recordingRef.current = true
    setListening(true)
    setText('')
    const onUp = () => {
      window.removeEventListener('pointerup', onUp)
      if (!recordingRef.current) return
      recordingRef.current = false
      setListening(false)
      void voice.stop().then(({ text }) => {
        if (text.trim()) send(text)
        else showToast('没听清,直接打字问我吧')
      })
    }
    window.addEventListener('pointerup', onUp)
    void voice.start(setText).then((ok) => {
      if (!ok) {
        window.removeEventListener('pointerup', onUp)
        recordingRef.current = false
        setListening(false)
        showToast('麦克风不可用,直接打字问我吧')
      }
    })
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', paddingTop: 64, position: 'relative', zIndex: 1, boxSizing: 'border-box' }}>
      {/* 顶部 */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '8px 16px 12px', gap: 12 }}>
        <div
          onClick={() => go('home')}
          style={{
            width: 38, height: 38, borderRadius: '50%', background: 'rgba(255,255,255,0.06)',
            border: `1px solid ${T.border8}`, display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', flexShrink: 0,
          }}
        >
          <BackIcon />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: T.text }}>问 BoxMind</div>
          <div style={{ fontSize: 11.5, color: T.textWeak }}>中 / 英 / 西 · 跨语言都能查</div>
        </div>
      </div>

      {/* 消息区 */}
      <div ref={scrollRef} style={{ flex: 1, overflow: 'auto', padding: '10px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {askMsgs.map((m, i) =>
          m.who === 'user' ? (
            <div key={i} style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <div style={{ maxWidth: '78%', background: '#273048', borderRadius: '18px 18px 4px 18px', padding: '11px 15px', fontSize: 15, lineHeight: 1.6, animation: 'bm-fadeUp 0.3s ease both', color: T.text }}>
                {m.text}
              </div>
            </div>
          ) : (
            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <div style={{ marginTop: 2 }}>
                <AiAvatar />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: '82%' }}>
                <div style={{ background: T.card2, border: `1px solid ${T.border}`, borderRadius: '4px 18px 18px 18px', padding: '12px 15px', fontSize: 15, lineHeight: 1.65, textWrap: 'pretty', color: T.text }}>
                  {m.text}
                  {m.streaming && <Cursor />}
                </div>
                {!m.streaming && m.text && (
                  <div
                    onClick={() => speak(i, m.text)}
                    style={{
                      alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 6,
                      padding: '5px 11px', borderRadius: 999, cursor: 'pointer',
                      background: speakingIdx === i ? 'rgba(124,140,255,0.12)' : 'rgba(255,255,255,0.04)',
                      border: `1px solid ${speakingIdx === i ? 'rgba(124,140,255,0.35)' : T.border8}`,
                    }}
                  >
                    <SpeakerIcon color={speakingIdx === i ? T.blue2 : T.textSub} />
                    <span style={{ fontSize: 12, color: speakingIdx === i ? T.blue2 : T.textSub }}>
                      {speakingIdx === i ? '播放中…' : '朗读'}
                    </span>
                  </div>
                )}
                {m.boxes?.map((box) => {
                  const dist = distText(userPos, box.gps_lat, box.gps_lng)
                  return (
                    <div
                      key={box.id}
                      onClick={() => openBox(box.id)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 12, background: T.card,
                        border: '1px solid rgba(124,140,255,0.25)', borderRadius: 16, padding: '11px 13px',
                        cursor: 'pointer', animation: 'bm-fadeUp 0.35s ease both',
                      }}
                    >
                      <div
                        style={{
                          width: 46, height: 40, borderRadius: 8,
                          background: `linear-gradient(140deg,${box.color_a},${box.color_b})`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                          fontFamily: T.fontNum, fontWeight: 700, fontSize: 15, color: T.ink, transform: 'rotate(-2deg)',
                        }}
                      >
                        {box.label}
                      </div>
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                        <div style={{ fontSize: 14.5, fontWeight: 600, color: T.text }}>{box.name}</div>
                        <div style={{ fontSize: 12, color: T.textSub, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {[box.location_text, dist].filter(Boolean).join(' · ') || '位置待补充'}
                        </div>
                      </div>
                      <ChevronIcon />
                    </div>
                  )
                })}
                {m.confirm && m.confirm.length > 0 && (
                  <div style={{ background: T.card, border: '1px solid rgba(255,90,90,0.3)', borderRadius: 16, padding: '13px 15px', display: 'flex', flexDirection: 'column', gap: 10, animation: 'bm-fadeUp 0.3s ease both' }}>
                    <div style={{ fontSize: 12.5, color: T.red2 }}>以下操作需要确认:</div>
                    {m.confirm.map((a, ai) => (
                      <div key={ai} style={{ fontSize: 14, color: T.text, lineHeight: 1.5 }}>· {a.summary}</div>
                    ))}
                    <div style={{ display: 'flex', gap: 10, marginTop: 2 }}>
                      <div
                        onClick={agentCancel}
                        style={{ flex: 1, height: 42, borderRadius: 999, border: '1px solid rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: 'rgba(235,240,250,0.7)', cursor: 'pointer' }}
                      >
                        取消
                      </div>
                      <div
                        className="bm-press98"
                        onClick={() => agentConfirm(m.confirm!)}
                        style={{ flex: 1, height: 42, borderRadius: 999, background: 'linear-gradient(135deg,#FF5A5A,#FF8A8A)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 600, color: '#fff', cursor: 'pointer' }}
                      >
                        确认执行
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ),
        )}
        {thinking && (
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <AiAvatar glow />
            <div style={{ background: T.card2, border: `1px solid ${T.border}`, borderRadius: '4px 18px 18px 18px', padding: '15px 16px' }}>
              <ThinkingDots />
            </div>
          </div>
        )}
        <div style={{ height: 6, flexShrink: 0 }} />
      </div>

      {/* 底部输入 */}
      <div style={{ padding: '10px 20px 36px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {chips.length > 0 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {chips.map((c) => (
              <div
                key={c}
                onClick={() => send(c)}
                style={{
                  fontSize: 13, color: T.blue2, background: 'rgba(124,140,255,0.1)',
                  border: '1px solid rgba(124,140,255,0.3)', borderRadius: 999, padding: '9px 14px', cursor: 'pointer',
                }}
              >
                {c}
              </div>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') send(text)
            }}
            placeholder={listening ? '正在听…' : '问我东西在哪…'}
            style={{
              flex: 1, height: 46, background: T.card,
              border: `1px solid ${listening ? 'rgba(255,90,90,0.4)' : T.border8}`,
              borderRadius: 999, padding: '0 18px', fontSize: 14, color: T.text,
              fontFamily: T.font, boxSizing: 'border-box',
            }}
          />
          <div
            className="bm-press"
            onClick={() => go('camera')}
            style={{
              width: 46, height: 46, borderRadius: '50%', background: T.card, border: `1px solid ${T.border8}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', flexShrink: 0,
            }}
          >
            <CameraIcon size={20} />
          </div>
          <div
            className="bm-press"
            onClick={() => go('scan')}
            style={{
              width: 46, height: 46, borderRadius: '50%', background: T.card, border: `1px solid ${T.border8}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', flexShrink: 0,
            }}
          >
            <ScanIcon size={20} />
          </div>
          {text.trim() ? (
            <div
              className="bm-press"
              onClick={() => send(text)}
              style={{
                width: 46, height: 46, borderRadius: '50%', background: T.grad, display: 'flex',
                alignItems: 'center', justifyContent: 'center', cursor: 'pointer', flexShrink: 0,
                boxShadow: '0 6px 20px rgba(99,102,241,0.4)', fontSize: 18, color: T.text,
              }}
            >
              ↑
            </div>
          ) : (
            <div
              className="bm-press"
              onPointerDown={startTalk}
              onContextMenu={(e) => e.preventDefault()}
              draggable={false}
              style={{
                width: 46, height: 46, borderRadius: '50%',
                background: listening ? 'linear-gradient(135deg,#FF5A5A,#FF8A8A)' : T.grad,
                display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
                flexShrink: 0, boxShadow: '0 6px 20px rgba(99,102,241,0.4)', touchAction: 'none',
                userSelect: 'none', WebkitUserSelect: 'none',
              }}
            >
              <MicIcon size={20} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
