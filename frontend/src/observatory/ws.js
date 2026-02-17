/**
 * WebSocket client — connects to Observatory backend via Vite proxy.
 * Reconnects automatically on disconnect.
 */

let ws = null
let reconnectTimer = null

function getWsUrl() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/observatory/ws/events`
}

export function connectWS(onEvent, onStatusChange) {
  if (ws && ws.readyState === WebSocket.OPEN) return

  ws = new WebSocket(getWsUrl())

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
      console.warn('Observatory WS parse error:', e)
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
  reconnectTimer = null
  if (ws) ws.close()
  ws = null
}
