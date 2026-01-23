import React, { useState, useEffect, useCallback } from 'react';
import GlassCard from './GlassCard';

const API_BASE = 'http://localhost:8000';

/**
 * TuningPanel - Luna Engine Tuning Interface
 *
 * Provides a slide-out panel for tuning Luna's parameters with:
 * - Parameter browser by category
 * - Live value adjustments with sliders
 * - Session management (start/end)
 * - Evaluation running and score display
 * - Iteration history and comparison
 */
const TuningPanel = ({ isOpen, onClose }) => {
  // State
  const [activeTab, setActiveTab] = useState('params');
  const [params, setParams] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [session, setSession] = useState(null);
  const [evalResults, setEvalResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pendingChanges, setPendingChanges] = useState({});
  const [isRelaunching, setIsRelaunching] = useState(false);

  // Ring buffer state
  const [ringStatus, setRingStatus] = useState(null);
  const [ringMaxTurns, setRingMaxTurns] = useState(6);
  const [isRingLoading, setIsRingLoading] = useState(false);

  // Fetch ring buffer status
  const fetchRingStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ring/status`);
      if (res.ok) {
        const data = await res.json();
        setRingStatus(data);
        setRingMaxTurns(data.max_turns);
      }
    } catch (e) {
      console.warn('Failed to fetch ring status:', e);
    }
  }, []);

  // Configure ring buffer size
  const handleRingConfig = async (newMaxTurns) => {
    setIsRingLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/ring/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_turns: newMaxTurns }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to configure ring');
      }
      await fetchRingStatus();
    } catch (e) {
      setError(e.message);
    } finally {
      setIsRingLoading(false);
    }
  };

  // Clear ring buffer
  const handleRingClear = async () => {
    if (!window.confirm('Clear conversation memory? Luna will forget recent context.')) {
      return;
    }
    setIsRingLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/ring/clear`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to clear ring');
      }
      await fetchRingStatus();
    } catch (e) {
      setError(e.message);
    } finally {
      setIsRingLoading(false);
    }
  };

  // Fetch params list
  const fetchParams = useCallback(async () => {
    try {
      const url = selectedCategory
        ? `${API_BASE}/tuning/params?category=${selectedCategory}`
        : `${API_BASE}/tuning/params`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setParams(data.params || []);
        setCategories(data.categories || []);
      }
    } catch (e) {
      console.warn('Failed to fetch params:', e);
    }
  }, [selectedCategory]);

  // Fetch session status
  const fetchSession = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/tuning/session`);
      if (res.ok) {
        const data = await res.json();
        setSession(data.active ? data : null);
      }
    } catch (e) {
      console.warn('Failed to fetch session:', e);
    }
  }, []);

  // Initial load
  useEffect(() => {
    if (isOpen) {
      fetchParams();
      fetchSession();
      fetchRingStatus();
    }
  }, [isOpen, fetchParams, fetchSession, fetchRingStatus]);

  // Start new session
  const handleStartSession = async (focus = 'all') => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/tuning/session/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ focus }),
      });
      if (res.ok) {
        const data = await res.json();
        setSession({ active: true, ...data, iterations: [] });
        fetchSession(); // Refresh to get full session data
      } else {
        const err = await res.json();
        setError(err.detail || 'Failed to start session');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  // End session
  const handleEndSession = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/tuning/session/end`, {
        method: 'POST',
      });
      if (res.ok) {
        setSession(null);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Run evaluation
  const handleRunEval = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/tuning/eval`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setEvalResults(data);
        fetchSession(); // Refresh session to get new iteration
      } else {
        const err = await res.json();
        setError(err.detail || 'Evaluation failed');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Set parameter value
  const handleSetParam = async (name, value) => {
    try {
      const res = await fetch(`${API_BASE}/tuning/params/${encodeURIComponent(name)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: parseFloat(value) }),
      });
      if (res.ok) {
        const data = await res.json();
        // Remove from pending changes
        setPendingChanges((prev) => {
          const next = { ...prev };
          delete next[name];
          return next;
        });
        // Refresh session if we got eval results
        if (data.eval_score !== undefined) {
          fetchSession();
        }
      }
    } catch (e) {
      console.error('Failed to set param:', e);
    }
  };

  // Reset parameter
  const handleResetParam = async (name) => {
    try {
      const res = await fetch(`${API_BASE}/tuning/param-reset/${encodeURIComponent(name)}`, {
        method: 'POST',
      });
      if (res.ok) {
        fetchParams();
      }
    } catch (e) {
      console.error('Failed to reset param:', e);
    }
  };

  // Apply best params
  const handleApplyBest = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/tuning/apply-best`, {
        method: 'POST',
      });
      if (res.ok) {
        fetchParams();
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Relaunch system
  const handleRelaunch = async () => {
    if (isRelaunching) return;
    setIsRelaunching(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/system/relaunch`, {
        method: 'POST',
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to relaunch');
      }
      // Keep relaunching state for a bit - system will restart
      setTimeout(() => setIsRelaunching(false), 10000);
    } catch (e) {
      setError(e.message);
      setIsRelaunching(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-[500px] bg-slate-900/95 backdrop-blur-xl border-l border-white/10 shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
            <span className="text-lg">⚙️</span>
          </div>
          <div>
            <h2 className="text-lg font-medium text-white">Tuning</h2>
            <p className="text-xs text-white/40">Parameter tuning & evaluation</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-lg hover:bg-white/10 transition-colors text-white/60 hover:text-white"
        >
          ✕
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-white/10">
        {['params', 'session', 'eval'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-3 text-sm font-medium transition-colors ${
              activeTab === tab
                ? 'text-amber-400 border-b-2 border-amber-400'
                : 'text-white/40 hover:text-white/60'
            }`}
          >
            {tab === 'params' && '🎛️ Parameters'}
            {tab === 'session' && '📊 Session'}
            {tab === 'eval' && '🧪 Evaluate'}
          </button>
        ))}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="m-4 p-3 rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-400 hover:text-red-200">
            ✕
          </button>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Parameters Tab */}
        {activeTab === 'params' && (
          <>
            {/* Category Filter */}
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setSelectedCategory(null)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                  !selectedCategory
                    ? 'bg-amber-500/20 border-amber-500/50 text-amber-400'
                    : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
                }`}
              >
                All
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                    selectedCategory === cat
                      ? 'bg-amber-500/20 border-amber-500/50 text-amber-400'
                      : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Parameters List */}
            <div className="space-y-3">
              {params.map((paramName) => (
                <ParamCard
                  key={paramName}
                  paramName={paramName}
                  pendingValue={pendingChanges[paramName]}
                  onPendingChange={(val) =>
                    setPendingChanges((prev) => ({ ...prev, [paramName]: val }))
                  }
                  onApply={(val) => handleSetParam(paramName, val)}
                  onReset={() => handleResetParam(paramName)}
                />
              ))}
            </div>
          </>
        )}

        {/* Session Tab */}
        {activeTab === 'session' && (
          <>
            {/* Session Status */}
            <GlassCard className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-white/70">Session Status</h3>
                <div
                  className={`px-2 py-1 rounded text-xs ${
                    session
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-white/10 text-white/40'
                  }`}
                >
                  {session ? 'Active' : 'No Session'}
                </div>
              </div>

              {session ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-white/40">Focus:</span>{' '}
                      <span className="text-white">{session.focus}</span>
                    </div>
                    <div>
                      <span className="text-white/40">Iterations:</span>{' '}
                      <span className="text-white">{session.iteration_count}</span>
                    </div>
                    <div>
                      <span className="text-white/40">Best Score:</span>{' '}
                      <span className="text-amber-400 font-medium">
                        {(session.best_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div>
                      <span className="text-white/40">Best Iter:</span>{' '}
                      <span className="text-white">#{session.best_iteration}</span>
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2">
                    <button
                      onClick={handleApplyBest}
                      disabled={isLoading}
                      className="flex-1 py-2 text-sm rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30 transition-colors disabled:opacity-50"
                    >
                      Apply Best
                    </button>
                    <button
                      onClick={handleEndSession}
                      disabled={isLoading}
                      className="flex-1 py-2 text-sm rounded-lg bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-colors disabled:opacity-50"
                    >
                      End Session
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-white/40">
                    Start a tuning session to track parameter changes and evaluate performance.
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    {['all', 'memory', 'routing', 'latency'].map((focus) => (
                      <button
                        key={focus}
                        onClick={() => handleStartSession(focus)}
                        disabled={isLoading}
                        className="py-2 text-sm rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30 transition-colors disabled:opacity-50 capitalize"
                      >
                        {focus}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </GlassCard>

            {/* Iteration History */}
            {session?.iterations?.length > 0 && (
              <GlassCard className="p-4">
                <h3 className="text-sm font-medium text-white/70 mb-3">Iteration History</h3>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {session.iterations.map((iter) => (
                    <div
                      key={iter.num}
                      className={`p-3 rounded-lg border ${
                        iter.num === session.best_iteration
                          ? 'bg-amber-500/10 border-amber-500/30'
                          : 'bg-white/5 border-white/10'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-white/70">
                          #{iter.num}
                          {iter.num === session.best_iteration && (
                            <span className="ml-2 text-amber-400">★ Best</span>
                          )}
                        </span>
                        <span
                          className={`text-sm font-medium ${
                            iter.score >= 0.7
                              ? 'text-green-400'
                              : iter.score >= 0.5
                              ? 'text-amber-400'
                              : 'text-red-400'
                          }`}
                        >
                          {(iter.score * 100).toFixed(1)}%
                        </span>
                      </div>
                      {Object.keys(iter.params_changed).length > 0 && (
                        <div className="mt-1 text-xs text-white/40">
                          Changed: {Object.keys(iter.params_changed).join(', ')}
                        </div>
                      )}
                      {iter.notes && (
                        <div className="mt-1 text-xs text-white/30">{iter.notes}</div>
                      )}
                    </div>
                  ))}
                </div>
              </GlassCard>
            )}

            {/* Ring Buffer Controls */}
            <GlassCard className="p-4">
              <h3 className="text-sm font-medium text-white/70 mb-3">Conversation Memory</h3>
              <div className="space-y-4">
                {/* Status Display */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white/5 rounded-lg p-3 text-center">
                    <div className="text-2xl font-light text-cyan-400">
                      {ringStatus?.current_turns ?? '-'}
                    </div>
                    <div className="text-[10px] text-white/40">Current Turns</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3 text-center">
                    <div className="text-2xl font-light text-amber-400">
                      {ringStatus?.max_turns ?? '-'}
                    </div>
                    <div className="text-[10px] text-white/40">Max Turns</div>
                  </div>
                </div>

                {/* Topics */}
                {ringStatus?.topics?.length > 0 && (
                  <div>
                    <div className="text-xs text-white/40 mb-2">Detected Topics</div>
                    <div className="flex flex-wrap gap-1">
                      {ringStatus.topics.slice(0, 8).map((topic, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 text-[10px] bg-white/5 border border-white/10 rounded-full text-white/60"
                        >
                          {topic}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Max Turns Slider */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-white/40">Buffer Size</span>
                    <span className="text-xs text-cyan-400">{ringMaxTurns} turns</span>
                  </div>
                  <input
                    type="range"
                    min={2}
                    max={20}
                    value={ringMaxTurns}
                    onChange={(e) => setRingMaxTurns(parseInt(e.target.value))}
                    className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                  />
                  <div className="flex justify-between text-[10px] text-white/30 mt-1">
                    <span>2 (minimal)</span>
                    <span>20 (extended)</span>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => handleRingConfig(ringMaxTurns)}
                    disabled={isRingLoading || ringMaxTurns === ringStatus?.max_turns}
                    className="py-2 text-sm rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/30 transition-colors disabled:opacity-50"
                  >
                    {isRingLoading ? 'Applying...' : 'Apply Size'}
                  </button>
                  <button
                    onClick={handleRingClear}
                    disabled={isRingLoading || !ringStatus?.current_turns}
                    className="py-2 text-sm rounded-lg bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-colors disabled:opacity-50"
                  >
                    Clear Memory
                  </button>
                </div>

                <p className="text-[10px] text-white/30">
                  The ring buffer holds recent conversation turns. More turns = better context retention, but higher token usage.
                </p>
              </div>
            </GlassCard>

            {/* System Controls */}
            <GlassCard className="p-4">
              <h3 className="text-sm font-medium text-white/70 mb-3">System Controls</h3>
              <div className="space-y-3">
                <p className="text-sm text-white/40">
                  Restart the Luna Engine to apply configuration changes or recover from errors.
                </p>
                <button
                  onClick={handleRelaunch}
                  disabled={isRelaunching}
                  className={`w-full py-3 text-sm font-medium rounded-lg border transition-all flex items-center justify-center gap-2 ${
                    isRelaunching
                      ? 'bg-amber-500/20 border-amber-500/30 text-amber-400 cursor-wait'
                      : 'bg-cyan-500/20 border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/30'
                  }`}
                >
                  <span className={isRelaunching ? 'animate-spin' : ''}>↻</span>
                  {isRelaunching ? 'Restarting Luna Engine...' : 'Relaunch Engine'}
                </button>
                {isRelaunching && (
                  <p className="text-xs text-amber-400/60 text-center">
                    Please wait while the system restarts...
                  </p>
                )}
              </div>
            </GlassCard>
          </>
        )}

        {/* Evaluate Tab */}
        {activeTab === 'eval' && (
          <>
            {/* Run Evaluation */}
            <GlassCard className="p-4">
              <h3 className="text-sm font-medium text-white/70 mb-3">Run Evaluation</h3>
              <p className="text-sm text-white/40 mb-4">
                Test Luna's performance across memory recall, context retention, routing, and
                latency.
              </p>
              <button
                onClick={handleRunEval}
                disabled={isLoading}
                className="w-full py-3 text-sm font-medium rounded-lg bg-gradient-to-r from-amber-500 to-orange-600 text-white hover:from-amber-400 hover:to-orange-500 transition-all disabled:opacity-50"
              >
                {isLoading ? 'Running...' : '🧪 Run Full Evaluation'}
              </button>
            </GlassCard>

            {/* Results */}
            {evalResults && (
              <GlassCard className="p-4">
                <h3 className="text-sm font-medium text-white/70 mb-3">Results</h3>

                {/* Overall Score */}
                <div className="mb-4 p-3 rounded-lg bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-amber-400">
                      {(evalResults.overall_score * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-white/40">Overall Score</div>
                  </div>
                </div>

                {/* Category Scores */}
                <div className="space-y-2 mb-4">
                  <ScoreBar
                    label="Memory Recall"
                    score={evalResults.memory_recall_score}
                    color="violet"
                  />
                  <ScoreBar
                    label="Context Retention"
                    score={evalResults.context_retention_score}
                    color="cyan"
                  />
                  <ScoreBar label="Routing" score={evalResults.routing_score} color="green" />
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="p-2 rounded bg-white/5">
                    <div className="text-white/40">Tests</div>
                    <div className="text-white">
                      {evalResults.passed_tests}/{evalResults.total_tests} passed
                    </div>
                  </div>
                  <div className="p-2 rounded bg-white/5">
                    <div className="text-white/40">Avg Latency</div>
                    <div className="text-white">{evalResults.avg_latency_ms.toFixed(0)}ms</div>
                  </div>
                </div>
              </GlassCard>
            )}
          </>
        )}
      </div>
    </div>
  );
};

/**
 * ParamCard - Individual parameter control
 */
const ParamCard = ({ paramName, pendingValue, onPendingChange, onApply, onReset }) => {
  const [param, setParam] = useState(null);
  const [localValue, setLocalValue] = useState(null);

  // Fetch parameter details
  useEffect(() => {
    const fetchParam = async () => {
      try {
        const res = await fetch(
          `${API_BASE}/tuning/params/${encodeURIComponent(paramName)}`
        );
        if (res.ok) {
          const data = await res.json();
          setParam(data);
          setLocalValue(pendingValue ?? data.value);
        }
      } catch (e) {
        console.warn('Failed to fetch param:', paramName, e);
      }
    };
    fetchParam();
  }, [paramName, pendingValue]);

  if (!param) {
    return (
      <div className="p-3 rounded-lg bg-white/5 animate-pulse">
        <div className="h-4 w-32 bg-white/10 rounded" />
      </div>
    );
  }

  const hasChanged = localValue !== param.value;
  const [min, max] = param.bounds;

  return (
    <div
      className={`p-3 rounded-lg border transition-all ${
        param.is_overridden || hasChanged
          ? 'bg-amber-500/5 border-amber-500/20'
          : 'bg-white/5 border-white/10'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="text-sm font-medium text-white/90">{paramName}</div>
          <div className="text-xs text-white/40">{param.description}</div>
        </div>
        {param.is_overridden && (
          <button
            onClick={onReset}
            className="text-xs text-amber-400 hover:text-amber-300"
            title="Reset to default"
          >
            ↺
          </button>
        )}
      </div>

      {/* Slider */}
      <div className="flex items-center gap-3">
        <input
          type="range"
          min={min}
          max={max}
          step={param.step}
          value={localValue ?? param.value}
          onChange={(e) => {
            const val = parseFloat(e.target.value);
            setLocalValue(val);
            onPendingChange(val);
          }}
          className="flex-1 h-2 bg-white/10 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-amber-400"
        />
        <div className="w-16 text-right">
          <span className="text-sm font-mono text-white">
            {(localValue ?? param.value).toFixed(2)}
          </span>
        </div>
      </div>

      {/* Range labels */}
      <div className="flex justify-between text-xs text-white/30 mt-1">
        <span>{min}</span>
        <span className="text-white/20">default: {param.default}</span>
        <span>{max}</span>
      </div>

      {/* Apply button */}
      {hasChanged && (
        <button
          onClick={() => onApply(localValue)}
          className="mt-2 w-full py-1.5 text-xs rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30 transition-colors"
        >
          Apply Change
        </button>
      )}
    </div>
  );
};

/**
 * ScoreBar - Visual score indicator
 */
const ScoreBar = ({ label, score, color = 'amber' }) => {
  const colorClasses = {
    amber: 'bg-amber-500',
    violet: 'bg-violet-500',
    cyan: 'bg-cyan-500',
    green: 'bg-green-500',
    red: 'bg-red-500',
  };

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-white/60">{label}</span>
        <span className="text-white/80">{(score * 100).toFixed(1)}%</span>
      </div>
      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
        <div
          className={`h-full ${colorClasses[color]} transition-all duration-500`}
          style={{ width: `${score * 100}%` }}
        />
      </div>
    </div>
  );
};

export default TuningPanel;
