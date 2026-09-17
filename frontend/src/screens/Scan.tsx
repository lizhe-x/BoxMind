import { useEffect, useRef, useState } from 'react'
import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser'
import { BackIcon, CheckIcon, ChevronIcon } from '../components/Icons'
import { distText, fmtTime, useStore } from '../store'
import { T } from '../theme'

export function Scan() {
  const scanPhase = useStore((s) => s.scanPhase)
  const foundBox = useStore((s) => s.foundBox)
  const userPos = useStore((s) => s.userPos)
  const resolveScan = useStore((s) => s.resolveScan)
  const scanManual = useStore((s) => s.scanManual)
  const recordToFound = useStore((s) => s.recordToFound)
  const openBox = useStore((s) => s.openBox)
  const openScan = useStore((s) => s.openScan)
  const go = useStore((s) => s.go)
  const showToast = useStore((s) => s.showToast)

  const videoRef = useRef<HTMLVideoElement>(null)
  const controlsRef = useRef<IScannerControls | null>(null)
  const handledRef = useRef(false)
  const [manualOpen, setManualOpen] = useState(false)
  const [manualVal, setManualVal] = useState('')

  useEffect(() => {
    handledRef.current = false
    if (scanPhase !== 'scanning' || !videoRef.current) return
    const reader = new BrowserMultiFormatReader()
    let stopped = false
    reader
      .decodeFromVideoDevice(undefined, videoRef.current, (result, _err, controls) => {
        controlsRef.current = controls
        if (result && !handledRef.current) {
          handledRef.current = true
          controls.stop()
          void resolveScan(result.getText())
        }
      })
      .then((controls) => {
        controlsRef.current = controls
        if (stopped) controls.stop()
      })
      .catch(() => showToast('无法打开摄像头,请检查权限'))
    return () => {
      stopped = true
      controlsRef.current?.stop()
      controlsRef.current = null
    }
  }, [scanPhase, resolveScan, showToast])

  const submitManual = () => {
    if (!manualVal.trim()) return
    setManualOpen(false)
    void scanManual(manualVal)
    setManualVal('')
  }

  const dist = distText(userPos, foundBox?.gps_lat ?? null, foundBox?.gps_lng ?? null)

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 1, background: '#04060A' }}>
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: 'linear-gradient(165deg,#10141D 0%,#080A10 70%)' }}>
        <video ref={videoRef} muted playsInline style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />

        <div style={{ position: 'absolute', top: 64, left: 16, right: 16, display: 'flex', alignItems: 'center', gap: 12, zIndex: 5 }}>
          <div onClick={() => go('home')} style={{ width: 38, height: 38, borderRadius: '50%', background: 'rgba(255,255,255,0.12)', backdropFilter: 'blur(10px)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
            <BackIcon color="#fff" />
          </div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#fff' }}>扫码</div>
        </div>

        {/* 取景框 */}
        <div style={{ position: 'absolute', left: '50%', top: '46%', transform: 'translate(-50%,-50%)', width: 236, height: 236 }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: 34, height: 34, borderTop: '3px solid #93A8FF', borderLeft: '3px solid #93A8FF', borderRadius: '8px 0 0 0' }} />
          <div style={{ position: 'absolute', top: 0, right: 0, width: 34, height: 34, borderTop: '3px solid #93A8FF', borderRight: '3px solid #93A8FF', borderRadius: '0 8px 0 0' }} />
          <div style={{ position: 'absolute', bottom: 0, left: 0, width: 34, height: 34, borderBottom: '3px solid #93A8FF', borderLeft: '3px solid #93A8FF', borderRadius: '0 0 0 8px' }} />
          <div style={{ position: 'absolute', bottom: 0, right: 0, width: 34, height: 34, borderBottom: '3px solid #93A8FF', borderRight: '3px solid #93A8FF', borderRadius: '0 0 8px 0' }} />
          {scanPhase === 'scanning' && (
            <div style={{ position: 'absolute', left: 6, right: 6, height: 2, background: 'linear-gradient(90deg,transparent,#7C9BFF 30%,#A78BFA 70%,transparent)', boxShadow: '0 0 16px rgba(124,155,255,0.8)', animation: 'bm-scan 2.4s ease-in-out infinite' }} />
          )}
          {scanPhase === 'found' && (
            <div style={{ position: 'absolute', inset: -3, border: '3px solid rgba(124,255,178,0.7)', borderRadius: 10, boxShadow: '0 0 30px rgba(124,255,178,0.3)', animation: 'bm-pop 0.3s ease both' }} />
          )}
        </div>
      </div>

      {scanPhase === 'scanning' && (
        <div style={{ padding: '22px 24px 48px', display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'center', background: '#04060A' }}>
          <div style={{ fontSize: 14, color: T.textSub55 }}>对准箱子上的二维码 / 条形码</div>
          <div onClick={() => setManualOpen(true)} style={{ fontSize: 13.5, color: T.blue, cursor: 'pointer', padding: '6px 10px', borderBottom: '1px dashed rgba(147,168,255,0.4)' }}>
            箱子没贴码?输入手写编号
          </div>
        </div>
      )}

      {/* 识别成功底浮层 */}
      {scanPhase === 'found' && foundBox && (
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, background: T.sheet, borderRadius: '28px 28px 0 0', borderTop: `1px solid ${T.border8}`, padding: '22px 22px 46px', display: 'flex', flexDirection: 'column', gap: 16, zIndex: 10, animation: 'bm-pop 0.35s ease both' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, alignSelf: 'center', background: 'rgba(124,255,178,0.1)', border: '1px solid rgba(124,255,178,0.25)', borderRadius: 999, padding: '6px 14px' }}>
            <CheckIcon size={13} width={3} />
            <span style={{ fontSize: 12.5, color: T.green, fontFamily: T.fontNum }}>识别成功 · {foundBox.barcode || foundBox.label}</span>
          </div>
          <div onClick={() => { openBox(foundBox.id) }} style={{ display: 'flex', alignItems: 'center', gap: 14, background: T.card2, border: `1px solid ${T.border8}`, borderRadius: 18, padding: 14, cursor: 'pointer' }}>
            <div style={{ width: 56, height: 48, borderRadius: 10, background: `linear-gradient(140deg,${foundBox.color_a},${foundBox.color_b})`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontFamily: T.fontNum, fontWeight: 700, fontSize: 18, color: T.ink, transform: 'rotate(-2deg)' }}>
              {foundBox.label}
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
              <div style={{ fontSize: 16, fontWeight: 600, color: T.text }}>{foundBox.name}</div>
              <div style={{ fontSize: 12.5, color: T.textSub, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {[foundBox.location_text, dist].filter(Boolean).join(' · ') || '位置待补充'}
              </div>
              <div style={{ fontSize: 12, color: T.textWeak35 }}>{foundBox.items.length} 类物品 · {fmtTime(foundBox.updated_at)}</div>
            </div>
            <ChevronIcon />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <div onClick={recordToFound} style={{ flex: 1, height: 50, borderRadius: 999, border: '1px solid rgba(124,140,255,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, fontWeight: 600, color: T.blue2, cursor: 'pointer' }}>
              录入到此箱
            </div>
            <div onClick={() => openBox(foundBox.id)} style={{ flex: 1, height: 50, borderRadius: 999, background: T.grad, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, fontWeight: 600, cursor: 'pointer', boxShadow: T.btnShadow, color: T.text }}>
              查看箱子
            </div>
          </div>
          <div onClick={openScan} style={{ alignSelf: 'center', fontSize: 13, color: T.textWeak, cursor: 'pointer', padding: '2px 8px' }}>重新扫描</div>
        </div>
      )}

      {/* 手写编号兜底 */}
      {manualOpen && (
        <>
          <div onClick={() => setManualOpen(false)} style={{ position: 'absolute', inset: 0, background: 'rgba(2,4,8,0.6)', zIndex: 15 }} />
          <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, background: T.sheet, borderRadius: '28px 28px 0 0', borderTop: `1px solid ${T.border8}`, padding: '24px 22px 46px', display: 'flex', flexDirection: 'column', gap: 14, zIndex: 20, animation: 'bm-pop 0.3s ease both' }}>
            <div style={{ fontSize: 17, fontWeight: 700, color: T.text }}>输入箱子上的手写编号</div>
            <div style={{ fontSize: 13, lineHeight: 1.6, color: T.textSub }}>数字、字母、中文都可以 — 比如 3号、ABC、红色大箱。没有就帮你新建。</div>
            <input
              value={manualVal}
              autoFocus
              onChange={(e) => setManualVal(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') submitManual() }}
              placeholder="如:3号"
              style={{ height: 52, background: T.card2, border: '1px solid rgba(124,140,255,0.35)', borderRadius: 16, padding: '0 16px', fontSize: 17, color: T.text, fontFamily: T.font, boxSizing: 'border-box', width: '100%' }}
            />
            <div onClick={submitManual} style={{ height: 52, borderRadius: 999, background: T.grad, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 600, cursor: 'pointer', color: T.text }}>
              确认
            </div>
          </div>
        </>
      )}
    </div>
  )
}
