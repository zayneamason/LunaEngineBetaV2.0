import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useVoice, VoiceState } from '../hooks/useVoice';
import GlassCard from './GlassCard';

/**
 * VoicePanel - Voice interaction UI for Luna
 *
 * Features:
 * - Visual status indicator (pulse animation for states)
 * - Push-to-talk mic button (hold to record)
 * - Transcription display
 * - Response display
 * - Start/stop voice system
 *
 * Props:
 * - voiceHook: Optional voice hook instance from parent (for shared state)
 */
const VoicePanel = ({ voiceHook }) => {
  // Use provided hook or create own
  const internalVoice = useVoice();
  const voice = voiceHook || internalVoice;

  const {
    voiceState,
    isRunning,
    transcription,
    response,
    error,
    handsFree,
    startVoice,
    stopVoice,
    startListening,
    stopListening,
    isListening,
    isThinking,
    isSpeaking,
  } = voice;

  const [isHolding, setIsHolding] = useState(false);
  const [lastAction, setLastAction] = useState(null); // Track last action result
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0); // Simulated audio level for visualization
  const holdTimeoutRef = useRef(null);
  const recordingTimerRef = useRef(null);
  const audioLevelRef = useRef(null);

  // Clear last action after 5 seconds
  useEffect(() => {
    if (lastAction) {
      const timer = setTimeout(() => setLastAction(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [lastAction]);

  // Recording duration timer
  useEffect(() => {
    if (isListening) {
      setRecordingDuration(0);
      recordingTimerRef.current = setInterval(() => {
        setRecordingDuration(prev => prev + 0.1);
      }, 100);

      // Simulate audio level changes for visual feedback
      audioLevelRef.current = setInterval(() => {
        setAudioLevel(Math.random() * 0.6 + 0.2); // Random between 0.2 and 0.8
      }, 100);
    } else {
      if (recordingTimerRef.current) {
        clearInterval(recordingTimerRef.current);
        recordingTimerRef.current = null;
      }
      if (audioLevelRef.current) {
        clearInterval(audioLevelRef.current);
        audioLevelRef.current = null;
      }
      setAudioLevel(0);
    }

    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      if (audioLevelRef.current) clearInterval(audioLevelRef.current);
    };
  }, [isListening]);

  // Status colors and labels
  const statusConfig = {
    [VoiceState.INACTIVE]: {
      color: 'bg-slate-500',
      ringColor: 'ring-slate-500/30',
      label: 'Voice Off',
      icon: '🔇',
    },
    [VoiceState.IDLE]: {
      color: 'bg-emerald-500',
      ringColor: 'ring-emerald-500/30',
      label: 'Ready',
      icon: '🎙️',
    },
    [VoiceState.LISTENING]: {
      color: 'bg-violet-500',
      ringColor: 'ring-violet-500/50',
      label: 'Listening...',
      icon: '👂',
      pulse: true,
    },
    [VoiceState.THINKING]: {
      color: 'bg-amber-500',
      ringColor: 'ring-amber-500/50',
      label: 'Thinking...',
      icon: '🧠',
      pulse: true,
    },
    [VoiceState.SPEAKING]: {
      color: 'bg-cyan-500',
      ringColor: 'ring-cyan-500/50',
      label: 'Speaking...',
      icon: '💬',
      pulse: true,
    },
  };

  const currentStatus = statusConfig[voiceState] || statusConfig[VoiceState.INACTIVE];

  // Handle mic button press (push-to-talk)
  const handleMicDown = useCallback(async (e) => {
    e.preventDefault();
    if (!isRunning || handsFree) return;

    setIsHolding(true);
    await startListening();
  }, [isRunning, handsFree, startListening]);

  // Handle mic button release
  const handleMicUp = useCallback(async (e) => {
    e.preventDefault();
    if (!isRunning || handsFree || !isHolding) return;

    const duration = recordingDuration;
    setIsHolding(false);

    const result = await stopListening();

    // Track what happened for user feedback
    if (result) {
      if (result.no_speech) {
        setLastAction({
          type: 'no_speech',
          message: result.hint || 'No speech detected',
          duration: duration.toFixed(1),
        });
      } else if (result.error) {
        setLastAction({
          type: 'error',
          message: result.error,
          duration: duration.toFixed(1),
        });
      } else if (result.transcription) {
        setLastAction({
          type: 'success',
          message: 'Speech captured!',
          duration: duration.toFixed(1),
        });
      }
    }
  }, [isRunning, handsFree, isHolding, stopListening, recordingDuration]);

  // Handle touch events for mobile
  const handleTouchStart = useCallback((e) => {
    e.preventDefault();
    handleMicDown(e);
  }, [handleMicDown]);

  const handleTouchEnd = useCallback((e) => {
    e.preventDefault();
    handleMicUp(e);
  }, [handleMicUp]);

  // Local hands-free preference
  const [wantHandsFree, setWantHandsFree] = useState(true); // Default to hands-free

  // Toggle voice system
  const toggleVoice = useCallback(async () => {
    if (isRunning) {
      await stopVoice();
    } else {
      await startVoice(wantHandsFree);
    }
  }, [isRunning, startVoice, stopVoice, wantHandsFree]);

  // Toggle hands-free mode (requires restart)
  const toggleHandsFree = useCallback(async () => {
    const newMode = !wantHandsFree;
    setWantHandsFree(newMode);
    if (isRunning) {
      // Restart with new mode
      await stopVoice();
      await startVoice(newMode);
    }
  }, [wantHandsFree, isRunning, stopVoice, startVoice]);

  return (
    <GlassCard className="p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-white/70">Voice Mode</h3>

        <div className="flex items-center gap-2">
          {/* Hands-free toggle */}
          <button
            onClick={toggleHandsFree}
            className={`px-2 py-1 text-xs rounded border transition-all ${
              wantHandsFree
                ? 'bg-kozmo-accent/20 border-kozmo-accent/50 text-kozmo-accent'
                : 'bg-kozmo-surface border-kozmo-border text-kozmo-muted'
            }`}
            title={wantHandsFree ? 'Hands-free (always listening)' : 'Push-to-talk'}
          >
            {wantHandsFree ? '🎙️ Open' : '👆 PTT'}
          </button>

          {/* Power toggle */}
          <button
            onClick={toggleVoice}
            className={`px-3 py-1 text-xs rounded border transition-all ${
              isRunning
                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/30'
                : 'bg-kozmo-surface border-kozmo-border text-kozmo-muted hover:border-kozmo-border/80 hover:text-white/60'
            }`}
          >
            {isRunning ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

      {/* Status Indicator */}
      <div className="flex flex-col items-center py-4">
        {/* Animated status ring */}
        <div className="relative">
          {/* Outer pulse ring */}
          <div
            className={`absolute inset-0 rounded-full ${currentStatus.ringColor} ${
              currentStatus.pulse ? 'animate-ping' : ''
            }`}
            style={{ animationDuration: '1.5s' }}
          />

          {/* Inner status indicator */}
          <div
            className={`relative w-20 h-20 rounded-full ${currentStatus.color} ring-4 ${currentStatus.ringColor} flex items-center justify-center transition-all duration-300`}
          >
            <span className="text-3xl">{currentStatus.icon}</span>
          </div>
        </div>

        {/* Status label */}
        <div className="mt-3 text-sm font-medium text-white/80">
          {currentStatus.label}
        </div>

        {/* Hands-free indicator */}
        {handsFree && isRunning && (
          <div className="mt-2 space-y-2">
            <div className="flex items-center justify-center gap-2 text-xs text-kozmo-accent">
              <span className="w-2 h-2 bg-kozmo-accent rounded-full animate-pulse" />
              Open mic - always listening
            </div>
            <div className="text-xs text-kozmo-muted text-center">
              Speak naturally, Luna will respond when you pause
            </div>
          </div>
        )}

        {/* Processing indicator */}
        {isThinking && (
          <div className="mt-2 flex items-center justify-center gap-2 text-xs text-amber-400">
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Processing your message...
          </div>
        )}

        {/* Speaking indicator */}
        {isSpeaking && (
          <div className="mt-2 flex items-center justify-center gap-2 text-xs text-kozmo-accent">
            <span className="flex gap-0.5">
              <span className="w-1 h-3 bg-kozmo-accent rounded-full animate-pulse" style={{ animationDelay: '0ms' }} />
              <span className="w-1 h-4 bg-kozmo-accent rounded-full animate-pulse" style={{ animationDelay: '100ms' }} />
              <span className="w-1 h-2 bg-kozmo-accent rounded-full animate-pulse" style={{ animationDelay: '200ms' }} />
            </span>
            Luna is speaking...
          </div>
        )}
      </div>

      {/* Push-to-Talk Button */}
      {isRunning && !handsFree && (
        <div className="flex flex-col items-center py-4 border-t border-kozmo-border">
          <div className="text-xs text-white/50 mb-3">
            Hold to speak
          </div>

          <button
            onMouseDown={handleMicDown}
            onMouseUp={handleMicUp}
            onMouseLeave={handleMicUp}
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
            disabled={isThinking || isSpeaking}
            className={`w-16 h-16 rounded-full flex items-center justify-center transition-all duration-150 select-none ${
              isListening || isHolding
                ? 'bg-violet-600 scale-110 shadow-lg shadow-violet-500/50'
                : isThinking || isSpeaking
                ? 'bg-slate-600 cursor-not-allowed opacity-50'
                : 'bg-slate-700 hover:bg-slate-600 active:scale-95'
            }`}
          >
            <svg
              className={`w-8 h-8 ${isListening || isHolding ? 'text-white' : 'text-white/70'}`}
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z" />
            </svg>
          </button>

          {/* Visual feedback for recording */}
          {isListening && (
            <div className="mt-3 space-y-2">
              {/* Recording duration */}
              <div className="text-center text-sm text-violet-300 font-mono">
                Recording: {recordingDuration.toFixed(1)}s
              </div>

              {/* Audio level visualization */}
              <div className="flex items-end justify-center gap-1 h-8">
                {[0.3, 0.5, 0.7, 1.0, 0.8, 0.6, 0.4].map((multiplier, i) => (
                  <span
                    key={i}
                    className="w-2 bg-gradient-to-t from-violet-600 to-violet-400 rounded-full transition-all duration-100"
                    style={{
                      height: `${Math.max(8, audioLevel * multiplier * 32)}px`,
                    }}
                  />
                ))}
              </div>

              {/* Visual indicator that audio is being captured */}
              <div className="flex items-center justify-center gap-2 text-xs text-kozmo-accent">
                <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                Capturing audio...
              </div>
            </div>
          )}

          {/* Last action feedback */}
          {lastAction && !isListening && (
            <div className={`mt-3 px-3 py-2 rounded text-xs text-center ${
              lastAction.type === 'success'
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : lastAction.type === 'no_speech'
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                : 'bg-red-500/20 text-red-400 border border-red-500/30'
            }`}>
              <div className="font-medium">{lastAction.message}</div>
              <div className="text-white/50 mt-0.5">Duration: {lastAction.duration}s</div>
            </div>
          )}
        </div>
      )}

      {/* Transcription & Response */}
      {(transcription || response) && (
        <div className="mt-4 pt-4 border-t border-kozmo-border space-y-3">
          {/* User transcription */}
          {transcription && (
            <div className="p-3 rounded bg-kozmo-surface">
              <div className="text-xs text-kozmo-muted mb-1">You said:</div>
              <div className="text-sm text-white/80">{transcription}</div>
            </div>
          )}

          {/* Luna's response */}
          {response && (
            <div className="p-3 rounded bg-kozmo-accent/10 border border-kozmo-accent/20">
              <div className="text-xs text-kozmo-accent mb-1">Luna:</div>
              <div className="text-sm text-white/90">{response}</div>
            </div>
          )}
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="mt-4 p-3 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* Inactive state hint */}
      {!isRunning && (
        <div className="text-center text-xs text-kozmo-muted mt-2">
          Click ON to enable voice interaction
        </div>
      )}

      {/* Debug Info */}
      <div className="mt-4 pt-4 border-t border-kozmo-border">
        <div className="text-xs text-kozmo-muted mb-2">Debug Info:</div>
        <div className="text-xs font-mono bg-black/30 rounded p-2 space-y-1">
          <div>voiceState: <span className="text-kozmo-accent">{voiceState}</span></div>
          <div>isRunning: <span className={isRunning ? 'text-green-400' : 'text-red-400'}>{String(isRunning)}</span></div>
          <div>isListening: <span className={isListening ? 'text-green-400' : 'text-white/60'}>{String(isListening)}</span></div>
          <div>isThinking: <span className={isThinking ? 'text-amber-400' : 'text-white/60'}>{String(isThinking)}</span></div>

          <div>isSpeaking: <span className={isSpeaking ? 'text-kozmo-accent' : 'text-white/60'}>{String(isSpeaking)}</span></div>
          <div>mode: <span className={handsFree ? 'text-kozmo-accent' : 'text-white/60'}>{handsFree ? 'Open Mic' : 'Push-to-talk'}</span></div>
          <div>isHolding: <span className={isHolding ? 'text-kozmo-accent' : 'text-white/60'}>{String(isHolding)}</span></div>
          <div>recordingDuration: <span className="text-kozmo-accent">{recordingDuration.toFixed(1)}s</span></div>
          <div>audioLevel: <span className="text-kozmo-accent">{audioLevel.toFixed(2)}</span></div>
          {lastAction && <div>lastAction: <span className={lastAction.type === 'success' ? 'text-green-400' : lastAction.type === 'no_speech' ? 'text-amber-400' : 'text-red-400'}>{lastAction.type} ({lastAction.duration}s)</span></div>}
          {transcription && <div>transcription: <span className="text-green-400">"{transcription}"</span></div>}
          {response && <div>response: <span className="text-kozmo-accent">"{response.slice(0, 50)}..."</span></div>}
          {error && <div>error: <span className="text-red-400">{error}</span></div>}
        </div>
      </div>
    </GlassCard>
  );
};

export default VoicePanel;
