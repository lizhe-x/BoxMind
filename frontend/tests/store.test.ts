/**
 * Store logic: how one sentence is routed (ingest / query / operation), the agent
 * confirm-card flow, photo-intake selection defaults, and display helpers.
 * The API layer is mocked; nothing here touches the network.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Box, InterpretResult } from '../src/types'

vi.mock('../src/api', () => ({
  hasToken: vi.fn(() => true),
  askStream: vi.fn(() => () => {}),
  api: {
    interpret: vi.fn(),
    ingest: vi.fn(),
    uploadAudio: vi.fn(),
    uploadPhoto: vi.fn(),
    agent: vi.fn(),
    agentExecute: vi.fn(),
    recognize: vi.fn(),
    me: vi.fn(),
    boxes: vi.fn(),
    resolveCode: vi.fn(),
    verifyCode: vi.fn(),
    logout: vi.fn(),
  },
}))

import { api, askStream } from '../src/api'
import { distText, fmtItems, fmtTime, isNewBox, useStore } from '../src/store'

const mocked = api as unknown as Record<keyof typeof api, ReturnType<typeof vi.fn>>
const initial = useStore.getState()

function box(partial: Partial<Box> = {}): Box {
  return {
    id: 'b1', label: '5号', name: '5号箱', barcode: null, photo_url: null, location_text: null,
    gps_lat: null, gps_lng: null, color_a: '#000', color_b: '#111', source: 'text',
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    items: [], photos: [], audios: [], ...partial,
  }
}

function interpret(partial: Partial<InterpretResult>): InterpretResult {
  return { intent: 'ingest', box_label: null, box: null, items: [], location_text: null, language: 'zh', next_label: '1号', ...partial }
}

beforeEach(() => {
  useStore.setState(initial, true)
  mocked.me.mockResolvedValue({ user_id: 'u', email: null, lang: 'zh', gps_enabled: true, credit_balance: 0, used: 0, box_count: 0, item_count: 0 })
  mocked.boxes.mockResolvedValue([])
})

describe('submitText routes one sentence to the right pipeline', () => {
  it('ingest with a box label → confirm card', async () => {
    mocked.interpret.mockResolvedValue(interpret({ box_label: '5号', items: [{ name: '头灯', qty_text: '×1' }] }))
    await useStore.getState().submitText('5号箱放了头灯')
    const s = useStore.getState()
    expect(s.entryPhase).toBe('confirm')
    expect(s.parsed?.items).toEqual([{ name: '头灯', qty_text: '×1' }])
    expect(s.rawText).toBe('5号箱放了头灯')
    expect(mocked.interpret).toHaveBeenCalledWith('5号箱放了头灯', undefined)
  })

  it('ingest without a box label → ask which box', async () => {
    mocked.interpret.mockResolvedValue(interpret({ items: [{ name: '头灯', qty_text: '×1' }] }))
    await useStore.getState().submitText('放了头灯')
    expect(useStore.getState().entryPhase).toBe('askbox')
  })

  it('a locked target box skips the askbox step and is forwarded to interpret', async () => {
    useStore.setState({ targetBox: box({ id: 'target' }) })
    mocked.interpret.mockResolvedValue(interpret({ items: [{ name: '头灯', qty_text: '×1' }] }))
    await useStore.getState().submitText('放了头灯')
    expect(useStore.getState().entryPhase).toBe('confirm')
    expect(mocked.interpret).toHaveBeenCalledWith('放了头灯', 'target')
  })

  it('ingest with no recognisable items → back to input with a toast', async () => {
    mocked.interpret.mockResolvedValue(interpret({ box_label: '5号', items: [] }))
    await useStore.getState().submitText('嗯……')
    const s = useStore.getState()
    expect(s.entryPhase).toBe('input')
    expect(s.toast).toContain('没听出')
  })

  it('query → chat screen and streaming ask', async () => {
    mocked.interpret.mockResolvedValue(interpret({ intent: 'query' }))
    await useStore.getState().submitText('头灯在哪')
    const s = useStore.getState()
    expect(s.screen).toBe('ask')
    expect(s.entryPhase).toBe('idle')
    expect(s.askMsgs.map((m) => m.who)).toEqual(['ai', 'user']) // greeting + question
    expect(askStream).toHaveBeenCalledWith('头灯在哪', expect.any(Object))
    expect(mocked.agent).not.toHaveBeenCalled()
  })

  it('operation → chat screen and the agent, with history and gps', async () => {
    useStore.setState({ userPos: { lat: 1, lng: 2 }, askMsgs: [{ who: 'ai', text: 'hi' }, { who: 'user', text: 'x' }, { who: 'ai', text: 'pending', confirm: [] }] })
    mocked.interpret.mockResolvedValue(interpret({ intent: 'operation' }))
    mocked.agent.mockResolvedValue({ type: 'message', text: '已改' })
    await useStore.getState().submitText('7号改名叫工具箱')
    await vi.waitFor(() => expect(useStore.getState().thinking).toBe(false))
    expect(mocked.agent).toHaveBeenCalledWith(
      '7号改名叫工具箱',
      [{ role: 'assistant', content: 'hi' }, { role: 'user', content: 'x' }], // confirm cards are not history
      { lat: 1, lng: 2 },
    )
    expect(useStore.getState().askMsgs.at(-1)).toEqual({ who: 'ai', text: '已改' })
    expect(askStream).not.toHaveBeenCalled()
  })

  it('interpret failure → back to input with a toast', async () => {
    mocked.interpret.mockRejectedValue(new Error('502'))
    await useStore.getState().submitText('x')
    expect(useStore.getState().entryPhase).toBe('input')
    expect(useStore.getState().toast).toContain('失败')
  })

  it('ignores empty input and concurrent submits', async () => {
    await useStore.getState().submitText('   ')
    expect(mocked.interpret).not.toHaveBeenCalled()
    useStore.setState({ entryBusy: true })
    await useStore.getState().submitText('x')
    expect(mocked.interpret).not.toHaveBeenCalled()
  })
})

describe('confirmEntry writes through and keeps voice audio best-effort', () => {
  it('ingests, uploads the pending audio, refreshes, and reports', async () => {
    const parsed = interpret({ box_label: '5号', items: [{ name: '头灯', qty_text: '×1' }], location_text: '车库' })
    useStore.setState({ parsed, rawText: 'raw', entrySource: 'voice', pendingAudio: new Blob(['a']), userPos: { lat: 1, lng: 2 } })
    mocked.ingest.mockResolvedValue({ box: box({ location_text: '车库' }), created: true, credits_left: -1 })
    mocked.uploadAudio.mockRejectedValue(new Error('disk full')) // must not break the flow
    await useStore.getState().confirmEntry()
    const s = useStore.getState()
    expect(mocked.ingest).toHaveBeenCalledWith({
      box_id: null, box_label: '5号', items: parsed.items, location_text: '车库',
      gps_lat: 1, gps_lng: 2, raw_text: 'raw', source: 'voice',
    })
    expect(mocked.uploadAudio).toHaveBeenCalledWith('b1', expect.any(Blob))
    expect(s.entryPhase).toBe('done')
    expect(s.pendingAudio).toBeNull()
    expect(s.doneInfo).toMatchObject({ boxId: 'b1', title: '已建 5号箱并入库', line1: '头灯 ×1', line2: '位置:车库' })
    expect(mocked.boxes).toHaveBeenCalled() // refresh
  })

  it('pickNewBox uses the suggested label and reminds the user to write it on the box', async () => {
    useStore.setState({ parsed: interpret({ items: [{ name: '头灯', qty_text: '×1' }], next_label: '4号' }) })
    mocked.ingest.mockResolvedValue({ box: box({ label: '4号', name: '4号箱' }), created: true, credits_left: -1 })
    await useStore.getState().pickNewBox()
    expect(mocked.ingest.mock.calls[0][0]).toMatchObject({ box_label: '4号' })
    expect(useStore.getState().doneInfo?.markerTip).toContain('「4」')
  })

  it('ingest failure keeps the confirm card and toasts', async () => {
    useStore.setState({ parsed: interpret({ box_label: '5号', items: [{ name: 'x', qty_text: '×1' }] }), entryPhase: 'confirm' })
    mocked.ingest.mockRejectedValue(new Error('500'))
    await useStore.getState().confirmEntry()
    expect(useStore.getState().entryPhase).toBe('confirm')
    expect(useStore.getState().entryBusy).toBe(false)
    expect(useStore.getState().toast).toContain('入库失败')
  })
})

describe('agent confirm card', () => {
  const actions = [{ tool: 'delete_box', args: { box: '5号' }, summary: '删除整个箱子「5号」' }]

  it('a confirm response renders a card instead of executing', async () => {
    mocked.agent.mockResolvedValue({ type: 'confirm', text: '', actions })
    useStore.getState().agentSend('删掉5号')
    await vi.waitFor(() => expect(useStore.getState().thinking).toBe(false))
    const last = useStore.getState().askMsgs.at(-1)
    expect(last).toEqual({ who: 'ai', text: '需要你确认这个操作:', confirm: actions })
    expect(mocked.agentExecute).not.toHaveBeenCalled()
  })

  it('confirming executes each action, clears the card, refreshes and reports', async () => {
    useStore.setState({ askMsgs: [{ who: 'ai', text: '确认?', confirm: actions }] })
    mocked.agentExecute.mockResolvedValueOnce({ ok: true, summary: '已删除箱子「5号箱」' })
    await useStore.getState().agentConfirm(actions)
    const msgs = useStore.getState().askMsgs
    expect(mocked.agentExecute).toHaveBeenCalledWith('delete_box', { box: '5号' })
    expect(msgs[0].confirm).toBeUndefined()
    expect(msgs.at(-1)).toEqual({ who: 'ai', text: '已删除箱子「5号箱」' })
    expect(mocked.boxes).toHaveBeenCalled()
  })

  it('a failed execution is reported inline, not thrown', async () => {
    mocked.agentExecute.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce({ ok: false, error: '没找到箱子' })
    await useStore.getState().agentConfirm([...actions, ...actions])
    expect(useStore.getState().askMsgs.at(-1)?.text).toBe('执行失败;没找到箱子')
  })

  it('cancel clears the card and acknowledges', () => {
    useStore.setState({ askMsgs: [{ who: 'ai', text: '确认?', confirm: actions }] })
    useStore.getState().agentCancel()
    const msgs = useStore.getState().askMsgs
    expect(msgs[0].confirm).toBeUndefined()
    expect(msgs.at(-1)?.text).toBe('好的,已取消。')
  })

  it('agent transport error becomes a chat message', async () => {
    mocked.agent.mockRejectedValue(new Error('502'))
    useStore.getState().agentSend('x')
    await vi.waitFor(() => expect(useStore.getState().thinking).toBe(false))
    expect(useStore.getState().askMsgs.at(-1)?.text).toContain('出错')
  })
})

describe('photo intake', () => {
  it('low-confidence items start unchecked, others checked', async () => {
    mocked.recognize.mockResolvedValue({
      box_label: '2号', box_exists: false, next_label: '3号',
      items: [
        { name: '登山包', qty_text: '×1', confidence: 'high' },
        { name: '帐篷', qty_text: '×1', confidence: 'medium' },
        { name: '手套', qty_text: '若干', confidence: 'low' },
      ],
    })
    await useStore.getState().recognizePhoto(new Blob(['img']))
    const s = useStore.getState()
    expect(s.camPhase).toBe('result')
    expect(s.recog?.items.map((i) => i.selected)).toEqual([true, true, false])
    expect(s.pendingPhoto).toBeInstanceOf(Blob)
  })

  it('empty recognition returns to the viewfinder with a hint', async () => {
    mocked.recognize.mockResolvedValue({ box_label: null, box_exists: false, next_label: '1号', items: [] })
    await useStore.getState().recognizePhoto(new Blob(['img']))
    expect(useStore.getState().camPhase).toBe('live')
    expect(useStore.getState().toast).toContain('没识别到')
  })

  it('a 502 from the vision endpoint gets a specific message', async () => {
    mocked.recognize.mockRejectedValue(Object.assign(new Error('x'), { status: 502 }))
    await useStore.getState().recognizePhoto(new Blob(['img']))
    expect(useStore.getState().toast).toBe('识别服务暂不可用')
  })

  it('toggle / edit / add items, then confirm ingests only the selected ones with the photo as cover', async () => {
    useStore.setState({
      camPhase: 'result',
      pendingPhoto: new Blob(['img']),
      recog: {
        boxLabel: null, boxExists: false, nextLabel: '3号',
        items: [
          { name: '登山包', qty_text: '×1', confidence: 'high', selected: true },
          { name: '手套', qty_text: '若干', confidence: 'low', selected: false },
        ],
      },
    })
    const st = useStore.getState()
    st.toggleRecogItem(1)
    st.editRecogItem(1, { qty_text: '×2' })
    st.addRecogItem('  头灯 ')
    st.addRecogItem('   ')
    expect(useStore.getState().recog?.items.map((i) => [i.name, i.qty_text, i.selected])).toEqual([
      ['登山包', '×1', true], ['手套', '×2', true], ['头灯', '×1', true],
    ])
    useStore.getState().toggleRecogItem(0)
    mocked.ingest.mockResolvedValue({ box: box({ id: 'nb', label: '3号', name: '3号箱' }), created: true, credits_left: -1 })
    mocked.uploadPhoto.mockResolvedValue({ url: '/media/x.jpg' })
    await useStore.getState().confirmPhoto()
    expect(mocked.ingest.mock.calls[0][0]).toMatchObject({
      box_label: '3号', source: 'photo',
      items: [{ name: '手套', qty_text: '×2' }, { name: '头灯', qty_text: '×1' }],
    })
    expect(mocked.uploadPhoto).toHaveBeenCalledWith('nb', expect.any(Blob))
    const s = useStore.getState()
    expect(s.screen).toBe('home')
    expect(s.doneInfo?.markerTip).toContain('「3」')
    expect(s.pendingPhoto).toBeNull()
  })

  it('confirm with nothing selected is refused', async () => {
    useStore.setState({ recog: { boxLabel: null, boxExists: false, nextLabel: '1号', items: [{ name: 'x', qty_text: '×1', confidence: 'high', selected: false }] } })
    await useStore.getState().confirmPhoto()
    expect(mocked.ingest).not.toHaveBeenCalled()
    expect(useStore.getState().toast).toBe('至少选一类物品')
  })
})

describe('scan', () => {
  it('unknown code suggests the handwritten-label fallback', async () => {
    mocked.resolveCode.mockRejectedValue(Object.assign(new Error('nf'), { status: 404 }))
    await useStore.getState().resolveScan('BX-1')
    expect(useStore.getState().scanPhase).toBe('scanning')
    expect(useStore.getState().toast).toContain('手写编号')
  })

  it('manual label creates or finds a box, and "record here" locks it as target', async () => {
    mocked.resolveCode.mockResolvedValue({ box: box({ id: 'found' }), created: true })
    await useStore.getState().scanManual(' 7号 ')
    expect(mocked.resolveCode).toHaveBeenCalledWith({ label: '7号', create: true })
    expect(useStore.getState().scanPhase).toBe('found')
    useStore.getState().recordToFound()
    expect(useStore.getState().targetBox?.id).toBe('found')
    expect(useStore.getState().screen).toBe('home')
  })
})

describe('voice recording hand-off', () => {
  it('empty transcript falls back to typing without breaking the loop', () => {
    useStore.getState().beginRecording()
    expect(useStore.getState().entryPhase).toBe('recording')
    useStore.getState().finishRecording('   ', null)
    const s = useStore.getState()
    expect(s.entryPhase).toBe('idle')
    expect(s.screen).toBe('home')
    expect(s.toast).toContain('打字')
    expect(mocked.interpret).not.toHaveBeenCalled()
  })
})

describe('display helpers', () => {
  it('fmtItems', () => {
    expect(fmtItems([{ name: '头灯', qty_text: '×2' }, { name: '帐篷', qty_text: '×1' }])).toBe('头灯 ×2 · 帐篷 ×1')
  })

  it('fmtTime buckets', () => {
    const now = Date.now()
    expect(fmtTime(new Date(now - 10_000).toISOString())).toBe('刚刚')
    expect(fmtTime(new Date(now - 5 * 60_000).toISOString())).toBe('5 分钟前')
    expect(fmtTime('2000-03-04T12:00:00')).toBe('2000年3月4日') // local-time ISO string, timezone-independent
  })

  it('isNewBox is a 24h window', () => {
    expect(isNewBox(box({ created_at: new Date(Date.now() - 3_600_000).toISOString() }))).toBe(true)
    expect(isNewBox(box({ created_at: new Date(Date.now() - 2 * 86_400_000).toISOString() }))).toBe(false)
  })

  it('distText uses haversine and degrades without a position', () => {
    expect(distText(null, 1, 2)).toBeNull()
    expect(distText({ lat: 1, lng: 2 }, null, 2)).toBeNull()
    expect(distText({ lat: 31.23, lng: 121.47 }, 31.23, 121.47)).toBe('就在附近')
    expect(distText({ lat: 31.23, lng: 121.47 }, 31.25, 121.47)).toBe('距你 2.2 km')
    expect(distText({ lat: 31.23, lng: 121.47 }, 39.9, 116.4)).toMatch(/^距你 106\d km$/) // Shanghai → Beijing
  })
})
