import { useEffect, useRef, useCallback } from 'react'

const KEYS = { ArrowLeft: 'left', ' ': 'space', ArrowRight: 'right' }

export default function useKeyboard() {
  const pressed = useRef({ left: false, space: false, right: false })
  const callbacks = useRef([]) // [{key: 'left'|'space'|'right'|'any', fn}]

  useEffect(() => {
    const handleDown = (e) => {
      const mapped = KEYS[e.key]
      if (!mapped) return
      e.preventDefault()
      pressed.current[mapped] = true

      // Fire registered callbacks
      for (const cb of callbacks.current) {
        if (cb.key === mapped || cb.key === 'any') cb.fn(mapped)
      }
    }

    const handleUp = (e) => {
      const mapped = KEYS[e.key]
      if (!mapped) return
      pressed.current[mapped] = false
    }

    window.addEventListener('keydown', handleDown)
    window.addEventListener('keyup', handleUp)
    return () => {
      window.removeEventListener('keydown', handleDown)
      window.removeEventListener('keyup', handleUp)
    }
  }, [])

  const onPress = useCallback((key, fn) => {
    const entry = { key, fn }
    callbacks.current.push(entry)
    return () => {
      callbacks.current = callbacks.current.filter((c) => c !== entry)
    }
  }, [])

  return { pressed, onPress }
}
