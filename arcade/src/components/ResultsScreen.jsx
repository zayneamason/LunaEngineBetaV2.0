import { useState, useEffect } from 'react'
import { useArcadeStore } from '../store'
import { pickRandom } from '../data/dialogue'
import useKeyboard from '../hooks/useKeyboard'
import LunaFace from './LunaFace'

const MEDAL_CONFIG = {
  gold:   { label: 'GOLD',   color: 'text-arcade-gold',   glow: 'neon-gold',    border: 'glow-border-gold' },
  silver: { label: 'SILVER', color: 'text-arcade-silver',  glow: '',              border: '' },
  bronze: { label: 'BRONZE', color: 'text-arcade-bronze',  glow: '',              border: '' },
}

export default function ResultsScreen() {
  const lastScore = useArcadeStore((s) => s.lastScore)
  const selectedGame = useArcadeStore((s) => s.selectedGame)
  const setMode = useArcadeStore((s) => s.setMode)
  const launchGame = useArcadeStore((s) => s.launchGame)
  const { onPress } = useKeyboard()

  const score = lastScore?.score ?? 0
  const medal = lastScore?.medal ?? 'bronze'
  const waves = lastScore?.waves ?? 0
  const medalCfg = MEDAL_CONFIG[medal] || MEDAL_CONFIG.bronze

  // Count-up animation
  const [displayScore, setDisplayScore] = useState(0)
  useEffect(() => {
    if (score <= 0) return
    const duration = 2000
    const start = Date.now()
    const tick = () => {
      const elapsed = Date.now() - start
      const progress = Math.min(elapsed / duration, 1)
      // Ease-out curve
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplayScore(Math.floor(eased * score))
      if (progress < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [score])

  // Luna's reaction
  const [reaction] = useState(() => pickRandom(`results_${medal}`))

  // Keyboard controls
  useEffect(() => {
    const unsubs = [
      onPress('left', () => setMode('host')),
      onPress('space', () => setMode('game_select')),
      onPress('right', () => launchGame(selectedGame)),
    ]
    return () => unsubs.forEach((u) => u())
  }, [onPress, setMode, launchGame, selectedGame])

  const expression = medal === 'gold' ? 'excited' : medal === 'silver' ? 'happy' : 'idle'

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-arcade-bg px-6">
      {/* Luna reaction */}
      <LunaFace expression={expression} size={80} />
      <p className="font-body text-sm text-arcade-magenta mt-3 text-center max-w-xs">
        {reaction}
      </p>

      {/* Score */}
      <p className="font-pixel text-3xl text-white mt-6 neon-cyan">
        {displayScore.toLocaleString()}
      </p>

      {/* Medal */}
      <div className={`mt-3 px-6 py-2 rounded-lg border-2 border-arcade-border ${medalCfg.border}`}>
        <p className={`font-pixel text-lg ${medalCfg.color} ${medalCfg.glow}`}>
          {medalCfg.label}
        </p>
      </div>

      {/* Stats */}
      <div className="mt-4 space-y-1 text-center">
        <p className="font-body text-xs text-arcade-muted">
          Waves survived: {waves}
        </p>
      </div>

      {/* Controls */}
      <div className="absolute bottom-6 flex gap-6 font-pixel text-[9px]">
        <span className="text-arcade-muted">&lt; Back to Luna</span>
        <span className="text-arcade-cyan">[SPACE] More Games</span>
        <span className="text-arcade-muted">Play Again &gt;</span>
      </div>
    </div>
  )
}
