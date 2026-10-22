import { useRef } from 'react'
import { api } from './api'
import { speechLocale } from './i18n'
import { useStore } from './store'

/**
 * 按住说话语音输入。
 *
 * 两条转写引擎,自动选择:
 *  1. 浏览器 Web Speech API(SpeechRecognition)— 实时、设备端,Chrome/Edge 可用,默认优先。
 *  2. MediaRecorder 录音 → 后端 /api/transcribe → 网关 ASR(qwen3-asr-flash-realtime)。
 *     用于不支持 Web Speech 的浏览器;也可用 localStorage['bm_asr']='server' 强制走网关。
 *
 * 两者都不可用 / 无结果时,start() 返回 false 或 stop() 返回 '',由调用方降级为手动输入。
 */

interface SpeechRecognitionLike {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: SpeechRecognitionEventLike) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}
interface SpeechRecognitionEventLike {
  resultIndex: number
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>
}
type SRCtor = new () => SpeechRecognitionLike

function getSRClass(): SRCtor | null {
  if (localStorage.getItem('bm_asr') === 'server') return null
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor }
  return w.SpeechRecognition || w.webkitSpeechRecognition || null
}

export function useVoice() {
  const lang = useStore((s) => s.lang)
  const recRef = useRef<SpeechRecognitionLike | null>(null)
  const mediaRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const finalRef = useRef('')
  const usingSpeechRef = useRef(false)

  /**
   * 开始采集。Web Speech(若可用)负责实时转写;同时尽量用 MediaRecorder 采一份音频用于保存
   * (best-effort,采音频失败绝不影响转写)。返回是否成功启动转写或采集。
   */
  async function start(onInterim: (t: string) => void): Promise<boolean> {
    finalRef.current = ''
    chunksRef.current = []
    usingSpeechRef.current = false
    let ok = false

    // 1) 转写引擎:优先 Web Speech(它自管麦克风,不走 getUserMedia)
    const SR = getSRClass()
    if (SR) {
      try {
        const rec = new SR()
        rec.lang = speechLocale(lang)
        rec.interimResults = true
        rec.continuous = true
        rec.onresult = (e) => {
          let interim = ''
          for (let i = e.resultIndex; i < e.results.length; i++) {
            const r = e.results[i]
            if (r.isFinal) finalRef.current += r[0].transcript
            else interim += r[0].transcript
          }
          onInterim((finalRef.current + interim).trim())
        }
        rec.onerror = () => {}
        rec.start()
        recRef.current = rec
        usingSpeechRef.current = true
        ok = true
      } catch {
        usingSpeechRef.current = false
      }
    }

    // 2) 录音采集(用于保存语音;无 Web Speech 时也作为服务端 ASR 的输入)。best-effort。
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const mr = new MediaRecorder(stream)
      mr.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data)
      }
      mr.start()
      mediaRef.current = mr
      ok = true
    } catch {
      /* 采音频失败:若有 Web Speech 仍可转写;否则本次无音频 */
    }

    return ok
  }

  /** 结束采集,返回 { text: 转写文本, audio: 录音(可能为 null) }。 */
  async function stop(): Promise<{ text: string; audio: Blob | null }> {
    // 1) 结束 Web Speech,拿最终转写
    let text = ''
    if (usingSpeechRef.current && recRef.current) {
      const rec = recRef.current
      recRef.current = null
      await new Promise<void>((resolve) => {
        rec.onend = () => resolve()
        try {
          rec.stop()
        } catch {
          resolve()
        }
        setTimeout(resolve, 1500)
      })
      text = finalRef.current.trim()
    }

    // 2) 结束录音,取音频 blob
    const mr = mediaRef.current
    mediaRef.current = null
    let audio: Blob | null = null
    if (mr && mr.state !== 'inactive') {
      audio = await new Promise<Blob>((resolve) => {
        mr.onstop = () => resolve(new Blob(chunksRef.current, { type: mr.mimeType || 'audio/webm' }))
        try {
          mr.stop()
        } catch {
          resolve(new Blob(chunksRef.current, { type: 'audio/webm' }))
        }
      })
    }
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null

    // 3) 没有 Web Speech 转写但有音频 → 走服务端 ASR
    if (!text && audio && audio.size > 0) {
      try {
        text = await api.transcribe(audio)
      } catch {
        /* 服务端 ASR 不可用 → 文本为空,交由调用方降级 */
      }
    }

    return { text, audio: audio && audio.size > 0 ? audio : null }
  }

  return { start, stop }
}
