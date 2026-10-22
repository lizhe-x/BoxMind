import type { AgentResp, Box, BoxRef, InterpretResult, Item, ItemDraft, Me, RecogResult } from './types'

// 默认同源(空 BASE → 调 /api/*,由前端服务器/Funnel 反代到后端,免 CORS、单端口对外)。
// 需要直连独立后端地址时用 VITE_API_BASE 覆盖。
const BASE = import.meta.env.VITE_API_BASE || ''

let token: string | null = localStorage.getItem('bm_token')

export function hasToken(): boolean {
  return !!token
}

function clearAuth(): void {
  token = null
  localStorage.removeItem('bm_token')
}

/** 需登录:无 token 直接抛错(应用据此显示登录页)。 */
export async function ensureAuth(): Promise<void> {
  if (!token) throw new Error('no_auth')
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  await ensureAuth()
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
  })
  if (r.status === 401) {
    clearAuth()
    const err = new Error('未登录') as Error & { status: number }
    err.status = 401
    throw err
  }
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    const err = new Error(body.detail || `HTTP ${r.status}`) as Error & { status: number }
    err.status = r.status
    throw err
  }
  return r.json()
}

export const api = {
  requestCode: async (email: string): Promise<{ sent: boolean; dev_mode?: boolean; dev_code?: string }> => {
    const r = await fetch(`${BASE}/api/auth/request-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
    if (!r.ok) {
      const b = await r.json().catch(() => ({}))
      throw new Error(b.detail || `HTTP ${r.status}`)
    }
    return r.json()
  },
  verifyCode: async (email: string, code: string): Promise<{ email: string }> => {
    const r = await fetch(`${BASE}/api/auth/verify-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, code }),
    })
    if (!r.ok) {
      const b = await r.json().catch(() => ({}))
      throw new Error(b.detail || `HTTP ${r.status}`)
    }
    const data = await r.json()
    token = data.token
    localStorage.setItem('bm_token', data.token)
    return { email: data.email }
  },
  logout: () => clearAuth(),
  me: () => req<Me>('/api/me'),
  updateMe: (body: { lang?: string; gps_enabled?: boolean }) =>
    req<Me>('/api/me', { method: 'PATCH', body: JSON.stringify(body) }),
  boxes: () => req<Box[]>('/api/boxes'),
  box: (id: string) => req<Box>(`/api/boxes/${id}`),
  deleteBox: (id: string) => req<{ ok: boolean }>(`/api/boxes/${id}`, { method: 'DELETE' }),
  addItem: (boxId: string, body: { name: string; qty_text?: string }) =>
    req<Item>(`/api/boxes/${boxId}/items`, { method: 'POST', body: JSON.stringify(body) }),
  updateItem: (boxId: string, itemId: string, patch: { name?: string; qty_text?: string }) =>
    req<Item>(`/api/boxes/${boxId}/items/${itemId}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  deleteItem: (boxId: string, itemId: string) =>
    req<{ ok: boolean }>(`/api/boxes/${boxId}/items/${itemId}`, { method: 'DELETE' }),
  interpret: (text: string, targetBoxId?: string | null) =>
    req<InterpretResult>('/api/interpret', {
      method: 'POST',
      body: JSON.stringify({ text, target_box_id: targetBoxId || null }),
    }),
  agent: (
    message: string,
    history: { role: string; content: string }[],
    gps: { lat: number; lng: number } | null,
  ) => req<AgentResp>('/api/agent', { method: 'POST', body: JSON.stringify({ message, history, gps }) }),
  agentExecute: (tool: string, args: Record<string, unknown>) =>
    req<{ ok: boolean; summary?: string; error?: string }>('/api/agent/execute', {
      method: 'POST',
      body: JSON.stringify({ tool, args }),
    }),
  ingest: (body: {
    box_id?: string | null
    box_label?: string | null
    items: ItemDraft[]
    location_text?: string | null
    gps_lat?: number | null
    gps_lng?: number | null
    raw_text?: string | null
    source?: string
  }) => req<{ box: Box; created: boolean; credits_left: number }>('/api/ingest', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  exportUrl: (fmt: 'json' | 'csv') => `${BASE}/api/me/export.${fmt}`,
  authToken: () => token,
  mediaUrl: (path: string) => `${BASE}${path}`,
  uploadPhoto: async (boxId: string, blob: Blob, setCover = true): Promise<{ url: string }> => {
    await ensureAuth()
    const fd = new FormData()
    fd.append('file', blob, 'photo.jpg')
    const r = await fetch(`${BASE}/api/boxes/${boxId}/photo?set_cover=${setCover}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    })
    if (!r.ok) throw new Error(`upload photo HTTP ${r.status}`)
    return r.json()
  },
  setCover: (boxId: string, url: string) =>
    req<Box>(`/api/boxes/${boxId}/cover`, { method: 'POST', body: JSON.stringify({ url }) }),
  uploadAudio: async (boxId: string, blob: Blob): Promise<{ url: string }> => {
    await ensureAuth()
    const fd = new FormData()
    fd.append('file', blob, 'audio.webm')
    const r = await fetch(`${BASE}/api/boxes/${boxId}/audio`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    })
    if (!r.ok) throw new Error(`upload audio HTTP ${r.status}`)
    return r.json()
  },
  resolveCode: (body: { code?: string; label?: string; create?: boolean }) =>
    req<{ box: Box; created: boolean }>('/api/boxes/resolve', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  /** 拍照识别:图片 → 物品清单 + 手写编号。 */
  recognize: async (blob: Blob): Promise<RecogResult> => {
    await ensureAuth()
    const fd = new FormData()
    fd.append('file', blob, 'photo.jpg')
    const r = await fetch(`${BASE}/api/recognize`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    })
    if (!r.ok) {
      const b = await r.json().catch(() => ({}))
      const err = new Error(b.detail || `HTTP ${r.status}`) as Error & { status: number }
      err.status = r.status
      throw err
    }
    return r.json()
  },
  /** 文字 → 语音音频 Blob(走网关 TTS)。 */
  tts: async (text: string): Promise<Blob> => {
    await ensureAuth()
    const r = await fetch(`${BASE}/api/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ text }),
    })
    if (!r.ok) {
      const b = await r.json().catch(() => ({}))
      throw new Error(b.detail || `HTTP ${r.status}`)
    }
    return r.blob()
  },
  /** 音频 → 文字(走网关 ASR)。失败抛错(含网关原因),由调用方降级处理。 */
  transcribe: async (blob: Blob, language?: string): Promise<string> => {
    await ensureAuth()
    const fd = new FormData()
    fd.append('file', blob, 'audio.webm')
    if (language) fd.append('language', language)
    const r = await fetch(`${BASE}/api/transcribe`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    })
    if (!r.ok) {
      const b = await r.json().catch(() => ({}))
      throw new Error(b.detail || `HTTP ${r.status}`)
    }
    const data = await r.json()
    return (data.text as string) || ''
  },
}

/** SSE 流式问答。返回中止函数。 */
export function askStream(
  question: string,
  cb: {
    onDelta: (t: string) => void
    onDone: (boxes: BoxRef[], creditsLeft: number) => void
    onError: (msg: string) => void
  },
): () => void {
  const ctrl = new AbortController()
  ;(async () => {
    await ensureAuth()
    let r: Response
    try {
      r = await fetch(`${BASE}/api/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ question }),
        signal: ctrl.signal,
      })
    } catch (e) {
      if (!ctrl.signal.aborted) cb.onError(String(e))
      return
    }
    if (!r.ok || !r.body) {
      const body = await r.json().catch(() => ({}))
      cb.onError(body.detail || `HTTP ${r.status}`)
      return
    }
    const reader = r.body.getReader()
    const dec = new TextDecoder()
    let buf = ''
    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        let idx
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const block = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          const ev = /^event: (\w+)$/m.exec(block)?.[1]
          const dataLine = /^data: (.*)$/m.exec(block)?.[1]
          if (!ev || !dataLine) continue
          const data = JSON.parse(dataLine)
          if (ev === 'delta') cb.onDelta(data.t)
          else if (ev === 'done') cb.onDone(data.boxes, data.credits_left)
          else if (ev === 'error') cb.onError(data.message)
        }
      }
    } catch (e) {
      if (!ctrl.signal.aborted) cb.onError(String(e))
    }
  })()
  return () => ctrl.abort()
}
