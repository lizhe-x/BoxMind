import { useState } from 'react'
import { GradButton, ThinkingDots } from './common'
import { CheckIcon, PencilIcon, PinIcon, SparkleIcon } from './Icons'
import { boxNameFor, makeT } from '../i18n'
import { useStore } from '../store'
import { KRAFT, T } from '../theme'
import type { ItemDraft } from '../types'

function ItemRows({ items, pad = '11px 2px' }: { items: ItemDraft[]; pad?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {items.map((it, i) => (
        <div
          key={i}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: pad,
            borderBottom: i < items.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
          }}
        >
          <div style={{ fontSize: 15, color: T.text }}>{it.name}</div>
          <div style={{ fontSize: 13.5, color: T.textSub, fontFamily: T.fontNum }}>{it.qty_text}</div>
        </div>
      ))}
    </div>
  )
}

export function EntryOverlay() {
  const lang = useStore((s) => s.lang)
  const t = makeT(lang)
  const phase = useStore((s) => s.entryPhase)
  const rawText = useStore((s) => s.rawText)
  const liveTranscript = useStore((s) => s.liveTranscript)
  const parsed = useStore((s) => s.parsed)
  const targetBox = useStore((s) => s.targetBox)
  const doneInfo = useStore((s) => s.doneInfo)
  const busy = useStore((s) => s.entryBusy)
  const boxes = useStore((s) => s.boxes)

  const setRawText = useStore((s) => s.setRawText)
  const toEdit = useStore((s) => s.toEdit)
  const cancelEdit = useStore((s) => s.cancelEdit)
  const reparse = useStore((s) => s.reparse)
  const confirmEntry = useStore((s) => s.confirmEntry)
  const pickNewBox = useStore((s) => s.pickNewBox)
  const pickExisting = useStore((s) => s.pickExisting)
  const closeEntry = useStore((s) => s.closeEntry)
  const openBox = useStore((s) => s.openBox)

  const [draft, setDraft] = useState(rawText)

  const items = parsed?.items ?? []
  const matchedBox = targetBox || parsed?.box || null
  const boxLabel = matchedBox?.label || parsed?.box_label || ''
  const boxName = matchedBox?.name || (boxLabel ? boxNameFor(boxLabel, lang) : t('new_box_generic'))
  const isNewTarget = !matchedBox
  const badgeColors: [string, string] = matchedBox
    ? [matchedBox.color_a, matchedBox.color_b]
    : KRAFT[0]
  const recent = boxes.slice(0, 3)

  return (
    <div
      style={{
        position: 'absolute', inset: 0, zIndex: 50, background: 'rgba(6,8,14,0.92)',
        backdropFilter: 'blur(20px)', display: 'flex', flexDirection: 'column',
        padding: '70px 24px 50px', boxSizing: 'border-box',
      }}
    >
      {/* 关闭 */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <div
          onClick={closeEntry}
          style={{
            width: 34, height: 34, borderRadius: '50%', background: 'rgba(255,255,255,0.07)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
            fontSize: 14, color: T.textSub,
          }}
        >
          ✕
        </div>
      </div>

      {/* ── 语音录音中 ── */}
      {phase === 'recording' && (
        <>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 30 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(255,90,90,0.1)', border: '1px solid rgba(255,90,90,0.3)', borderRadius: 999, padding: '7px 16px' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: T.red, display: 'inline-block', animation: 'bm-blink 1s infinite' }} />
              <span style={{ fontSize: 13, color: T.red2 }}>{t('listening')}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, height: 44 }}>
              {[
                { h: 16, bg: '#7C9BFF', d: 0 },
                { h: 34, bg: '#93A8FF', d: 0.12 },
                { h: 24, bg: '#A78BFA', d: 0.24 },
                { h: 40, bg: '#8B5CF6', d: 0.36 },
                { h: 28, bg: '#A78BFA', d: 0.48 },
                { h: 36, bg: '#93A8FF', d: 0.6 },
                { h: 18, bg: '#7C9BFF', d: 0.72 },
              ].map((w, i) => (
                <div key={i} style={{ width: 5, height: w.h, borderRadius: 99, background: w.bg, animation: `bm-wave 0.9s ease-in-out ${w.d}s infinite` }} />
              ))}
            </div>
            <div style={{ fontSize: 20, lineHeight: 1.8, textAlign: 'center', minHeight: 120, textWrap: 'pretty', color: T.text }}>
              {liveTranscript || <span style={{ color: T.textWeak }}>{t('rec_ph')}</span>}
              <span style={{ display: 'inline-block', width: 2.5, height: 20, background: T.blue, marginLeft: 3, verticalAlign: 'middle', animation: 'bm-blink 0.8s infinite' }} />
            </div>
          </div>
          <div style={{ textAlign: 'center', fontSize: 13, color: T.textWeak }}>{t('rec_release')}</div>
        </>
      )}


      {/* ── AI 整理中 ── */}
      {phase === 'parsing' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 26 }}>
          <div style={{ fontSize: 16, lineHeight: 1.8, textAlign: 'center', color: T.textWeak, padding: '0 8px' }}>
            “{rawText}”
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: T.grad, display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'bm-glow 1.1s infinite' }}>
              <SparkleIcon size={14} />
            </div>
            <span style={{ fontSize: 16, fontWeight: 500, color: T.blue2 }}>{t('parsing')}</span>
            <ThinkingDots size={5} />
          </div>
        </div>
      )}

      {/* ── 确认入库 ── */}
      {phase === 'confirm' && parsed && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 14, overflow: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <span style={{ display: 'inline-flex', width: 24, height: 24, borderRadius: '50%', background: T.grad, alignItems: 'center', justifyContent: 'center' }}>
              <SparkleIcon size={12} />
            </span>
            <span style={{ fontSize: 16, fontWeight: 600, color: T.text }}>{t('confirm_title')}</span>
          </div>
          <div style={{ background: T.card, border: `1px solid ${T.border8}`, borderRadius: 22, padding: 18, display: 'flex', flexDirection: 'column', gap: 14, animation: 'bm-pop 0.35s ease both' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div
                style={{
                  width: 48, height: 42, borderRadius: 9,
                  background: `linear-gradient(140deg,${badgeColors[0]},${badgeColors[1]})`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  fontFamily: T.fontNum, fontWeight: 700, fontSize: 16, color: T.ink, transform: 'rotate(-2deg)',
                }}
              >
                {boxLabel || '?'}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: T.text }}>{boxName}</div>
                <div style={{ fontSize: 11.5, color: isNewTarget ? T.green : T.textSub }}>
                  {isNewTarget ? t('new_box_auto') : t('existing_append')}
                </div>
              </div>
            </div>
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
              <ItemRows items={items} />
            </div>
            {(parsed.location_text || targetBox?.location_text) && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <PinIcon size={13} />
                <span style={{ fontSize: 13.5, color: 'rgba(235,240,250,0.7)' }}>
                  {parsed.location_text || targetBox?.location_text}
                </span>
              </div>
            )}
          </div>
          <div style={{ fontSize: 12, color: T.textWeak35, lineHeight: 1.6, padding: '0 4px' }}>{t('original', { text: rawText })}</div>
          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <div
              onClick={toEdit}
              style={{
                flex: 1, height: 52, borderRadius: 999, border: '1px solid rgba(255,255,255,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15,
                color: 'rgba(235,240,250,0.7)', cursor: 'pointer',
              }}
            >
              {t('fix')}
            </div>
            <GradButton onClick={confirmEntry} flex={2} style={{ opacity: busy ? 0.6 : 1 }}>
              {busy ? t('saving') : t('confirm_save')}
            </GradButton>
          </div>
        </div>
      )}

      {/* ── 追问:放进哪个箱子 ── */}
      {phase === 'askbox' && parsed && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 14, overflow: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <span style={{ display: 'inline-flex', width: 24, height: 24, borderRadius: '50%', background: T.grad, alignItems: 'center', justifyContent: 'center' }}>
              <SparkleIcon size={12} />
            </span>
            <span style={{ fontSize: 16, fontWeight: 600, color: T.text }}>{t('askbox_title', { n: items.length })}</span>
          </div>
          <div style={{ background: T.card, border: `1px solid ${T.border8}`, borderRadius: 18, padding: '6px 16px', animation: 'bm-pop 0.35s ease both' }}>
            <ItemRows items={items} pad="10px 0" />
          </div>
          <div style={{ fontSize: 12.5, color: T.textWeak }}>{t('askbox_hint')}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            <div
              onClick={pickNewBox}
              style={{
                display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(242,192,120,0.08)',
                border: '1.5px dashed rgba(242,192,120,0.45)', borderRadius: 16, padding: '12px 14px',
                cursor: 'pointer', opacity: busy ? 0.6 : 1,
              }}
            >
              <div
                style={{
                  width: 44, height: 38, borderRadius: 8, background: 'linear-gradient(140deg,#9C7A52,#7A5E3E)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  fontFamily: T.fontNum, fontWeight: 700, fontSize: 14, color: T.ink, transform: 'rotate(-2deg)',
                }}
              >
                {parsed.next_label}
              </div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <div style={{ fontSize: 14.5, fontWeight: 600, color: T.amber }}>{t('new_box_n', { name: boxNameFor(parsed.next_label, lang) })}</div>
                <div style={{ fontSize: 11.5, color: T.textWeak }}>{t('new_box_desc')}</div>
              </div>
              <div style={{ fontSize: 10.5, color: T.amber, background: 'rgba(242,192,120,0.12)', borderRadius: 999, padding: '3px 9px' }}>{t('recommended')}</div>
            </div>
            {recent.map((p) => (
              <div
                key={p.id}
                onClick={() => pickExisting(p.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12, background: T.card,
                  border: `1px solid ${T.border8}`, borderRadius: 16, padding: '11px 14px',
                  cursor: 'pointer', opacity: busy ? 0.6 : 1,
                }}
              >
                <div
                  style={{
                    width: 44, height: 38, borderRadius: 8,
                    background: `linear-gradient(140deg,${p.color_a},${p.color_b})`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    fontFamily: T.fontNum, fontWeight: 700, fontSize: 14, color: T.ink, transform: 'rotate(-2deg)',
                  }}
                >
                  {p.label}
                </div>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                  <div style={{ fontSize: 14.5, fontWeight: 600, color: T.text }}>{p.name}</div>
                  <div style={{ fontSize: 11.5, color: T.textWeak, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {p.location_text || t('location_pending')}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div onClick={closeEntry} style={{ alignSelf: 'center', fontSize: 13, color: T.textWeak, cursor: 'pointer', padding: '2px 10px' }}>
            {t('cancel')}
          </div>
        </div>
      )}

      {/* ── 修正文本 ── */}
      {phase === 'edit' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 14 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: T.text }}>{t('edit_title')}</div>
          <textarea
            defaultValue={rawText}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            style={{
              minHeight: 130, background: T.card, border: '1px solid rgba(124,140,255,0.35)',
              borderRadius: 18, padding: '14px 16px', fontSize: 16, lineHeight: 1.7, color: T.text,
              fontFamily: T.font, resize: 'none', boxSizing: 'border-box', width: '100%',
            }}
          />
          <div style={{ display: 'flex', gap: 10 }}>
            <div
              onClick={cancelEdit}
              style={{
                flex: 1, height: 52, borderRadius: 999, border: '1px solid rgba(255,255,255,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15,
                color: 'rgba(235,240,250,0.7)', cursor: 'pointer',
              }}
            >
              {t('cancel')}
            </div>
            <GradButton
              onClick={() => {
                setRawText(draft || rawText)
                void reparse()
              }}
              flex={2}
            >
              {t('reparse')}
            </GradButton>
          </div>
        </div>
      )}

      {/* ── 完成 ── */}
      {phase === 'done' && doneInfo && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
          <div
            style={{
              width: 86, height: 86, borderRadius: '50%', background: T.gradGreen, display: 'flex',
              alignItems: 'center', justifyContent: 'center', boxShadow: '0 16px 50px rgba(16,185,129,0.4)',
              animation: 'bm-pop 0.4s ease both',
            }}
          >
            <CheckIcon size={40} color="#fff" width={3} />
          </div>
          <div style={{ fontSize: 21, fontWeight: 700, color: T.text, textAlign: 'center' }}>{doneInfo.title}</div>
          <div style={{ fontSize: 13.5, lineHeight: 1.9, color: T.textSub55, textAlign: 'center' }}>
            {doneInfo.line1}
            <br />
            {doneInfo.line2}
          </div>
          {doneInfo.markerTip && (
            <div
              style={{
                display: 'flex', alignItems: 'center', gap: 11, background: 'rgba(242,192,120,0.08)',
                border: '1px solid rgba(242,192,120,0.35)', borderRadius: 16, padding: '13px 15px',
                animation: 'bm-fadeUp 0.4s 0.2s ease both',
              }}
            >
              <PencilIcon />
              <div style={{ fontSize: 13, lineHeight: 1.6, color: T.amber, textWrap: 'pretty' }}>{doneInfo.markerTip}</div>
            </div>
          )}
          <div style={{ display: 'flex', gap: 10, width: '100%', marginTop: 10 }}>
            <div
              onClick={() => {
                openBox(doneInfo.boxId)
                closeEntry()
              }}
              style={{
                flex: 1, height: 52, borderRadius: 999, border: '1px solid rgba(124,140,255,0.4)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15,
                color: T.blue2, cursor: 'pointer',
              }}
            >
              {t('view_box')}
            </div>
            <GradButton onClick={closeEntry} flex={1}>
              {t('done')}
            </GradButton>
          </div>
        </div>
      )}
    </div>
  )
}
