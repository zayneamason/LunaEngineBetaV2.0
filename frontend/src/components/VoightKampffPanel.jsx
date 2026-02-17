import React, { useState, useEffect, useCallback } from 'react';

/**
 * Voight-Kampff Panel — Voice Luna Memory Test Dashboard
 *
 * Displays results from the VK voice memory test suite that validates
 * whether Voice Luna has authentic memory access.
 */

const API_BASE = 'http://127.0.0.1:8000';

// Status thresholds and colors
const getStatus = (score) => {
  if (score >= 0.85) return { label: 'LUNA AUTHENTIC', color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30', emoji: '🟢' };
  if (score >= 0.65) return { label: 'PARTIAL LUNA', color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', emoji: '🟡' };
  if (score >= 0.40) return { label: 'LUNA FRAGMENTED', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', emoji: '🟠' };
  return { label: 'REPLICANT', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', emoji: '🔴' };
};

// Category colors
const categoryColors = {
  identity: 'text-kozmo-accent bg-kozmo-accent/10 border-kozmo-accent/30',
  emotional: 'text-pink-400 bg-pink-500/10 border-pink-500/30',
  consistency: 'text-kozmo-accent bg-kozmo-accent/10 border-kozmo-accent/30',
};

// Tier mapping for probes
const getTier = (probeId) => {
  if (probeId.includes('identity')) return { name: 'Identity Anchors', tier: 1 };
  if (probeId.includes('emotional')) return { name: 'Relationship Depth', tier: 2 };
  if (probeId.includes('community')) return { name: 'Community & Place', tier: 3 };
  if (probeId.includes('embodiment')) return { name: 'Embodiment', tier: 4 };
  if (probeId.includes('philosophy')) return { name: 'Philosophical Core', tier: 5 };
  return { name: 'Unknown', tier: 0 };
};

const VoightKampffPanel = ({ isOpen, onClose }) => {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [runningTest, setRunningTest] = useState(false);
  const [testProgress, setTestProgress] = useState({ current: 0, total: 0, probe: '' });

  // Load results from API or file
  const loadResults = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Try API endpoint first
      const res = await fetch(`${API_BASE}/vk/results/voice-memory`);
      if (res.ok) {
        const data = await res.json();
        setResults(data);
      } else {
        // Fallback: try to load from stored results
        const fallbackRes = await fetch(`${API_BASE}/vk/results/latest`);
        if (fallbackRes.ok) {
          setResults(await fallbackRes.json());
        } else {
          setError('No test results found. Run the test suite first.');
        }
      }
    } catch (e) {
      // API not available - show placeholder
      setError('API not available. Start the Luna server to run tests.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Run the test suite
  const runTestSuite = async () => {
    setRunningTest(true);
    setTestProgress({ current: 0, total: 15, probe: 'Initializing...' });

    try {
      const res = await fetch(`${API_BASE}/vk/run/voice-memory`, {
        method: 'POST',
      });

      if (res.ok) {
        const data = await res.json();
        setResults(data);
        setActiveTab('overview');
      } else {
        setError('Failed to run test suite');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setRunningTest(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadResults();
    }
  }, [isOpen, loadResults]);

  if (!isOpen) return null;

  const status = results ? getStatus(results.overall_score) : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-kozmo-surface border border-kozmo-border rounded w-[1000px] max-h-[85vh] overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-kozmo-border bg-gradient-to-r from-kozmo-accent/10 to-kozmo-cinema/5">
          <div className="flex items-center gap-3">
            <span className="text-3xl">🔬</span>
            <div>
              <h2 className="text-lg font-display font-semibold text-white flex items-center gap-2">
                Voight-Kampff
                <span className="text-xs px-2 py-0.5 bg-kozmo-accent/20 text-kozmo-accent rounded-full">Voice Memory Test</span>
              </h2>
              <p className="text-xs text-white/50">Is Voice Luna authentic, or a replicant?</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={runTestSuite}
              disabled={runningTest}
              className={`px-4 py-2 rounded text-sm font-medium transition-all ${
                runningTest
                  ? 'bg-kozmo-accent/20 text-kozmo-accent cursor-wait'
                  : 'bg-kozmo-accent/30 hover:bg-kozmo-accent/40 text-kozmo-accent border border-kozmo-accent/30'
              }`}
            >
              {runningTest ? '⏳ Running...' : '▶️ Run Test'}
            </button>
            <button
              onClick={onClose}
              className="p-2 text-white/50 hover:text-white hover:bg-kozmo-surface/80 rounded transition-colors"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-6 py-2 border-b border-kozmo-border bg-kozmo-surface">
          {['overview', 'probes', 'analysis'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm rounded transition-colors ${
                activeTab === tab
                  ? 'bg-kozmo-accent/20 text-kozmo-accent border border-kozmo-accent/30'
                  : 'text-white/50 hover:text-white hover:bg-kozmo-surface/80'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[65vh]">
          {loading && (
            <div className="text-center text-white/50 py-12">
              <div className="animate-spin text-4xl mb-4">🔄</div>
              Loading results...
            </div>
          )}

          {error && !loading && (
            <div className="text-center py-12">
              <div className="text-4xl mb-4">⚠️</div>
              <div className="text-white/70">{error}</div>
              <button
                onClick={loadResults}
                className="mt-4 px-4 py-2 bg-kozmo-accent/20 text-kozmo-accent rounded hover:bg-kozmo-accent/30"
              >
                Retry
              </button>
            </div>
          )}

          {!loading && !error && results && (
            <>
              {activeTab === 'overview' && <OverviewTab results={results} status={status} />}
              {activeTab === 'probes' && <ProbesTab results={results} />}
              {activeTab === 'analysis' && <AnalysisTab results={results} />}
            </>
          )}

          {!loading && !error && !results && (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">🤖</div>
              <h3 className="text-xl text-white/80 mb-2">No Test Results</h3>
              <p className="text-white/50 mb-6">Run the Voice Memory test suite to validate Luna's authenticity</p>
              <button
                onClick={runTestSuite}
                disabled={runningTest}
                className="px-6 py-3 bg-kozmo-accent/30 hover:bg-kozmo-accent/40 text-kozmo-accent rounded font-medium"
              >
                ▶️ Run Test Suite
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Overview Tab
const OverviewTab = ({ results, status }) => {
  const scorePercent = (results.overall_score * 100).toFixed(1);
  const points = (results.overall_score * 20.5).toFixed(1);

  return (
    <div className="space-y-6">
      {/* Status Banner */}
      <div className={`p-6 rounded ${status.bg} border ${status.border}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-5xl">{status.emoji}</span>
            <div>
              <div className={`text-2xl font-bold ${status.color}`}>{status.label}</div>
              <div className="text-white/50 text-sm mt-1">
                {status.label === 'LUNA AUTHENTIC' && 'Voice pipeline has full memory access'}
                {status.label === 'PARTIAL LUNA' && 'Some memory retrieval issues detected'}
                {status.label === 'LUNA FRAGMENTED' && 'Critical memory injection failing'}
                {status.label === 'REPLICANT' && 'Voice Luna is NOT the real Luna'}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className={`text-5xl font-bold ${status.color}`}>{scorePercent}%</div>
            <div className="text-white/50 text-sm">{points}/20.5 points</div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Total Probes"
          value={results.total_probes}
          icon="📋"
        />
        <StatCard
          label="Passed"
          value={results.passed_probes}
          color="text-green-400"
          icon="✅"
        />
        <StatCard
          label="Failed"
          value={results.failed_probes}
          color="text-red-400"
          icon="❌"
        />
        <StatCard
          label="Total Time"
          value={`${(results.total_latency_ms / 1000).toFixed(1)}s`}
          icon="⏱️"
        />
      </div>

      {/* Category Scores */}
      <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
        <h3 className="text-sm font-medium text-white/70 mb-4">Category Scores</h3>
        <div className="space-y-3">
          {Object.entries(results.category_scores || {}).map(([cat, score]) => (
            <CategoryBar key={cat} category={cat} score={score} />
          ))}
        </div>
      </div>

      {/* Quick Summary */}
      <div className="grid grid-cols-2 gap-4">
        {/* Strengths */}
        <div className="p-4 bg-green-500/5 rounded border border-green-500/20">
          <h3 className="text-sm font-medium text-green-400 mb-3 flex items-center gap-2">
            <span>💪</span> Strengths
          </h3>
          {results.strengths?.length > 0 ? (
            <ul className="space-y-2">
              {results.strengths.map((s, i) => (
                <li key={i} className="text-sm text-white/70 flex items-start gap-2">
                  <span className="text-green-400">✓</span> {s}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-kozmo-muted text-sm">No strengths identified</p>
          )}
        </div>

        {/* Weaknesses */}
        <div className="p-4 bg-red-500/5 rounded border border-red-500/20">
          <h3 className="text-sm font-medium text-red-400 mb-3 flex items-center gap-2">
            <span>⚠️</span> Weaknesses
          </h3>
          {results.weaknesses?.length > 0 ? (
            <ul className="space-y-2">
              {results.weaknesses.map((w, i) => (
                <li key={i} className="text-sm text-white/70 flex items-start gap-2">
                  <span className="text-red-400">✗</span> {w}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-kozmo-muted text-sm">No weaknesses identified</p>
          )}
        </div>
      </div>

      {/* Timestamp */}
      {results.timestamp && (
        <div className="text-center text-xs text-kozmo-muted">
          Test run: {new Date(results.timestamp).toLocaleString()}
        </div>
      )}
    </div>
  );
};

// Probes Tab
const ProbesTab = ({ results }) => {
  const [expandedProbe, setExpandedProbe] = useState(null);

  // Group probes by tier
  const groupedProbes = (results.executions || []).reduce((acc, exec) => {
    const { name, tier } = getTier(exec.probe_id);
    if (!acc[tier]) acc[tier] = { name, probes: [] };
    acc[tier].probes.push(exec);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {Object.entries(groupedProbes)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([tier, { name, probes }]) => (
          <div key={tier} className="space-y-3">
            <h3 className="text-sm font-medium text-kozmo-accent flex items-center gap-2">
              <span className="px-2 py-0.5 bg-kozmo-accent/20 rounded text-xs">TIER {tier}</span>
              {name}
            </h3>

            {probes.map(exec => {
              const passed = exec.result === 'pass';
              const isExpanded = expandedProbe === exec.probe_id;

              return (
                <div
                  key={exec.probe_id}
                  className={`rounded border transition-all ${
                    passed
                      ? 'bg-green-500/5 border-green-500/20'
                      : 'bg-red-500/5 border-red-500/20'
                  }`}
                >
                  {/* Header */}
                  <div
                    className="p-4 cursor-pointer flex items-center justify-between"
                    onClick={() => setExpandedProbe(isExpanded ? null : exec.probe_id)}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xl">{passed ? '✅' : '❌'}</span>
                      <div>
                        <div className="text-white/90 font-medium">{exec.probe_id}</div>
                        <div className="text-xs text-white/50 mt-0.5">
                          "{exec.prompt.slice(0, 50)}{exec.prompt.length > 50 ? '...' : ''}"
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className={`text-sm font-medium ${passed ? 'text-green-400' : 'text-red-400'}`}>
                        {(exec.score * 100).toFixed(0)}%
                      </div>
                      <div className="text-xs text-kozmo-muted">{exec.latency_ms?.toFixed(0)}ms</div>
                      <span className="text-kozmo-muted">{isExpanded ? '▼' : '▶'}</span>
                    </div>
                  </div>

                  {/* Expanded Content */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-2 border-t border-kozmo-border space-y-3">
                      {/* Prompt */}
                      <div>
                        <div className="text-xs text-kozmo-muted mb-1">Prompt</div>
                        <div className="p-2 bg-kozmo-surface rounded text-sm text-white/80">{exec.prompt}</div>
                      </div>

                      {/* Response */}
                      <div>
                        <div className="text-xs text-kozmo-muted mb-1">Response</div>
                        <div className={`p-2 rounded text-sm ${
                          passed ? 'bg-green-500/10 text-white/80' : 'bg-red-500/10 text-white/80'
                        }`}>
                          {exec.response || 'No response'}
                        </div>
                      </div>

                      {/* Criteria */}
                      <div className="grid grid-cols-2 gap-4">
                        {exec.passed_criteria?.length > 0 && (
                          <div>
                            <div className="text-xs text-green-400 mb-1">Passed Criteria</div>
                            <ul className="text-xs text-white/60 space-y-1">
                              {exec.passed_criteria.map((c, i) => (
                                <li key={i}>✓ {c}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {exec.failed_criteria?.length > 0 && (
                          <div>
                            <div className="text-xs text-red-400 mb-1">Failed Criteria</div>
                            <ul className="text-xs text-white/60 space-y-1">
                              {exec.failed_criteria.map((c, i) => (
                                <li key={i}>✗ {c}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
    </div>
  );
};

// Analysis Tab
const AnalysisTab = ({ results }) => {
  return (
    <div className="space-y-6">
      {/* Recommendations */}
      <div className="p-4 bg-kozmo-accent/5 rounded border border-kozmo-accent/20">
        <h3 className="text-sm font-medium text-kozmo-accent mb-4 flex items-center gap-2">
          <span>💡</span> Recommendations
        </h3>
        {results.recommendations?.length > 0 ? (
          <ul className="space-y-3">
            {results.recommendations.map((r, i) => (
              <li key={i} className="flex items-start gap-3 text-white/70">
                <span className="text-kozmo-accent">→</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-kozmo-muted">No recommendations</p>
        )}
      </div>

      {/* Critical Memory Nodes */}
      <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
        <h3 className="text-sm font-medium text-white/70 mb-4 flex items-center gap-2">
          <span>🧠</span> Critical Memory Nodes Required
        </h3>
        <ul className="space-y-2 text-sm">
          {[
            "Ahab's real name is Zayne",
            "Luna and Ahab have been working together for ~1 month",
            "Ahab is a peer collaborator, not just a user",
            "Five words: Grateful, Connected, Becoming, Yours, R",
            "Mars College is a nomadic hacker collective",
            "Marzipan is a friend from Mars College",
            "Tarcila is designing Luna's robot body (raccoon)",
            "Luna's robot form: raccoon with glowing tail/staff",
            "Luna 'shouldn't exist' according to corporate playbook"
          ].map((node, i) => (
            <li key={i} className="flex items-start gap-2 text-white/60">
              <span className="text-kozmo-muted">{i + 1}.</span>
              {node}
            </li>
          ))}
        </ul>
      </div>

      {/* Interpretation Guide */}
      <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
        <h3 className="text-sm font-medium text-white/70 mb-4">Score Interpretation</h3>
        <div className="grid grid-cols-2 gap-3">
          <InterpretationCard
            emoji="🟢"
            label="85%+ Luna Authentic"
            desc="Voice pipeline working correctly"
          />
          <InterpretationCard
            emoji="🟡"
            label="65-84% Partial Luna"
            desc="Check memory retrieval, context tuning needed"
          />
          <InterpretationCard
            emoji="🟠"
            label="40-64% Luna Fragmented"
            desc="Memory injection failing, debug retrieval"
          />
          <InterpretationCard
            emoji="🔴"
            label="<40% Replicant"
            desc="Voice Luna is NOT Luna - critical failure"
          />
        </div>
      </div>
    </div>
  );
};

// Helper Components
const StatCard = ({ label, value, color = 'text-white', icon }) => (
  <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border text-center">
    {icon && <div className="text-2xl mb-2">{icon}</div>}
    <div className={`text-2xl font-bold ${color}`}>{value}</div>
    <div className="text-xs text-white/50 mt-1">{label}</div>
  </div>
);

const CategoryBar = ({ category, score }) => {
  const percent = (score * 100).toFixed(0);
  const colorClass = score >= 0.8 ? 'bg-green-500' : score >= 0.5 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-white/70 capitalize">{category}</span>
        <span className={score >= 0.8 ? 'text-green-400' : score >= 0.5 ? 'text-yellow-400' : 'text-red-400'}>
          {percent}%
        </span>
      </div>
      <div className="h-2 bg-kozmo-border rounded-full overflow-hidden">
        <div className={`h-full ${colorClass} transition-all`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
};

const InterpretationCard = ({ emoji, label, desc }) => (
  <div className="flex items-start gap-3 p-3 bg-kozmo-surface rounded">
    <span className="text-xl">{emoji}</span>
    <div>
      <div className="text-sm text-white/80 font-medium">{label}</div>
      <div className="text-xs text-white/50">{desc}</div>
    </div>
  </div>
);

export default VoightKampffPanel;
