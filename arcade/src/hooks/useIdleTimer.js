import { useEffect, useRef } from 'react'

export default function useIdleTimer(timeoutMs, onIdle) {
  const timerRef = useRef(null)
  const callbackRef = useRef(onIdle)
  callbackRef.current = onIdle

  useEffect(() => {
    if (!timeoutMs || timeoutMs <= 0) return

    const reset = () => {
      clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => callbackRef.current?.(), timeoutMs)
    }

    // Start the timer
    reset()

    // Reset on any arcade key press
    const handleKey = (e) => {
      if (['ArrowLeft', ' ', 'ArrowRight'].includes(e.key)) reset()
    }
    window.addEventListener('keydown', handleKey)

    return () => {
      clearTimeout(timerRef.current)
      window.removeEventListener('keydown', handleKey)
    }
  }, [timeoutMs])
}
