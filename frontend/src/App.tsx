import { lazy, Suspense, useEffect } from 'react'
import type { ComponentType } from 'react'
import { useStore } from './store'
import { Onboarding } from './screens/Onboarding'
import { Home } from './screens/Home'
import { Boxes } from './screens/Boxes'
import { BoxDetail } from './screens/BoxDetail'
import { Ask } from './screens/Ask'
import { Settings } from './screens/Settings'
import { Login } from './screens/Login'
import { EntryOverlay } from './components/EntryOverlay'
import { TabBar, Toast } from './components/common'
import type { Screen } from './types'

// 摄像头/扫码屏按需加载(扫码依赖较重的 ZXing,只在用到时才下载)
const Camera = lazy(() => import('./screens/Camera').then((m) => ({ default: m.Camera })))
const Scan = lazy(() => import('./screens/Scan').then((m) => ({ default: m.Scan })))

const SCREENS: Record<Screen, ComponentType> = {
  onboarding: Onboarding,
  home: Home,
  boxes: Boxes,
  boxdetail: BoxDetail,
  ask: Ask,
  settings: Settings,
  camera: Camera,
  scan: Scan,
}

const TAB_SCREENS: Screen[] = ['home', 'boxes', 'settings']

export default function App() {
  const screen = useStore((s) => s.screen)
  const init = useStore((s) => s.init)
  const entryPhase = useStore((s) => s.entryPhase)
  const authed = useStore((s) => s.authed)
  const authChecked = useStore((s) => s.authChecked)

  useEffect(() => {
    void init()
  }, [init])

  const Screen = SCREENS[screen] ?? Home

  return (
    <div className="bm-page">
      <div className="bm-frame">
        {!authChecked ? (
          <div style={{ height: '100%' }} />
        ) : !authed ? (
          <>
            <Login />
            <Toast />
          </>
        ) : (
          <>
            <Suspense fallback={<div style={{ height: '100%' }} />}>
              <Screen />
            </Suspense>
            {TAB_SCREENS.includes(screen) && <TabBar />}
            {entryPhase !== 'idle' && <EntryOverlay />}
            <Toast />
          </>
        )}
      </div>
    </div>
  )
}
