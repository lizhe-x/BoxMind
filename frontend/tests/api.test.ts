/**
 * API client: auth header handling, error propagation, and the hand-rolled
 * server-sent-events parser used for streaming answers.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

type ApiModule = typeof import('../src/api')

async function load(token: string | null): Promise<ApiModule> {
  vi.resetModules()
  localStorage.clear()
  if (token) localStorage.setItem('bm_token', token)
  return import('../src/api')
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** Build a streaming Response whose body arrives in the given raw chunks. */
function sseResponse(chunks: string[]): Response {
  const enc = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c))
      controller.close()
    },
  })
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

describe('authenticated requests', () => {
  it('sends the bearer token and parses JSON', async () => {
    const { api } = await load('tok-1')
    fetchMock.mockResolvedValue(jsonResponse(200, [{ id: 'b1' }]))
    await expect(api.boxes()).resolves.toEqual([{ id: 'b1' }])
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/boxes')
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-1')
  })

  it('refuses to call the network without a token', async () => {
    const { api, hasToken } = await load(null)
    expect(hasToken()).toBe(false)
    await expect(api.me()).rejects.toThrow('no_auth')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('a 401 clears the stored token so the app shows the login screen', async () => {
    const { api, hasToken } = await load('expired')
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: 'invalid token' }))
    await expect(api.me()).rejects.toMatchObject({ status: 401 })
    expect(hasToken()).toBe(false)
    expect(localStorage.getItem('bm_token')).toBeNull()
  })

  it('surfaces the backend detail message and status on other errors', async () => {
    const { api } = await load('tok')
    fetchMock.mockResolvedValue(jsonResponse(409, { detail: 'box with this label already exists' }))
    await expect(api.addItem('b1', { name: 'x' })).rejects.toMatchObject({
      message: 'box with this label already exists', status: 409,
    })
    fetchMock.mockResolvedValue(new Response('<html>', { status: 502 }))
    await expect(api.me()).rejects.toMatchObject({ message: 'HTTP 502', status: 502 })
  })

  it('verifyCode stores the token; logout removes it', async () => {
    const { api, hasToken } = await load(null)
    fetchMock.mockResolvedValue(jsonResponse(200, { token: 'fresh', user_id: 'u', email: 'a@b.co' }))
    await expect(api.verifyCode('a@b.co', '123456')).resolves.toEqual({ email: 'a@b.co' })
    expect(hasToken()).toBe(true)
    expect(localStorage.getItem('bm_token')).toBe('fresh')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ email: 'a@b.co', code: '123456' })
    api.logout()
    expect(hasToken()).toBe(false)
  })

  it('multipart uploads carry only the auth header (browser sets the boundary)', async () => {
    const { api } = await load('tok')
    fetchMock.mockResolvedValue(jsonResponse(200, { url: '/media/x.jpg' }))
    await api.uploadPhoto('b1', new Blob(['img']), false)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/boxes/b1/photo?set_cover=false')
    expect(init.headers).toEqual({ Authorization: 'Bearer tok' })
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('file')).toBeInstanceOf(Blob)
  })

  it('agent payload shape', async () => {
    const { api } = await load('tok')
    fetchMock.mockResolvedValue(jsonResponse(200, { type: 'message', text: 'ok' }))
    await api.agent('删掉5号', [{ role: 'user', content: 'hi' }], { lat: 1, lng: 2 })
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      message: '删掉5号', history: [{ role: 'user', content: 'hi' }], gps: { lat: 1, lng: 2 },
    })
  })
})

describe('askStream SSE parser', () => {
  it('reassembles events split across arbitrary chunk boundaries', async () => {
    const { askStream } = await load('tok')
    const wire =
      'event: delta\ndata: {"t":"登山包在"}\n\n' +
      'event: delta\ndata: {"t":" 6号箱"}\n\n' +
      'event: done\ndata: {"boxes":[{"id":"b6"}],"credits_left":-1}\n\n'
    // split in the middle of a JSON payload and of a multi-byte character
    const bytes = new TextEncoder().encode(wire)
    const cut1 = 20
    const cut2 = 61
    const dec = new TextDecoder()
    const chunks = [bytes.slice(0, cut1), bytes.slice(cut1, cut2), bytes.slice(cut2)]
    fetchMock.mockResolvedValue(
      new Response(
        new ReadableStream<Uint8Array>({
          start(c) {
            chunks.forEach((ch) => c.enqueue(ch))
            c.close()
          },
        }),
        { status: 200 },
      ),
    )
    void dec

    const deltas: string[] = []
    const done = new Promise<{ boxes: unknown; credits: number }>((resolve, reject) => {
      askStream('登山包在哪', {
        onDelta: (t) => deltas.push(t),
        onDone: (boxes, credits) => resolve({ boxes, credits }),
        onError: (m) => reject(new Error(m)),
      })
    })
    await expect(done).resolves.toEqual({ boxes: [{ id: 'b6' }], credits: -1 })
    expect(deltas.join('')).toBe('登山包在 6号箱')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ question: '登山包在哪' })
  })

  it('forwards server-side error events', async () => {
    const { askStream } = await load('tok')
    fetchMock.mockResolvedValue(sseResponse(['event: error\ndata: {"message":"gateway down"}\n\n']))
    const err = await new Promise<string>((resolve) => {
      askStream('x', { onDelta: () => {}, onDone: () => {}, onError: resolve })
    })
    expect(err).toBe('gateway down')
  })

  it('non-2xx responses become an error with the backend detail', async () => {
    const { askStream } = await load('tok')
    fetchMock.mockResolvedValue(jsonResponse(422, { detail: 'question too long' }))
    const err = await new Promise<string>((resolve) => {
      askStream('x', { onDelta: () => {}, onDone: () => {}, onError: resolve })
    })
    expect(err).toBe('question too long')
  })

  it('network failure becomes an error unless aborted', async () => {
    const { askStream } = await load('tok')
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const err = await new Promise<string>((resolve) => {
      askStream('x', { onDelta: () => {}, onDone: () => {}, onError: resolve })
    })
    expect(err).toContain('Failed to fetch')

    // aborted: the caller cancelled, so no error callback
    const onError = vi.fn()
    fetchMock.mockImplementation((_u: string, init: RequestInit) =>
      new Promise((_res, rej) => init.signal?.addEventListener('abort', () => rej(new DOMException('aborted', 'AbortError')))),
    )
    const abort = askStream('y', { onDelta: () => {}, onDone: () => {}, onError })
    abort()
    await new Promise((r) => setTimeout(r, 0))
    expect(onError).not.toHaveBeenCalled()
  })
})
