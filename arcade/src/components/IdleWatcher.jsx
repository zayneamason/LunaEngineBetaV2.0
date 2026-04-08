import { useArcadeStore } from '../store'
import useIdleTimer from '../hooks/useIdleTimer'

const TIMEOUTS = {
  host:        60_000,
  game_select: 30_000,
  results:     30_000,
}

export default function IdleWatcher() {
  const mode = useArcadeStore((s) => s.mode)
  const returnToSleep = useArcadeStore((s) => s.returnToSleep)

  const timeout = TIMEOUTS[mode] || 0

  useIdleTimer(timeout, () => {
    const currentMode = useArcadeStore.getState().mode
    if (TIMEOUTS[currentMode]) {
      returnToSleep()
    }
  })

  return null
}
