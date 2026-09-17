// 原型内联 SVG 图标(线宽 2,圆头)
export const MicIcon = ({ size = 48 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ pointerEvents: 'none' }}>
    <rect x="9" y="3" width="6" height="11" rx="3" fill="#fff" />
    <path d="M5 11a7 7 0 0 0 14 0" stroke="#fff" strokeWidth="2" strokeLinecap="round" fill="none" />
    <path d="M12 18v3" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
  </svg>
)

export const SparkleIcon = ({ size = 13 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24">
    <path d="M12 2l2.2 5.8L20 10l-5.8 2.2L12 18l-2.2-5.8L4 10l5.8-2.2L12 2z" fill="#fff" />
  </svg>
)

export const ChevronIcon = ({ color = 'rgba(235,240,250,0.3)' }: { color?: string }) => (
  <svg width="7" height="12" viewBox="0 0 8 14">
    <path d="M1 1l6 6-6 6" stroke={color} strokeWidth="2" fill="none" strokeLinecap="round" />
  </svg>
)

export const BackIcon = ({ color = 'rgba(235,240,250,0.7)' }: { color?: string }) => (
  <svg width="10" height="17" viewBox="0 0 12 20" fill="none">
    <path d="M10 2L2 10l8 8" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

export const PinIcon = ({ size = 11 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <path d="M12 21s-7-5.1-7-11a7 7 0 1 1 14 0c0 5.9-7 11-7 11z" stroke="#93A8FF" strokeWidth="2" />
    <circle cx="12" cy="10" r="2.5" fill="#93A8FF" />
  </svg>
)

export const CheckIcon = ({ size = 16, color = '#7CFFB2', width = 2.5 }: { size?: number; color?: string; width?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path d="M5 13l4 4L19 7" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

export const ChatIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
    <path
      d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z"
      stroke="rgba(235,240,250,0.45)" strokeWidth="2" strokeLinejoin="round"
    />
  </svg>
)

export const CameraIcon = ({ size = 22, color = '#93A8FF' }: { size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path
      d="M4 8a2 2 0 0 1 2-2h1.6l1.2-2h6.4l1.2 2H18a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8z"
      stroke={color} strokeWidth="2" strokeLinejoin="round"
    />
    <circle cx="12" cy="12.5" r="3.4" stroke={color} strokeWidth="2" />
  </svg>
)

export const ScanIcon = ({ size = 22, color = '#93A8FF' }: { size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path
      d="M3 8V5a2 2 0 0 1 2-2h3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3"
      stroke={color} strokeWidth="2" strokeLinecap="round"
    />
    <path d="M3 12h18" stroke={color} strokeWidth="2" strokeLinecap="round" />
  </svg>
)

export const SpeakerIcon = ({ size = 15, color = 'rgba(235,240,250,0.55)' }: { size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path d="M4 9v6h4l5 4V5L8 9H4z" stroke={color} strokeWidth="2" strokeLinejoin="round" />
    <path d="M16 9a3.5 3.5 0 0 1 0 6" stroke={color} strokeWidth="2" strokeLinecap="round" />
    <path d="M18.5 6.5a7 7 0 0 1 0 11" stroke={color} strokeWidth="2" strokeLinecap="round" />
  </svg>
)

export const PencilIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <path d="M16.5 3.5l4 4L8 20l-5 1 1-5L16.5 3.5z" stroke="#F2C078" strokeWidth="2" strokeLinejoin="round" />
    <path d="M14 6l4 4" stroke="#F2C078" strokeWidth="2" />
  </svg>
)

export const HomeTabIcon = ({ color }: { color: string }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
    <path
      d="M3 10.5L12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1v-9.5z"
      stroke={color} strokeWidth="2" strokeLinejoin="round"
    />
  </svg>
)

export const BoxTabIcon = ({ color }: { color: string }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
    <path d="M12 2l9 5v10l-9 5-9-5V7l9-5z" stroke={color} strokeWidth="2" strokeLinejoin="round" />
    <path d="M3.5 7.5L12 12l8.5-4.5M12 12v9.5" stroke={color} strokeWidth="2" strokeLinejoin="round" />
  </svg>
)

export const GearTabIcon = ({ color }: { color: string }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
    <circle cx="12" cy="12" r="3.2" stroke={color} strokeWidth="2" />
    <path
      d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.5-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.5 2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.5 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.5-2-1.5c.1-.4.1-.8.1-1.2z"
      stroke={color} strokeWidth="1.6" strokeLinejoin="round"
    />
  </svg>
)
