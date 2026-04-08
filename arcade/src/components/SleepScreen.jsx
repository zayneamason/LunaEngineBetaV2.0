import { useEffect, useMemo } from 'react'
import useKeyboard from '../hooks/useKeyboard'
import { useArcadeStore } from '../store'
import LunaFace from './LunaFace'

function StarField() {
  const stars = useMemo(() => {
    return Array.from({ length: 60 }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      top: Math.random() * 100,
      size: Math.random() * 2 + 1,
      delay: Math.random() * 3,
      duration: 2 + Math.random() * 4,
    }))
  }, [])

  return (
    <>
      {stars.map((s) => (
        <div
          key={s.id}
          className="star animate-twinkle"
          style={{
            left: `${s.left}%`,
            top: `${s.top}%`,
            width: s.size,
            height: s.size,
            animationDelay: `${s.delay}s`,
            animationDuration: `${s.duration}s`,
          }}
        />
      ))}
    </>
  )
}

export default function SleepScreen() {
  const wake = useArcadeStore((s) => s.wake)
  const { onPress } = useKeyboard()

  useEffect(() => {
    return onPress('any', () => wake())
  }, [onPress, wake])

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-black">
      <StarField />

      <div className="animate-breathe relative z-10">
        <LunaFace expression="sleeping" size={96} />
      </div>

      <p
        className="mt-8 font-pixel text-xs text-arcade-cyan opacity-60 relative z-10"
        style={{ animation: 'breathe 3s ease-in-out infinite' }}
      >
        PRESS ANY BUTTON
      </p>
    </div>
  )
}
