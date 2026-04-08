import { useState, useEffect } from 'react'
import { useArcadeStore } from '../store'
import { pickRandom } from '../data/dialogue'
import LunaFace from './LunaFace'

export default function WakeSequence({ reverse = false }) {
  const [phase, setPhase] = useState(0) // 0=start, 1=face visible, 2=text typing, 3=done
  const [typedText, setTypedText] = useState('')
  const [fullText] = useState(() =>
    reverse ? pickRandom('farewell') : pickRandom('greetings')
  )
  const returnToSleep = useArcadeStore((s) => s.returnToSleep)

  // Phase progression
  useEffect(() => {
    const timers = []

    if (reverse) {
      // Farewell sequence: show text, then fade out
      setPhase(2)
      timers.push(setTimeout(() => setPhase(3), 2500))
    } else {
      // Wake sequence: face appears, then text types in
      timers.push(setTimeout(() => setPhase(1), 300))
      timers.push(setTimeout(() => setPhase(2), 800))
      timers.push(setTimeout(() => setPhase(3), 2500))
    }

    return () => timers.forEach(clearTimeout)
  }, [reverse])

  // Typewriter effect for text
  useEffect(() => {
    if (phase < 2) return
    let i = 0
    const interval = setInterval(() => {
      i++
      setTypedText(fullText.slice(0, i))
      if (i >= fullText.length) clearInterval(interval)
    }, 40)
    return () => clearInterval(interval)
  }, [phase, fullText])

  const faceExpression = reverse ? 'sleeping' : (phase >= 1 ? 'happy' : 'sleeping')
  const opacity = reverse
    ? (phase >= 3 ? 'opacity-0' : 'opacity-100')
    : (phase >= 1 ? 'opacity-100' : 'opacity-0')

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-arcade-bg">
      <div className={`transition-opacity duration-700 ${opacity}`}>
        <LunaFace expression={faceExpression} size={120} />
      </div>

      {phase >= 2 && (
        <p className="mt-6 font-pixel text-sm text-arcade-cyan neon-cyan text-center px-8 animate-fade-in">
          {typedText}
          <span className="border-r-2 border-arcade-cyan animate-type-cursor ml-0.5">&nbsp;</span>
        </p>
      )}

      {reverse && (
        <p className="absolute bottom-8 font-pixel text-xs text-arcade-muted opacity-50">
          Goodnight...
        </p>
      )}
    </div>
  )
}
