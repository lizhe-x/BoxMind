/**
 * Store logic: how one sentence is routed (ingest / query / operation), the agent
 * confirm-card flow, photo-intake selection defaults, language handling and display helpers.
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
    updateMe: vi.fn(),
    logout: vi.fn(),
  },
}))

import { api, askStream } from '../src/api'
import { authError, boxNameFor, markerText, tr } from '../src/i18n'
import { distText, fmtItems, fmtTime, isNewBox, plainText, useStore } from '../src/store'

const mocked = api as unknown as Record<keyof typeof api, ReturnType<typeof vi.fn>>
const initial = useStore.getState()

function box(partial: Partial<Box> = {}): Box {
  return {
    id: 'b1', label: '5', name: 'Box 5', barcode: null, photo_url: null, location_text: null,
    gps_lat: null, gps_lng: null, color_a: '#000', color_b: '#111', source: 'text',
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    items: [], photos: [], audios: [], ...partial,
  }
}

function interpret(partial: Partial<InterpretResult>): InterpretResult {
  return { intent: 'ingest', box_label: null, box: null, items: [], location_text: null, language: 'en', next_label: '1', ...partial }
}

const me = { user_id: 'u', email: null, lang: 'en', gps_enabled: true, credit_balance: 0, used: 0, box_count: 0, item_count: 0 }

beforeEach(() => {
  localStorage.clear()
  useStore.setState({ ...initial, lang: 'en' }, true)
  mocked.me.mockResolvedValue(me)
  mocked.boxes.mockResolvedValue([])
  mocked.updateMe.mockImplementation(async (body: Record<string, unknown>) => ({ ...me, ...body }))
})

describe('language', () => {
  it('defaults to English', () => {
    expect(useStore.getState().lang).toBe('en')
  })

  it('setLang persists locally and, when signed in, syncs to the server', async () => {
    await useStore.getState().setLang('zh')
    expect(useStore.getState().lang).toBe('zh')
    expect(localStorage.getItem('bm_lang')).toBe('zh')
    expect(mocked.updateMe).not.toHaveBeenCalled() // not authed yet

    useStore.setState({ authed: true, me })
    await useStore.getState().setLang('en')
    expect(mocked.updateMe).toHaveBeenCalledWith({ lang: 'en' })
  })

  it('refresh adopts the server language', async () => {
    mocked.me.mockResolvedValue({ ...me, lang: 'zh-CN' })
    await useStore.getState().refresh()
    expect(useStore.getState().lang).toBe('zh')
    expect(localStorage.getItem('bm_lang')).toBe('zh')
  })

  it('login pushes a language chosen before signing in to a fresh account', async () => {
    useStore.setState({ lang: 'zh' })
    mocked.verifyCode.mockResolvedValue({ email: 'a@b.co' })
    mocked.me.mockResolvedValue({ ...me, lang: 'en' }) // server default for a new user
    await useStore.getState().login('a@b.co', '123456')
    expect(useStore.getState().lang).toBe('zh')
    expect(mocked.updateMe).toHaveBeenCalledWith({ lang: 'zh' })
  })

  it('toasts follow the active language', async () => {
    useStore.setState({ lang: 'zh' })
    mocked.interpret.mockRejectedValue(new Error('502'))
    await useStore.getState().submitText('x')
    expect(useStore.getState().toast).toBe('AI 解析失败,请重试')
  })

  it('i18n helpers', () => {
    expect(tr('en', 'home_stats', { boxes: 2, items: 9 })).toBe('2 boxes · 9 item types remembered')
    expect(tr('zh', 'home_stats', { boxes: 2, items: 9 })).toBe('2 个箱子 · 9 类物品已记住')
    expect(boxNameFor('4', 'en')).toBe('Box 4')
    expect(boxNameFor('4号', 'zh')).toBe('4号箱')
    expect(boxNameFor('Liam', 'en')).toBe('Liam')
    expect(markerText('4号')).toBe('4')
    expect(authError('en', 'code_invalid', 'err_verify_failed')).toBe('Wrong code')
    expect(authError('zh', 'too_soon', 'err_send_failed')).toBe('请求过于频繁,请稍后再试')
    expect(authError('en', 'send_failed: smtp down', 'err_send_failed')).toBe('Could not send the code')
    expect(authError('en', 'HTTP 500', 'err_send_failed')).toBe('HTTP 500') // unknown details pass through
    expect(authError('en', undefined, 'err_verify_failed')).toBe('Verification failed')
  })
})

describe('submitText routes one sentence to the right pipeline', () => {
  it('ingest with a box label → confirm card', async () => {
    mocked.interpret.mockResolvedValue(interpret({ box_label: '5', items: [{ name: 'headlamp', qty_text: '×1' }] }))
    await useStore.getState().submitText('box 5 has a headlamp')
    const s = useStore.getState()
    expect(s.entryPhase).toBe('confirm')
    expect(s.parsed?.items).toEqual([{ name: 'headlamp', qty_text: '×1' }])
    expect(s.rawText).toBe('box 5 has a headlamp')
    expect(mocked.interpret).toHaveBeenCalledWith('box 5 has a headlamp', undefined)
  })

  it('ingest without a box label → ask which box', async () => {
    mocked.interpret.mockResolvedValue(interpret({ items: [{ name: 'headlamp', qty_text: '×1' }] }))
    await useStore.getState().submitText('a headlamp')
    expect(useStore.getState().entryPhase).toBe('askbox')
  })

  it('a locked target box skips the askbox step and is forwarded to interpret', async () => {
    useStore.setState({ targetBox: box({ id: 'target' }) })
    mocked.interpret.mockResolvedValue(interpret({ items: [{ name: 'headlamp', qty_text: '×1' }] }))
    await useStore.getState().submitText('a headlamp')
    expect(useStore.getState().entryPhase).toBe('confirm')
    expect(mocked.interpret).toHaveBeenCalledWith('a headlamp', 'target')
  })

  it('ingest with no recognisable items → back to input with a toast', async () => {
    mocked.interpret.mockResolvedValue(interpret({ box_label: '5', items: [] }))
    await useStore.getState().submitText('hmm…')
    const s = useStore.getState()
    expect(s.entryPhase).toBe('input')
    expect(s.toast).toContain("couldn't find any items")
  })

  it('query → chat screen and streaming ask', async () => {
    mocked.interpret.mockResolvedValue(interpret({ intent: 'query' }))
    await useStore.getState().submitText('where is the headlamp')
    const s = useStore.getState()
    expect(s.screen).toBe('ask')
    expect(s.entryPhase).toBe('idle')
    expect(s.askMsgs.map((m) => m.who)).toEqual(['ai', 'user']) // greeting + question
    expect(s.askMsgs[0].text).toContain('where is the drill')
    expect(askStream).toHaveBeenCalledWith('where is the headlamp', expect.any(Object))
    expect(mocked.agent).not.toHaveBeenCalled()
  })

  it('operation → chat screen and the agent, with history and gps', async () => {
    useStore.setState({ userPos: { lat: 1, lng: 2 }, askMsgs: [{ who: 'ai', text: 'hi' }, { who: 'user', text: 'x' }, { who: 'ai', text: 'pending', confirm: [] }] })
    mocked.interpret.mockResolvedValue(interpret({ intent: 'operation' }))
    mocked.agent.mockResolvedValue({ type: 'message', text: 'Renamed.' })
    await useStore.getState().submitText('rename box 7 to tools')
    await vi.waitFor(() => expect(useStore.getState().thinking).toBe(false))
    expect(mocked.agent).toHaveBeenCalledWith(
      'rename box 7 to tools',
      [{ role: 'assistant', content: 'hi' }, { role: 'user', content: 'x' }], // confirm cards are not history
      { lat: 1, lng: 2 },
    )
    expect(useStore.getState().askMsgs.at(-1)).toEqual({ who: 'ai', text: 'Renamed.' })
    expect(askStream).not.toHaveBeenCalled()
  })

  it('interpret failure → back to input with a toast', async () => {
    mocked.interpret.mockRejectedValue(new Error('502'))
    await useStore.getState().submitText('x')
    expect(useStore.getState().entryPhase).toBe('input')
    expect(useStore.getState().toast).toBe('The AI could not parse that, please try again')
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
    const parsed = interpret({ box_label: '5', items: [{ name: 'headlamp', qty_text: '×1' }], location_text: 'garage' })
    useStore.setState({ parsed, rawText: 'raw', entrySource: 'voice', pendingAudio: new Blob(['a']), userPos: { lat: 1, lng: 2 } })
    mocked.ingest.mockResolvedValue({ box: box({ location_text: 'garage' }), created: true, credits_left: -1 })
    mocked.uploadAudio.mockRejectedValue(new Error('disk full')) // must not break the flow
    await useStore.getState().confirmEntry()
    const s = useStore.getState()
    expect(mocked.ingest).toHaveBeenCalledWith({
      box_id: null, box_label: '5', items: parsed.items, location_text: 'garage',
      gps_lat: 1, gps_lng: 2, raw_text: 'raw', source: 'voice',
    })
    expect(mocked.uploadAudio).toHaveBeenCalledWith('b1', expect.any(Blob))
    expect(s.entryPhase).toBe('done')
    expect(s.pendingAudio).toBeNull()
    expect(s.targetBox).toBeNull()
    expect(s.doneInfo).toMatchObject({ boxId: 'b1', title: 'Created Box 5 and saved', line1: 'headlamp ×1', line2: 'Location: garage' })
    expect(mocked.boxes).toHaveBeenCalled() // refresh
  })

  it('pickNewBox uses the suggested label and reminds the user to write it on the box', async () => {
    useStore.setState({ parsed: interpret({ items: [{ name: 'headlamp', qty_text: '×1' }], next_label: '4' }) })
    mocked.ingest.mockResolvedValue({ box: box({ label: '4', name: 'Box 4' }), created: true, credits_left: -1 })
    await useStore.getState().pickNewBox()
    expect(mocked.ingest.mock.calls[0][0]).toMatchObject({ box_label: '4' })
    expect(useStore.getState().doneInfo?.markerTip).toContain('“4”')
  })

  it('ingest failure keeps the confirm card and toasts', async () => {
    useStore.setState({ parsed: interpret({ box_label: '5', items: [{ name: 'x', qty_text: '×1' }] }), entryPhase: 'confirm' })
    mocked.ingest.mockRejectedValue(new Error('500'))
    await useStore.getState().confirmEntry()
    expect(useStore.getState().entryPhase).toBe('confirm')
    expect(useStore.getState().entryBusy).toBe(false)
    expect(useStore.getState().toast).toBe('Saving failed, please try again')
  })
})

describe('agent confirm card', () => {
  const actions = [{ tool: 'delete_box', args: { box: '5' }, summary: 'Delete box “5”' }]

  it('a confirm response renders a card instead of executing', async () => {
    mocked.agent.mockResolvedValue({ type: 'confirm', text: '', actions })
    useStore.getState().agentSend('delete box 5')
    await vi.waitFor(() => expect(useStore.getState().thinking).toBe(false))
    const last = useStore.getState().askMsgs.at(-1)
    expect(last).toEqual({ who: 'ai', text: 'Please confirm this action:', confirm: actions })
    expect(mocked.agentExecute).not.toHaveBeenCalled()
  })

  it('a confirm response with already-executed sibling calls refreshes the boxes', async () => {
    mocked.agent.mockResolvedValue({ type: 'confirm', text: '', actions, executed: [{ tool: 'move_items', result: { ok: true } }] })
    useStore.getState().agentSend('move then delete')
    await vi.waitFor(() => expect(mocked.boxes).toHaveBeenCalled())
  })

  it('confirming executes each action, clears the card, refreshes and reports', async () => {
    useStore.setState({ askMsgs: [{ who: 'ai', text: 'confirm?', confirm: actions }] })
    mocked.agentExecute.mockResolvedValueOnce({ ok: true, summary: 'Deleted box “Box 5”' })
    await useStore.getState().agentConfirm(actions)
    const msgs = useStore.getState().askMsgs
    expect(mocked.agentExecute).toHaveBeenCalledWith('delete_box', { box: '5' })
    expect(msgs[0].confirm).toBeUndefined()
    expect(msgs.at(-1)).toEqual({ who: 'ai', text: 'Deleted box “Box 5”' })
    expect(mocked.boxes).toHaveBeenCalled()
  })

  it('a failed execution is reported inline, not thrown', async () => {
    mocked.agentExecute.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce({ ok: false, error: 'box not found' })
    await useStore.getState().agentConfirm([...actions, ...actions])
    expect(useStore.getState().askMsgs.at(-1)?.text).toBe('Failed; box not found')
  })

  it('cancel clears the card and acknowledges', () => {
    useStore.setState({ askMsgs: [{ who: 'ai', text: 'confirm?', confirm: actions }] })
    useStore.getState().agentCancel()
    const msgs = useStore.getState().askMsgs
    expect(msgs[0].confirm).toBeUndefined()
    expect(msgs.at(-1)?.text).toBe('OK, cancelled.')
  })

  it('agent transport error becomes a chat message', async () => {
    mocked.agent.mockRejectedValue(new Error('502'))
    useStore.getState().agentSend('x')
    await vi.waitFor(() => expect(useStore.getState().thinking).toBe(false))
    expect(useStore.getState().askMsgs.at(-1)?.text).toContain('Something went wrong')
  })
})

describe('photo intake', () => {
  it('low-confidence items start unchecked, others checked', async () => {
    mocked.recognize.mockResolvedValue({
      box_label: '2', box_exists: false, next_label: '3',
      items: [
        { name: 'backpack', qty_text: '×1', confidence: 'high' },
        { name: 'tent', qty_text: '×1', confidence: 'medium' },
        { name: 'gloves', qty_text: 'some', confidence: 'low' },
      ],
    })
    await useStore.getState().recognizePhoto(new Blob(['img']))
    const s = useStore.getState()
    expect(s.camPhase).toBe('result')
    expect(s.recog?.items.map((i) => i.selected)).toEqual([true, true, false])
    expect(s.pendingPhoto).toBeInstanceOf(Blob)
  })

  it('empty recognition returns to the viewfinder with a hint', async () => {
    mocked.recognize.mockResolvedValue({ box_label: null, box_exists: false, next_label: '1', items: [] })
    await useStore.getState().recognizePhoto(new Blob(['img']))
    expect(useStore.getState().camPhase).toBe('live')
    expect(useStore.getState().toast).toContain('Nothing recognised')
  })

  it('a 502 from the vision endpoint gets a specific message', async () => {
    mocked.recognize.mockRejectedValue(Object.assign(new Error('x'), { status: 502 }))
    await useStore.getState().recognizePhoto(new Blob(['img']))
    expect(useStore.getState().toast).toBe('Recognition service unavailable')
  })

  it('toggle / edit / add items, then confirm ingests only the selected ones with the photo as cover', async () => {
    useStore.setState({
      camPhase: 'result',
      pendingPhoto: new Blob(['img']),
      recog: {
        boxLabel: null, boxExists: false, nextLabel: '3',
        items: [
          { name: 'backpack', qty_text: '×1', confidence: 'high', selected: true },
          { name: 'gloves', qty_text: 'some', confidence: 'low', selected: false },
        ],
      },
    })
    const st = useStore.getState()
    st.toggleRecogItem(1)
    st.editRecogItem(1, { qty_text: '×2' })
    st.addRecogItem('  headlamp ')
    st.addRecogItem('   ')
    expect(useStore.getState().recog?.items.map((i) => [i.name, i.qty_text, i.selected])).toEqual([
      ['backpack', '×1', true], ['gloves', '×2', true], ['headlamp', '×1', true],
    ])
    useStore.getState().toggleRecogItem(0)
    mocked.ingest.mockResolvedValue({ box: box({ id: 'nb', label: '3', name: 'Box 3' }), created: true, credits_left: -1 })
    mocked.uploadPhoto.mockResolvedValue({ url: '/media/x.jpg' })
    await useStore.getState().confirmPhoto()
    expect(mocked.ingest.mock.calls[0][0]).toMatchObject({
      box_label: '3', source: 'photo',
      items: [{ name: 'gloves', qty_text: '×2' }, { name: 'headlamp', qty_text: '×1' }],
    })
    expect(mocked.uploadPhoto).toHaveBeenCalledWith('nb', expect.any(Blob))
    const s = useStore.getState()
    expect(s.screen).toBe('home')
    expect(s.doneInfo?.markerTip).toContain('“3”')
    expect(s.pendingPhoto).toBeNull()
  })

  it('confirm with nothing selected is refused', async () => {
    useStore.setState({ recog: { boxLabel: null, boxExists: false, nextLabel: '1', items: [{ name: 'x', qty_text: '×1', confidence: 'high', selected: false }] } })
    await useStore.getState().confirmPhoto()
    expect(mocked.ingest).not.toHaveBeenCalled()
    expect(useStore.getState().toast).toBe('Select at least one item')
  })
})

describe('scan', () => {
  it('unknown code suggests the handwritten-label fallback', async () => {
    mocked.resolveCode.mockRejectedValue(Object.assign(new Error('nf'), { status: 404 }))
    await useStore.getState().resolveScan('BX-1')
    expect(useStore.getState().scanPhase).toBe('scanning')
    expect(useStore.getState().toast).toContain('handwritten label')
  })

  it('manual label creates or finds a box, and "record here" locks it as target', async () => {
    mocked.resolveCode.mockResolvedValue({ box: box({ id: 'found' }), created: true })
    await useStore.getState().scanManual(' 7 ')
    expect(mocked.resolveCode).toHaveBeenCalledWith({ label: '7', create: true })
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
    expect(s.toast).toContain('typing')
    expect(mocked.interpret).not.toHaveBeenCalled()
  })
})

describe('display helpers', () => {
  it('plainText strips the markdown the answer model leaks despite the prompt', () => {
    expect(plainText('The drill is in **Box 4**, location `storage room floor`.')).toBe('The drill is in Box 4, location storage room floor.')
    expect(plainText('**a** and **b**')).toBe('a and b')
    expect(plainText('no markup 2*3')).toBe('no markup 2*3')
  })

  it('fmtItems', () => {
    expect(fmtItems([{ name: 'headlamp', qty_text: '×2' }, { name: 'tent', qty_text: '×1' }])).toBe('headlamp ×2 · tent ×1')
  })

  it('fmtTime buckets in both languages', () => {
    const now = Date.now()
    expect(fmtTime(new Date(now - 10_000).toISOString())).toBe('just now')
    expect(fmtTime(new Date(now - 5 * 60_000).toISOString())).toBe('5 min ago')
    expect(fmtTime('2000-03-04T12:00:00')).toBe('Mar 4, 2000') // local-time ISO string, timezone-independent
    expect(fmtTime(new Date(now - 10_000).toISOString(), 'zh')).toBe('刚刚')
    expect(fmtTime(new Date(now - 5 * 60_000).toISOString(), 'zh')).toBe('5 分钟前')
    expect(fmtTime('2000-03-04T12:00:00', 'zh')).toBe('2000年3月4日')
  })

  it('isNewBox is a 24h window', () => {
    expect(isNewBox(box({ created_at: new Date(Date.now() - 3_600_000).toISOString() }))).toBe(true)
    expect(isNewBox(box({ created_at: new Date(Date.now() - 2 * 86_400_000).toISOString() }))).toBe(false)
  })

  it('distText uses haversine and degrades without a position', () => {
    expect(distText(null, 1, 2)).toBeNull()
    expect(distText({ lat: 1, lng: 2 }, null, 2)).toBeNull()
    expect(distText({ lat: 31.23, lng: 121.47 }, 31.23, 121.47)).toBe('nearby')
    expect(distText({ lat: 31.23, lng: 121.47 }, 31.25, 121.47)).toBe('2.2 km away')
    expect(distText({ lat: 31.23, lng: 121.47 }, 39.9, 116.4)).toMatch(/^106\d km away$/) // Shanghai → Beijing
    expect(distText({ lat: 31.23, lng: 121.47 }, 31.25, 121.47, 'zh')).toBe('距你 2.2 km')
  })
})
