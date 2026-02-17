/**
 * WebSocket client — connects to Observatory backend on :8100.
 * Reconnects automatically on disconnect.
 */

const WS_URL = 'ws://localhost:8100/ws/events'
let ws = null
let reconnectTimer = null

export function connectWS(onEvent, onStatusChange) {
  if (ws && ws.readyState === WebSocket.OPEN) return

  ws = new WebSocket(WS_URL)

  ws.onopen = () => {
    onStatusChange(true)
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  ws.onmessage = (msg) => {
    try {
      const event = JSON.parse(msg.data)
      onEvent(event)
    } catch (e) {
      console.warn('WS parse error:', e)
    }
  }

  ws.onclose = () => {
    onStatusChange(false)
    reconnectTimer = setTimeout(() => connectWS(onEvent, onStatusChange), 2000)
  }

  ws.onerror = () => {
    ws.close()
  }
}

export function disconnectWS() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  if (ws) ws.close()
  ws = null
}
