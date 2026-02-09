import React, { useState, useEffect, useRef } from 'react';
import {
  GlassCard,
  GradientOrb,
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

// Storage key for chat persistence
const CHAT_STORAGE_KEY = 'luna_chat_messages';

const LunaHub = () => {
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
  // QA status tracking (for visual alerts)
  const [qaStatus, setQaStatus] = useState({ passed: true, failures: 0, lastId: null });
  const [qaFlash, setQaFlash] = useState(false); // Flash animation on failure

  // Fetch debug context for keywords when debug mode is on
  useEffect(() => {
    if (!debugMode || !isConnected) {
      setDebugKeywords([]);
      return;
    }

    const fetchDebugContext = async () => {
      try {
        const res = await fetch('http://localhost:8000/debug/context');
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
        const res = await fetch('http://localhost:8000/qa/last');
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
    <div className="min-h-screen bg-slate-950 text-white overflow-hidden">
      {/* Background Orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <GradientOrb
          className="w-[600px] h-[600px] -top-40 -left-40"
          color1="#8b5cf6"
          color2="#3b82f6"
        />
        <GradientOrb
          className="w-[500px] h-[500px] top-1/3 -right-32"
          color1="#06b6d4"
          color2="#8b5cf6"
          delay={1}
        />
        <GradientOrb
          className="w-[400px] h-[400px] -bottom-32 left-1/4"
          color1="#ec4899"
          color2="#8b5cf6"
          delay={2}
        />
      </div>

      {/* Main Content */}
      <div className="relative min-h-screen p-6">
        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-1 h-10 bg-gradient-to-b from-violet-400 to-cyan-400 rounded-full" />
              <div>
                <h1 className="text-3xl font-light tracking-wide text-white/90">LUNA HUB</h1>
                <p className="text-white/40 text-sm tracking-widest uppercase">Engine v2.0</p>
              </div>
            </div>

            {/* Connection Status & Debug Toggle */}
            <div className="flex items-center gap-4">
              {/* QA Toggle with failure indicator */}
              <button
                onClick={() => setQaMode(!qaMode)}
                className={`relative px-3 py-1.5 text-xs rounded-lg border transition-all ${
                  qaFlash
                    ? 'bg-red-500/30 border-red-500/70 text-red-300 animate-pulse'
                    : qaMode
                    ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400'
                    : !qaStatus.passed
                    ? 'bg-red-500/20 border-red-500/50 text-red-400'
                    : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
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
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                  vkMode
                    ? 'bg-pink-500/20 border-pink-500/50 text-pink-400'
                    : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
                }`}
              >
                🔬 VK
              </button>

              {/* Memory Monitor Toggle */}
              <button
                onClick={() => setMemoryMode(!memoryMode)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                  memoryMode
                    ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400'
                    : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
                }`}
              >
                🧠 {memoryMode ? 'MEMORY' : 'Memory'}
              </button>

              {/* Debug Toggle */}
              <button
                onClick={() => setDebugMode(!debugMode)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                  debugMode
                    ? 'bg-red-500/20 border-red-500/50 text-red-400'
                    : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
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

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-400/30 text-red-300 text-sm">
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
            />
          </div>

          {/* Right Panel - Status & Consciousness */}
          <div className="col-span-5 h-full min-h-0 overflow-y-auto space-y-6 pr-2">
            {/* Voice Panel - Voice interaction */}
            <VoicePanel voiceHook={voice} />

            {/* Engine Status */}
            <EngineStatus status={status} isConnected={isConnected} onRelaunch={relaunchSystem} />

            {/* Conversation Cache - What Luna remembers */}
            <ConversationCache isConnected={isConnected} />

            {/* Thought Stream - Luna's internal process */}
            <ThoughtStream apiUrl="http://localhost:8000" />

            {/* Consciousness Monitor */}
            <ConsciousnessMonitor consciousness={consciousness} />
          </div>
        </div>

        {/* Footer */}
        <footer className="fixed bottom-4 left-6 right-6">
          <div className="flex items-center justify-between text-xs text-white/30">
            <div className="flex items-center gap-4">
              <span>Luna Engine v2.0</span>
              <span>|</span>
              <span>Phase 4: Consciousness</span>
            </div>
            <div className="flex items-center gap-2">
              <span>Model:</span>
              <span className="text-violet-400">Claude Sonnet</span>
            </div>
          </div>
        </footer>

        {/* Context Debug Panel */}
        <ContextDebugPanel
          isOpen={debugMode}
          onClose={() => setDebugMode(false)}
        />

        {/* Memory Monitor Panel */}
        <MemoryMonitorPanel
          isOpen={memoryMode}
          onClose={() => setMemoryMode(false)}
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
      </div>
    </div>
  );
};

export default LunaHub;
