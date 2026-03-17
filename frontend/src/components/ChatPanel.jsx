import React, { useState, useRef, useEffect, useCallback } from 'react';
import GlassCard from './GlassCard';
import { OrbCanvas } from './OrbCanvas';
import { useOrbState } from '../hooks/useOrbState';
import ApertureDial from '../eclissi/components/ApertureDial';
import { VoiceTuningPanel } from './VoiceTuningPanel';
import { OrbSettingsPanel } from './OrbSettingsPanel';
import { FallbackChainPanel } from './FallbackChainPanel';
import { ServerMonitorPanel } from './ServerMonitorPanel';
import AnnotatedText from './AnnotatedText';
import GroundingOverlay, { VerificationToggle, HelpToggle } from './GroundingOverlay';
import { useNavigation } from '../hooks/useNavigation';
import { GridProvider } from '../contexts/GridContext';
import GridLayer from './GridLayer';
import GridDebug from './GridDebug';
import KnowledgeBar from '../eclissi/knowledge/KnowledgeBar';
import ConfirmationCard from './ConfirmationCard';
import { useBadgeConfig } from '../hooks/useBadgeConfig';
import BadgeRow from './BadgeRow';
import ActivityCard from './ActivityCard';
import ThreadCard from './ThreadCard';
import QuestCard from './QuestCard';
import AttentionPrompt from './AttentionPrompt';
import ContextStrip from './ContextStrip';
import TimelineScrubber from './TimelineScrubber';
import WidgetAnchor from './WidgetAnchor';
import TPanels from '../eclissi/knowledge/TPanels';
import VoiceModeBar from '../eclissi/components/VoiceModeBar';
import TBar from '../eclissi/components/TBar';
import { useWindowedMessages } from '../hooks/useWindowedMessages';

// LunaScript feedback (thumbs up/down)
function LunaScriptFeedback({ messageId, lunascript }) {
  const [sent, setSent] = useState(null); // 'up' | 'down' | null
  if (!lunascript) return null;
  const send = async (score) => {
    const label = score > 0.5 ? 'up' : 'down';
    try {
      await fetch('/api/lunascript/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, score }),
      });
      setSent(label);
    } catch {}
  };
  if (sent) return <span className="text-[10px] text-kozmo-muted ml-1">{sent === 'up' ? 'thanks!' : 'noted'}</span>;
  return (
    <span className="ml-1 opacity-40 hover:opacity-100 transition-opacity flex items-center gap-1">
      <button onClick={() => send(1.0)} className="text-[10px] text-emerald-400 hover:text-emerald-300" title="Good response">+</button>
      <button onClick={() => send(0.0)} className="text-[10px] text-red-400 hover:text-red-300" title="Bad response">-</button>
    </span>
  );
}

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
  { command: '/fallback-chain', description: 'Configure inference fallback order', icon: '⛓️', isPanel: true },
  { command: '/server', description: 'Server monitor & management', icon: '🖥️', isPanel: true },
  { command: '/performance', description: 'Show performance state', icon: '📈' },
  { command: '/emotion', description: 'Set emotion preset', icon: '💜', placeholder: '<name>' },
  { command: '/reset-performance', description: 'Reset to auto-detect', icon: '🔄' },
  { command: '/restart-backend', description: 'Restart Luna backend server', icon: '🔃' },
  { command: '/restart-frontend', description: 'Reload frontend UI', icon: '🔄' },
  { command: '/options-test', description: 'Test interactive options widget', icon: '◇' },
  { command: '/help', description: 'List all commands', icon: '❓' },
  { command: '/vk', description: 'Run Voight-Kampff identity test', icon: '🧠' },
  { command: '/voight-kampff', description: 'Run full identity verification', icon: '🧠' },
  { command: '/prompt', description: 'Show last system prompt sent to LLM', icon: '📋' },
  { command: '/faceid', description: 'FaceID: status, set-pin, or reset', icon: '🔐', placeholder: '[set-pin <pin> | reset <pin>]' },
];

/**
 * ActivitySummary — shows the most relevant pipeline events (one per type),
 * with a collapsed count and expand link to Observatory.
 */
function ActivitySummary({ events, navigate }) {
  const [expanded, setExpanded] = useState(false);

  const relevant = events.filter((e) =>
    ['fact_extracted', 'edge_created', 'thread_updated', 'quest_generated'].includes(e.type)
  );
  if (relevant.length === 0) return null;

  // Deduplicate: keep the latest event per type
  const byType = {};
  for (const e of relevant) {
    byType[e.type] = e;
  }
  const deduped = Object.values(byType);

  // Count totals per type for the summary line
  const typeCounts = {};
  for (const e of relevant) {
    typeCounts[e.type] = (typeCounts[e.type] || 0) + 1;
  }

  const summaryParts = [];
  if (typeCounts.fact_extracted) summaryParts.push(`${typeCounts.fact_extracted} facts`);
  if (typeCounts.edge_created) summaryParts.push(`${typeCounts.edge_created} edges`);
  if (typeCounts.thread_updated) summaryParts.push(`thread activity`);
  if (typeCounts.quest_generated) summaryParts.push(`${typeCounts.quest_generated} quests`);

  return (
    <div className="mt-1" style={{ fontSize: 11 }}>
      {/* Summary line */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '3px 12px', color: 'var(--ec-text-faint, #6b7280)',
        }}
      >
        <span style={{ opacity: 0.5 }}>pipeline:</span>
        <span>{summaryParts.join(' · ')}</span>
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#60a5fa', fontSize: 10, padding: 0,
          }}
        >
          {expanded ? 'collapse' : 'expand'}
        </button>
        <button
          onClick={() => navigate({ to: 'observatory' })}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--ec-text-faint, #6b7280)', fontSize: 10, padding: 0,
            marginLeft: 'auto',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = '#60a5fa'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--ec-text-faint, #6b7280)'; }}
        >
          full report →
        </button>
      </div>

      {/* Expanded: show individual cards */}
      {expanded && (
        <div className="flex flex-col">
          {deduped.map((event, i) => (
            <ActivityCard key={`activity-${i}`} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}

const ChatPanel = ({ onSend, isLoading, messages = [], debugKeywords = [], entities = [], identityName = null, identityTier = null, extractions = [], extractionEntities = [], extractionRelationships = [], pendingEntities = [], onConfirmEntity, onRejectEntity, voice = null, activeProjectSlug = null, knowledgeEvents = [], guardianOpen = false, onToggleGuardian = null, consciousness = null }) => {
  const [input, setInput] = useState('');
  const [showCommands, setShowCommands] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [filteredCommands, setFilteredCommands] = useState(SLASH_COMMANDS);
  const [animationOverride, setAnimationOverride] = useState(null);
  const [activePanel, setActivePanel] = useState(null); // 'voice-tuning' | 'orb-settings' | null
  const [panelData, setPanelData] = useState(null);
  const [activeTPanel, setActiveTPanel] = useState(null); // index of message with open T-panels
  const [verificationMode, setVerificationMode] = useState(false); // GroundingLink verification UI
  const [helpMode, setHelpMode] = useState(false); // Luna system knowledge help mode
  const chatContainerRef = useRef(null);
  const gridContainerRef = useRef(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const animationTimeoutRef = useRef(null);
  const orbCanvasRef = useRef(null);
  const hideApertureTimeout = useRef(null);
  const { orbState, isConnected } = useOrbState();
  const { navigate } = useNavigation();
  const { config: badgeConfig } = useBadgeConfig();

  // Aperture state
  const [apertureAngle, setApertureAngle] = useState(55);
  const [apertureVisible, setApertureVisible] = useState(false);
  const [orbCenter, setOrbCenter] = useState(null);

  // Fetch aperture on mount
  useEffect(() => {
    fetch('/api/aperture').then(r => r.json()).then(d => {
      if (d.angle) setApertureAngle(d.angle);
    }).catch(() => {});
  }, []);

  // Proximity listener — tracks orb center + auto-hides aperture after 1s away
  useEffect(() => {
    const UPDATE_RADIUS = 160;
    const HIDE_DELAY = 1000;
    const onMove = (e) => {
      if (!orbCanvasRef.current) return;
      const rect = orbCanvasRef.current.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dist = Math.hypot(e.clientX - cx, e.clientY - cy);
      if (dist < UPDATE_RADIUS) {
        setOrbCenter({ x: cx, y: cy });
        clearTimeout(hideApertureTimeout.current);
      } else if (apertureVisible) {
        if (!hideApertureTimeout.current) {
          hideApertureTimeout.current = setTimeout(() => {
            setApertureVisible(false);
            hideApertureTimeout.current = null;
          }, HIDE_DELAY);
        }
      }
    };
    window.addEventListener('mousemove', onMove);
    return () => {
      window.removeEventListener('mousemove', onMove);
      clearTimeout(hideApertureTimeout.current);
    };
  }, [apertureVisible]);

  // Aperture toggle — shift+left-click on orb
  const handleOrbClick = useCallback((e) => {
    if (e.shiftKey) {
      e.preventDefault();
      if (!orbCanvasRef.current) return;
      const rect = orbCanvasRef.current.getBoundingClientRect();
      setOrbCenter({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
      setApertureVisible(v => !v);
    }
    // Normal clicks on orb do nothing — use /orb-settings command instead
  }, []);

  const handleApertureChange = useCallback((angle) => {
    setApertureAngle(angle);
    const presets = { tunnel: 15, narrow: 35, balanced: 55, wide: 75, open: 95 };
    let nearest = 'balanced';
    let minDist = Infinity;
    for (const [name, a] of Object.entries(presets)) {
      if (Math.abs(a - angle) < minDist) { minDist = Math.abs(a - angle); nearest = name; }
    }
    fetch('/api/aperture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset: nearest, angle }),
    }).catch(() => {});
  }, []);

  // Windowed message rendering (Guardian pattern)
  const {
    visibleMessages,
    onScroll: handleWindowScroll,
    scrollRef: windowScrollRef,
    canLoadOlder,
    scrollToBottom: windowScrollToBottom,
    isAtBottom: isAtBottomRef,
  } = useWindowedMessages(messages);

  // Merge scroll refs
  const mergeScrollRefs = useCallback((el) => {
    chatContainerRef.current = el;
    windowScrollRef.current = el;
  }, [windowScrollRef]);

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
    if (panelType === 'orb-settings') {
      // Physics sliders are client-side; backend data is optional
      try {
        const res = await fetch('/slash/orb-settings');
        const data = await res.json();
        if (data.success !== false) setPanelData(data.data);
      } catch { /* panel works without backend data */ }
      setActivePanel('orb-settings');
      return;
    }
    const endpoint = panelType === 'voice-tuning' ? '/slash/voice-tuning' : '/slash/orb-settings';
    const res = await fetch(endpoint);
    const data = await res.json();
    if (data.success !== false) {
      setPanelData(data.data);
      setActivePanel(panelType);
    }
  };

  // Auto-scroll when new messages arrive (only if user was at bottom)
  useEffect(() => {
    if (isAtBottomRef.current) {
      windowScrollToBottom();
    }
  }, [messages.length, windowScrollToBottom]);

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

    // P0 FIX: Preserve capitalization for messages
    // See: Docs/HANDOFF_Luna_Voice_Restoration.md
    const trimmedInput = input.trim();  // Preserves case for messages
    const commandInput = trimmedInput.toLowerCase();  // Lowercase only for command detection

    // Handle local orb commands
    if (commandInput === '/animate') {
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

    if (commandInput === '/orb') {
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

    if (commandInput === '/orb-test') {
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
    if (commandInput === '/voice-tuning') {
      await openPanel('voice-tuning');
      setInput('');
      setShowCommands(false);
      return;
    }

    if (commandInput === '/orb-settings') {
      await openPanel('orb-settings');
      setInput('');
      setShowCommands(false);
      return;
    }

    if (commandInput === '/fallback-chain') {
      setActivePanel('fallback-chain');
      setInput('');
      setShowCommands(false);
      return;
    }

    if (commandInput === '/server') {
      setActivePanel('server');
      setInput('');
      setShowCommands(false);
      return;
    }

    // Send message with original capitalization preserved
    onSend(trimmedInput);
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
    <GlassCard className="flex flex-col h-full" padding="p-0" hover={false} glow>
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-kozmo-border">
        <div className="flex items-center gap-3">
          <div className="w-1 h-6 bg-kozmo-accent rounded-full" style={{ boxShadow: '0 0 12px rgba(192,132,252,0.5), 0 0 4px rgba(192,132,252,0.8)' }} />
          <h2 className="text-lg font-display font-semibold tracking-tight text-white/90">Chat</h2>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
            <HelpToggle enabled={helpMode} onChange={setHelpMode} />
            <VerificationToggle enabled={verificationMode} onChange={setVerificationMode} />
          </div>
        </div>
      </div>

      {/* Messages container with floating orb + grid */}
      <GridProvider containerRef={gridContainerRef}>
      <div ref={gridContainerRef} style={{ position: 'relative', display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        {/* Grid canvas — spatial index for orb navigation (fixed layer) */}
        <GridLayer />
        <GridDebug />

        {/* Context strip + timeline above messages */}
        <div style={{ flexShrink: 0, padding: '4px 16px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ flex: 1 }}>
              <ContextStrip
                consciousness={consciousness}
                entities={entities}
                sessionStart={messages[0]?.timestamp || messages[0]?.created_at}
              />
            </div>
            <TimelineScrubber />
          </div>
        </div>

        {/* Scrollable message list */}
        <div ref={mergeScrollRefs} onScroll={handleWindowScroll} className="overflow-y-auto p-4 space-y-4" style={{ flex: 1, minHeight: 0 }}>

        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-kozmo-muted text-sm">
            Start a conversation with Luna
          </div>
        ) : (
          <>
            {canLoadOlder && (
              <div style={{
                textAlign: 'center',
                padding: '8px',
                color: 'var(--ec-text-faint, #5a5a70)',
                fontSize: 11,
              }}>
                Scroll up for older messages
              </div>
            )}
            {visibleMessages.map((msg) => (
              <React.Fragment key={msg.id}>
                <div
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded px-4 py-3 ${
                      msg.role === 'user'
                        ? 'bg-kozmo-accent/10 border border-kozmo-accent/30 text-white/90'
                        : 'bg-kozmo-surface border border-kozmo-border text-white/80'
                    }`}
                    style={msg.role === 'assistant' && msg.metadata?.life_state ? {
                      borderLeft: `2.5px solid ${
                        msg.metadata.life_state === 'personal' ? '#5b8fa8' :
                        msg.metadata.life_state === 'project' ? '#7a9e6d' :
                        msg.metadata.life_state === 'bridge' ? '#c4975a' :
                        msg.metadata.life_state === 'mixed' ? '#9a7fb5' :
                        'transparent'
                      }`,
                    } : undefined}
                    data-state={msg.role === 'assistant' ? (msg.metadata?.life_state || undefined) : undefined}
                  >
                    <div className="text-sm whitespace-pre-wrap">
                      {debugKeywords.length > 0
                        ? <p>{highlightKeywords(msg.content, debugKeywords)}</p>
                        : msg.role === 'assistant'
                        ? <GroundingOverlay
                            text={msg.content}
                            groundingMetadata={msg.groundingMetadata}
                            verificationMode={verificationMode}
                            entities={entities}
                            onEntityClick={(entityId) => navigate({ to: 'observatory', tab: 'entities', entityId })}
                          />
                        : <AnnotatedText
                            text={msg.content}
                            entities={entities}
                            onEntityClick={(entityId) => navigate({ to: 'observatory', tab: 'entities', entityId })}
                          />}
                    </div>
                    <BadgeRow msg={msg} badgeConfig={badgeConfig} />
                    {msg.lunascript && !msg.streaming && msg.role === 'assistant' && (
                      <LunaScriptFeedback messageId={msg.id} lunascript={msg.lunascript} />
                    )}
                  </div>
                  {msg.widget && !msg.streaming && (
                    <WidgetAnchor
                      widget={msg.widget}
                      onSelect={(value) => onSend(value)}
                    />
                  )}
                </div>

                {/* Knowledge Bar — shown after the last assistant message if extractions exist */}
                {msg.role === 'assistant' && !msg.streaming &&
                  msg.id === messages[messages.length - 1]?.id &&
                  extractions.length > 0 && (
                  <KnowledgeBar
                    extractions={extractions}
                    liveEvents={knowledgeEvents.filter((e) => e.type === 'fact_extracted')}
                    isActive={activeTPanel === msg.id}
                    onClick={() => setActiveTPanel(activeTPanel === msg.id ? null : msg.id)}
                  />
                )}

                {/* Confirmation Cards — entity approval prompts after last assistant message */}
                {msg.role === 'assistant' && !msg.streaming &&
                  msg.id === messages[messages.length - 1]?.id &&
                  pendingEntities.length > 0 && (
                  <div className="flex flex-col gap-1 mt-1">
                    {pendingEntities.map((entity) => (
                      <ConfirmationCard
                        key={entity.entity_id}
                        entity={entity}
                        onConfirm={onConfirmEntity}
                        onReject={onRejectEntity}
                        onEntityClick={(entityId) => navigate({ to: 'observatory', tab: 'entities', entityId })}
                      />
                    ))}
                  </div>
                )}

                {/* Activity Cards — most relevant pipeline events after last assistant message */}
                {badgeConfig.show_knowledge_events &&
                  msg.role === 'assistant' && !msg.streaming &&
                  msg.id === messages[messages.length - 1]?.id &&
                  knowledgeEvents.length > 0 && (
                  <ActivitySummary events={knowledgeEvents} navigate={navigate} />
                )}

                {/* Thread Card — active thread after last assistant message */}
                {msg.role === 'assistant' && !msg.streaming &&
                  msg.id === messages[messages.length - 1]?.id &&
                  (() => {
                    const threadEvent = [...knowledgeEvents].reverse().find(
                      (e) => e.type === 'thread_updated' && (e.payload?.status === 'active' || e.payload?.status === 'resumed')
                    );
                    return threadEvent ? <ThreadCard thread={threadEvent.payload} /> : null;
                  })()}

                {/* Quest Cards — quest notifications after last assistant message */}
                {msg.role === 'assistant' && !msg.streaming &&
                  msg.id === messages[messages.length - 1]?.id &&
                  knowledgeEvents
                    .filter((e) => e.type === 'quest_generated')
                    .slice(-3)
                    .map((e, i) => (
                      <QuestCard key={`quest-${i}`} quest={e.payload} />
                    ))}

                {/* Attention Prompts — entities mentioned frequently across extractions */}
                {msg.role === 'assistant' && !msg.streaming &&
                  msg.id === messages[messages.length - 1]?.id &&
                  (() => {
                    // Count how often each entity name appears across fact_extracted events
                    const counts = {};
                    knowledgeEvents.forEach((e) => {
                      if (e.type === 'fact_extracted' && e.payload?.entities) {
                        for (const name of e.payload.entities) {
                          counts[name] = (counts[name] || 0) + 1;
                        }
                      }
                    });
                    return Object.entries(counts)
                      .filter(([, count]) => count >= 3)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 2)
                      .map(([name, count]) => (
                        <AttentionPrompt key={`attn-${name}`} entityName={name} mentionCount={count} />
                      ));
                  })()}
              </React.Fragment>
            ))}
          </>
        )}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-kozmo-surface border border-kozmo-border rounded px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-kozmo-accent animate-pulse" />
                <div className="w-2 h-2 rounded-full bg-kozmo-accent animate-pulse" style={{ animationDelay: '0.2s' }} />
                <div className="w-2 h-2 rounded-full bg-kozmo-accent animate-pulse" style={{ animationDelay: '0.4s' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
        </div>
        {/* END scroll div */}

        {/* Fixed overlay layer — orb, aperture, and T-panels stay pinned to wrapper */}
        <OrbCanvas
          ref={orbCanvasRef}
          state={animationOverride || (!isConnected ? 'disconnected' : (isLoading ? 'processing' : orbState.animation))}
          colorOverride={!isConnected ? null : orbState.color}
          brightness={!isConnected ? 0.7 : orbState.brightness}
          size={56}
          chatContainerRef={gridContainerRef}
          messagesEndRef={messagesEndRef}
          rendererState={orbState.renderer}
          onClick={handleOrbClick}
        />

        <ApertureDial
          angle={apertureAngle}
          onChange={handleApertureChange}
          visible={apertureVisible}
          orbCenter={orbCenter}
        />

        {activeTPanel !== null && (
          <TPanels
            extractions={extractions}
            entities={extractionEntities}
            relationships={extractionRelationships}
            onClose={() => setActiveTPanel(null)}
          />
        )}
      </div>
      </GridProvider>

      {/* Voice Mode Bar */}
      {voice?.isRunning && (
        <VoiceModeBar
          voiceState={voice.voiceState}
          isListening={voice.isListening}
          isSpeaking={voice.isSpeaking}
          isThinking={voice.isThinking}
          onClose={voice.stopVoice}
        />
      )}

      {/* T-Bar — Guardian Luna toggle */}
      <TBar
        extractionCount={knowledgeEvents.filter((e) => e.type === 'extraction_batch').length}
        isOpen={guardianOpen}
        onToggle={onToggleGuardian}
      />

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex-shrink-0 p-4 border-t border-kozmo-border relative">
        {/* Slash command dropdown */}
        {showCommands && (
          <div className="absolute bottom-full left-4 right-4 mb-2 bg-kozmo-surface backdrop-blur-xl border border-kozmo-border rounded overflow-hidden shadow-2xl z-50">
            <div className="px-3 py-2 border-b border-kozmo-border">
              <span className="text-xs text-kozmo-muted">Commands</span>
            </div>
            <div className="max-h-64 overflow-y-auto">
              {filteredCommands.map((cmd, i) => (
                <button
                  key={cmd.command}
                  type="button"
                  onClick={() => selectCommand(cmd)}
                  className={`w-full px-3 py-2.5 flex items-center gap-3 text-left transition-all ${
                    i === selectedIndex
                      ? 'bg-kozmo-accent/20 border-l-2 border-kozmo-accent'
                      : 'hover:bg-kozmo-surface border-l-2 border-transparent'
                  }`}
                >
                  <span className="text-lg">{cmd.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-white/90">{cmd.command}</span>
                      {cmd.placeholder && (
                        <span className="text-xs text-kozmo-muted">{cmd.placeholder}</span>
                      )}
                    </div>
                    <p className="text-xs text-kozmo-muted truncate">{cmd.description}</p>
                  </div>
                  {i === selectedIndex && (
                    <span className="text-xs text-kozmo-muted px-1.5 py-0.5 bg-kozmo-surface rounded">↵</span>
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
            placeholder={activeProjectSlug
              ? (identityName ? `Message Luna about ${activeProjectSlug}... (as ${identityName})` : `Message Luna about ${activeProjectSlug}...`)
              : (identityName ? `Message Luna... (as ${identityName})` : "Message Luna... (type / for commands)")}
            disabled={isLoading}
            className="flex-1 font-mono bg-kozmo-surface border border-kozmo-border rounded px-4 py-3 text-sm text-white/90 placeholder-white/30 focus:outline-none focus:border-kozmo-accent/50 transition-all disabled:opacity-50"
            style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03), 0 2px 8px rgba(0,0,0,0.3)' }}
          />
          {/* Mic button */}
          {voice && (
            <button
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                if (!voice.isRunning) {
                  voice.startVoice(false);
                } else if (!voice.isListening) {
                  voice.startListening();
                }
              }}
              onMouseUp={() => {
                if (voice.isListening) voice.stopListening();
              }}
              onMouseLeave={() => {
                if (voice.isListening) voice.stopListening();
              }}
              style={{
                width: 40,
                height: 40,
                borderRadius: 8,
                border: voice.isRunning
                  ? '1px solid rgba(192,132,252,0.5)'
                  : '1px solid var(--ec-border, rgba(255,255,255,0.06))',
                background: voice.isListening
                  ? 'rgba(192,132,252,0.3)'
                  : voice.isRunning
                  ? 'rgba(192,132,252,0.12)'
                  : 'rgba(255,255,255,0.03)',
                color: voice.isRunning ? 'var(--ec-accent-luna, #c084fc)' : 'var(--ec-text-faint, #5a5a70)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                transition: 'all 0.2s ease',
                animation: voice.isListening ? 'ec-mic-pulse 1.5s ease-in-out infinite' : 'none',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            </button>
          )}

          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="px-6 py-3 rounded text-white/90 text-sm font-medium transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              background: 'linear-gradient(135deg, rgba(192,132,252,0.2), rgba(129,140,248,0.15))',
              border: '1px solid rgba(192,132,252,0.3)',
              boxShadow: '0 0 20px rgba(192,132,252,0.1), inset 0 1px 0 rgba(255,255,255,0.05)',
            }}
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
          top: 16,
          left: 16,
          zIndex: 1000
        }}>
          <OrbSettingsPanel
            data={panelData}
            onUpdate={handleOrbUpdate}
            onClose={() => setActivePanel(null)}
          />
        </div>
      )}

      {activePanel === 'fallback-chain' && (
        <div style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 1000
        }}>
          <FallbackChainPanel
            onClose={() => setActivePanel(null)}
          />
        </div>
      )}

      {activePanel === 'server' && (
        <div style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 1000
        }}>
          <ServerMonitorPanel
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
