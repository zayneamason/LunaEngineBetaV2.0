import { useState, useEffect, useRef } from 'react'
import { useArcadeStore } from '../store'
import { pickRandom } from '../data/dialogue'
import useKeyboard from '../hooks/useKeyboard'
import useVoice from '../hooks/useVoice'
import LunaFace from './LunaFace'

export default function LunaHost() {
  const setMode = useArcadeStore((s) => s.setMode)
  const { onPress } = useKeyboard()
  const { speak } = useVoice()

  const [messages, setMessages] = useState(() => [
    { speaker: 'luna', text: pickRandom('greetings') },
  ])
  const [expression, setExpression] = useState('idle')
  const scrollRef = useRef(null)

  // SPACE → go to game select
  useEffect(() => {
    return onPress('space', () => setMode('game_select'))
  }, [onPress, setMode])

  // Cycle ambient dialogue every 8 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      const line = pickRandom('ambient')
      setMessages((prev) => [...prev.slice(-8), { speaker: 'luna', text: line }])
      speak(line)

      // Randomly change expression
      const exprs = ['idle', 'happy', 'thinking']
      setExpression(exprs[Math.floor(Math.random() * exprs.length)])
    }, 8000)
    return () => clearInterval(interval)
  }, [speak])

  // Auto-scroll conversation
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  return (
    <div className="absolute inset-0 flex flex-col items-center bg-arcade-bg pt-6">
      {/* Luna face */}
      <div className="animate-float">
        <LunaFace expression={expression} size={120} />
      </div>

      <p className="font-pixel text-lg text-arcade-cyan neon-cyan mt-4">LUNA</p>

      {/* Conversation area */}
      <div
        ref={scrollRef}
        className="flex-1 w-full max-w-md overflow-y-auto px-6 mt-4 space-y-3"
        style={{ scrollbarWidth: 'none' }}
      >
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`rounded-lg px-4 py-2 text-sm animate-fade-in ${
              msg.speaker === 'luna'
                ? 'bg-arcade-surface border border-arcade-border text-white'
                : 'bg-arcade-cyan/10 border border-arcade-cyan/30 text-arcade-cyan ml-8'
            }`}
          >
            {msg.text}
          </div>
        ))}
      </div>

      {/* Controls hint */}
      <div className="pb-6 pt-3 text-center">
        <p className="font-pixel text-xs text-arcade-muted">
          [SPACE] Play Games
        </p>
      </div>
    </div>
  )
}
