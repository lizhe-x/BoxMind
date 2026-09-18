import { useState } from 'react'
import { T } from '../theme'
import { MicIcon, SparkleIcon } from '../components/Icons'
import { makeT } from '../i18n'
import type { Key } from '../i18n'
import { useStore } from '../store'

const OB: { tag: Key; title: Key; desc: Key }[] = [
  { tag: 'ob1_tag', title: 'ob1_title', desc: 'ob1_desc' },
  { tag: 'ob2_tag', title: 'ob2_title', desc: 'ob2_desc' },
  { tag: 'ob3_tag', title: 'ob3_title', desc: 'ob3_desc' },
]

const WAVE = [
  { h: 14, bg: '#7C9BFF', d: 0 },
  { h: 26, bg: '#93A8FF', d: 0.15 },
  { h: 20, bg: '#A78BFA', d: 0.3 },
  { h: 28, bg: '#93A8FF', d: 0.45 },
  { h: 12, bg: '#7C9BFF', d: 0.6 },
]

export function Onboarding() {
  const lang = useStore((s) => s.lang)
  const t = makeT(lang)
  const [slide, setSlide] = useState(0)
  const go = useStore((s) => s.go)
  const ob = OB[slide]

  const finish = () => {
    localStorage.setItem('bm_onboarded', '1')
    go('home')
  }
  const next = () => (slide >= 2 ? finish() : setSlide(slide + 1))

  return (
    <div
      style={{
        height: '100%', display: 'flex', flexDirection: 'column',
        padding: '84px 28px 44px', position: 'relative', zIndex: 1, boxSizing: 'border-box',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <div onClick={finish} style={{ fontSize: 14, color: T.textWeak, cursor: 'pointer', padding: '6px 10px' }}>
          {t('ob_skip')}
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        {slide === 0 && (
          <div
            style={{
              width: 172, height: 128, borderRadius: 14,
              background: 'linear-gradient(140deg,#9C7A52,#6E5638)', transform: 'rotate(-3deg)',
              position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 24px 50px rgba(0,0,0,0.45)',
            }}
          >
            <div
              style={{
                position: 'absolute', top: -7, left: '50%', transform: 'translateX(-50%) rotate(-2deg)',
                width: 74, height: 18, background: 'rgba(255,255,255,0.28)', borderRadius: 2,
              }}
            />
            <div style={{ fontFamily: T.fontNum, fontSize: 46, fontWeight: 700, color: T.ink, transform: 'rotate(-1deg)' }}>
              {t('label_sample')}
            </div>
          </div>
        )}
        {slide === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22 }}>
            <div
              style={{
                width: 96, height: 96, borderRadius: '50%', background: T.grad,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 16px 50px rgba(99,102,241,0.5)',
              }}
            >
              <MicIcon size={36} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, height: 30 }}>
              {WAVE.map((w, i) => (
                <div
                  key={i}
                  style={{
                    width: 4, height: w.h, borderRadius: 99, background: w.bg,
                    animation: `bm-wave 1s ease-in-out ${w.d}s infinite`,
                  }}
                />
              ))}
            </div>
          </div>
        )}
        {slide === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: 260 }}>
            <div
              style={{
                alignSelf: 'flex-end', background: '#273048', borderRadius: '16px 16px 4px 16px',
                padding: '10px 14px', fontSize: 14, color: T.text,
              }}
            >
              {t('ob_demo_q')}
            </div>
            <div
              style={{
                alignSelf: 'flex-start', background: T.card2, border: `1px solid ${T.borderHi}`,
                borderRadius: '4px 16px 16px 16px', padding: '10px 14px', fontSize: 14,
                display: 'flex', alignItems: 'center', gap: 8, color: T.text,
              }}
            >
              <span
                style={{
                  display: 'inline-flex', width: 18, height: 18, borderRadius: '50%',
                  background: T.grad, alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}
              >
                <SparkleIcon size={10} />
              </span>
              <span>{t('ob_demo_a')}</span>
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div
          style={{
            alignSelf: 'flex-start', fontSize: 12, letterSpacing: 2, color: T.blue,
            border: '1px solid rgba(124,140,255,0.35)', borderRadius: 999, padding: '5px 12px',
            fontFamily: T.fontNum,
          }}
        >
          {t(ob.tag)}
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, lineHeight: 1.35, textWrap: 'pretty', color: T.text }}>
          {t(ob.title)}
        </div>
        <div style={{ fontSize: 15, lineHeight: 1.75, color: T.textSub55, textWrap: 'pretty' }}>{t(ob.desc)}</div>
        <div style={{ display: 'flex', gap: 7, marginTop: 6 }}>
          {OB.map((_, i) => (
            <div
              key={i}
              style={{
                width: i === slide ? 22 : 6, height: 6, borderRadius: 99,
                background: i === slide ? T.blue : 'rgba(255,255,255,0.18)', transition: 'all 0.3s',
              }}
            />
          ))}
        </div>
        <div
          className="bm-press98"
          onClick={next}
          style={{
            marginTop: 10, height: 56, borderRadius: 999, background: T.grad,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 17, fontWeight: 600, cursor: 'pointer', color: T.text,
            boxShadow: '0 10px 36px rgba(99,102,241,0.4)',
          }}
        >
          {slide >= 2 ? t('ob_start') : t('ob_continue')}
        </div>
      </div>
    </div>
  )
}
