import type { CSSProperties, ReactNode } from 'react'
import { T } from '../theme'
import { BoxTabIcon, GearTabIcon, HomeTabIcon, SparkleIcon } from './Icons'
import { useStore } from '../store'

/** 牛皮纸渐变 + 旋转手写编号徽章 */
export function BoxBadge({
  label, colorA, colorB, w = 44, h = 38, fontSize = 14, radius = 8,
}: {
  label: string; colorA: string; colorB: string
  w?: number; h?: number; fontSize?: number; radius?: number
}) {
  return (
    <div
      style={{
        width: w, height: h, borderRadius: radius,
        background: `linear-gradient(140deg,${colorA},${colorB})`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        fontFamily: T.fontNum, fontWeight: 700, fontSize, color: T.ink, transform: 'rotate(-2deg)',
      }}
    >
      {label}
    </div>
  )
}

export function AiAvatar({ size = 26, glow = false }: { size?: number; glow?: boolean }) {
  return (
    <div
      style={{
        width: size, height: size, borderRadius: '50%', background: T.grad,
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        animation: glow ? 'bm-glow 1.2s infinite' : undefined,
      }}
    >
      <SparkleIcon size={Math.round(size / 2)} />
    </div>
  )
}

export function GradButton({
  children, onClick, height = 52, flex, style,
}: {
  children: ReactNode; onClick?: () => void; height?: number; flex?: number; style?: CSSProperties
}) {
  return (
    <div
      className="bm-press98"
      onClick={onClick}
      style={{
        height, flex, borderRadius: 999, background: T.grad,
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9,
        fontSize: 15, fontWeight: 600, cursor: 'pointer', boxShadow: T.btnShadow, color: T.text,
        ...style,
      }}
    >
      {children}
    </div>
  )
}

export function ThinkingDots({ size = 6 }: { size?: number }) {
  return (
    <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
      {[0, 0.15, 0.3].map((d) => (
        <div
          key={d}
          style={{
            width: size, height: size, borderRadius: '50%', background: T.blue,
            animation: `bm-dot 1.2s ${d}s infinite`,
          }}
        />
      ))}
    </div>
  )
}

export function Cursor({ h = 15 }: { h?: number }) {
  return (
    <span
      style={{
        display: 'inline-block', width: 2, height: h, background: T.blue,
        marginLeft: 2, verticalAlign: 'middle', animation: 'bm-blink 0.8s infinite',
      }}
    />
  )
}

export function TabBar() {
  const screen = useStore((s) => s.screen)
  const go = useStore((s) => s.go)
  const on = '#C3CEFF'
  const off = 'rgba(235,240,250,0.4)'
  const tabs = [
    { key: 'home' as const, label: '首页', Icon: HomeTabIcon },
    { key: 'boxes' as const, label: '箱子', Icon: BoxTabIcon },
    { key: 'settings' as const, label: '我的', Icon: GearTabIcon },
  ]
  return (
    <div
      style={{
        position: 'absolute', left: 0, right: 0, bottom: 0, zIndex: 40, height: 82,
        paddingBottom: 18, boxSizing: 'border-box', background: 'rgba(9,12,19,0.82)',
        backdropFilter: 'blur(18px)', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex',
      }}
    >
      {tabs.map(({ key, label, Icon }) => {
        const c = screen === key ? on : off
        return (
          <div
            key={key}
            onClick={() => go(key)}
            style={{
              flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', gap: 4, cursor: 'pointer',
            }}
          >
            <Icon color={c} />
            <span style={{ fontSize: 10.5, color: c }}>{label}</span>
          </div>
        )
      })}
    </div>
  )
}

export function Toast() {
  const toast = useStore((s) => s.toast)
  if (!toast) return null
  return (
    <div
      style={{
        position: 'absolute', top: 66, left: 0, right: 0, display: 'flex',
        justifyContent: 'center', zIndex: 80, pointerEvents: 'none',
      }}
    >
      <div
        style={{
          background: 'rgba(22,28,44,0.95)', border: `1px solid rgba(124,140,255,0.3)`,
          borderRadius: 999, padding: '10px 18px', fontSize: 13, color: T.text,
          boxShadow: '0 10px 34px rgba(0,0,0,0.5)', animation: 'bm-pop 0.25s ease both',
          maxWidth: 320, textAlign: 'center',
        }}
      >
        {toast}
      </div>
    </div>
  )
}
