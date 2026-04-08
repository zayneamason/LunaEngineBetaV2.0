import { useEffect } from 'react'
import { useArcadeStore } from '../store'
import { getGameIntro } from '../data/dialogue'
import useKeyboard from '../hooks/useKeyboard'
import LunaFace from './LunaFace'

export default function GameSelect() {
  const games = useArcadeStore((s) => s.games)
  const highlightIndex = useArcadeStore((s) => s.highlightIndex)
  const setHighlight = useArcadeStore((s) => s.setHighlight)
  const launchGame = useArcadeStore((s) => s.launchGame)
  const setMode = useArcadeStore((s) => s.setMode)
  const { onPress } = useKeyboard()

  // Ensure games are loaded
  const fetchGames = useArcadeStore((s) => s.fetchGames)
  useEffect(() => {
    if (games.length === 0) fetchGames()
  }, [games.length, fetchGames])

  // Keyboard navigation
  useEffect(() => {
    const unsubs = [
      onPress('left', () => {
        setHighlight(Math.max(0, useArcadeStore.getState().highlightIndex - 1))
      }),
      onPress('right', () => {
        const max = useArcadeStore.getState().games.length - 1
        setHighlight(Math.min(max, useArcadeStore.getState().highlightIndex + 1))
      }),
      onPress('space', () => {
        const state = useArcadeStore.getState()
        const game = state.games[state.highlightIndex]
        if (game?.available) {
          launchGame(game.id)
        }
      }),
    ]
    return () => unsubs.forEach((u) => u())
  }, [onPress, setHighlight, launchGame])

  const highlighted = games[highlightIndex]
  const introText = highlighted ? getGameIntro(highlighted.id) : ''

  const ICONS = {
    steve_j_savage: '👾',
    moon_wisdom:    '🌙',
    rocket_raccoon: '🚀',
  }

  return (
    <div className="absolute inset-0 flex flex-col items-center bg-arcade-bg pt-4">
      {/* Luna (small, top corner) */}
      <div className="absolute top-3 right-3">
        <LunaFace expression="happy" size={48} />
      </div>

      <h1 className="font-pixel text-base text-arcade-cyan neon-cyan mt-2">
        SELECT A GAME
      </h1>

      {/* Luna's comment on highlighted game */}
      <p className="font-body text-sm text-arcade-magenta mt-2 px-6 text-center h-10">
        {introText}
      </p>

      {/* Game cards */}
      <div className="flex gap-4 mt-4 px-4">
        {games.map((game, i) => {
          const isHighlighted = i === highlightIndex
          const isAvailable = game.available

          return (
            <div
              key={game.id}
              className={`
                relative flex flex-col items-center justify-center
                w-36 h-44 rounded-xl border-2 transition-all duration-200
                ${isHighlighted
                  ? 'border-arcade-cyan glow-border-cyan scale-105'
                  : 'border-arcade-border scale-95 opacity-60'
                }
                ${!isAvailable ? 'grayscale' : ''}
                bg-arcade-surface
              `}
            >
              {/* Icon */}
              <span className="text-4xl mb-2">
                {ICONS[game.id] || '🎮'}
              </span>

              {/* Title */}
              <p className="font-pixel text-[8px] text-center text-white px-2 leading-tight">
                {game.title}
              </p>

              {/* Description */}
              <p className="font-body text-[10px] text-arcade-muted text-center px-2 mt-1">
                {game.description?.slice(0, 50)}
              </p>

              {/* Coming soon overlay */}
              {!isAvailable && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 rounded-xl">
                  <span className="text-2xl mb-1">🔒</span>
                  <p className="font-pixel text-[7px] text-arcade-muted">COMING SOON</p>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Controls */}
      <div className="absolute bottom-6 flex gap-8 font-pixel text-[9px] text-arcade-muted">
        <span>&lt; PREV</span>
        <span className="text-arcade-cyan">[SPACE] PLAY</span>
        <span>NEXT &gt;</span>
      </div>
    </div>
  )
}
