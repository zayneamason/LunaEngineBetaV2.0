import { useEffect } from 'react'
import { useArcadeStore } from './store'
import SleepScreen from './components/SleepScreen'
import WakeSequence from './components/WakeSequence'
import LunaHost from './components/LunaHost'
import GameSelect from './components/GameSelect'
import GameEmbed from './components/GameEmbed'
import ResultsScreen from './components/ResultsScreen'
import IdleWatcher from './components/IdleWatcher'

const screens = {
  sleep:       SleepScreen,
  waking:      WakeSequence,
  host:        LunaHost,
  game_select: GameSelect,
  playing:     GameEmbed,
  results:     ResultsScreen,
  sleeping:    () => <WakeSequence reverse />,
}

export default function App() {
  const mode = useArcadeStore((s) => s.mode)
  const fetchGames = useArcadeStore((s) => s.fetchGames)

  useEffect(() => { fetchGames() }, [fetchGames])

  const Screen = screens[mode] || SleepScreen

  return (
    <div className="w-screen h-screen bg-arcade-bg overflow-hidden relative font-body">
      <Screen />
      <IdleWatcher />
      <div className="scanline-overlay" />
    </div>
  )
}
