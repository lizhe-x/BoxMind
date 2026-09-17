import { useEffect, useRef, useState } from 'react'
import { BackIcon, CheckIcon, SparkleIcon } from '../components/Icons'
import { useStore } from '../store'
import { T } from '../theme'

const CONF: Record<string, { label: string; color: string; bg: string }> = {
  high: { label: '置信度高', color: T.green, bg: 'rgba(124,255,178,0.12)' },
  medium: { label: '置信度中', color: T.amber, bg: 'rgba(242,192,120,0.12)' },
  low: { label: '置信度低', color: T.textWeak, bg: 'rgba(255,255,255,0.06)' },
}

export function Camera() {
  const camPhase = useStore((s) => s.camPhase)
  const recog = useStore((s) => s.recog)
  const entryBusy = useStore((s) => s.entryBusy)
  const recognizePhoto = useStore((s) => s.recognizePhoto)
  const retakePhoto = useStore((s) => s.retakePhoto)
  const toggleRecogItem = useStore((s) => s.toggleRecogItem)
  const editRecogItem = useStore((s) => s.editRecogItem)
  const addRecogItem = useStore((s) => s.addRecogItem)
  const confirmPhoto = useStore((s) => s.confirmPhoto)
  const go = useStore((s) => s.go)
  const showToast = useStore((s) => s.showToast)

  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [newName, setNewName] = useState('')

  const addItem = () => {
    const n = newName.trim()
    if (!n) return
    addRecogItem(n)
    setNewName('')
  }

  useEffect(() => {
    let cancelled = false
    if (camPhase === 'live') {
      navigator.mediaDevices
        ?.getUserMedia({ video: { facingMode: 'environment' } })
        .then((stream) => {
          if (cancelled) {
            stream.getTracks().forEach((t) => t.stop())
            return
          }
          streamRef.current = stream
          if (videoRef.current) {
            videoRef.current.srcObject = stream
            void videoRef.current.play().catch(() => {})
          }
        })
        .catch(() => showToast('无法打开摄像头,请检查权限'))
    }
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [camPhase, showToast])

  const shutter = () => {
    const v = videoRef.current
    if (!v || !v.videoWidth) {
      showToast('摄像头还没准备好')
      return
    }
    const canvas = document.createElement('canvas')
    canvas.width = v.videoWidth
    canvas.height = v.videoHeight
    canvas.getContext('2d')?.drawImage(v, 0, 0)
    canvas.toBlob(
      (blob) => {
        if (blob) void recognizePhoto(blob)
      },
      'image/jpeg',
      0.85,
    )
  }

  const selectedCount = recog?.items.filter((it) => it.selected).length ?? 0

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 1, background: '#04060A' }}>
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: '#0A0D15' }}>
        <video ref={videoRef} muted playsInline style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />

        {/* 顶部返回 */}
        <div style={{ position: 'absolute', top: 64, left: 16, right: 16, display: 'flex', alignItems: 'center', gap: 12, zIndex: 5 }}>
          <div
            onClick={() => go('home')}
            style={{ width: 38, height: 38, borderRadius: '50%', background: 'rgba(255,255,255,0.12)', backdropFilter: 'blur(10px)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
          >
            <BackIcon color="#fff" />
          </div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#fff' }}>拍照识别</div>
        </div>

        {/* 三分构图线 */}
        {camPhase === 'live' && (
          <>
            <div style={{ position: 'absolute', left: 0, right: 0, top: '33%', height: 1, background: 'rgba(255,255,255,0.12)' }} />
            <div style={{ position: 'absolute', left: 0, right: 0, top: '66%', height: 1, background: 'rgba(255,255,255,0.12)' }} />
            <div style={{ position: 'absolute', top: 0, bottom: 0, left: '33%', width: 1, background: 'rgba(255,255,255,0.12)' }} />
            <div style={{ position: 'absolute', top: 0, bottom: 0, left: '66%', width: 1, background: 'rgba(255,255,255,0.12)' }} />
          </>
        )}

        {/* 识别中 */}
        {camPhase === 'recog' && (
          <>
            <div style={{ position: 'absolute', inset: 0, background: 'rgba(3,5,9,0.45)' }} />
            <div style={{ position: 'absolute', left: 24, right: 24, height: 2, background: 'linear-gradient(90deg,transparent,#7C9BFF 30%,#A78BFA 70%,transparent)', boxShadow: '0 0 18px rgba(124,155,255,0.8)', animation: 'bm-scan 1.8s ease-in-out infinite' }} />
            <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(14,19,32,0.9)', backdropFilter: 'blur(12px)', border: '1px solid rgba(124,140,255,0.3)', borderRadius: 999, padding: '11px 20px' }}>
              <div style={{ width: 22, height: 22, borderRadius: '50%', background: T.grad, display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'bm-glow 1.1s infinite' }}>
                <SparkleIcon size={12} />
              </div>
              <span style={{ fontSize: 14, fontWeight: 500, color: T.blue3 }}>AI 识别中…</span>
            </div>
          </>
        )}
        {camPhase === 'result' && <div style={{ position: 'absolute', inset: 0, background: 'rgba(3,5,9,0.55)' }} />}
      </div>

      {/* 快门 */}
      {camPhase === 'live' && (
        <div style={{ padding: '18px 24px 44px', display: 'flex', flexDirection: 'column', gap: 18, alignItems: 'center', background: '#04060A' }}>
          <div style={{ fontSize: 13.5, color: T.textSub55 }}>对准打开的箱子,拍一张就行 — 物品和手写编号都能认</div>
          <div className="bm-press" onClick={shutter} style={{ width: 74, height: 74, borderRadius: '50%', border: '4px solid rgba(255,255,255,0.9)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
            <div style={{ width: 58, height: 58, borderRadius: '50%', background: '#fff' }} />
          </div>
        </div>
      )}

      {/* 结果底浮层 */}
      {camPhase === 'result' && recog && (
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, background: T.sheet, borderRadius: '28px 28px 0 0', borderTop: `1px solid ${T.border8}`, padding: '22px 22px 44px', display: 'flex', flexDirection: 'column', gap: 14, zIndex: 10, animation: 'bm-pop 0.35s ease both', maxHeight: '76%', overflow: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: T.grad, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <SparkleIcon size={12} />
              </div>
              <span style={{ fontSize: 16, fontWeight: 600, color: T.text }}>识别结果</span>
            </div>
            <div onClick={retakePhoto} style={{ fontSize: 13, color: T.textSub, cursor: 'pointer', padding: '4px 8px' }}>重拍</div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, background: T.card2, border: `1px solid ${T.border}`, borderRadius: 16, padding: '12px 14px' }}>
            <div style={{ width: 44, height: 38, borderRadius: 8, background: 'linear-gradient(140deg,#94714B,#6F5639)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontFamily: T.fontNum, fontWeight: 700, fontSize: 14, color: T.ink, transform: 'rotate(-2deg)' }}>
              {recog.boxLabel || recog.nextLabel}
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>
                入库到 {recog.boxLabel || recog.nextLabel}箱 · {recog.boxExists ? '已有箱子' : '自动新建'}
              </div>
              <div style={{ fontSize: 11.5, color: T.textWeak }}>
                {recog.boxLabel ? `照片识别到手写编号「${recog.boxLabel}」` : '未识别到编号,自动起号'}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {recog.items.map((it, i) => {
              const conf = CONF[it.confidence] || CONF.medium
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 2px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <div
                    onClick={() => toggleRecogItem(i)}
                    style={{ width: 22, height: 22, borderRadius: '50%', background: it.selected ? T.grad : 'transparent', border: `1.5px solid ${it.selected ? 'transparent' : 'rgba(255,255,255,0.25)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxSizing: 'border-box', cursor: 'pointer' }}
                  >
                    {it.selected && <CheckIcon size={11} color="#fff" width={3} />}
                  </div>
                  <input
                    value={it.name}
                    onChange={(e) => editRecogItem(i, { name: e.target.value })}
                    style={{ flex: 1, minWidth: 0, fontSize: 15, color: it.selected ? T.text : T.textWeak, background: 'transparent', border: 'none', fontFamily: T.font, padding: '4px 0' }}
                  />
                  <input
                    value={it.qty_text}
                    onChange={(e) => editRecogItem(i, { qty_text: e.target.value })}
                    style={{ width: 56, fontSize: 13, color: T.textSub, fontFamily: T.fontNum, background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.border8}`, borderRadius: 8, padding: '5px 8px', textAlign: 'center', boxSizing: 'border-box' }}
                  />
                  <div style={{ fontSize: 10.5, color: conf.color, background: conf.bg, borderRadius: 999, padding: '3px 8px', flexShrink: 0 }}>{conf.label}</div>
                </div>
              )
            })}
            {/* 手动添加物品 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 2px 2px' }}>
              <div style={{ width: 22, height: 22, borderRadius: '50%', border: '1.5px dashed rgba(124,140,255,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: 15, color: T.blue, boxSizing: 'border-box' }}>
                +
              </div>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') addItem()
                }}
                placeholder="手动添加物品(输入名称)"
                style={{ flex: 1, minWidth: 0, fontSize: 15, color: T.text, background: 'transparent', border: 'none', fontFamily: T.font, padding: '4px 0' }}
              />
              {newName.trim() && (
                <div onClick={addItem} style={{ fontSize: 13, color: T.blue2, cursor: 'pointer', padding: '4px 8px', flexShrink: 0 }}>添加</div>
              )}
            </div>
          </div>
          <div style={{ fontSize: 11.5, color: T.textWeak35 }}>可改名称/数量 · 点圆点取消勾选 · 可手动加物品</div>
          <div
            className="bm-press98"
            onClick={confirmPhoto}
            style={{ height: 52, borderRadius: 999, background: T.grad, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, fontWeight: 600, cursor: 'pointer', boxShadow: T.btnShadow, color: T.text, opacity: entryBusy || selectedCount === 0 ? 0.6 : 1 }}
          >
            {entryBusy ? '入库中…' : `确认入库(${selectedCount} 类)`}
          </div>
        </div>
      )}
    </div>
  )
}
