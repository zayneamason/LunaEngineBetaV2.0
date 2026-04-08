import { useEffect, useRef, useState } from 'react'
import { useArcadeStore } from '../store'
import LunaFace from './LunaFace'

export default function GameEmbed() {
  const selectedGame = useArcadeStore((s) => s.selectedGame)
  const pollStatus = useArcadeStore((s) => s.pollStatus)
  const fetchLastScore = useArcadeStore((s) => s.fetchLastScore)
  const stopGame = useArcadeStore((s) => s.stopGame)

  const [status, setStatus] = useState('launching') // launching | running | finishing
  const pollRef = useRef(null)
  const hasLaunched = useRef(false)

  // Start polling once the game is launched
  useEffect(() => {
    // Small delay to let the subprocess start
    const startDelay = setTimeout(() => {
      hasLaunched.current = true
      setStatus('running')

      pollRef.current = setInterval(async () => {
        const running = await pollStatus()
        if (!running && hasLaunched.current) {
          clearInterval(pollRef.current)
          setStatus('finishing')
          // Small delay for score file to be flushed to disk
          setTimeout(() => fetchLastScore(), 500)
        }
      }, 1500)
    }, 2000)

    return () => {
      clearTimeout(startDelay)
      clearInterval(pollRef.current)
    }
  }, [pollStatus, fetchLastScore])

  // ESC / long-press SPACE to force quit (fallback)
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') {
        clearInterval(pollRef.current)
        stopGame()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [stopGame])

  const dots = '.'.repeat((Math.floor(Date.now() / 500) % 3) + 1)

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-black">
      <LunaFace expression="excited" size={64} />

      <p className="font-pixel text-sm text-arcade-cyan neon-cyan mt-6">
        {status === 'launching' && `LAUNCHING${dots}`}
        {status === 'running' && 'GAME IN PROGRESS'}
        {status === 'finishing' && 'CALCULATING SCORE...'}
      </p>

      <p className="font-body text-xs text-arcade-muted mt-3">
        {selectedGame || 'Unknown game'}
      </p>

      {status === 'running' && (
        <p className="absolute bottom-6 font-pixel text-[8px] text-arcade-muted opacity-40">
          [ESC] Force quit
        </p>
      )}

      {/* Animated loading ring */}
      <div
        className="mt-8 w-8 h-8 border-2 border-arcade-cyan border-t-transparent rounded-full"
        style={{ animation: 'spin 1s linear infinite' }}
      />
    </div>
  )
}
