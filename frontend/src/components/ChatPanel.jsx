import React, { useState, useRef, useEffect } from 'react';
import GlassCard from './GlassCard';
import { LunaOrb } from './LunaOrb';
import { useOrbState } from '../hooks/useOrbState';
import { VoiceTuningPanel } from './VoiceTuningPanel';
import { OrbSettingsPanel } from './OrbSettingsPanel';

// Highlight keywords in text for debug mode
const highlightKeywords = (text, keywords) => {
  if (!keywords || keywords.length === 0) return text;

  // Create regex pattern for all keywords (word boundaries for better matching)
  const pattern = keywords.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const regex = new RegExp(`\\b(${pattern})\\b`, 'gi');

  const parts = text.split(regex);
  return parts.map((part, i) => {
    const isKeyword = keywords.some(k => k.toLowerCase() === part.toLowerCase());
    if (isKeyword) {
      return (
        <span key={i} className="debug-keyword debug-keyword-active">
          {part}
        </span>
      );
    }
    return part;
  });
};

// Available slash commands
const SLASH_COMMANDS = [
  { command: '/health', description: 'Check all system components', icon: '🏥' },
  { command: '/find-person', description: 'Find a person in memory', icon: '👤', placeholder: '<name>' },
  { command: '/stats', description: 'Database statistics', icon: '📊' },
  { command: '/search', description: 'Search memory nodes', icon: '🔍', placeholder: '<query>' },
  { command: '/recent', description: 'Recent activity (24h)', icon: '🕐' },
  { command: '/extraction', description: 'Extraction pipeline status', icon: '⚙️' },
  { command: '/animate', description: 'Trigger random orb animation', icon: '✨' },
  { command: '/orb', description: 'Show orb state & diagnostics', icon: '🔮' },
  { command: '/orb-test', description: 'Cycle through all animations', icon: '🎬' },
  { command: '/voice-tuning', description: 'Voice tuning panel', icon: '🎤', isPanel: true },
  { command: '/orb-settings', description: 'Orb visual settings', icon: '🟣', isPanel: true },
  { command: '/performance', description: 'Show performance state', icon: '📈' },
  { command: '/emotion', description: 'Set emotion preset', icon: '💜', placeholder: '<name>' },
  { command: '/reset-performance', description: 'Reset to auto-detect', icon: '🔄' },
  { command: '/restart-backend', description: 'Restart Luna backend server', icon: '🔃' },
  { command: '/restart-frontend', description: 'Reload frontend UI', icon: '🔄' },
  { command: '/help', description: 'List all commands', icon: '❓' },
  { command: '/vk', description: 'Run Voight-Kampff identity test', icon: '🧠' },
  { command: '/voight-kampff', description: 'Run full identity verification', icon: '🧠' },
];

const ChatPanel = ({ onSend, isLoading, messages = [], debugKeywords = [] }) => {
  const [input, setInput] = useState('');
  const [showCommands, setShowCommands] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [filteredCommands, setFilteredCommands] = useState(SLASH_COMMANDS);
  const [animationOverride, setAnimationOverride] = useState(null);
  const [activePanel, setActivePanel] = useState(null); // 'voice-tuning' | 'orb-settings' | null
  const [panelData, setPanelData] = useState(null);
  const chatContainerRef = useRef(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const animationTimeoutRef = useRef(null);
  const { orbState, isConnected } = useOrbState();

  // Panel update handlers
  const handleVoiceUpdate = async (values) => {
    await fetch('/slash/voice-tuning', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    });
  };

  const handleOrbUpdate = async (values) => {
    await fetch('/slash/orb-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    });
  };

  // Open panel commands
  const openPanel = async (panelType) => {
    const endpoint = panelType === 'voice-tuning' ? '/slash/voice-tuning' : '/slash/orb-settings';
    const res = await fetch(endpoint);
    const data = await res.json();
    if (data.success !== false) {
      setPanelData(data.data);
      setActivePanel(panelType);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Filter commands based on input
  useEffect(() => {
    if (input.startsWith('/')) {
      const query = input.slice(1).toLowerCase();
      const filtered = SLASH_COMMANDS.filter(cmd =>
        cmd.command.slice(1).toLowerCase().startsWith(query) ||
        cmd.description.toLowerCase().includes(query)
      );
      setFilteredCommands(filtered);
      setShowCommands(filtered.length > 0 && !input.includes(' '));
      setSelectedIndex(0);
    } else {
      setShowCommands(false);
    }
  }, [input]);

  const selectCommand = (cmd) => {
    if (cmd.placeholder) {
      setInput(cmd.command + ' ');
    } else {
      setInput(cmd.command);
    }
    setShowCommands(false);
    inputRef.current?.focus();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const trimmedInput = input.trim().toLowerCase();

    // Handle local orb commands
    if (trimmedInput === '/animate') {
      const result = await onSend('/animate');
      if (result?.animation) {
        setAnimationOverride(result.animation);
        if (animationTimeoutRef.current) clearTimeout(animationTimeoutRef.current);
        animationTimeoutRef.current = setTimeout(() => setAnimationOverride(null), 3000);
      }
      setInput('');
      setShowCommands(false);
      return;
    }

    if (trimmedInput === '/orb') {
      // Pass current orb state to useChat for the status message
      const orbInfo = {
        isConnected,
        animation: orbState.animation || 'idle',
        color: orbState.color || 'default (violet)',
        brightness: orbState.brightness || 1,
        override: animationOverride,
      };
      await onSend('/orb', { orbState: orbInfo });
      setInput('');
      setShowCommands(false);
      return;
    }

    if (trimmedInput === '/orb-test') {
      const result = await onSend('/orb-test');
      if (result?.animations) {
        // Cycle through each animation
        let index = 0;
        const cycleAnimation = () => {
          if (index < result.animations.length) {
            setAnimationOverride(result.animations[index]);
            index++;
            animationTimeoutRef.current = setTimeout(cycleAnimation, 1500);
          } else {
            setAnimationOverride(null);
          }
        };
        if (animationTimeoutRef.current) clearTimeout(animationTimeoutRef.current);
        cycleAnimation();
      }
      setInput('');
      setShowCommands(false);
      return;
    }

    // Handle panel commands
    if (trimmedInput === '/voice-tuning') {
      await openPanel('voice-tuning');
      setInput('');
      setShowCommands(false);
      return;
    }

    if (trimmedInput === '/orb-settings') {
      await openPanel('orb-settings');
      setInput('');
      setShowCommands(false);
      return;
    }

    onSend(input.trim());
    setInput('');
    setShowCommands(false);
  };

  const handleKeyDown = (e) => {
    if (showCommands) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(i => Math.min(i + 1, filteredCommands.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(i => Math.max(i - 1, 0));
      } else if (e.key === 'Tab' || (e.key === 'Enter' && filteredCommands.length > 0)) {
        e.preventDefault();
        selectCommand(filteredCommands[selectedIndex]);
      } else if (e.key === 'Escape') {
        setShowCommands(false);
      }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      handleSubmit(e);
    }
  };

  return (
    <GlassCard className="flex flex-col h-full" padding="p-0" hover={false}>
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-1 h-6 bg-gradient-to-b from-violet-400 to-cyan-400 rounded-full" />
          <h2 className="text-lg font-light tracking-wide text-white/90">Chat</h2>
        </div>
      </div>

      {/* Messages container with floating orb */}
      <div ref={chatContainerRef} className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 relative">
        {/* Luna Orb - Follows conversation with spring physics */}
        <LunaOrb
          state={animationOverride || (!isConnected ? 'disconnected' : (isLoading ? 'processing' : orbState.animation))}
          colorOverride={!isConnected ? null : orbState.color}
          brightness={!isConnected ? 0.7 : orbState.brightness}
          size={56}
          chatContainerRef={chatContainerRef}
          messagesEndRef={messagesEndRef}
        />

        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-white/30 text-sm">
            Start a conversation with Luna
          </div>
        ) : (
          messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-r from-violet-500/20 to-cyan-500/20 border border-violet-400/30 text-white/90'
                    : 'bg-white/5 border border-white/10 text-white/80'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">
                  {debugKeywords.length > 0
                    ? highlightKeywords(msg.content, debugKeywords)
                    : msg.content}
                </p>
                {(msg.model || msg.delegated || msg.local || msg.fallback) && (
                  <div className="mt-2 flex items-center gap-3 text-xs">
                    {/* Model indicator */}
                    {msg.delegated ? (
                      <span className="flex items-center gap-1 text-fuchsia-400">
                        <span>⚡</span>
                        <span>delegated</span>
                      </span>
                    ) : msg.local ? (
                      <span className="flex items-center gap-1 text-emerald-400">
                        <span>●</span>
                        <span>local</span>
                      </span>
                    ) : msg.fallback ? (
                      <span className="flex items-center gap-1 text-amber-400">
                        <span>☁</span>
                        <span>cloud</span>
                      </span>
                    ) : (
                      <span className="text-white/30">{msg.model}</span>
                    )}
                    {msg.tokens && <span className="text-white/30">{msg.tokens} tokens</span>}
                    {msg.latency && <span className="text-white/30">{msg.latency}ms</span>}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white/5 border border-white/10 rounded-2xl px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
                <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" style={{ animationDelay: '0.2s' }} />
                <div className="w-2 h-2 rounded-full bg-pink-400 animate-pulse" style={{ animationDelay: '0.4s' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex-shrink-0 p-4 border-t border-white/10 relative">
        {/* Slash command dropdown */}
        {showCommands && (
          <div className="absolute bottom-full left-4 right-4 mb-2 bg-gray-900/95 backdrop-blur-xl border border-white/10 rounded-xl overflow-hidden shadow-2xl z-50">
            <div className="px-3 py-2 border-b border-white/10">
              <span className="text-xs text-white/40">Commands</span>
            </div>
            <div className="max-h-64 overflow-y-auto">
              {filteredCommands.map((cmd, i) => (
                <button
                  key={cmd.command}
                  type="button"
                  onClick={() => selectCommand(cmd)}
                  className={`w-full px-3 py-2.5 flex items-center gap-3 text-left transition-all ${
                    i === selectedIndex
                      ? 'bg-violet-500/20 border-l-2 border-violet-400'
                      : 'hover:bg-white/5 border-l-2 border-transparent'
                  }`}
                >
                  <span className="text-lg">{cmd.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-white/90">{cmd.command}</span>
                      {cmd.placeholder && (
                        <span className="text-xs text-white/30">{cmd.placeholder}</span>
                      )}
                    </div>
                    <p className="text-xs text-white/50 truncate">{cmd.description}</p>
                  </div>
                  {i === selectedIndex && (
                    <span className="text-xs text-white/30 px-1.5 py-0.5 bg-white/10 rounded">↵</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Luna... (type / for commands)"
            disabled={isLoading}
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white/90 placeholder-white/30 focus:outline-none focus:border-violet-400/50 transition-all disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="px-6 py-3 rounded-xl bg-gradient-to-r from-violet-500/20 to-cyan-500/20 border border-violet-400/30 text-white/80 text-sm hover:border-violet-400/50 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </form>

      {/* Performance Panels */}
      {activePanel === 'voice-tuning' && (
        <div style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 1000
        }}>
          <VoiceTuningPanel
            data={panelData}
            onUpdate={handleVoiceUpdate}
            onClose={() => setActivePanel(null)}
          />
        </div>
      )}

      {activePanel === 'orb-settings' && (
        <div style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 1000
        }}>
          <OrbSettingsPanel
            data={panelData}
            onUpdate={handleOrbUpdate}
            onClose={() => setActivePanel(null)}
          />
        </div>
      )}

      {/* Panel backdrop */}
      {activePanel && (
        <div
          onClick={() => setActivePanel(null)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            zIndex: 999,
          }}
        />
      )}
    </GlassCard>
  );
};

export default ChatPanel;
