import { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = '';

/**
 * Voice states for UI feedback
 */
export const VoiceState = {
  INACTIVE: 'inactive',   // Voice system not started
  IDLE: 'idle',          // Ready, waiting for input
  LISTENING: 'listening', // Recording user speech
  THINKING: 'thinking',   // Processing / generating response
  SPEAKING: 'speaking',   // Playing Luna's response
};

/**
 * Hook for managing voice interactions with Luna.
 *
 * Provides:
 * - Voice system start/stop
 * - Push-to-talk recording
 * - Real-time status updates via SSE
 * - Transcription and response callbacks
 */
export function useVoice() {
  // State
  const [voiceState, setVoiceState] = useState(VoiceState.INACTIVE);
  const [isRunning, setIsRunning] = useState(false);
  const [transcription, setTranscription] = useState(null);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [handsFreee, setHandsFree] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [hint, setHint] = useState(null);
  const hintTimerRef = useRef(null);
  const thinkingTimeoutRef = useRef(null);

  // SSE connection ref
  const eventSourceRef = useRef(null);

  // Connect to voice status stream
  const connectStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(`${API_BASE}/voice/stream`);

    es.addEventListener('status', (e) => {
      try {
        const data = JSON.parse(e.data);
        setIsRunning(data.running);
        if (data.status) {
          setVoiceState(data.status);
          // Backend sent a real status — cancel any stale thinking timeout
          if (thinkingTimeoutRef.current) {
            clearTimeout(thinkingTimeoutRef.current);
            thinkingTimeoutRef.current = null;
          }
        }
      } catch {}
    });

    es.addEventListener('transcription', (e) => {
      try {
        const data = JSON.parse(e.data);
        setTranscription(data.text);
      } catch {}
    });

    es.addEventListener('response', (e) => {
      try {
        const data = JSON.parse(e.data);
        setResponse(data.text);
      } catch {}
    });

    es.addEventListener('audio_level', (e) => {
      try {
        const data = JSON.parse(e.data);
        setAudioLevel(data.level || 0);
      } catch {}
    });

    es.addEventListener('ping', (e) => {
      try {
        const data = JSON.parse(e.data);
        setIsRunning(data.running);
      } catch {}
    });

    es.onerror = (err) => {
      console.warn('Voice stream error, will reconnect...');
      es.close();
      // Only reconnect if we're still mounted
      if (eventSourceRef.current === es) {
        eventSourceRef.current = null;
        setTimeout(connectStream, 3000);
      }
    };

    eventSourceRef.current = es;
  }, []);

  // Connect on mount
  useEffect(() => {
    connectStream();

    // Check initial status
    fetch(`${API_BASE}/voice/status`)
      .then(res => res.json())
      .then(data => {
        setIsRunning(data.running);
        setHandsFree(data.hands_free);
        if (!data.running) {
          setVoiceState(VoiceState.INACTIVE);
        }
      })
      .catch(() => {});

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (hintTimerRef.current) clearTimeout(hintTimerRef.current);
      if (thinkingTimeoutRef.current) clearTimeout(thinkingTimeoutRef.current);
    };
  }, [connectStream]);

  // Start voice system
  const startVoice = useCallback(async (handsFreeMode = false) => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/voice/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hands_free: handsFreeMode }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to start voice');
      }

      const data = await res.json();
      setIsRunning(true);
      setHandsFree(handsFreeMode);
      setVoiceState(VoiceState.IDLE);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  // Stop voice system
  const stopVoice = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/voice/stop`, {
        method: 'POST',
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to stop voice');
      }

      setIsRunning(false);
      setVoiceState(VoiceState.INACTIVE);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  // Start listening (push-to-talk press)
  const startListening = useCallback(async () => {
    if (!isRunning || handsFreee) return;

    setError(null);
    setTranscription(null);
    setResponse(null);

    try {
      const res = await fetch(`${API_BASE}/voice/listen/start`, {
        method: 'POST',
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to start listening');
      }

      setVoiceState(VoiceState.LISTENING);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, [isRunning, handsFreee]);

  // Stop listening (push-to-talk release)
  const stopListening = useCallback(async () => {
    if (!isRunning || handsFreee) return;

    setError(null);
    setAudioLevel(0);

    try {
      setVoiceState(VoiceState.THINKING);

      const res = await fetch(`${API_BASE}/voice/listen/stop`, {
        method: 'POST',
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to stop listening');
      }

      const data = await res.json();

      // Check if speech was detected
      if (data.transcription) {
        setTranscription(data.transcription);
        setHint(null);
      } else {
        // No speech detected - show hint briefly
        setVoiceState(VoiceState.IDLE);
        const hintText = data.hint || 'No speech detected — hold longer while speaking';
        setHint(hintText);
        if (hintTimerRef.current) clearTimeout(hintTimerRef.current);
        hintTimerRef.current = setTimeout(() => setHint(null), 3000);
        return {
          ...data,
          no_speech: true,
          hint: hintText,
        };
      }

      // Safety net: if SSE doesn't deliver a status update within 15s, reset to idle
      if (thinkingTimeoutRef.current) clearTimeout(thinkingTimeoutRef.current);
      thinkingTimeoutRef.current = setTimeout(() => {
        setVoiceState((prev) => {
          if (prev === VoiceState.THINKING) {
            return VoiceState.IDLE;
          }
          return prev;
        });
        thinkingTimeoutRef.current = null;
      }, 15000);

      return { ...data, no_speech: false };
    } catch (e) {
      setError(e.message);
      setVoiceState(VoiceState.IDLE);
      return { error: e.message };
    }
  }, [isRunning, handsFreee]);

  // Speak text (for typed chat responses when voice is active)
  const speakResponse = useCallback(async (text) => {
    if (!isRunning || !text) return null;

    try {
      setVoiceState(VoiceState.SPEAKING);

      const res = await fetch(`${API_BASE}/voice/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to speak');
      }

      return await res.json();
    } catch (e) {
      console.warn('Speak failed:', e.message);
      return null;
    }
  }, [isRunning]);

  return {
    // State
    voiceState,
    isRunning,
    transcription,
    response,
    error,
    handsFree: handsFreee,
    audioLevel,
    hint,

    // Actions
    startVoice,
    stopVoice,
    startListening,
    stopListening,
    speakResponse,

    // Derived state
    isListening: voiceState === VoiceState.LISTENING,
    isThinking: voiceState === VoiceState.THINKING,
    isSpeaking: voiceState === VoiceState.SPEAKING,
    isIdle: voiceState === VoiceState.IDLE,
    isInactive: voiceState === VoiceState.INACTIVE,
  };
}
