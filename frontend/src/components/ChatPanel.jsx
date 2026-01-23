import React, { useState, useRef, useEffect } from 'react';
import GlassCard from './GlassCard';

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

const ChatPanel = ({ onSend, isLoading, messages = [], debugKeywords = [] }) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
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

      {/* Messages - min-h-0 is critical for flex overflow to work */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
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
      <form onSubmit={handleSubmit} className="flex-shrink-0 p-4 border-t border-white/10">
        <div className="flex items-center gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Luna..."
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
    </GlassCard>
  );
};

export default ChatPanel;
