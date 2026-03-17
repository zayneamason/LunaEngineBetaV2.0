import React, { useState, useEffect, useRef } from 'react';
import { ChatPanel } from '../components';
import { useLunaAPI } from '../hooks/useLunaAPI';
import { useIdentity } from '../hooks/useIdentity';
import { useChat } from '../hooks/useChat';
import { useVoice } from '../hooks/useVoice';
import { useExtractions } from '../hooks/useExtractions';
import { useKnowledgeStream } from '../hooks/useKnowledgeStream';
import { useGuardianLuna, useGuardianEventAggregator, useGuardianStats } from '../hooks/useGuardianLuna';
import GuardianLunaPanel from './components/GuardianLunaPanel';

const CHAT_STORAGE_KEY = 'luna_chat_messages';

const EclissiHome = ({ activeProjectSlug }) => {
  const {
    status,
    consciousness,
    isConnected,
    error: apiError,
    relaunchSystem,
    refresh,
  } = useLunaAPI();

  const {
    messages,
    context,
    isStreaming,
    error: chatError,
    send,
  } = useChat();

  const {
    identity, isPresent, entityName, lunaTier, confidence,
  } = useIdentity();

  const voice = useVoice();
  const lastSpokenMsgId = useRef(null);

  // T-shape knowledge panel data
  const extractionData = useExtractions(isConnected);

  // Live knowledge stream (replaces polling — falls back to useExtractions)
  const { events: knowledgeEvents, pendingEntities, confirmEntity, rejectEntity } = useKnowledgeStream();

  // Guardian Luna panel state + event aggregation
  const guardian = useGuardianLuna();
  useGuardianEventAggregator(knowledgeEvents);
  useGuardianStats();

  // Entity data for keyword highlighting
  const [knownEntities, setKnownEntities] = useState([]);

  // Fetch entity list for highlighting
  useEffect(() => {
    let cancelled = false;
    let retryTimer = null;

    const fetchEntities = async (attempt = 0) => {
      if (cancelled) return;
      const projectParam = activeProjectSlug ? `?project=${activeProjectSlug}` : '';
      try {
        const res = await fetch(`/api/entities${projectParam}`);
        if (res.ok) {
          const data = await res.json();
          if (data?.entities?.length > 0) {
            setKnownEntities(data.entities);
            return;
          }
        }
      } catch {}
      try {
        const res = await fetch(`/observatory/api/entities${projectParam}`);
        if (res.ok) {
          const data = await res.json();
          if (data?.entities?.length > 0) {
            setKnownEntities(data.entities);
            return;
          }
        }
      } catch {}
      if (attempt < 5) {
        const delay = Math.min(2000 * Math.pow(2, attempt), 30000);
        retryTimer = setTimeout(() => fetchEntities(attempt + 1), delay);
      }
    };

    fetchEntities();
    return () => { cancelled = true; if (retryTimer) clearTimeout(retryTimer); };
  }, [activeProjectSlug]);

  // Persist messages to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      try {
        localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
      } catch (e) {
        console.warn('Failed to save chat to localStorage:', e);
      }
    }
  }, [messages]);

  // Speak completed assistant responses
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

  // Check QA status after each response (log-only, widget handles display)
  useEffect(() => {
    if (isStreaming || !isConnected) return;

    const checkQA = async () => {
      try {
        const res = await fetch('/qa/last');
        if (!res.ok) return;
        const report = await res.json();
        if (report.error) return;

        if (!report.passed) {
          console.warn(
            '%c QA FAILED',
            'background: #ef4444; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;',
            `\n${report.failed_count} assertion(s) failed for: "${report.query}"\n`,
            report.diagnosis || 'No diagnosis available'
          );
          report.assertions?.filter(a => !a.passed).forEach(a => {
            console.warn(`  [${a.severity}] ${a.name}: ${a.actual}`);
          });
        }
      } catch {}
    };

    const timeout = setTimeout(checkQA, 500);
    return () => clearTimeout(timeout);
  }, [isStreaming, messages.length, isConnected]);

  const error = chatError || apiError;

  return (
    <div style={{ display: 'flex', height: '100%', background: 'var(--ec-bg)' }}>
      {/* Chat column */}
      <div className="relative" style={{ flex: 1, minWidth: 0, height: '100%' }}>
        {/* Ambient glow layers */}
        <div
          style={{
            position: 'absolute', top: '-10%', left: '-5%', width: '500px', height: '500px',
            background: 'radial-gradient(circle, rgba(192,132,252,0.08) 0%, transparent 70%)',
            borderRadius: '50%', filter: 'blur(80px)', pointerEvents: 'none', zIndex: 0,
            animation: 'ambient-drift 20s ease-in-out infinite, ambient-breathe 8s ease-in-out infinite',
          }}
        />
        <div
          style={{
            position: 'absolute', bottom: '-15%', right: '-5%', width: '600px', height: '600px',
            background: 'radial-gradient(circle, rgba(129,140,248,0.06) 0%, transparent 70%)',
            borderRadius: '50%', filter: 'blur(100px)', pointerEvents: 'none', zIndex: 0,
            animation: 'ambient-drift 25s ease-in-out infinite reverse, ambient-breathe 10s ease-in-out infinite 2s',
          }}
        />
        <div
          style={{
            position: 'absolute', top: '40%', right: '20%', width: '400px', height: '400px',
            background: 'radial-gradient(circle, rgba(52,211,153,0.04) 0%, transparent 70%)',
            borderRadius: '50%', filter: 'blur(100px)', pointerEvents: 'none', zIndex: 0,
            animation: 'ambient-drift 30s ease-in-out infinite 5s, ambient-breathe 12s ease-in-out infinite 4s',
          }}
        />

        {/* Conversation Spine */}
        <div
          style={{
            position: 'relative',
            zIndex: 1,
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            padding: '16px 24px',
          }}
        >
          {/* Error Banner */}
          {error && (
            <div
              style={{
                marginBottom: 12,
                padding: '10px 14px',
                borderRadius: 8,
                background: 'rgba(248,113,113,0.1)',
                border: '1px solid rgba(248,113,113,0.3)',
                color: 'var(--ec-accent-qa)',
                fontSize: 13,
                flexShrink: 0,
              }}
            >
              {error}
            </div>
          )}

          {/* Chat fills remaining space */}
          <div style={{ flex: 1, minHeight: 0 }}>
            <ChatPanel
              messages={messages}
              onSend={send}
              isLoading={isStreaming}
              debugKeywords={[]}
              entities={knownEntities}
              identityName={isPresent ? entityName : null}
              identityTier={isPresent ? lunaTier : null}
              extractions={extractionData.extractions}
              extractionEntities={extractionData.entities}
              extractionRelationships={extractionData.relationships}
              pendingEntities={pendingEntities}
              onConfirmEntity={confirmEntity}
              onRejectEntity={rejectEntity}
              voice={voice}
              activeProjectSlug={activeProjectSlug}
              knowledgeEvents={knowledgeEvents}
              consciousness={consciousness}
              guardianOpen={guardian.isOpen}
              onToggleGuardian={guardian.toggle}
            />
          </div>
        </div>
      </div>

      {/* Guardian Luna panel — slides in from right */}
      {guardian.isOpen && (
        <GuardianLunaPanel
          messages={guardian.messages}
          stats={guardian.stats}
          onClose={guardian.close}
          onSend={guardian.sendMessage}
          inputText={guardian.inputText}
          onInputChange={guardian.setInputText}
        />
      )}
    </div>
  );
};

export default EclissiHome;
