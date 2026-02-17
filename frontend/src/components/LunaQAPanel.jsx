import React, { useState, useEffect, useCallback } from 'react';

/**
 * Luna QA Panel — Live validation dashboard
 *
 * Shows real-time QA health, assertion results, and bug tracking.
 */

const API_BASE = 'http://127.0.0.1:8000';

// Severity colors
const severityColors = {
  critical: 'text-red-400 bg-red-500/10 border-red-500/30',
  high: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  medium: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  low: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
};

const categoryColors = {
  personality: 'text-kozmo-accent',
  structural: 'text-kozmo-accent',
  voice: 'text-pink-400',
  flow: 'text-green-400',
};

// Tabs
const TABS = ['health', 'last', 'history', 'stats', 'simulate', 'test-suite', 'assertions', 'bugs'];

const LunaQAPanel = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState('health');
  const [health, setHealth] = useState(null);
  const [lastReport, setLastReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [assertions, setAssertions] = useState([]);
  const [bugs, setBugs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch data based on active tab
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      switch (activeTab) {
        case 'health':
          const healthRes = await fetch(`${API_BASE}/qa/health`);
          if (healthRes.ok) setHealth(await healthRes.json());
          break;
        case 'last':
          const lastRes = await fetch(`${API_BASE}/qa/last`);
          if (lastRes.ok) setLastReport(await lastRes.json());
          break;
        case 'history':
          const histRes = await fetch(`${API_BASE}/qa/history?limit=20`);
          if (histRes.ok) setHistory(await histRes.json());
          break;
        case 'stats':
          const statsRes = await fetch(`${API_BASE}/qa/stats/detailed`);
          if (statsRes.ok) setStats(await statsRes.json());
          break;
        case 'assertions':
          const assertRes = await fetch(`${API_BASE}/qa/assertions`);
          if (assertRes.ok) setAssertions(await assertRes.json());
          break;
        case 'bugs':
          const bugsRes = await fetch(`${API_BASE}/qa/bugs`);
          if (bugsRes.ok) setBugs(await bugsRes.json());
          break;
        case 'simulate':
        case 'test-suite':
          // These tabs need bugs data
          const simBugsRes = await fetch(`${API_BASE}/qa/bugs`);
          if (simBugsRes.ok) setBugs(await simBugsRes.json());
          break;
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  // Fetch on tab change or open
  useEffect(() => {
    if (isOpen) {
      fetchData();
    }
  }, [isOpen, activeTab, fetchData]);

  // Auto-refresh health and stats every 5 seconds
  useEffect(() => {
    if (!isOpen || (activeTab !== 'health' && activeTab !== 'stats')) return;
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [isOpen, activeTab, fetchData]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-kozmo-surface border border-kozmo-border rounded w-[900px] max-h-[80vh] overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-kozmo-border">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🔬</span>
            <div>
              <h2 className="text-lg font-display font-semibold text-white">Luna QA</h2>
              <p className="text-xs text-white/50">Live inference validation</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-white/50 hover:text-white hover:bg-kozmo-surface/80 rounded transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-6 py-2 border-b border-kozmo-border bg-kozmo-surface">
          {TABS.map(tab => (
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
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {loading && (
            <div className="text-center text-white/50 py-8">Loading...</div>
          )}

          {error && (
            <div className="text-center text-red-400 py-8">{error}</div>
          )}

          {!loading && !error && (
            <>
              {activeTab === 'health' && <HealthTab health={health} onRefresh={fetchData} loading={loading} />}
              {activeTab === 'last' && <LastReportTab report={lastReport} />}
              {activeTab === 'history' && <HistoryTab history={history} />}
              {activeTab === 'stats' && <StatsTab stats={stats} onRefresh={fetchData} loading={loading} />}
              {activeTab === 'simulate' && <SimulateTab bugs={bugs} onRefresh={fetchData} />}
              {activeTab === 'test-suite' && <TestSuiteTab bugs={bugs} onRefresh={fetchData} />}
              {activeTab === 'assertions' && <AssertionsTab assertions={assertions} onRefresh={fetchData} />}
              {activeTab === 'bugs' && <BugsTab bugs={bugs} onRefresh={fetchData} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// Health Tab
const HealthTab = ({ health, onRefresh, loading }) => {
  if (!health) return <div className="text-white/50">No health data</div>;

  const passRate = (health.pass_rate * 100).toFixed(1);
  const statusColor = passRate >= 90 ? 'text-green-400' : passRate >= 70 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className="space-y-6">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span className="text-xs text-kozmo-muted">Auto-refreshing every 5s</span>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className={`px-3 py-1.5 text-xs rounded border transition-all ${
            loading
              ? 'bg-kozmo-surface border-kozmo-border text-kozmo-muted cursor-wait'
              : 'bg-kozmo-accent/20 border-kozmo-accent/30 text-kozmo-accent hover:bg-kozmo-accent/30'
          }`}
        >
          {loading ? '↻ Refreshing...' : '↻ Refresh'}
        </button>
      </div>

      {/* Pass Rate */}
      <div className="text-center py-8">
        <div className={`text-6xl font-bold ${statusColor}`}>{passRate}%</div>
        <div className="text-white/50 mt-2">Pass Rate (24h)</div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Total (24h)" value={health.total_24h} />
        <StatCard label="Failed (24h)" value={health.failed_24h} color={health.failed_24h > 0 ? 'text-red-400' : 'text-green-400'} />
        <StatCard label="Open Bugs" value={health.failing_bugs} color={health.failing_bugs > 0 ? 'text-orange-400' : 'text-green-400'} />
      </div>

      {/* Top Failures */}
      {health.top_failures?.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-white/70 mb-3">Top Failing Assertions</h3>
          <div className="space-y-2">
            {health.top_failures.map(f => (
              <div key={f.id} className="flex items-center justify-between p-3 bg-kozmo-surface rounded">
                <span className="text-white/80">{f.name}</span>
                <span className="text-red-400">{f.count}x</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Failures */}
      {health.recent_failures?.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-white/70 mb-3">Recent Failures</h3>
          <div className="flex flex-wrap gap-2">
            {health.recent_failures.map((name, i) => (
              <span key={i} className="px-3 py-1 bg-red-500/10 text-red-400 rounded-full text-sm">
                {name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Last Report Tab
const LastReportTab = ({ report }) => {
  if (!report) return <div className="text-white/50">No reports yet</div>;
  if (report.error) return <div className="text-white/50">{report.error}</div>;

  const statusIcon = report.passed ? '✅' : '❌';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl">{statusIcon}</span>
            <span className={`text-xl font-medium ${report.passed ? 'text-green-400' : 'text-red-400'}`}>
              {report.passed ? 'PASSED' : 'FAILED'}
            </span>
          </div>
          <p className="text-white/50 mt-1 text-sm">ID: {report.inference_id}</p>
        </div>
        <div className="text-right text-sm text-white/50">
          <div>{report.route}</div>
          <div>{report.latency_ms?.toFixed(0)}ms</div>
        </div>
      </div>

      {/* Query */}
      <div className="p-4 bg-kozmo-surface rounded">
        <div className="text-xs text-white/50 mb-1">Query</div>
        <div className="text-white">{report.query}</div>
      </div>

      {/* Assertions */}
      <div>
        <h3 className="text-sm font-medium text-white/70 mb-3">
          Assertions ({report.assertions?.length || 0})
        </h3>
        <div className="space-y-2">
          {report.assertions?.map(a => (
            <div
              key={a.id}
              className={`p-3 rounded border ${a.passed ? 'bg-green-500/5 border-green-500/20' : 'bg-red-500/10 border-red-500/30'}`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span>{a.passed ? '✓' : '✗'}</span>
                  <span className={`font-medium ${a.passed ? 'text-green-400' : 'text-red-400'}`}>
                    {a.name}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded ${severityColors[a.severity]}`}>
                    {a.severity}
                  </span>
                </div>
                <span className="text-xs text-white/50">{a.id}</span>
              </div>
              {!a.passed && (
                <div className="mt-2 text-sm text-white/60">
                  <span className="text-kozmo-muted">Expected:</span> {a.expected}<br/>
                  <span className="text-kozmo-muted">Actual:</span> {a.actual}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Diagnosis */}
      {report.diagnosis && (
        <div className="p-4 bg-orange-500/10 border border-orange-500/30 rounded">
          <div className="text-xs text-orange-400 mb-1">Diagnosis</div>
          <div className="text-white/80 text-sm">{report.diagnosis}</div>
        </div>
      )}
    </div>
  );
};

// History Tab
const HistoryTab = ({ history }) => {
  if (!history?.length) return <div className="text-white/50">No history yet</div>;

  return (
    <div className="space-y-2">
      {history.map(r => (
        <div
          key={r.inference_id}
          className={`p-4 rounded border ${r.passed ? 'bg-kozmo-surface border-kozmo-border' : 'bg-red-500/10 border-red-500/30'}`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span>{r.passed ? '✅' : '❌'}</span>
              <span className="text-white/80 truncate max-w-[400px]">{r.query}</span>
            </div>
            <div className="flex items-center gap-4 text-sm text-white/50">
              <span>{r.route}</span>
              <span>{r.latency_ms?.toFixed(0)}ms</span>
              <span>{new Date(r.timestamp).toLocaleTimeString()}</span>
            </div>
          </div>
          {!r.passed && r.failed_count > 0 && (
            <div className="mt-2 text-sm text-red-400">
              {r.failed_count} assertion{r.failed_count > 1 ? 's' : ''} failed
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

// Stats Tab
const StatsTab = ({ stats, onRefresh, loading }) => {
  const [autoRefresh, setAutoRefresh] = useState(true);

  if (!stats) return <div className="text-white/50">No stats available</div>;

  const passRate = (stats.pass_rate * 100).toFixed(1);

  return (
    <div className="space-y-6">
      {/* Header with refresh controls */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-kozmo-accent font-medium">QA Statistics</h3>
          <p className="text-xs text-kozmo-muted mt-1">
            Time range: {stats.time_range || '7d'} • Last updated: {new Date().toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-white/50 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="accent-violet-500"
            />
            Auto-refresh
          </label>
          <button
            onClick={onRefresh}
            disabled={loading}
            className={`px-3 py-1.5 text-xs rounded border transition-all ${
              loading
                ? 'bg-kozmo-surface border-kozmo-border text-kozmo-muted cursor-wait'
                : 'bg-kozmo-accent/20 border-kozmo-accent/30 text-kozmo-accent hover:bg-kozmo-accent/30'
            }`}
          >
            {loading ? '↻ Refreshing...' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="p-4 bg-kozmo-surface rounded text-center">
          <div className="text-2xl font-bold text-white">{stats.total || 0}</div>
          <div className="text-xs text-white/50 mt-1">Total Inferences</div>
        </div>
        <div className="p-4 bg-green-500/10 border border-green-500/20 rounded text-center">
          <div className="text-2xl font-bold text-green-400">{stats.passed || 0}</div>
          <div className="text-xs text-green-400/70 mt-1">Passed</div>
        </div>
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded text-center">
          <div className="text-2xl font-bold text-red-400">{stats.failed || 0}</div>
          <div className="text-xs text-red-400/70 mt-1">Failed</div>
        </div>
        <div className="p-4 bg-kozmo-accent/10 border border-kozmo-accent/20 rounded text-center">
          <div className="text-2xl font-bold text-kozmo-accent">{passRate}%</div>
          <div className="text-xs text-kozmo-accent/70 mt-1">Pass Rate</div>
        </div>
      </div>

      {/* Trend Chart */}
      {stats.trend?.length > 0 && (
        <div className="p-4 bg-kozmo-surface rounded">
          <h3 className="text-sm font-medium text-kozmo-accent mb-4">Pass Rate Trend</h3>
          <div className="flex items-end gap-2 h-32">
            {stats.trend.map((day, i) => {
              const total = (day.passed || 0) + (day.failed || 0);
              const rate = total > 0 ? (day.passed || 0) / total : 0;
              return (
                <div key={i} className="flex-1 flex flex-col items-center">
                  <div
                    className={`w-full rounded-t transition-all ${
                      rate >= 0.8 ? 'bg-green-500' : rate >= 0.6 ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                    style={{ height: `${Math.max(rate * 100, 5)}%` }}
                  />
                  <div className="text-[10px] text-kozmo-muted mt-2 truncate w-full text-center">
                    {day.date}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* By Route */}
      {stats.by_route && Object.keys(stats.by_route).length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-kozmo-surface rounded">
            <h3 className="text-sm font-medium text-kozmo-accent mb-4">By Route</h3>
            {Object.entries(stats.by_route).map(([route, data]) => {
              const total = (data.passed || 0) + (data.failed || 0);
              const passPercent = total > 0 ? ((data.passed || 0) / total) * 100 : 0;
              return (
                <div key={route} className="mb-3">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-white/70">{route}</span>
                    <span className="text-white/50">{data.passed || 0}/{total}</span>
                  </div>
                  <div className="h-2 bg-kozmo-border rounded-full overflow-hidden flex">
                    <div
                      className="bg-green-500 h-full"
                      style={{ width: `${passPercent}%` }}
                    />
                    <div
                      className="bg-red-500 h-full"
                      style={{ width: `${100 - passPercent}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* By Provider */}
          <div className="p-4 bg-kozmo-surface rounded">
            <h3 className="text-sm font-medium text-kozmo-accent mb-4">By Provider</h3>
            {stats.by_provider && Object.entries(stats.by_provider).map(([provider, data]) => {
              const total = (data.passed || 0) + (data.failed || 0);
              const passPercent = total > 0 ? ((data.passed || 0) / total) * 100 : 0;
              return (
                <div key={provider} className="mb-3">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-white/70">{provider}</span>
                    <span className="text-white/50">{data.passed || 0}/{total}</span>
                  </div>
                  <div className="h-2 bg-kozmo-border rounded-full overflow-hidden flex">
                    <div
                      className="bg-green-500 h-full"
                      style={{ width: `${passPercent}%` }}
                    />
                    <div
                      className="bg-red-500 h-full"
                      style={{ width: `${100 - passPercent}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* By Assertion */}
      {stats.by_assertion && Object.keys(stats.by_assertion).length > 0 && (
        <div className="p-4 bg-kozmo-surface rounded">
          <h3 className="text-sm font-medium text-kozmo-accent mb-4">Assertion Failure Rates</h3>
          {Object.entries(stats.by_assertion)
            .sort((a, b) => {
              const aTotal = (a[1].passed || 0) + (a[1].failed || 0);
              const bTotal = (b[1].passed || 0) + (b[1].failed || 0);
              const aRate = aTotal > 0 ? (a[1].failed || 0) / aTotal : 0;
              const bRate = bTotal > 0 ? (b[1].failed || 0) / bTotal : 0;
              return bRate - aRate;
            })
            .map(([id, data]) => {
              const total = (data.passed || 0) + (data.failed || 0);
              const passPercent = total > 0 ? ((data.passed || 0) / total) * 100 : 100;
              return (
                <div key={id} className="flex items-center gap-3 mb-2">
                  <div className="w-32 text-xs text-white/70 truncate">{data.name || id}</div>
                  <div className="flex-1 h-4 bg-kozmo-border rounded overflow-hidden flex">
                    <div
                      className="bg-green-500 h-full"
                      style={{ width: `${passPercent}%` }}
                    />
                    <div
                      className="bg-red-500 h-full"
                      style={{ width: `${100 - passPercent}%` }}
                    />
                  </div>
                  <div className="w-16 text-right text-xs">
                    <span className="text-red-400">{data.failed || 0}</span>
                    <span className="text-kozmo-muted"> fail</span>
                  </div>
                </div>
              );
            })}
        </div>
      )}
    </div>
  );
};

// Assertions Tab
const AssertionsTab = ({ assertions, onRefresh }) => {
  const toggleAssertion = async (id, enabled) => {
    try {
      await fetch(`${API_BASE}/qa/assertions/${id}?enabled=${!enabled}`, { method: 'PUT' });
      onRefresh();
    } catch (e) {
      console.error('Failed to toggle assertion:', e);
    }
  };

  if (!assertions?.length) return <div className="text-white/50">No assertions loaded</div>;

  // Group by category
  const grouped = assertions.reduce((acc, a) => {
    if (!acc[a.category]) acc[a.category] = [];
    acc[a.category].push(a);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category}>
          <h3 className={`text-sm font-medium mb-3 ${categoryColors[category] || 'text-white/70'}`}>
            {category.charAt(0).toUpperCase() + category.slice(1)} ({items.length})
          </h3>
          <div className="space-y-2">
            {items.map(a => (
              <div key={a.id} className="flex items-center justify-between p-3 bg-kozmo-surface rounded">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-white/80">{a.id}</span>
                    <span className="text-white/60">{a.name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${severityColors[a.severity]}`}>
                      {a.severity}
                    </span>
                  </div>
                  {a.description && (
                    <p className="text-xs text-kozmo-muted mt-1">{a.description}</p>
                  )}
                </div>
                <button
                  onClick={() => toggleAssertion(a.id, a.enabled)}
                  className={`px-3 py-1 text-xs rounded ${
                    a.enabled
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-kozmo-border text-kozmo-muted'
                  }`}
                >
                  {a.enabled ? 'ON' : 'OFF'}
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

// Simulate Tab
const SimulateTab = ({ bugs, onRefresh }) => {
  const [selectedBug, setSelectedBug] = useState(null);
  const [simResult, setSimResult] = useState(null);
  const [running, setRunning] = useState(false);

  const runSimulation = async (bug) => {
    setRunning(true);
    setSimResult(null);

    try {
      const res = await fetch(`${API_BASE}/qa/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: bug.query, bug_id: bug.id }),
      });

      if (res.ok) {
        const data = await res.json();
        setSimResult(data);
      } else {
        setSimResult({ error: 'Simulation failed' });
      }
    } catch (e) {
      setSimResult({ error: e.message });
    } finally {
      setRunning(false);
    }
  };

  const statusColors = {
    open: 'border-red-500/50',
    failing: 'border-orange-500/50',
    fixed: 'border-green-500/50',
    wontfix: 'border-kozmo-border/80',
  };

  return (
    <div className="grid grid-cols-2 gap-6">
      {/* Bug List */}
      <div>
        <h3 className="text-sm font-medium text-kozmo-accent mb-3">Known Bugs</h3>
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {bugs?.map(bug => (
            <div
              key={bug.id}
              onClick={() => setSelectedBug(bug)}
              className={`p-3 rounded border-l-4 cursor-pointer transition-colors ${statusColors[bug.status]} ${
                selectedBug?.id === bug.id ? 'bg-kozmo-accent/20 border-kozmo-accent/50' : 'bg-kozmo-surface hover:bg-kozmo-surface/80'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-white/90">{bug.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  bug.status === 'fixed' ? 'bg-green-500/20 text-green-400' :
                  bug.status === 'failing' ? 'bg-red-500/20 text-red-400' :
                  'bg-orange-500/20 text-orange-400'
                }`}>
                  {bug.status}
                </span>
              </div>
              <p className="text-xs text-white/50 truncate">"{bug.query}"</p>
              <div className="flex gap-2 mt-2">
                <span className="text-xs px-2 py-0.5 bg-kozmo-border rounded text-white/50">{bug.severity}</span>
                <span className="text-xs px-2 py-0.5 bg-kozmo-border rounded text-kozmo-muted">{bug.id}</span>
              </div>
            </div>
          ))}
          {(!bugs || bugs.length === 0) && (
            <div className="text-white/50 text-center py-8">No bugs tracked yet</div>
          )}
        </div>
      </div>

      {/* Simulation Panel */}
      <div>
        <h3 className="text-sm font-medium text-kozmo-accent mb-3">Simulation</h3>
        {selectedBug ? (
          <div className="bg-kozmo-surface rounded p-4 border border-kozmo-border">
            <div className="mb-4">
              <div className="text-xs text-white/50 mb-1">Selected Bug</div>
              <div className="text-white font-medium">{selectedBug.name}</div>
              <div className="text-kozmo-accent mt-1">"{selectedBug.query}"</div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <div className="text-xs text-green-400 mb-1">Expected</div>
                <div className="text-sm text-white/70">{selectedBug.expected_behavior}</div>
              </div>
              <div>
                <div className="text-xs text-red-400 mb-1">Last Actual</div>
                <div className="text-sm text-white/70">{selectedBug.actual_behavior}</div>
              </div>
            </div>

            {selectedBug.root_cause && (
              <div className="text-xs text-white/50 mb-4">
                <strong>Root Cause:</strong> {selectedBug.root_cause}
              </div>
            )}

            <button
              onClick={() => runSimulation(selectedBug)}
              disabled={running}
              className={`w-full py-3 rounded font-medium transition-colors ${
                running
                  ? 'bg-kozmo-accent/20 text-kozmo-accent cursor-wait'
                  : 'bg-kozmo-accent/30 hover:bg-kozmo-accent/40 text-kozmo-accent'
              }`}
            >
              {running ? '⏳ Running...' : '▶️ Run Simulation'}
            </button>

            {simResult && (
              <div className="mt-4 pt-4 border-t border-kozmo-border">
                {simResult.error ? (
                  <div className="text-red-400">{simResult.error}</div>
                ) : (
                  <>
                    <div className="flex items-center gap-3 mb-4">
                      <span className="text-2xl">{simResult.passed ? '✅' : '❌'}</span>
                      <div>
                        <div className={`font-medium ${simResult.passed ? 'text-green-400' : 'text-red-400'}`}>
                          {simResult.passed ? 'PASSED' : 'STILL FAILING'}
                        </div>
                        {simResult.latency_ms && (
                          <div className="text-xs text-white/50">{simResult.latency_ms}ms</div>
                        )}
                      </div>
                    </div>

                    <div className="text-xs text-white/50 mb-2">Response</div>
                    <pre className={`p-3 rounded text-sm whitespace-pre-wrap ${
                      simResult.passed
                        ? 'bg-green-500/10 border border-green-500/20 text-white/80'
                        : 'bg-red-500/10 border border-red-500/20 text-white/80'
                    }`}>
                      {simResult.response || simResult.final_response || 'No response'}
                    </pre>

                    {simResult.failed_assertions?.length > 0 && (
                      <div className="mt-3 text-xs text-red-400">
                        Failed: {simResult.failed_assertions.join(', ')}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="bg-kozmo-surface rounded p-8 text-center border border-kozmo-border">
            <div className="text-white/50">← Select a bug to simulate</div>
          </div>
        )}
      </div>
    </div>
  );
};

// Test Suite Tab
const TestSuiteTab = ({ bugs, onRefresh }) => {
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState(null);

  const runFullSuite = async () => {
    if (!bugs?.length) return;

    setRunning(true);
    setProgress(0);
    setResults(null);

    const testResults = [];
    const startTime = Date.now();

    for (let i = 0; i < bugs.length; i++) {
      const bug = bugs[i];
      try {
        const res = await fetch(`${API_BASE}/qa/simulate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: bug.query, bug_id: bug.id }),
        });

        if (res.ok) {
          const data = await res.json();
          testResults.push({
            bugId: bug.id,
            bugName: bug.name,
            query: bug.query,
            passed: data.passed,
            response: data.response || data.final_response,
            failedAssertions: data.failed_assertions || [],
          });
        } else {
          testResults.push({
            bugId: bug.id,
            bugName: bug.name,
            query: bug.query,
            passed: false,
            response: 'API Error',
            failedAssertions: ['API_ERROR'],
          });
        }
      } catch (e) {
        testResults.push({
          bugId: bug.id,
          bugName: bug.name,
          query: bug.query,
          passed: false,
          response: e.message,
          failedAssertions: ['EXCEPTION'],
        });
      }

      setProgress(((i + 1) / bugs.length) * 100);
    }

    setResults({
      lastRun: new Date().toISOString(),
      duration: Date.now() - startTime,
      results: testResults,
    });
    setRunning(false);
  };

  const passedCount = results?.results.filter(r => r.passed).length || 0;
  const totalCount = results?.results.length || 0;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-kozmo-accent font-medium">Regression Test Suite</h3>
          {results && (
            <p className="text-xs text-white/50 mt-1">
              Last run: {new Date(results.lastRun).toLocaleString()} ({results.duration}ms)
            </p>
          )}
        </div>
        <button
          onClick={runFullSuite}
          disabled={running || !bugs?.length}
          className={`px-6 py-3 rounded font-medium transition-colors ${
            running
              ? 'bg-kozmo-accent/20 text-kozmo-accent cursor-wait'
              : 'bg-kozmo-accent/30 hover:bg-kozmo-accent/40 text-kozmo-accent'
          }`}
        >
          {running ? `⏳ Running... ${progress.toFixed(0)}%` : '▶️ Run All Tests'}
        </button>
      </div>

      {/* Progress Bar */}
      {running && (
        <div className="mb-6">
          <div className="h-2 bg-kozmo-border rounded-full overflow-hidden">
            <div
              className="h-full bg-kozmo-accent transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Summary Cards */}
      {results && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="p-4 bg-kozmo-surface rounded text-center">
            <div className="text-2xl font-bold text-white">{totalCount}</div>
            <div className="text-xs text-white/50 mt-1">Total Tests</div>
          </div>
          <div className="p-4 bg-green-500/10 border border-green-500/20 rounded text-center">
            <div className="text-2xl font-bold text-green-400">{passedCount}</div>
            <div className="text-xs text-green-400/70 mt-1">Passing</div>
          </div>
          <div className="p-4 bg-red-500/10 border border-red-500/20 rounded text-center">
            <div className="text-2xl font-bold text-red-400">{totalCount - passedCount}</div>
            <div className="text-xs text-red-400/70 mt-1">Failing</div>
          </div>
        </div>
      )}

      {/* Results List */}
      {results && (
        <div>
          <h4 className="text-sm font-medium text-white/70 mb-3">Test Results</h4>
          <div className="space-y-2">
            {results.results.map(result => (
              <div
                key={result.bugId}
                className={`p-4 rounded border-l-4 ${
                  result.passed
                    ? 'bg-green-500/5 border-green-500'
                    : 'bg-red-500/10 border-red-500'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{result.passed ? '✅' : '❌'}</span>
                    <div>
                      <div className="text-white/90 font-medium">{result.bugName}</div>
                      <div className="text-xs text-white/50">"{result.query}"</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-xs px-2 py-1 rounded ${
                      result.passed ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {result.passed ? 'PASS' : 'FAIL'}
                    </span>
                    {result.failedAssertions.length > 0 && (
                      <div className="text-xs text-red-400 mt-1">
                        {result.failedAssertions.join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!results && !running && (
        <div className="text-center py-12 text-white/50">
          Click "Run All Tests" to execute the regression suite
        </div>
      )}
    </div>
  );
};

// Bugs Tab
const BugsTab = ({ bugs, onRefresh }) => {
  const updateStatus = async (bugId, status) => {
    try {
      await fetch(`${API_BASE}/qa/bugs/${bugId}?status=${status}`, { method: 'PUT' });
      onRefresh();
    } catch (e) {
      console.error('Failed to update bug:', e);
    }
  };

  if (!bugs?.length) return <div className="text-white/50">No bugs tracked yet</div>;

  const statusColors = {
    open: 'bg-red-500/20 text-red-400',
    failing: 'bg-orange-500/20 text-orange-400',
    fixed: 'bg-green-500/20 text-green-400',
    wontfix: 'bg-kozmo-border text-kozmo-muted',
  };

  return (
    <div className="space-y-3">
      {bugs.map(bug => (
        <div key={bug.id} className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-white/50">{bug.id}</span>
                <span className="font-medium text-white">{bug.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${statusColors[bug.status]}`}>
                  {bug.status}
                </span>
              </div>
              <p className="text-sm text-white/60 mt-2">
                <span className="text-kozmo-muted">Query:</span> {bug.query}
              </p>
            </div>
            <select
              value={bug.status}
              onChange={(e) => updateStatus(bug.id, e.target.value)}
              className="px-2 py-1 text-xs bg-kozmo-border border border-kozmo-border/80 rounded text-white"
            >
              <option value="open">Open</option>
              <option value="failing">Failing</option>
              <option value="fixed">Fixed</option>
              <option value="wontfix">Won't Fix</option>
            </select>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-kozmo-muted text-xs mb-1">Expected</div>
              <div className="text-white/70">{bug.expected_behavior}</div>
            </div>
            <div>
              <div className="text-kozmo-muted text-xs mb-1">Actual</div>
              <div className="text-white/70">{bug.actual_behavior}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// Stat Card Component
const StatCard = ({ label, value, color = 'text-white' }) => (
  <div className="p-4 bg-kozmo-surface rounded text-center">
    <div className={`text-2xl font-bold ${color}`}>{value}</div>
    <div className="text-xs text-white/50 mt-1">{label}</div>
  </div>
);

export default LunaQAPanel;
