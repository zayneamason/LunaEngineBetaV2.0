/**
 * useWebSocket Hook (Phase 4)
 *
 * Manages WebSocket connection for real-time entity/scene updates.
 * Reconnects automatically on disconnect.
 */
import { useEffect, useRef, useState } from 'react';

export function useWebSocket(projectSlug, userId = null) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const messageHandlers = useRef(new Map());

  useEffect(() => {
    if (!projectSlug) return;

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/kozmo/ws/${projectSlug}${userId ? `?user_id=${userId}` : ''}`;

      const socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);

        // Clear reconnect timeout if exists
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      };

      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        console.log('WebSocket message:', message);

        setLastMessage(message);

        // Call registered handlers for this message type
        const handlers = messageHandlers.current.get(message.type) || [];
        handlers.forEach(handler => handler(message));
      };

      socket.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);

        // Attempt reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('Attempting to reconnect...');
          connect();
        }, 3000);
      };

      socket.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      socketRef.current = socket;
    };

    connect();

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [projectSlug, userId]);

  const sendMessage = (message) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  };

  const on = (messageType, handler) => {
    if (!messageHandlers.current.has(messageType)) {
      messageHandlers.current.set(messageType, []);
    }
    messageHandlers.current.get(messageType).push(handler);

    // Return unsubscribe function
    return () => {
      const handlers = messageHandlers.current.get(messageType);
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    };
  };

  return {
    isConnected,
    lastMessage,
    sendMessage,
    on
  };
}
