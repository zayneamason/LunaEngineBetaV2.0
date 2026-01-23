import React, { useState } from 'react';
import GlassCard from './GlassCard';
import StatusDot from './StatusDot';

const EngineStatus = ({ status, isConnected, onRelaunch }) => {
  const [isRelaunching, setIsRelaunching] = useState(false);

  const handleRelaunch = async () => {
    if (!onRelaunch || isRelaunching) return;
    setIsRelaunching(true);
    try {
      await onRelaunch();
    } finally {
      // Keep relaunching state - will reset when page reloads
      setTimeout(() => setIsRelaunching(false), 10000);
    }
  };
  if (!status) {
    return (
      <GlassCard padding="p-6" hover={false}>
        <div className="flex items-center gap-3">
          <StatusDot status={isConnected ? 'loading' : 'disconnected'} />
          <span className="text-white/50 text-sm">
            {isConnected ? 'Loading...' : 'Waiting for engine...'}
          </span>
        </div>
      </GlassCard>
    );
  }

  const {
    state = 'UNKNOWN',
    uptime_seconds = 0,
    cognitive_ticks = 0,
    events_processed = 0,
    messages_generated = 0,
    actors = [],
    buffer_size = 0,
    context = null,
    agentic = null,
  } = status;

  const formatUptime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hours > 0) return `${hours}h ${mins}m`;
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  };

  return (
    <GlassCard padding="p-0" hover={false}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-1 h-6 bg-gradient-to-b from-emerald-400 to-cyan-400 rounded-full" />
            <h2 className="text-lg font-light tracking-wide text-white/90">Engine</h2>
          </div>
          <div className="flex items-center gap-3">
            <StatusDot status={state === 'RUNNING' ? 'active' : 'disconnected'} />
            <span className="text-xs text-white/50">{state}</span>
            {onRelaunch && (
              <button
                onClick={handleRelaunch}
                disabled={isRelaunching}
                className={`px-2 py-1 text-[10px] rounded-md border transition-all ${
                  isRelaunching
                    ? 'bg-amber-500/20 border-amber-500/30 text-amber-400 cursor-wait'
                    : 'bg-white/5 border-white/10 text-white/40 hover:border-cyan-400/50 hover:text-cyan-400'
                }`}
                title="Restart Luna Engine"
              >
                {isRelaunching ? '...' : '↻'}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="p-6">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <div className="text-xs text-white/40 mb-1">Uptime</div>
            <div className="text-lg font-light text-white/90">{formatUptime(uptime_seconds)}</div>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <div className="text-xs text-white/40 mb-1">Ticks</div>
            <div className="text-lg font-light text-white/90">{cognitive_ticks.toLocaleString()}</div>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <div className="text-xs text-white/40 mb-1">Events</div>
            <div className="text-lg font-light text-white/90">{events_processed.toLocaleString()}</div>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <div className="text-xs text-white/40 mb-1">Messages</div>
            <div className="text-lg font-light text-white/90">{messages_generated.toLocaleString()}</div>
          </div>
        </div>

        {/* Actors */}
        <div>
          <div className="text-xs text-white/40 uppercase tracking-widest mb-3">Active Actors</div>
          <div className="flex flex-wrap gap-2">
            {actors.map((actor) => (
              <div
                key={actor}
                className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5"
              >
                <StatusDot status="active" size="w-1.5 h-1.5" />
                <span className="text-xs text-white/60">{actor}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Agentic Processing */}
        {agentic && (
          <div className="mt-6">
            <div className="text-xs text-white/40 uppercase tracking-widest mb-3">Agentic Processing</div>

            {/* Processing Status */}
            <div className={`bg-white/5 rounded-xl p-3 mb-3 border ${agentic.is_processing ? 'border-amber-400/30' : 'border-white/5'}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${agentic.is_processing ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}`} />
                  <span className="text-xs text-white/60">
                    {agentic.is_processing ? 'Processing...' : 'Ready'}
                  </span>
                </div>
                <span className="text-xs text-white/30">{agentic.agent_loop_status}</span>
              </div>

              {/* Current Goal */}
              {agentic.current_goal && (
                <div className="text-xs text-white/50 bg-white/5 rounded-lg p-2 mt-2">
                  <span className="text-white/30">Goal: </span>
                  {agentic.current_goal}
                </div>
              )}

              {/* Pending Messages */}
              {agentic.pending_messages > 0 && (
                <div className="flex items-center gap-2 mt-2 text-xs">
                  <span className="text-amber-400">{agentic.pending_messages} message{agentic.pending_messages > 1 ? 's' : ''} queued</span>
                </div>
              )}
            </div>

            {/* Agentic Stats Grid */}
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-white/5 rounded-lg p-2 text-center">
                <div className="text-[10px] text-white/30">Started</div>
                <div className="text-sm font-light text-white/70">{agentic.tasks_started}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-2 text-center">
                <div className="text-[10px] text-white/30">Completed</div>
                <div className="text-sm font-light text-emerald-400">{agentic.tasks_completed}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-2 text-center">
                <div className="text-[10px] text-white/30">Aborted</div>
                <div className="text-sm font-light text-white/50">{agentic.tasks_aborted}</div>
              </div>
            </div>

            {/* Routing Stats */}
            <div className="flex justify-between mt-3 text-[10px] text-white/30">
              <span>Direct: {agentic.direct_responses}</span>
              <span>Planned: {agentic.planned_responses}</span>
            </div>
          </div>
        )}

        {/* Buffer */}
        {buffer_size > 0 && (
          <div className="mt-4 flex items-center gap-2 text-xs text-white/40">
            <span>Buffer:</span>
            <span className="text-amber-400">{buffer_size} pending</span>
          </div>
        )}

        {/* Context Window */}
        {context && (
          <div className="mt-6">
            <div className="text-xs text-white/40 uppercase tracking-widest mb-3">Context Window</div>

            {/* Token Budget Bar */}
            <div className="bg-white/5 rounded-xl p-3 mb-3">
              <div className="flex justify-between text-xs mb-2">
                <span className="text-white/40">Tokens</span>
                <span className="text-white/60">
                  {context.total_tokens?.toLocaleString()} / {context.token_budget?.toLocaleString()}
                </span>
              </div>
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, context.budget_used_pct || 0)}%` }}
                />
              </div>
              <div className="text-right text-xs text-white/30 mt-1">
                {(context.budget_used_pct || 0).toFixed(1)}% used
              </div>
            </div>

            {/* Ring Breakdown */}
            {context.rings && (
              <div className="grid grid-cols-4 gap-2">
                {['CORE', 'INNER', 'MIDDLE', 'OUTER'].map((ring) => {
                  const ringData = context.rings[ring] || { count: 0, tokens: 0 };
                  const ringColors = {
                    CORE: 'from-violet-500 to-purple-500',
                    INNER: 'from-cyan-400 to-blue-500',
                    MIDDLE: 'from-emerald-400 to-teal-500',
                    OUTER: 'from-slate-400 to-gray-500',
                  };
                  return (
                    <div key={ring} className="bg-white/5 rounded-lg p-2 text-center">
                      <div className={`w-2 h-2 mx-auto mb-1 rounded-full bg-gradient-to-r ${ringColors[ring]}`} />
                      <div className="text-[10px] text-white/30 uppercase">{ring}</div>
                      <div className="text-sm font-light text-white/70">{ringData.count}</div>
                      <div className="text-[9px] text-white/30">{ringData.tokens} tok</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </GlassCard>
  );
};

export default EngineStatus;
