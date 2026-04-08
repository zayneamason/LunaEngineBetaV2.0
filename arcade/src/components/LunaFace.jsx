import { useMemo } from 'react'

const _ = null // transparent
const C = '#00F5FF' // cyan
const M = '#FF00AA' // magenta
const W = '#FFFFFF' // white
const D = '#1A0A3E' // dark fill
const G = '#6B5B95' // muted grey
const P = '#C084FC' // purple accent
const Y = '#FFD700' // gold

// 12x12 pixel art frames — each row is left→right
const EXPRESSIONS = {
  idle: [
    [_,_,_,D,D,D,D,D,D,_,_,_],
    [_,_,D,D,P,D,D,P,D,D,_,_],
    [_,D,D,D,D,D,D,D,D,D,D,_],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,C,C,D,D,D,D,C,C,D,D],
    [D,D,C,W,D,D,D,D,C,W,D,D],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,D,D,D,G,G,D,D,D,D,D],
    [D,D,D,M,D,D,D,D,M,D,D,D],
    [D,D,D,D,M,M,M,M,D,D,D,D],
    [_,D,D,D,D,D,D,D,D,D,D,_],
    [_,_,D,D,D,D,D,D,D,D,_,_],
  ],
  happy: [
    [_,_,_,D,D,D,D,D,D,_,_,_],
    [_,_,D,D,P,D,D,P,D,D,_,_],
    [_,D,D,D,D,D,D,D,D,D,D,_],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,C,C,D,D,D,D,C,C,D,D],
    [D,D,C,W,D,D,D,D,C,W,D,D],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,D,D,D,G,G,D,D,D,D,D],
    [D,D,D,D,M,D,D,M,D,D,D,D],
    [D,D,D,D,D,M,M,D,D,D,D,D],
    [_,D,D,D,D,D,D,D,D,D,D,_],
    [_,_,D,D,D,D,D,D,D,D,_,_],
  ],
  excited: [
    [_,_,_,D,D,D,D,D,D,_,_,_],
    [_,_,D,D,Y,D,D,Y,D,D,_,_],
    [_,D,D,D,D,D,D,D,D,D,D,_],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,Y,Y,D,D,D,D,Y,Y,D,D],
    [D,D,Y,W,D,D,D,D,Y,W,D,D],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,D,D,D,G,G,D,D,D,D,D],
    [D,D,D,M,M,D,D,M,M,D,D,D],
    [D,D,D,D,M,M,M,M,D,D,D,D],
    [_,D,D,D,D,D,D,D,D,D,D,_],
    [_,_,D,D,D,D,D,D,D,D,_,_],
  ],
  sleeping: [
    [_,_,_,D,D,D,D,D,D,_,_,_],
    [_,_,D,D,P,D,D,P,D,D,_,_],
    [_,D,D,D,D,D,D,D,D,D,D,_],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,G,G,G,D,D,G,G,G,D,D],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,D,D,D,G,G,D,D,D,D,D],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,D,D,G,G,G,G,D,D,D,D],
    [_,D,D,D,D,D,D,D,D,D,D,_],
    [_,_,D,D,D,D,D,D,D,D,_,_],
  ],
  thinking: [
    [_,_,_,D,D,D,D,D,D,_,_,_],
    [_,_,D,D,P,D,D,P,D,D,_,_],
    [_,D,D,D,D,D,D,D,D,D,D,_],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,D,C,D,D,D,D,C,C,D,D],
    [D,D,C,W,D,D,D,D,C,W,D,D],
    [D,D,D,D,D,D,D,D,D,D,D,D],
    [D,D,D,D,D,G,G,D,D,D,D,D],
    [D,D,D,D,D,D,D,M,D,D,D,D],
    [D,D,D,D,G,G,G,D,D,D,D,D],
    [_,D,D,D,D,D,D,D,D,D,D,_],
    [_,_,D,D,D,D,D,D,D,D,_,_],
  ],
}

export default function LunaFace({ expression = 'idle', size = 120 }) {
  const frame = EXPRESSIONS[expression] || EXPRESSIONS.idle
  const pixelSize = Math.floor(size / 12)
  const gridSize = pixelSize * 12

  const pixels = useMemo(() => {
    const result = []
    for (let y = 0; y < 12; y++) {
      for (let x = 0; x < 12; x++) {
        const color = frame[y][x]
        if (color) {
          result.push(
            <div
              key={`${x}-${y}`}
              style={{
                position: 'absolute',
                left: x * pixelSize,
                top: y * pixelSize,
                width: pixelSize,
                height: pixelSize,
                backgroundColor: color,
                transition: 'background-color 0.3s ease',
              }}
            />
          )
        }
      }
    }
    return result
  }, [frame, pixelSize])

  return (
    <div
      className="pixel-grid relative"
      style={{ width: gridSize, height: gridSize }}
    >
      {pixels}
    </div>
  )
}
