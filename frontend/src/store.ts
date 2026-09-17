import { create } from 'zustand'
import { api, askStream, hasToken } from './api'
import type { AgentAction, Box, BoxRef, EntryPhase, InterpretResult, Me, Screen } from './types'

export interface AskMsg {
  who: 'user' | 'ai'
  text: string
  streaming?: boolean
  boxes?: BoxRef[]
  confirm?: AgentAction[] // 待用户确认的破坏性操作
}

interface DoneInfo {
  boxId: string
  title: string
  line1: string
  line2: string
  markerTip: string | null
}

interface RecogDraft {
  boxLabel: string | null
  boxExists: boolean
  nextLabel: string
  items: { name: string; qty_text: string; confidence: string; selected: boolean }[]
}

interface S {
  authed: boolean
  authChecked: boolean
  screen: Screen
  backTo: Screen
  activeBoxId: string | null
  me: Me | null
  boxes: Box[]
  userPos: { lat: number; lng: number } | null
  toast: string | null
  // 录入浮层
  entryPhase: EntryPhase
  entrySource: 'text' | 'voice'
  rawText: string
  liveTranscript: string
  parsed: InterpretResult | null
  targetBox: Box | null // 「录入到此箱」
  doneInfo: DoneInfo | null
  entryBusy: boolean
  // 问答
  askMsgs: AskMsg[]
  thinking: boolean
  // 拍照识别
  camPhase: 'live' | 'recog' | 'result'
  recog: RecogDraft | null
  pendingPhoto: Blob | null // 待入库后上传的照片
  pendingAudio: Blob | null // 待入库后上传的录入语音
  // 扫码
  scanPhase: 'scanning' | 'found'
  foundBox: Box | null

  init: () => Promise<void>
  login: (email: string, code: string) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
  go: (s: Screen) => void
  openBox: (id: string) => void
  backFromDetail: () => void
  showToast: (msg: string) => void
  setTargetBox: (b: Box | null) => void

  textEntry: (text: string) => Promise<void>
  closeEntry: () => void
  beginRecording: () => void
  setLiveTranscript: (t: string) => void
  finishRecording: (text: string, audio?: Blob | null) => void
  submitText: (text: string) => Promise<void>
  setRawText: (t: string) => void
  toEdit: () => void
  cancelEdit: () => void
  reparse: () => Promise<void>
  confirmEntry: () => Promise<void>
  pickNewBox: () => Promise<void>
  pickExisting: (boxId: string) => Promise<void>

  openAsk: () => void
  ask: (q: string) => void
  agentSend: (message: string) => void
  agentConfirm: (actions: AgentAction[]) => Promise<void>
  agentCancel: () => void
  updateMe: (body: { lang?: string; gps_enabled?: boolean }) => Promise<void>

  openCamera: () => void
  recognizePhoto: (blob: Blob) => Promise<void>
  retakePhoto: () => void
  toggleRecogItem: (i: number) => void
  editRecogItem: (i: number, patch: { name?: string; qty_text?: string }) => void
  addRecogItem: (name: string) => void
  confirmPhoto: () => Promise<void>

  openScan: () => void
  resolveScan: (code: string) => Promise<void>
  scanManual: (label: string) => Promise<void>
  recordToFound: () => void

  addBoxPhoto: (boxId: string, blob: Blob, setCover: boolean) => Promise<void>
  setBoxCover: (boxId: string, url: string) => Promise<void>
  addBoxItem: (boxId: string, name: string) => Promise<void>
  updateBoxItem: (boxId: string, itemId: string, patch: { name?: string; qty_text?: string }) => Promise<void>
  deleteBoxItem: (boxId: string, itemId: string) => Promise<void>
}

let toastTimer: ReturnType<typeof setTimeout> | undefined

export function fmtItems(items: { name: string; qty_text: string }[]): string {
  return items.map((i) => `${i.name} ${i.qty_text}`).join(' · ')
}

export const useStore = create<S>((set, get) => ({
  authed: false,
  authChecked: false,
  screen: localStorage.getItem('bm_onboarded') ? 'home' : 'onboarding',
  backTo: 'boxes',
  activeBoxId: null,
  me: null,
  boxes: [],
  userPos: null,
  toast: null,
  entryPhase: 'idle',
  entrySource: 'text',
  rawText: '',
  liveTranscript: '',
  parsed: null,
  targetBox: null,
  doneInfo: null,
  entryBusy: false,
  askMsgs: [],
  thinking: false,
  camPhase: 'live',
  recog: null,
  pendingPhoto: null,
  pendingAudio: null,
  scanPhase: 'scanning',
  foundBox: null,

  init: async () => {
    if (!hasToken()) {
      set({ authed: false, authChecked: true })
      return
    }
    try {
      await get().refresh()
      set({ authed: true, authChecked: true })
    } catch {
      set({ authed: false, authChecked: true })
      return
    }
    const me = get().me
    if (me?.gps_enabled && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (p) => set({ userPos: { lat: p.coords.latitude, lng: p.coords.longitude } }),
        () => {}, // 拒绝授权 → 全功能降级,不打扰
        { maximumAge: 600_000, timeout: 8000 },
      )
    }
  },

  login: async (email, code) => {
    await api.verifyCode(email, code) // 成功后写入 token
    await get().init()
    set({ screen: localStorage.getItem('bm_onboarded') ? 'home' : 'onboarding' })
  },

  logout: () => {
    api.logout()
    set({
      authed: false,
      me: null,
      boxes: [],
      askMsgs: [],
      targetBox: null,
      entryPhase: 'idle',
      screen: localStorage.getItem('bm_onboarded') ? 'home' : 'onboarding',
    })
  },

  refresh: async () => {
    const [me, boxes] = await Promise.all([api.me(), api.boxes()])
    set({ me, boxes })
  },

  go: (s) => set({ screen: s }),

  openBox: (id) =>
    set((st) => ({
      screen: 'boxdetail',
      activeBoxId: id,
      backTo: st.screen === 'boxdetail' ? st.backTo : st.screen,
    })),

  backFromDetail: () =>
    set((st) => ({ screen: st.backTo === 'boxdetail' ? 'boxes' : st.backTo || 'boxes' })),

  showToast: (msg) => {
    clearTimeout(toastTimer)
    set({ toast: msg })
    toastTimer = setTimeout(() => set({ toast: null }), 2600)
  },

  setTargetBox: (b) => set({ targetBox: b }),

  // 首页直接打字录入/提问(无中间浮层):标记来源为文字,直接进入解析
  textEntry: async (text) => {
    if (!text.trim()) return
    set({ entrySource: 'text', parsed: null, doneInfo: null })
    await get().submitText(text)
  },
  closeEntry: () => set({ entryPhase: 'idle', rawText: '', liveTranscript: '', parsed: null, entryBusy: false }),
  setRawText: (t) => set({ rawText: t }),

  beginRecording: () => set({ entryPhase: 'recording', entrySource: 'voice', rawText: '', liveTranscript: '', parsed: null, doneInfo: null, pendingAudio: null }),
  setLiveTranscript: (t) => set({ liveTranscript: t }),
  finishRecording: (text, audio) => {
    set({ pendingAudio: audio ?? null }) // 入库后上传保存
    const t = text.trim()
    if (t) {
      void get().submitText(t)
    } else {
      // 没听清/麦克风不可用 → 回首页,提示用下方输入框打字,闭环不中断
      set({ entryPhase: 'idle', liveTranscript: '', screen: 'home' })
      get().showToast('没听清,在下方输入框直接打字试试')
    }
  },

  submitText: async (text) => {
    const st = get()
    if (!text.trim() || st.entryBusy) return
    set({ rawText: text, entryPhase: 'parsing', entryBusy: true })
    try {
      const parsed = await api.interpret(text, st.targetBox?.id)
      if (parsed.intent === 'query') {
        set({ entryPhase: 'idle', entryBusy: false })
        get().openAsk()
        get().ask(text)
        return
      }
      if (parsed.intent === 'operation') {
        set({ entryPhase: 'idle', entryBusy: false, liveTranscript: '' })
        get().openAsk()
        get().agentSend(text)
        return
      }
      if (parsed.items.length === 0) {
        set({ entryPhase: 'input', entryBusy: false })
        get().showToast('没听出要录入的物品,再说具体一点?')
        return
      }
      if (st.targetBox || parsed.box_label) {
        set({ entryPhase: 'confirm', parsed, entryBusy: false })
      } else {
        set({ entryPhase: 'askbox', parsed, entryBusy: false })
      }
    } catch {
      set({ entryPhase: 'input', entryBusy: false })
      get().showToast('AI 解析失败,请重试')
    }
  },

  toEdit: () => set({ entryPhase: 'edit' }),
  cancelEdit: () => set({ entryPhase: 'confirm' }),
  reparse: async () => {
    await get().submitText(get().rawText)
  },

  confirmEntry: async () => {
    const st = get()
    const p = st.parsed
    if (!p || st.entryBusy) return
    set({ entryBusy: true })
    try {
      const res = await api.ingest({
        box_id: st.targetBox?.id || p.box?.id || null,
        box_label: p.box_label,
        items: p.items,
        location_text: p.location_text,
        gps_lat: st.userPos?.lat ?? null,
        gps_lng: st.userPos?.lng ?? null,
        raw_text: st.rawText,
        source: st.entrySource,
      })
      if (st.pendingAudio) {
        try {
          await api.uploadAudio(res.box.id, st.pendingAudio)
        } catch {
          /* 语音保存失败,物品已入库,忽略 */
        }
      }
      await st.refresh()
      set({
        entryPhase: 'done',
        entryBusy: false,
        targetBox: null,
        pendingAudio: null,
        doneInfo: {
          boxId: res.box.id,
          title: res.created ? `已建 ${res.box.name}并入库` : `已记录到 ${res.box.name}`,
          line1: fmtItems(p.items),
          line2: res.box.location_text
            ? `位置:${res.box.location_text}`
            : st.userPos
              ? 'GPS 已记录当前位置'
              : '位置待补充',
          markerTip: null,
        },
      })
    } catch {
      set({ entryBusy: false })
      get().showToast('入库失败,请重试')
    }
  },

  pickNewBox: async () => {
    const st = get()
    const p = st.parsed
    if (!p || st.entryBusy) return
    set({ entryBusy: true })
    const label = p.next_label
    try {
      const res = await api.ingest({
        box_label: label,
        items: p.items,
        location_text: p.location_text,
        gps_lat: st.userPos?.lat ?? null,
        gps_lng: st.userPos?.lng ?? null,
        raw_text: st.rawText,
        source: st.entrySource,
      })
      if (st.pendingAudio) {
        try {
          await api.uploadAudio(res.box.id, st.pendingAudio)
        } catch {
          /* 忽略 */
        }
      }
      await st.refresh()
      set({
        pendingAudio: null,
        entryPhase: 'done',
        entryBusy: false,
        doneInfo: {
          boxId: res.box.id,
          title: `已建 ${res.box.name}并入库`,
          line1: fmtItems(p.items),
          line2: st.userPos ? 'GPS 已记录当前位置' : '位置待补充',
          markerTip: `记得用马克笔把「${label.replace('号', '')}」写到箱子上,下次一眼对上号`,
        },
      })
    } catch {
      set({ entryBusy: false })
      get().showToast('入库失败,请重试')
    }
  },

  pickExisting: async (boxId) => {
    const st = get()
    const p = st.parsed
    if (!p || st.entryBusy) return
    set({ entryBusy: true })
    try {
      const res = await api.ingest({
        box_id: boxId,
        items: p.items,
        location_text: p.location_text,
        gps_lat: st.userPos?.lat ?? null,
        gps_lng: st.userPos?.lng ?? null,
        raw_text: st.rawText,
        source: st.entrySource,
      })
      if (st.pendingAudio) {
        try {
          await api.uploadAudio(res.box.id, st.pendingAudio)
        } catch {
          /* 忽略 */
        }
      }
      await st.refresh()
      set({
        pendingAudio: null,
        entryPhase: 'done',
        entryBusy: false,
        doneInfo: {
          boxId: res.box.id,
          title: `已记录到 ${res.box.name}`,
          line1: fmtItems(p.items),
          line2: res.box.location_text ? `位置:${res.box.location_text}` : '位置待补充',
          markerTip: null,
        },
      })
    } catch {
      set({ entryBusy: false })
      get().showToast('入库失败,请重试')
    }
  },

  openAsk: () => {
    const st = get()
    if (st.askMsgs.length === 0) {
      set({
        screen: 'ask',
        askMsgs: [
          {
            who: 'ai',
            text: '你好!我记得你所有箱子里的东西。想找什么直接问,比如「电钻在哪?」',
          },
        ],
      })
    } else set({ screen: 'ask' })
  },

  ask: (q) => {
    const st = get()
    if (st.thinking) return
    set({ askMsgs: [...st.askMsgs, { who: 'user', text: q }], thinking: true, screen: 'ask' })
    askStream(q, {
      onDelta: (t) => {
        set((s) => {
          const msgs = [...s.askMsgs]
          const last = msgs[msgs.length - 1]
          if (last?.who === 'ai' && last.streaming) {
            msgs[msgs.length - 1] = { ...last, text: last.text + t }
          } else {
            msgs.push({ who: 'ai', text: t, streaming: true })
          }
          return { askMsgs: msgs, thinking: false }
        })
      },
      onDone: (boxes) => {
        set((s) => {
          const msgs = [...s.askMsgs]
          const last = msgs[msgs.length - 1]
          if (last?.who === 'ai') {
            msgs[msgs.length - 1] = { ...last, streaming: false, boxes }
          }
          return {
            askMsgs: msgs,
            thinking: false,
            me: s.me ? { ...s.me, used: s.me.used + 1 } : s.me,
          }
        })
      },
      onError: () => {
        set((s) => ({
          thinking: false,
          askMsgs: [
            ...s.askMsgs.filter((m) => !(m.who === 'ai' && m.streaming)),
            { who: 'ai', text: '出错了,请稍后再试。' },
          ],
        }))
      },
    })
  },

  // ── 拍照识别 ──
  openCamera: () => set({ screen: 'camera', camPhase: 'live', recog: null }),

  recognizePhoto: async (blob) => {
    set({ camPhase: 'recog', pendingPhoto: blob }) // 保留照片,入库后上传
    try {
      const r = await api.recognize(blob)
      if (r.items.length === 0) {
        set({ camPhase: 'live' })
        get().showToast('没识别到物品,换个角度再拍?')
        return
      }
      set({
        camPhase: 'result',
        recog: {
          boxLabel: r.box_label,
          boxExists: r.box_exists,
          nextLabel: r.next_label,
          items: r.items.map((it) => ({ ...it, selected: it.confidence !== 'low' })),
        },
      })
    } catch (e) {
      set({ camPhase: 'live' })
      const err = e as Error & { status?: number }
      get().showToast(err.status === 502 ? '识别服务暂不可用' : '识别失败,请重试')
    }
  },

  retakePhoto: () => set({ camPhase: 'live', recog: null }),

  toggleRecogItem: (i) =>
    set((st) => {
      if (!st.recog) return {}
      const items = st.recog.items.map((it, idx) => (idx === i ? { ...it, selected: !it.selected } : it))
      return { recog: { ...st.recog, items } }
    }),

  editRecogItem: (i, patch) =>
    set((st) => {
      if (!st.recog) return {}
      const items = st.recog.items.map((it, idx) => (idx === i ? { ...it, ...patch } : it))
      return { recog: { ...st.recog, items } }
    }),

  addRecogItem: (name) =>
    set((st) => {
      const n = name.trim()
      if (!st.recog || !n) return {}
      return {
        recog: {
          ...st.recog,
          items: [...st.recog.items, { name: n, qty_text: '×1', confidence: 'high', selected: true }],
        },
      }
    }),

  confirmPhoto: async () => {
    const st = get()
    const r = st.recog
    if (!r || st.entryBusy) return
    const chosen = r.items.filter((it) => it.selected).map((it) => ({ name: it.name, qty_text: it.qty_text }))
    if (chosen.length === 0) {
      st.showToast('至少选一类物品')
      return
    }
    set({ entryBusy: true })
    const label = r.boxLabel || r.nextLabel
    try {
      const res = await api.ingest({
        box_label: label,
        items: chosen,
        gps_lat: st.userPos?.lat ?? null,
        gps_lng: st.userPos?.lng ?? null,
        source: 'photo',
      })
      // 保存识别照片(设为封面)。失败不阻断入库。
      if (st.pendingPhoto) {
        try {
          await api.uploadPhoto(res.box.id, st.pendingPhoto)
        } catch {
          /* 照片保存失败,物品已入库,忽略 */
        }
      }
      await st.refresh()
      set({
        screen: 'home',
        camPhase: 'live',
        recog: null,
        pendingPhoto: null,
        entryBusy: false,
        entryPhase: 'done',
        doneInfo: {
          boxId: res.box.id,
          title: res.created ? `已建 ${res.box.name}并入库` : `已记录到 ${res.box.name}`,
          line1: fmtItems(chosen),
          line2: '照片已识别 · AI 自动整理',
          markerTip: res.created ? `记得用马克笔把「${label.replace('号', '')}」写到箱子上` : null,
        },
      })
    } catch {
      set({ entryBusy: false })
      st.showToast('入库失败,请重试')
    }
  },

  // ── 扫码 ──
  openScan: () => set({ screen: 'scan', scanPhase: 'scanning', foundBox: null }),

  resolveScan: async (code) => {
    try {
      const { box } = await api.resolveCode({ code })
      set({ foundBox: box, scanPhase: 'found' })
    } catch (e) {
      const err = e as Error & { status?: number }
      if (err.status === 404) get().showToast('未关联箱子,试试输入手写编号')
      else get().showToast('识别失败,请重试')
    }
  },

  scanManual: async (label) => {
    if (!label.trim()) return
    try {
      const { box } = await api.resolveCode({ label: label.trim(), create: true })
      set({ foundBox: box, scanPhase: 'found' })
    } catch {
      get().showToast('操作失败,请重试')
    }
  },

  recordToFound: () => {
    const b = get().foundBox
    if (b) {
      set({ targetBox: b, screen: 'home' })
    }
  },

  addBoxPhoto: async (boxId, blob, setCover) => {
    try {
      await api.uploadPhoto(boxId, blob, setCover)
      await get().refresh()
    } catch {
      get().showToast('照片上传失败,请重试')
    }
  },

  setBoxCover: async (boxId, url) => {
    try {
      await api.setCover(boxId, url)
      await get().refresh()
      get().showToast('已设为封面')
    } catch {
      get().showToast('设置封面失败')
    }
  },

  addBoxItem: async (boxId, name) => {
    if (!name.trim()) return
    try {
      await api.addItem(boxId, { name: name.trim() })
      await get().refresh()
    } catch {
      get().showToast('添加失败,请重试')
    }
  },

  updateBoxItem: async (boxId, itemId, patch) => {
    try {
      await api.updateItem(boxId, itemId, patch)
      await get().refresh()
    } catch {
      get().showToast('保存失败,请重试')
    }
  },

  deleteBoxItem: async (boxId, itemId) => {
    try {
      await api.deleteItem(boxId, itemId)
      await get().refresh()
    } catch {
      get().showToast('删除失败,请重试')
    }
  },

  agentSend: (message) => {
    const st = get()
    if (st.thinking) return
    const history = st.askMsgs
      .filter((m) => m.text && !m.confirm)
      .map((m) => ({ role: m.who === 'user' ? 'user' : 'assistant', content: m.text }))
    const gps = st.userPos ? { lat: st.userPos.lat, lng: st.userPos.lng } : null
    set({ askMsgs: [...st.askMsgs, { who: 'user', text: message }], thinking: true, screen: 'ask' })
    api
      .agent(message, history, gps)
      .then((resp) => {
        set((s) => ({
          thinking: false,
          askMsgs: [
            ...s.askMsgs,
            resp.type === 'confirm'
              ? { who: 'ai' as const, text: resp.text || '需要你确认这个操作:', confirm: resp.actions }
              : { who: 'ai' as const, text: resp.text || '好的。' },
          ],
        }))
      })
      .catch(() => {
        set((s) => ({ thinking: false, askMsgs: [...s.askMsgs, { who: 'ai', text: '操作出错了,请重试。' }] }))
      })
  },

  agentConfirm: async (actions) => {
    set((s) => ({ thinking: true, askMsgs: s.askMsgs.map((m) => (m.confirm ? { ...m, confirm: undefined } : m)) }))
    const results: string[] = []
    for (const a of actions) {
      try {
        const r = await api.agentExecute(a.tool, a.args)
        results.push(r.summary || (r.ok ? '已完成' : r.error || '未完成'))
      } catch {
        results.push('执行失败')
      }
    }
    await get().refresh()
    set((s) => ({ thinking: false, askMsgs: [...s.askMsgs, { who: 'ai', text: results.join(';') }] }))
  },

  agentCancel: () =>
    set((s) => ({
      askMsgs: [...s.askMsgs.map((m) => (m.confirm ? { ...m, confirm: undefined } : m)), { who: 'ai', text: '好的,已取消。' }],
    })),

  updateMe: async (body) => {
    const prev = get().me
    // 乐观更新,让开关/语言切换立即反馈
    if (prev) set({ me: { ...prev, ...body, gps_enabled: body.gps_enabled ?? prev.gps_enabled } })
    try {
      const me = await api.updateMe(body)
      set({ me })
    } catch {
      if (prev) set({ me: prev })
      get().showToast('设置保存失败,请重试')
    }
  },
}))

// 仅开发环境:暴露 store 句柄,便于自动化自测(生产构建不包含)
if (import.meta.env.DEV) {
  ;(window as unknown as { __bmStore?: typeof useStore }).__bmStore = useStore
}

// ── 展示辅助 ──────────────────────────────

export function fmtTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 90_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (d.toDateString() === now.toDateString()) return '今天'
  if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}月${d.getDate()}日`
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

export function isNewBox(b: Box): boolean {
  return Date.now() - new Date(b.created_at).getTime() < 86_400_000
}

export function distText(
  userPos: { lat: number; lng: number } | null,
  lat: number | null,
  lng: number | null,
): string | null {
  if (!userPos || lat == null || lng == null) return null
  const R = 6371
  const dLat = ((lat - userPos.lat) * Math.PI) / 180
  const dLng = ((lng - userPos.lng) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((userPos.lat * Math.PI) / 180) * Math.cos((lat * Math.PI) / 180) * Math.sin(dLng / 2) ** 2
  const km = 2 * R * Math.asin(Math.sqrt(a))
  if (km < 0.2) return '就在附近'
  if (km < 10) return `距你 ${km.toFixed(1)} km`
  return `距你 ${Math.round(km)} km`
}
