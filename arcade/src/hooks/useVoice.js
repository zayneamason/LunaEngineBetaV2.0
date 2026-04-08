/**
 * Stubbed voice hook — will be wired to Luna's TTS/STT backend later.
 * Components can use this interface now; only this file changes when voice is added.
 */
export default function useVoice() {
  return {
    transcript: null,
    isListening: false,
    isSpeaking: false,
    speak: (text) => {
      console.log('[voice-stub] speak:', text)
    },
    startListening: () => {
      console.log('[voice-stub] startListening (no-op)')
    },
    stopListening: () => {
      console.log('[voice-stub] stopListening (no-op)')
    },
  }
}
