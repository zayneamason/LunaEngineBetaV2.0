# HANDOFF: Voice Chat Auto-Start

**Priority:** HIGH — Luna can't speak typed responses  
**Estimated effort:** 30 minutes  
**Root cause:** Voice system never starts automatically; wiring exists but is gated behind manual activation

---

## Problem

User types a message → Luna responds → silence.

The speak-on-response logic **already exists** in `EclissiHome.jsx` (lines 92–104). It correctly calls `voice.speakResponse(lastMsg.content)` when a new assistant message lands. But `speakResponse` hits `POST /voice/speak`, which requires `_voice_backend` to be active.

The voice backend is **never started automatically.** The user would have to:
1. Find the VoicePanel component (not rendered in EclissiHome)
2. Click the ON button
3. Then type

That's too much friction. Nobody does it. Hence: silence.

---

## Architecture (what exists, don't rebuild it)

```
EclissiHome.jsx
    useVoice()          → voice hook (has speakResponse, startVoice, etc.)
    useChat()           → streaming chat

# Already wired (lines 92-104 of EclissiHome.jsx):
useEffect(() => {
    if (!voice.isRunning || isStreaming) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.role === 'assistant' && !lastMsg.streaming && lastMsg.id !== lastSpokenMsgId.current) {
        lastSpokenMsgId.current = lastMsg.id;
        voice.speakResponse(lastMsg.content);   // ← this calls POST /voice/speak
    }
}, [messages, isStreaming, voice.isRunning]);

# What speakResponse does (useVoice.js line 239):
const speakResponse = async (text) => {
    if (!isRunning || !text) return null;
    // hits POST /voice/speak
    // voice backend preprocesses → Piper TTS → audio playback
}

# Voice backend in server.py:
POST /voice/start        → starts VoiceBackend (STT + TTS + PersonaAdapter)
POST /voice/speak        → speaks text through active backend
GET  /voice/status       → { running: bool, ... }
```

The full pipeline works — just needs to be started.

---

## Fix

**Auto-start voice on first user message (hands-free=false, TTS-only).**

The mic/STT doesn't need to activate. We only need TTS so Luna can speak responses. Push-to-talk can remain opt-in. The voice backend handles both, so starting it with `hands_free: false` gives us TTS without always-on mic.

### File: `frontend/src/eclissi/EclissiHome.jsx`

**Add auto-start logic after the existing speak effect (around line 104):**

```javascript
// Auto-start voice system for TTS (speak typed responses)
// Starts once on mount — enables speakResponse without manual activation
// hands_free: false means mic is push-to-talk only (not always-on)
useEffect(() => {
  let started = false;

  const autoStart = async () => {
    if (voice.isRunning || started) return;
    try {
      started = true;
      await voice.startVoice(false); // false = PTT mode, TTS always available
    } catch (e) {
      console.warn('[Voice] Auto-start failed:', e.message);
      // Non-fatal — typed chat still works, just silent
    }
  };

  // Small delay to let engine settle before starting voice backend
  const timer = setTimeout(autoStart, 2000);
  return () => clearTimeout(timer);
}, []); // Run once on mount
```

**That's it.** The rest is already wired.

---

## What this changes

| Before | After |
|--------|-------|
| Voice must be manually activated via VoicePanel | Auto-starts 2s after app load |
| Typed responses are silent | Luna speaks every assistant response |
| PTT mic is off by default | PTT mic is off by default (unchanged) |
| Hands-free mode requires manual toggle | Hands-free mode still requires manual toggle |

---

## Edge cases to handle

**1. Voice backend fails to start (Piper not found, MLX not available)**
Already handled — `startVoice` catches the error and sets `voice.error`. The app continues silently. No change needed.

**2. User doesn't want TTS**
Add a mute/unmute toggle. Simplest approach: a small speaker icon in ChatPanel's header that calls `voice.stopVoice()` / `voice.startVoice(false)`. Don't block the auto-start — add the toggle as a follow-up.

**3. Voice speaking while user is typing the next message**
The existing logic already guards this — `speakResponse` is gated on `!isStreaming`. If user sends a new message mid-speech, the backend will cut off (or queue — Piper is subprocess-based so it'll finish the current synthesis then stop). Acceptable behavior for now.

**4. Duplicate speaks on re-render**
Already handled — `lastSpokenMsgId.current` deduplicates by message ID.

**5. Backend not ready at 2s**
The `/voice/start` endpoint returns 503 if engine isn't ready. The catch block handles this silently. 2s is conservative — engine is typically ready in 0.5s.

---

## Files to Modify

| File | Change | Lines |
|------|--------|-------|
| `frontend/src/eclissi/EclissiHome.jsx` | Add auto-start useEffect | After line ~104 |

---

## Do NOT

- Do NOT touch `useVoice.js` — it's correct
- Do NOT touch `useChat.js` — the speak logic doesn't belong there
- Do NOT touch `server.py` — voice routes are complete
- Do NOT auto-start in hands-free mode — that means always-on mic, which is intrusive
- Do NOT fail silently without the try/catch — voice backend start is best-effort

---

## Verify

1. Start the app
2. Wait ~2 seconds
3. Check `VoicePanel` debug info: `isRunning: true`
4. Type any message to Luna
5. After response completes: Luna speaks it through speakers
6. Check logs for `[NARRATION]` or TTS entries

If Piper isn't working (no audio), check:
- `src/voice/piper_bin/piper/piper` exists and is executable
- `src/voice/piper_models/en_US-amy-medium.onnx` exists
- Backend logs for `PiperTTS not available` warnings

---

## Optional Follow-Up: Mute Toggle in ChatPanel

If auto-start is too aggressive (always speaking), add a toggle:

**`frontend/src/components/ChatPanel.jsx`** — in the header area, add a speaker button:

```jsx
{/* Mute toggle (only show when voice is running) */}
{voice?.isRunning && (
  <button
    onClick={() => voice.isRunning ? voice.stopVoice() : voice.startVoice(false)}
    title={voice.isRunning ? 'Mute Luna' : 'Unmute Luna'}
    className="p-1 rounded text-kozmo-muted hover:text-white/80 transition-colors"
  >
    {voice.isRunning ? '🔊' : '🔇'}
  </button>
)}
```

This is optional — implement only if the always-speaking behavior causes friction.

---

*Luna should speak. One useEffect. Ship it.*
