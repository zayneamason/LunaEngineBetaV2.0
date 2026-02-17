/**
 * CODEX Production Board — Master planning view over LAB briefs
 *
 * Grouped board (status/priority/assignee/character), dependency graph,
 * AI chat per brief, bulk operations.
 *
 * Ported from prototype: ClaudeArtifacts/files 3/codex_production_board.jsx
 * Wired to real API via useBoardAPI + useLabAPI hooks.
 */
import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useBoardAPI } from '../hooks/useBoardAPI';
import { useLabAPI } from '../hooks/useLabAPI';

// --- Config ---
const STATUS_CONFIG = {
  planning: { icon: '○', label: 'Planning', color: '#818cf8', order: 0 },
  rigging: { icon: '◎', label: 'Rigging', color: '#fbbf24', order: 1 },
  queued: { icon: '◉', label: 'Queued', color: '#c084fc', order: 2 },
  generating: { icon: '⟳', label: 'Generating', color: '#34d399', order: 3 },
  review: { icon: '◈', label: 'Review', color: '#38bdf8', order: 4 },
  approved: { icon: '✓', label: 'Approved', color: '#4ade80', order: 5 },
  locked: { icon: '◆', label: 'Locked', color: '#4ade80', order: 6 },
};

const PRIORITY_CONFIG = {
  critical: { label: 'Critical', color: '#f87171' },
  high: { label: 'High', color: '#fb923c' },
  medium: { label: 'Medium', color: '#fbbf24' },
  low: { label: 'Low', color: '#64748b' },
};

const AGENTS = [
  { id: 'luna', name: 'Luna', color: '#c084fc', icon: '☾' },
  { id: 'maya', name: 'Maya', color: '#34d399', icon: '◐' },
  { id: 'chiba', name: 'Chiba', color: '#38bdf8', icon: '◈' },
  { id: 'ben', name: 'Ben', color: '#fbbf24', icon: '✎' },
];

const GROUP_OPTIONS = [
  { id: 'status', label: 'Status' },
  { id: 'priority', label: 'Priority' },
  { id: 'assignee', label: 'Assignee' },
  { id: 'character', label: 'Character' },
  { id: 'type', label: 'Type' },
];

// --- Brief Row ---
function BriefRow({ brief, isSelected, onClick, onStatusChange }) {
  const st = STATUS_CONFIG[brief.status] || STATUS_CONFIG.planning;
  const pr = PRIORITY_CONFIG[brief.priority] || PRIORITY_CONFIG.medium;
  const agent = AGENTS.find(a => a.id === brief.assignee);

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
        borderRadius: 4, cursor: 'pointer', transition: 'all 0.12s',
        background: isSelected ? 'rgba(129, 140, 248, 0.06)' : 'transparent',
        borderLeft: isSelected ? '2px solid #818cf8' : '2px solid transparent',
      }}
      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'rgba(255,255,255,0.015)'; }}
      onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
    >
      {/* Status dot */}
      <div
        onClick={e => { e.stopPropagation(); onStatusChange?.(brief.id); }}
        style={{
          width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: st.color + '20', cursor: 'pointer',
        }}
        title={`Status: ${st.label} (click to cycle)`}
      >
        <span style={{ fontSize: 8, color: st.color }}>{st.icon}</span>
      </div>

      {/* Priority */}
      <span style={{
        fontSize: 7, padding: '2px 5px', borderRadius: 2,
        background: pr.color + '15', color: pr.color, fontWeight: 600,
        letterSpacing: 0.5, whiteSpace: 'nowrap',
      }}>{pr.label.charAt(0)}</span>

      {/* Title */}
      <span style={{ flex: 1, fontSize: 11, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {brief.title}
      </span>

      {/* Type badge */}
      <span style={{ fontSize: 8, color: '#4a4a5a', whiteSpace: 'nowrap' }}>{brief.type}</span>

      {/* Indicators */}
      {brief.dependencies?.length > 0 && (
        <span style={{ fontSize: 8, color: '#f87171' }} title="Has dependencies">⚑</span>
      )}
      {brief.ai_thread?.length > 0 && (
        <span style={{ fontSize: 8, color: '#818cf8' }} title="Has discussion">💬</span>
      )}

      {/* Progress */}
      {brief.progress != null && (
        <span style={{ fontSize: 9, color: '#34d399', fontFamily: "'JetBrains Mono', monospace" }}>{brief.progress}%</span>
      )}

      {/* Assignee */}
      {agent && (
        <span style={{ fontSize: 10, color: agent.color }} title={agent.name}>{agent.icon}</span>
      )}
    </div>
  );
}

// --- Group Header ---
function GroupHeader({ label, count, color, isOpen, onToggle }) {
  return (
    <div
      onClick={onToggle}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
        cursor: 'pointer', borderBottom: '1px solid #1a1a24',
      }}
    >
      <span style={{
        fontSize: 10, color: '#4a4a5a',
        transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)',
        transition: 'transform 0.15s',
      }}>▸</span>
      <span style={{ fontSize: 11, color: color || '#e2e8f0', fontWeight: 600 }}>{label}</span>
      <span style={{
        fontSize: 9, padding: '1px 6px', borderRadius: 3,
        background: (color || '#818cf8') + '15',
        color: color || '#818cf8',
      }}>{count}</span>
    </div>
  );
}

// --- Detail Panel ---
function DetailPanel({ brief, onClose, onUpdate, boardAPI }) {
  const [tab, setTab] = useState('details');
  const [chatInput, setChatInput] = useState('');
  const [chatAgent, setChatAgent] = useState('luna');
  const [thread, setThread] = useState(brief.ai_thread || []);
  const [deps, setDeps] = useState(null);
  const chatEndRef = useRef(null);

  const st = STATUS_CONFIG[brief.status] || STATUS_CONFIG.planning;

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thread]);

  useEffect(() => {
    if (tab === 'deps' && !deps) {
      boardAPI.checkDependencies(brief.id).then(d => { if (d) setDeps(d); });
    }
  }, [tab, brief.id, boardAPI, deps]);

  // Reload thread from brief
  useEffect(() => {
    setThread(brief.ai_thread || []);
    setDeps(null);
  }, [brief.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSendChat = async () => {
    if (!chatInput.trim()) return;
    const result = await boardAPI.addThreadMessage(brief.id, chatAgent, chatInput.trim());
    if (result?.thread) setThread(result.thread);
    setChatInput('');
  };

  const statusOrder = Object.keys(STATUS_CONFIG);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'rgba(10, 10, 16, 0.4)' }}>
      {/* Header */}
      <div style={{ padding: '10px 14px', borderBottom: '1px solid #1e1e2e', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600 }}>{brief.title}</div>
          <div style={{ fontSize: 9, color: '#4a4a5a', marginTop: 2 }}>{brief.type} · {brief.id}</div>
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: '#4a4a5a', fontSize: 14, cursor: 'pointer',
        }}>×</button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #1e1e2e' }}>
        {[
          { id: 'details', label: 'Details' },
          { id: 'ai', label: 'AI Chat' },
          { id: 'deps', label: 'Dependencies' },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            flex: 1, padding: '8px 0', fontSize: 9, border: 'none',
            borderBottom: tab === t.id ? '2px solid #818cf8' : '2px solid transparent',
            background: 'transparent', color: tab === t.id ? '#818cf8' : '#4a4a5a',
            cursor: 'pointer', fontFamily: 'inherit', letterSpacing: 1,
          }}>{t.label}</button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        {tab === 'details' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* Status pipeline */}
            <div>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>STATUS</div>
              <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                {statusOrder.map(s => {
                  const cfg = STATUS_CONFIG[s];
                  return (
                    <button key={s} onClick={() => onUpdate?.({ status: s })} style={{
                      padding: '3px 8px', borderRadius: 3, border: 'none',
                      background: brief.status === s ? cfg.color + '20' : 'transparent',
                      color: brief.status === s ? cfg.color : '#3a3a50',
                      fontSize: 9, cursor: 'pointer', fontFamily: 'inherit',
                    }}>{cfg.icon} {cfg.label}</button>
                  );
                })}
              </div>
            </div>

            {/* Priority */}
            <div>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>PRIORITY</div>
              <div style={{ display: 'flex', gap: 3 }}>
                {Object.entries(PRIORITY_CONFIG).map(([id, cfg]) => (
                  <button key={id} onClick={() => onUpdate?.({ priority: id })} style={{
                    padding: '3px 8px', borderRadius: 3, border: 'none',
                    background: brief.priority === id ? cfg.color + '20' : 'transparent',
                    color: brief.priority === id ? cfg.color : '#3a3a50',
                    fontSize: 9, cursor: 'pointer', fontFamily: 'inherit',
                  }}>{cfg.label}</button>
                ))}
              </div>
            </div>

            {/* Assignee */}
            <div>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>ASSIGNEE</div>
              <div style={{ display: 'flex', gap: 4 }}>
                {AGENTS.map(a => (
                  <button key={a.id} onClick={() => onUpdate?.({ assignee: a.id })} style={{
                    padding: '4px 10px', borderRadius: 4, border: 'none',
                    background: brief.assignee === a.id ? a.color + '20' : 'rgba(18, 18, 26, 0.5)',
                    color: brief.assignee === a.id ? a.color : '#4a4a5a',
                    fontSize: 10, cursor: 'pointer', fontFamily: 'inherit',
                    display: 'flex', alignItems: 'center', gap: 4,
                  }}>
                    <span>{a.icon}</span> {a.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Prompt */}
            <div>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>PROMPT</div>
              <div style={{
                padding: 10, background: '#0a0a14', borderRadius: 4, border: '1px solid #1a1a24',
                color: '#94a3b8', fontSize: 12, lineHeight: 1.6,
              }}>{brief.prompt}</div>
            </div>

            {/* Tags */}
            {brief.tags?.length > 0 && (
              <div>
                <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>TAGS</div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {brief.tags.map(t => (
                    <span key={t} style={{
                      padding: '2px 8px', borderRadius: 3,
                      background: '#1e1e2e', color: '#6b6b80', fontSize: 9,
                    }}>{t}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Source */}
            {brief.source_scene && (
              <div style={{ fontSize: 9, color: '#4a4a5a' }}>
                Source: SCRIBO › {brief.source_scene}
              </div>
            )}
          </div>
        )}

        {tab === 'ai' && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* Agent selector */}
            <div style={{ display: 'flex', gap: 3, marginBottom: 8 }}>
              {AGENTS.map(a => (
                <button key={a.id} onClick={() => setChatAgent(a.id)} style={{
                  padding: '3px 8px', borderRadius: 3, border: 'none',
                  background: chatAgent === a.id ? a.color + '20' : 'transparent',
                  color: chatAgent === a.id ? a.color : '#4a4a5a',
                  fontSize: 9, cursor: 'pointer',
                }}>{a.icon} {a.name}</button>
              ))}
            </div>

            {/* Thread */}
            <div style={{ flex: 1, overflow: 'auto', marginBottom: 8 }}>
              {thread.length === 0 ? (
                <div style={{ color: '#2a2a3a', fontSize: 11, textAlign: 'center', paddingTop: 20 }}>
                  No discussion yet
                </div>
              ) : thread.map((msg, i) => {
                const agent = AGENTS.find(a => a.id === msg.role);
                const isUser = msg.role === 'user';
                return (
                  <div key={i} style={{
                    padding: '6px 10px', marginBottom: 4, borderRadius: 4,
                    background: isUser ? 'rgba(255,255,255,0.03)' : (agent?.color || '#818cf8') + '08',
                    borderLeft: `2px solid ${isUser ? '#4a4a5a' : (agent?.color || '#818cf8')}`,
                  }}>
                    <div style={{ fontSize: 9, color: isUser ? '#4a4a5a' : (agent?.color || '#818cf8'), marginBottom: 2 }}>
                      {isUser ? 'You' : (agent?.name || msg.role)}
                      {msg.time && <span style={{ color: '#2a2a3a', marginLeft: 6 }}>{msg.time}</span>}
                    </div>
                    <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.5 }}>{msg.text}</div>
                  </div>
                );
              })}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendChat(); } }}
                placeholder={`Ask ${AGENTS.find(a => a.id === chatAgent)?.name || 'agent'}...`}
                style={{
                  flex: 1, padding: '8px 10px', borderRadius: 4,
                  background: '#0a0a14', border: '1px solid #1e1e2e',
                  color: '#e2e8f0', fontSize: 11, outline: 'none',
                }}
              />
              <button onClick={handleSendChat} style={{
                padding: '8px 12px', borderRadius: 4, border: 'none',
                background: chatInput.trim() ? '#818cf820' : '#1e1e2e',
                color: chatInput.trim() ? '#818cf8' : '#2a2a3a',
                fontSize: 10, cursor: chatInput.trim() ? 'pointer' : 'default',
              }}>Send</button>
            </div>
          </div>
        )}

        {tab === 'deps' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {deps ? (
              <>
                <div style={{
                  padding: '8px 10px', borderRadius: 4,
                  background: deps.can_proceed ? 'rgba(74, 222, 128, 0.06)' : 'rgba(248, 113, 113, 0.06)',
                  border: `1px solid ${deps.can_proceed ? 'rgba(74, 222, 128, 0.2)' : 'rgba(248, 113, 113, 0.2)'}`,
                  color: deps.can_proceed ? '#4ade80' : '#f87171',
                  fontSize: 11,
                }}>
                  {deps.can_proceed ? '✓ Can proceed — all dependencies met' : '⚑ Blocked — waiting on dependencies'}
                </div>

                {deps.blocking?.length > 0 && (
                  <div>
                    <div style={{ fontSize: 8, color: '#f87171', letterSpacing: 2, marginBottom: 6 }}>BLOCKING</div>
                    {deps.blocking.map(d => (
                      <div key={d.id} style={{
                        padding: '6px 10px', marginBottom: 3, borderRadius: 4,
                        background: 'rgba(248, 113, 113, 0.04)', border: '1px solid rgba(248, 113, 113, 0.1)',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      }}>
                        <span style={{ fontSize: 10, color: '#e2e8f0' }}>{d.title}</span>
                        <span style={{ fontSize: 9, color: (STATUS_CONFIG[d.status] || STATUS_CONFIG.planning).color }}>{d.status}</span>
                      </div>
                    ))}
                  </div>
                )}

                {deps.blocked_by_this?.length > 0 && (
                  <div>
                    <div style={{ fontSize: 8, color: '#818cf8', letterSpacing: 2, marginBottom: 6 }}>DEPENDENTS</div>
                    {deps.blocked_by_this.map(d => (
                      <div key={d.id} style={{
                        padding: '6px 10px', marginBottom: 3, borderRadius: 4,
                        background: 'rgba(129, 140, 248, 0.04)', border: '1px solid rgba(129, 140, 248, 0.1)',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      }}>
                        <span style={{ fontSize: 10, color: '#e2e8f0' }}>{d.title}</span>
                        <span style={{ fontSize: 9, color: (STATUS_CONFIG[d.status] || STATUS_CONFIG.planning).color }}>{d.status}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div style={{ color: '#2a2a3a', fontSize: 11, textAlign: 'center', paddingTop: 20 }}>Loading...</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Production Board
// ============================================================================

export default function ProductionBoard() {
  const boardAPI = useBoardAPI();
  const labAPI = useLabAPI();
  const [boardData, setBoardData] = useState(null);
  const [selectedBrief, setSelectedBrief] = useState(null);
  const [groupBy, setGroupBy] = useState('status');
  const [statusFilter, setStatusFilter] = useState('all');
  const [openGroups, setOpenGroups] = useState({});
  const [stats, setStats] = useState(null);

  // Load board
  const loadBoard = useCallback(async () => {
    const filter = statusFilter === 'all' ? null : statusFilter;
    const data = await boardAPI.getBoard(groupBy, filter);
    if (data) setBoardData(data);
    const s = await boardAPI.getStats();
    if (s) setStats(s);
  }, [boardAPI, groupBy, statusFilter]);

  useEffect(() => { loadBoard(); }, [groupBy, statusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleGroup = useCallback((key) => {
    setOpenGroups(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const handleUpdateBrief = useCallback(async (updates) => {
    if (!selectedBrief) return;
    await labAPI.updateBrief(selectedBrief, updates);
    loadBoard();
  }, [labAPI, selectedBrief, loadBoard]);

  const handlePushReady = useCallback(async () => {
    await boardAPI.pushReady();
    loadBoard();
  }, [boardAPI, loadBoard]);

  const cycleStatus = useCallback(async (briefId) => {
    const allBriefs = boardData?.groups?.flatMap(g => g.briefs) || [];
    const brief = allBriefs.find(b => b.id === briefId);
    if (!brief) return;
    const order = Object.keys(STATUS_CONFIG);
    const idx = order.indexOf(brief.status);
    const next = order[(idx + 1) % order.length];
    await labAPI.updateBrief(briefId, { status: next });
    loadBoard();
  }, [labAPI, boardData, loadBoard]);

  // Find selected brief data
  const briefData = useMemo(() => {
    if (!selectedBrief || !boardData) return null;
    for (const group of boardData.groups || []) {
      const found = group.briefs?.find(b => b.id === selectedBrief);
      if (found) return found;
    }
    return null;
  }, [selectedBrief, boardData]);

  // Default: all groups open
  useEffect(() => {
    if (boardData?.groups) {
      const defaults = {};
      boardData.groups.forEach(g => { defaults[g.key] = true; });
      setOpenGroups(prev => ({ ...defaults, ...prev }));
    }
  }, [boardData]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Top Bar */}
      <div style={{
        display: 'flex', alignItems: 'center', height: 36, padding: '0 16px',
        borderBottom: '1px solid #141420', background: 'rgba(10, 10, 18, 0.4)',
        backdropFilter: 'blur(20px)', flexShrink: 0, gap: 8,
      }}>
        {/* Status pipeline */}
        <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
          {Object.entries(STATUS_CONFIG).map(([id, cfg], i) => (
            <React.Fragment key={id}>
              <button onClick={() => setStatusFilter(statusFilter === id ? 'all' : id)} style={{
                padding: '3px 8px', borderRadius: 3, border: 'none',
                background: statusFilter === id ? cfg.color + '20' : 'transparent',
                color: statusFilter === id ? cfg.color : '#3a3a50',
                fontSize: 8, cursor: 'pointer', fontFamily: 'inherit',
              }}>
                {cfg.icon} {stats?.by_status?.[id] || 0}
              </button>
              {i < Object.keys(STATUS_CONFIG).length - 1 && (
                <span style={{ color: '#1a1a24', fontSize: 8 }}>→</span>
              )}
            </React.Fragment>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* Stats */}
        {stats && (
          <div style={{ display: 'flex', gap: 8, fontSize: 8, color: '#3a3a50', letterSpacing: 2 }}>
            <span>{stats.total_briefs} BRIEFS</span>
            <span>·</span>
            <span>{stats.total_shots} SHOTS</span>
          </div>
        )}

        <button onClick={handlePushReady} style={{
          padding: '4px 10px', borderRadius: 4, border: 'none',
          background: 'rgba(74, 222, 128, 0.1)', color: '#4ade80',
          fontSize: 9, cursor: 'pointer', fontWeight: 600,
        }}>Push Ready → LAB</button>
      </div>

      {/* Group-by bar */}
      <div style={{
        display: 'flex', alignItems: 'center', padding: '4px 16px', gap: 6,
        borderBottom: '1px solid #141420', fontSize: 9,
      }}>
        <span style={{ color: '#2a2a3a', fontSize: 8, letterSpacing: 2, fontFamily: "'JetBrains Mono', monospace" }}>GROUP</span>
        {GROUP_OPTIONS.map(g => (
          <button key={g.id} onClick={() => setGroupBy(g.id)} style={{
            padding: '3px 8px', borderRadius: 3, border: 'none',
            background: groupBy === g.id ? 'rgba(255,255,255,0.06)' : 'transparent',
            color: groupBy === g.id ? '#e2e8f0' : '#4a4a5a',
            fontSize: 9, cursor: 'pointer',
          }}>{g.label}</button>
        ))}
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Board */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {boardData?.groups?.length > 0 ? boardData.groups.map(group => {
            const isOpen = openGroups[group.key] !== false;
            const groupColor = STATUS_CONFIG[group.key]?.color
              || PRIORITY_CONFIG[group.key]?.color
              || AGENTS.find(a => a.id === group.key)?.color
              || '#818cf8';

            return (
              <div key={group.key}>
                <GroupHeader
                  label={group.key}
                  count={group.briefs?.length || 0}
                  color={groupColor}
                  isOpen={isOpen}
                  onToggle={() => toggleGroup(group.key)}
                />
                {isOpen && (group.briefs || []).map(brief => (
                  <BriefRow
                    key={brief.id}
                    brief={brief}
                    isSelected={brief.id === selectedBrief}
                    onClick={() => setSelectedBrief(brief.id === selectedBrief ? null : brief.id)}
                    onStatusChange={cycleStatus}
                  />
                ))}
              </div>
            );
          }) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, color: '#1a1a24', marginBottom: 8 }}>◈</div>
                <div style={{ fontSize: 11, color: '#2a2a3a' }}>No production briefs yet</div>
                <div style={{ fontSize: 9, color: '#1e1e2e', marginTop: 4 }}>Push annotations from SCRIBO to create briefs</div>
              </div>
            </div>
          )}
        </div>

        {/* Detail Panel */}
        {briefData && (
          <div style={{ width: 400, borderLeft: '1px solid #141420', flexShrink: 0 }}>
            <DetailPanel
              brief={briefData}
              onClose={() => setSelectedBrief(null)}
              onUpdate={handleUpdateBrief}
              boardAPI={boardAPI}
            />
          </div>
        )}
      </div>
    </div>
  );
}
