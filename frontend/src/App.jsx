import React, { useState, useEffect, useRef } from 'react';
import {
  GlassCard,
  StatusDot,
  ChatPanel,
  ConsciousnessMonitor,
  EngineStatus,
  ThoughtStream,
  ContextDebugPanel,
  ConversationCache,
  VoicePanel,
  LunaQAPanel,
  VoightKampffPanel,
  MemoryMonitorPanel,
} from './components';
import { useLunaAPI } from './hooks/useLunaAPI';
import { useChat } from './hooks/useChat';
import { useVoice } from './hooks/useVoice';
import KozmoApp from './kozmo/KozmoApp';
import ObservatoryApp from './observatory/ObservatoryApp';
import { useNavigation } from './hooks/useNavigation';

// Storage key for chat persistence
const CHAT_STORAGE_KEY = 'luna_chat_messages';

const Eclissi = () => {
  const {
    status,
    consciousness,
    isConnected,
    error: apiError,
    relaunchSystem,
    refresh,
  } = useLunaAPI();

  // Streaming chat hook (uses /persona/stream with context-first)
  const {
    messages,
    context,
    isStreaming,
    error: chatError,
    send,
  } = useChat();

  // Voice hook for TTS when voice mode is active
  const voice = useVoice();
  const lastSpokenMsgId = useRef(null);

  // Debug mode state
  const [debugMode, setDebugMode] = useState(false);
  const [debugKeywords, setDebugKeywords] = useState([]);
  // Memory monitor state
  const [memoryMode, setMemoryMode] = useState(false);
  // QA panel state
  const [qaMode, setQaMode] = useState(false);
  // Voight-Kampff panel state
  const [vkMode, setVkMode] = useState(false);
  // Entity data for keyword highlighting (fetched from Observatory API)
  const [knownEntities, setKnownEntities] = useState([]);
  // KOZMO mode - full takeover view
  const [kozmoMode, setKozmoMode] = useState(false);
  // Observatory mode - memory matrix visualization
  const [observatoryMode, setObservatoryMode] = useState(false);
  // Navigation bus
  const { pending: navPending, consume: navConsume } = useNavigation();
  // QA status tracking (for visual alerts)
  const [qaStatus, setQaStatus] = useState({ passed: true, failures: 0, lastId: null });
  const [qaFlash, setQaFlash] = useState(false); // Flash animation on failure

  // Fetch entity list for keyword highlighting (once on mount)
  useEffect(() => {
    fetch('/observatory/api/entities')
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data?.entities) setKnownEntities(data.entities); })
      .catch(() => {}); // Silent fail — Observatory may not be running
  }, []);

  // Fetch debug context for keywords when debug mode is on
  useEffect(() => {
    if (!debugMode || !isConnected) {
      setDebugKeywords([]);
      return;
    }

    const fetchDebugContext = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/debug/context');
        if (res.ok) {
          const data = await res.json();
          setDebugKeywords(data.keywords || []);
        }
      } catch (e) {
        console.warn('Failed to fetch debug context:', e);
      }
    };

    fetchDebugContext();
    const interval = setInterval(fetchDebugContext, 3000);
    return () => clearInterval(interval);
  }, [debugMode, isConnected]);

  // Persist messages to localStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      try {
        localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
      } catch (e) {
        console.warn('Failed to save chat to localStorage:', e);
      }
    }
  }, [messages]);

  // Speak completed assistant responses (when streaming finishes)
  useEffect(() => {
    if (!voice.isRunning || isStreaming) return;
    const lastMsg = messages[messages.length - 1];
    if (
      lastMsg?.role === 'assistant' &&
      !lastMsg.streaming &&
      lastMsg.content &&
      lastMsg.id !== lastSpokenMsgId.current
    ) {
      lastSpokenMsgId.current = lastMsg.id;
      voice.speakResponse(lastMsg.content);
    }
  }, [messages, isStreaming, voice.isRunning]);

  // Navigation bus consumer (Observatory Navigation Bus)
  useEffect(() => {
    if (!navPending) return

    switch (navPending.to) {
      case 'observatory':
        setObservatoryMode(true)
        setKozmoMode(false)
        break
      case 'kozmo':
        setKozmoMode(true)
        setObservatoryMode(false)
        break
      case 'eclissi':
        setKozmoMode(false)
        setObservatoryMode(false)
        break
    }

    navConsume()
  }, [navPending]);

  // Refresh consciousness after response completes
  useEffect(() => {
    if (!isStreaming && messages.length > 0) {
      refresh();
    }
  }, [isStreaming]);

  // Check QA status after each response (poll /qa/last)
  useEffect(() => {
    if (isStreaming || !isConnected) return;

    const checkQA = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/qa/last');
        if (!res.ok) return;

        const report = await res.json();
        if (report.error) return;

        // Only alert on new reports
        if (report.inference_id !== qaStatus.lastId) {
          setQaStatus({
            passed: report.passed,
            failures: report.failed_count || 0,
            lastId: report.inference_id,
          });

          // Flash and console warn on failure
          if (!report.passed) {
            setQaFlash(true);
            setTimeout(() => setQaFlash(false), 2000);

            console.warn(
              '%c🔬 QA FAILED',
              'background: #ef4444; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;',
              `\n${report.failed_count} assertion(s) failed for: "${report.query}"\n`,
              report.diagnosis || 'No diagnosis available'
            );

            // Log individual failures
            report.assertions?.filter(a => !a.passed).forEach(a => {
              console.warn(`  ❌ [${a.severity}] ${a.name}: ${a.actual}`);
            });
          }
        }
      } catch (e) {
        // Silent fail - QA check is non-critical
      }
    };

    // Small delay to let QA report be created after response
    const timeout = setTimeout(checkQA, 500);
    return () => clearTimeout(timeout);
  }, [isStreaming, messages.length, isConnected]);

  // Combine errors
  const error = chatError || apiError;

  return (
    <div className="min-h-screen bg-kozmo-bg text-white overflow-hidden">
      {/* Ambient glow layers — give glass panels something to blur against */}
      <div
        style={{
          position: 'fixed', top: '-10%', left: '-5%', width: '500px', height: '500px',
          background: 'radial-gradient(circle, rgba(192,132,252,0.08) 0%, transparent 70%)',
          borderRadius: '50%', filter: 'blur(80px)', pointerEvents: 'none', zIndex: 0,
          animation: 'ambient-drift 20s ease-in-out infinite, ambient-breathe 8s ease-in-out infinite',
        }}
      />
      <div
        style={{
          position: 'fixed', bottom: '-15%', right: '-5%', width: '600px', height: '600px',
          background: 'radial-gradient(circle, rgba(129,140,248,0.06) 0%, transparent 70%)',
          borderRadius: '50%', filter: 'blur(100px)', pointerEvents: 'none', zIndex: 0,
          animation: 'ambient-drift 25s ease-in-out infinite reverse, ambient-breathe 10s ease-in-out infinite 2s',
        }}
      />
      <div
        style={{
          position: 'fixed', top: '40%', right: '20%', width: '400px', height: '400px',
          background: 'radial-gradient(circle, rgba(52,211,153,0.04) 0%, transparent 70%)',
          borderRadius: '50%', filter: 'blur(100px)', pointerEvents: 'none', zIndex: 0,
          animation: 'ambient-drift 30s ease-in-out infinite 5s, ambient-breathe 12s ease-in-out infinite 4s',
        }}
      />

      {/* Main Content */}
      <div className="relative min-h-screen p-6" style={{ zIndex: 1 }}>
        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-1 h-10 bg-kozmo-accent rounded-full" style={{ boxShadow: '0 0 12px rgba(192,132,252,0.5), 0 0 4px rgba(192,132,252,0.8)' }} />
              <div className="flex items-center gap-3">
                <span style={{ fontSize: 10, letterSpacing: 4, color: '#c084fc', fontWeight: 800 }}>ECLISSI</span>
                <span style={{ fontSize: 10, letterSpacing: 2, color: '#2a2a3a' }}>LUNA ENGINE v2.0</span>
              </div>
            </div>

            {/* Connection Status & Debug Toggle */}
            <div className="flex items-center gap-4">
              {/* KOZMO Toggle */}
              <button
                onClick={() => { setKozmoMode(!kozmoMode); setObservatoryMode(false); }}
                className={`px-3 py-1.5 text-xs rounded border transition-all ${
                  kozmoMode
                    ? 'border-[#c8ff00]/50 text-[#c8ff00]'
                    : 'bg-kozmo-bg border-kozmo-border text-kozmo-muted hover:border-kozmo-border/80'
                }`}
                style={kozmoMode ? { background: 'rgba(200,255,0,0.1)' } : {}}
              >
                KOZMO
              </button>

              {/* Observatory Toggle */}
              <button
                onClick={() => { setObservatoryMode(!observatoryMode); setKozmoMode(false); }}
                className={`px-3 py-1.5 text-xs rounded border transition-all ${
                  observatoryMode
                    ? 'border-[#7dd3fc]/50 text-[#7dd3fc]'
                    : 'bg-kozmo-bg border-kozmo-border text-kozmo-muted hover:border-kozmo-border/80'
                }`}
                style={observatoryMode ? { background: 'rgba(125,211,252,0.1)' } : {}}
              >
                OBSERVATORY
              </button>

              {/* QA Toggle with failure indicator */}
              <button
                onClick={() => setQaMode(!qaMode)}
                className={`relative px-3 py-1.5 text-xs rounded border transition-all ${
                  qaFlash
                    ? 'bg-red-500/30 border-red-500/70 text-red-300 animate-pulse'
                    : qaMode
                    ? 'bg-kozmo-accent/20 border-kozmo-accent/50 text-kozmo-accent'
                    : !qaStatus.passed
                    ? 'bg-kozmo-danger/20 border-kozmo-danger/50 text-kozmo-danger'
                    : 'bg-kozmo-bg border-kozmo-border text-kozmo-muted hover:border-kozmo-border/80'
                }`}
              >
                🔬 QA
                {!qaStatus.passed && qaStatus.failures > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center font-bold">
                    {qaStatus.failures}
                  </span>
                )}
              </button>

              {/* Voight-Kampff Toggle */}
              <button
                onClick={() => setVkMode(!vkMode)}
                className={`px-3 py-1.5 text-xs rounded border transition-all ${
                  vkMode
                    ? 'bg-kozmo-cinema/20 border-kozmo-cinema/50 text-kozmo-cinema'
                    : 'bg-kozmo-bg border-kozmo-border text-kozmo-muted hover:border-kozmo-border/80'
                }`}
              >
                🔬 VK
              </button>

              {/* Memory Monitor Toggle */}
              <button
                onClick={() => setMemoryMode(!memoryMode)}
                className={`px-3 py-1.5 text-xs rounded border transition-all ${
                  memoryMode
                    ? 'bg-kozmo-accent/20 border-kozmo-accent/50 text-kozmo-accent'
                    : 'bg-kozmo-bg border-kozmo-border text-kozmo-muted hover:border-kozmo-border/80'
                }`}
              >
                🧠 {memoryMode ? 'MEMORY' : 'Memory'}
              </button>

              {/* Debug Toggle */}
              <button
                onClick={() => setDebugMode(!debugMode)}
                className={`px-3 py-1.5 text-xs rounded border transition-all ${
                  debugMode
                    ? 'bg-kozmo-danger/20 border-kozmo-danger/50 text-kozmo-danger'
                    : 'bg-kozmo-bg border-kozmo-border text-kozmo-muted hover:border-kozmo-border/80'
                }`}
              >
                🔍 {debugMode ? 'DEBUG ON' : 'Debug'}
              </button>

              <div className="flex items-center gap-3">
                <StatusDot status={isConnected ? 'connected' : 'disconnected'} />
                <span className="text-sm text-white/50">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </header>

        {kozmoMode ? (
          /* KOZMO Full Takeover */
          <div className="absolute inset-0 top-[72px]" style={{ zIndex: 2 }}>
            <KozmoApp onBack={() => setKozmoMode(false)} />
          </div>
        ) : observatoryMode ? (
          /* Observatory Full Takeover */
          <div className="absolute inset-0 top-[72px]" style={{ zIndex: 2 }}>
            <ObservatoryApp onBack={() => setObservatoryMode(false)} />
          </div>
        ) : (
          <>
            {/* Error Banner */}
            {error && (
              <div className="mb-6 p-4 rounded bg-kozmo-danger/10 border border-kozmo-danger/30 text-kozmo-danger text-sm">
                {error}
              </div>
            )}

            {/* Main Grid */}
            <div className="grid grid-cols-12 gap-6 h-[calc(100vh-180px)]">
              {/* Left Panel - Chat (streaming with context-first) */}
              <div className="col-span-7 h-full min-h-0">
                <ChatPanel
                  messages={messages}
                  onSend={send}
                  isLoading={isStreaming}
                  debugKeywords={debugMode ? debugKeywords : []}
                  entities={knownEntities}
                />
              </div>

              {/* Right Panel - Status & Consciousness */}
              <div className="col-span-5 h-full min-h-0 overflow-y-auto space-y-6 pr-2">
                {/* Voice Panel - Voice interaction */}
                <VoicePanel voiceHook={voice} />

                {/* Engine Status */}
                <EngineStatus status={status} isConnected={isConnected} onRelaunch={relaunchSystem} />

                {/* Conversation Cache - What Luna remembers */}
                <ConversationCache isConnected={isConnected} entities={knownEntities} />

                {/* Thought Stream - Luna's internal process */}
                <ThoughtStream apiUrl="http://127.0.0.1:8000" entities={knownEntities} />

                {/* Consciousness Monitor */}
                <ConsciousnessMonitor consciousness={consciousness} />
              </div>
            </div>

            {/* Footer */}
            <footer className="fixed bottom-4 left-6 right-6">
              <div className="flex items-center justify-between text-xs text-kozmo-muted">
                <div className="flex items-center gap-4">
                  <span>LUNA ENGINE v2.0</span>
                  <span>|</span>
                  <span>Phase 4: Consciousness</span>
                </div>
                <div className="flex items-center gap-2">
                  <span>Model:</span>
                  <span className="text-kozmo-accent">Claude Sonnet</span>
                </div>
              </div>
            </footer>

            {/* Context Debug Panel */}
            <ContextDebugPanel
              isOpen={debugMode}
              onClose={() => setDebugMode(false)}
              entities={knownEntities}
            />

            {/* Memory Monitor Panel */}
            <MemoryMonitorPanel
              isOpen={memoryMode}
              onClose={() => setMemoryMode(false)}
              entities={knownEntities}
            />

            {/* QA Panel */}
            <LunaQAPanel
              isOpen={qaMode}
              onClose={() => setQaMode(false)}
            />

            {/* Voight-Kampff Panel */}
            <VoightKampffPanel
              isOpen={vkMode}
              onClose={() => setVkMode(false)}
            />
          </>
        )}
      </div>
    </div>
  );
};

export default Eclissi;
