import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { api } from '../api'
import { compressImage } from '../image'
import { BackIcon, MicIcon, PinIcon, SpeakerIcon, SparkleIcon } from '../components/Icons'
import { makeT } from '../i18n'
import type { Lang } from '../i18n'
import { distText, fmtTime, isNewBox, useStore } from '../store'
import { T } from '../theme'

function AudioRow({ url, index, lang }: { url: string; index: number; lang: Lang }) {
  const t = makeT(lang)
  const [playing, setPlaying] = useState(false)
  const ref = useRef<HTMLAudioElement | null>(null)
  const toggle = () => {
    if (!ref.current) {
      ref.current = new Audio(url)
      ref.current.onended = () => setPlaying(false)
    }
    if (playing) {
      ref.current.pause()
      setPlaying(false)
    } else {
      void ref.current.play().catch(() => setPlaying(false))
      setPlaying(true)
    }
  }
  return (
    <div
      onClick={toggle}
      style={{ display: 'flex', alignItems: 'center', gap: 10, background: T.card, border: `1px solid ${T.border}`, borderRadius: 14, padding: '11px 14px', cursor: 'pointer' }}
    >
      <div style={{ width: 34, height: 34, borderRadius: '50%', background: T.grad, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <SpeakerIcon size={16} color="#fff" />
      </div>
      <div style={{ fontSize: 14, color: T.text }}>{playing ? t('playing') : t('voice_note_n', { n: index + 1 })}</div>
    </div>
  )
}

export function BoxDetail() {
  const lang = useStore((s) => s.lang)
  const t = makeT(lang)
  const boxes = useStore((s) => s.boxes)
  const activeBoxId = useStore((s) => s.activeBoxId)
  const userPos = useStore((s) => s.userPos)
  const backFromDetail = useStore((s) => s.backFromDetail)
  const setTargetBox = useStore((s) => s.setTargetBox)
  const go = useStore((s) => s.go)
  const addBoxPhoto = useStore((s) => s.addBoxPhoto)
  const setBoxCover = useStore((s) => s.setBoxCover)
  const addBoxItem = useStore((s) => s.addBoxItem)
  const updateBoxItem = useStore((s) => s.updateBoxItem)
  const deleteBoxItem = useStore((s) => s.deleteBoxItem)
  const [newItem, setNewItem] = useState('')

  const b = boxes.find((x) => x.id === activeBoxId)
  if (!b) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.textSub }}>
        {t('box_missing')}
      </div>
    )
  }

  const isNew = isNewBox(b)
  const dist = distText(userPos, b.gps_lat, b.gps_lng, lang)
  const hasGps = b.gps_lat != null
  const cover = b.photo_url || b.photos[0]

  const onAddPhotos = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || !files.length) return
    let setAsCover = !b.photo_url // 第一张且原本无封面 → 设为封面
    for (const f of Array.from(files)) {
      const blob = await compressImage(f) // 上传前压缩(最长边 1600 / JPEG 0.82)
      await addBoxPhoto(b.id, blob, setAsCover)
      setAsCover = false
    }
    e.target.value = ''
  }

  const doAddItem = () => {
    const v = newItem.trim()
    if (!v) return
    setNewItem('')
    void addBoxItem(b.id, v)
  }

  const recordHere = () => {
    setTargetBox(b)
    go('home')
  }

  return (
    <div style={{ height: '100%', overflow: 'auto', position: 'relative', zIndex: 1, boxSizing: 'border-box' }}>
      {/* 封面 */}
      <div
        style={{
          height: 240,
          background: `linear-gradient(140deg,${b.color_a},${b.color_b})`,
          ...(cover
            ? { backgroundImage: `url(${api.mediaUrl(cover)})`, backgroundSize: 'cover', backgroundPosition: 'center' }
            : {}),
          position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        {!cover && (
          <>
            <div
              style={{
                position: 'absolute', top: 30, left: '50%', transform: 'translateX(-50%) rotate(-2deg)',
                width: 110, height: 24, background: 'rgba(255,255,255,0.22)', borderRadius: 2,
              }}
            />
            <div
              style={{
                fontFamily: T.fontNum, fontSize: 54, fontWeight: 700,
                color: 'rgba(43,31,18,0.85)', transform: 'rotate(-2deg)', marginTop: 14,
              }}
            >
              {b.label}
            </div>
          </>
        )}
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 80, background: 'linear-gradient(transparent,#0A0D15)' }} />
        <div
          onClick={backFromDetail}
          style={{
            position: 'absolute', top: 64, left: 16, width: 38, height: 38, borderRadius: '50%',
            background: 'rgba(10,13,21,0.45)', backdropFilter: 'blur(10px)', display: 'flex',
            alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          }}
        >
          <BackIcon color="#fff" />
        </div>
        <div
          style={{
            position: 'absolute', top: 64, right: 16, fontSize: 11, color: 'rgba(255,255,255,0.75)',
            background: 'rgba(10,13,21,0.45)', backdropFilter: 'blur(10px)', borderRadius: 999, padding: '8px 12px',
          }}
        >
          {cover ? t('cover_photo') : t('cover_placeholder')}
        </div>
      </div>

      <div style={{ padding: '0 20px 60px', marginTop: -12, position: 'relative', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* 标题 + 徽章 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: T.text }}>{b.name}</div>
            {isNew && (
              <div style={{ background: 'rgba(124,255,178,0.12)', color: T.green, fontSize: 11, fontWeight: 600, borderRadius: 999, padding: '4px 10px' }}>
                {t('new_box_badge')}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(242,192,120,0.1)', border: '1px solid rgba(242,192,120,0.3)', borderRadius: 999, padding: '6px 12px', fontSize: 12, color: T.amber }}>
              {t('handwritten', { label: b.label })}
            </div>
            {b.barcode && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(124,140,255,0.1)', border: '1px solid rgba(124,140,255,0.3)', borderRadius: 999, padding: '6px 12px', fontSize: 12, color: T.blue2 }}>
                {b.barcode}
              </div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.09)', borderRadius: 999, padding: '6px 12px', fontSize: 12, color: T.textSub }}>
              {t('updated_at', { time: fmtTime(b.updated_at, lang) })}
            </div>
          </div>
        </div>

        {/* 位置卡 */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 20, overflow: 'hidden' }}>
          <div
            style={{
              height: 106, position: 'relative', background: '#0D1119',
              backgroundImage:
                'repeating-linear-gradient(0deg,rgba(255,255,255,0.035) 0,rgba(255,255,255,0.035) 1px,transparent 1px,transparent 22px),' +
                'repeating-linear-gradient(90deg,rgba(255,255,255,0.035) 0,rgba(255,255,255,0.035) 1px,transparent 1px,transparent 22px),' +
                'linear-gradient(115deg,transparent 44%,rgba(124,140,255,0.1) 44%,rgba(124,140,255,0.1) 56%,transparent 56%)',
            }}
          >
            <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', width: 36, height: 36, borderRadius: '50%', border: '1px solid rgba(124,140,255,0.5)', animation: 'bm-pulse 2s ease-out infinite' }} />
            <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', width: 13, height: 13, borderRadius: '50%', background: T.grad, boxShadow: '0 0 14px rgba(99,102,241,0.8)' }} />
            {dist && (
              <div style={{ position: 'absolute', top: 10, right: 10, background: 'rgba(10,13,21,0.7)', backdropFilter: 'blur(8px)', borderRadius: 999, padding: '5px 11px', fontSize: 11, color: T.blue2, fontFamily: T.fontNum }}>
                {dist}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '13px 15px' }}>
            <PinIcon size={14} />
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div style={{ fontSize: 14, fontWeight: 500, color: T.text }}>{b.location_text || t('location_pending')}</div>
              <div style={{ fontSize: 11.5, color: T.textWeak }}>
                {hasGps ? t('gps_recorded') : t('gps_none')}
              </div>
            </div>
          </div>
        </div>

        {/* 物品 */}
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: 2 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: T.text }}>{t('items_title')}</div>
          <div style={{ fontSize: 12.5, color: T.textWeak }}>{t('items_count', { n: b.items.length })}</div>
        </div>
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 20, overflow: 'hidden', display: 'flex', flexDirection: 'column', marginTop: -6 }}>
          {b.items.map((it) => (
            <div
              key={it.id}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px 6px 16px',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
              }}
            >
              <input
                defaultValue={it.name}
                onBlur={(e) => {
                  const v = e.target.value.trim()
                  if (v && v !== it.name) updateBoxItem(b.id, it.id, { name: v })
                  else if (!v) e.target.value = it.name
                }}
                style={{ flex: 1, minWidth: 0, fontSize: 15, color: T.text, background: 'transparent', border: 'none', fontFamily: T.font, padding: '8px 0' }}
              />
              <input
                defaultValue={it.qty_text}
                onBlur={(e) => {
                  if (e.target.value !== it.qty_text) updateBoxItem(b.id, it.id, { qty_text: e.target.value })
                }}
                style={{ width: 64, fontSize: 13, color: T.textSub, fontFamily: T.fontNum, background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.border8}`, borderRadius: 8, padding: '6px 8px', textAlign: 'center', boxSizing: 'border-box' }}
              />
              <div
                onClick={() => deleteBoxItem(b.id, it.id)}
                style={{ width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.textWeak, cursor: 'pointer', fontSize: 14, flexShrink: 0 }}
              >
                ✕
              </div>
            </div>
          ))}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px 8px 16px' }}>
            <span style={{ fontSize: 17, color: T.blue, width: 16, textAlign: 'center', flexShrink: 0 }}>+</span>
            <input
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') doAddItem()
              }}
              placeholder={t('add_item_ph')}
              style={{ flex: 1, minWidth: 0, fontSize: 15, color: T.text, background: 'transparent', border: 'none', fontFamily: T.font, padding: '8px 0' }}
            />
            {newItem.trim() && (
              <div onClick={doAddItem} style={{ fontSize: 13, color: T.blue2, cursor: 'pointer', padding: '4px 8px', flexShrink: 0 }}>{t('add')}</div>
            )}
          </div>
        </div>

        {(b.source === 'text' || b.source === 'voice') && b.items.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: T.textWeak, marginTop: -4 }}>
            <span style={{ display: 'inline-flex', width: 16, height: 16, borderRadius: '50%', background: T.grad, alignItems: 'center', justifyContent: 'center' }}>
              <SparkleIcon size={9} />
            </span>
            {t('from_source', { source: t(b.source === 'voice' ? 'source_voice' : 'source_text') })}
          </div>
        )}

        {/* 箱子照片:添加 + 点选设为封面 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: T.text }}>{t('photos_title')}</div>
            {b.photos.length > 0 && <div style={{ fontSize: 12, color: T.textWeak }}>{t('tap_cover')}</div>}
          </div>
          <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
            {b.photos.map((p, i) => {
              const isCover = p === b.photo_url
              return (
                <div key={i} onClick={() => setBoxCover(b.id, p)} style={{ position: 'relative', flexShrink: 0, cursor: 'pointer' }}>
                  <img
                    src={api.mediaUrl(p)}
                    alt=""
                    style={{ width: 92, height: 92, borderRadius: 12, objectFit: 'cover', display: 'block', border: `2px solid ${isCover ? T.blue : T.border}` }}
                  />
                  {isCover && (
                    <div style={{ position: 'absolute', left: 5, bottom: 5, background: T.grad, color: '#fff', fontSize: 10, fontWeight: 600, borderRadius: 6, padding: '2px 6px' }}>
                      {t('cover_badge')}
                    </div>
                  )}
                </div>
              )
            })}
            <label
              style={{ width: 92, height: 92, borderRadius: 12, border: '1.5px dashed rgba(124,140,255,0.4)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3, flexShrink: 0, cursor: 'pointer', color: T.blue }}
            >
              <span style={{ fontSize: 22, fontWeight: 300 }}>+</span>
              <span style={{ fontSize: 11 }}>{t('add_photo')}</span>
              <input type="file" accept="image/*" multiple style={{ display: 'none' }} onChange={onAddPhotos} />
            </label>
          </div>
        </div>

        {b.audios.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: T.text }}>{t('voice_notes')}</div>
            {b.audios.map((a, i) => (
              <AudioRow key={i} url={api.mediaUrl(a)} index={i} lang={lang} />
            ))}
          </div>
        )}

        <div
          className="bm-press98"
          onClick={recordHere}
          style={{
            height: 54, borderRadius: 999, background: T.grad, display: 'flex', alignItems: 'center',
            justifyContent: 'center', gap: 9, fontSize: 16, fontWeight: 600, cursor: 'pointer',
            boxShadow: '0 10px 30px rgba(99,102,241,0.35)', marginTop: 4, color: T.text,
          }}
        >
          <MicIcon size={18} />
          {t('record_here')}
        </div>
      </div>
    </div>
  )
}
