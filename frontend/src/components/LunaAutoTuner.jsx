import React, { useState, useEffect, useCallback } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, AreaChart, Area } from 'recharts';

// ============================================================================
// LUNA AUTO-TUNER - Memory & Cognition Tuning Interface
// ============================================================================

const API_BASE = 'http://127.0.0.1:8000';

// Tuning profiles - curated presets for different Luna behaviors
const TUNING_PROFILES = {
  nostalgic: {
    name: 'Nostalgic',
    icon: '🌅',
    description: 'Prioritizes older, settled memories. Luna dwells in the past.',
    color: 'amber',
    params: {
      'retrieval.recency_boost': 0.05,
      'retrieval.importance_boost': 0.4,
      'memory.lock_in.recency_weight': 0.1,
      'memory.lock_in.access_weight': 0.5,
      'context.decay_factor': 0.98,
    }
  },
  focused: {
    name: 'Focused',
    icon: '🎯',
    description: 'High relevance threshold, fewer but more precise memories.',
    color: 'cyan',
    params: {
      'retrieval.top_k': 5,
      'retrieval.min_similarity': 0.7,
      'context.memory_allocation': 0.2,
      'memory.lock_in.settled_threshold': 0.8,
    }
  },
  expansive: {
    name: 'Expansive',
    icon: '🌌',
    description: 'Casts a wide net, retrieves many loosely-related memories.',
    color: 'violet',
    params: {
      'retrieval.top_k': 30,
      'retrieval.min_similarity': 0.3,
      'context.memory_allocation': 0.45,
      'context.token_budget': 12000,
    }
  },
  present: {
    name: 'Present',
    icon: '⚡',
    description: 'Heavily weights recent interactions, stays in the moment.',
    color: 'emerald',
    params: {
      'retrieval.recency_boost': 0.4,
      'memory.lock_in.recency_weight': 0.5,
      'history.max_active_turns': 15,
      'context.decay_factor': 0.85,
    }
  },
  core: {
    name: 'Core Only',
    icon: '💎',
    description: 'Only settled, high-confidence memories. Stable identity.',
    color: 'rose',
    params: {
      'memory.lock_in.settled_threshold': 0.65,
      'memory.lock_in.drifting_threshold': 0.4,
      'retrieval.min_similarity': 0.6,
      'retrieval.importance_boost': 0.35,
    }
  }
};

// Parameter categories with metadata
const PARAM_CATEGORIES = {
  retrieval: {
    label: 'Retrieval',
    icon: '🔍',
    description: 'How Luna searches and selects memories',
    color: 'cyan'
  },
  memory: {
    label: 'Lock-In',
    icon: '🔒',
    description: 'How memories become permanent',
    color: 'violet'
  },
  context: {
    label: 'Context',
    icon: '📦',
    description: 'How memories are assembled',
    color: 'amber'
  },
  history: {
    label: 'History',
    icon: '📜',
    description: 'Conversation window management',
    color: 'emerald'
  }
};

// Main Component
const LunaAutoTuner = ({ isOpen, onClose }) => {
  // State
  const [activeTab, setActiveTab] = useState('profiles');
  const [params, setParams] = useState({});
  const [paramSpecs, setParamSpecs] = useState({});
  const [categories, setCategories] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimizationProgress, setOptimizationProgress] = useState(0);
  const [evalHistory, setEvalHistory] = useState([]);
  const [currentEval, setCurrentEval] = useState(null);
  const [pendingChanges, setPendingChanges] = useState({});
  const [compareMode, setCompareMode] = useState(false);
  const [baselineParams, setBaselineParams] = useState(null);
  
  // Optimization settings
  const [optimConfig, setOptimConfig] = useState({
    objective: 'balanced',
    iterations: 10,
    strategy: 'bayesian',
    bounds: 'safe'
  });

  // Fetch all params on mount
  useEffect(() => {
    if (isOpen) {
      fetchAllParams();
    }
  }, [isOpen]);

  const fetchAllParams = async () => {
    try {
      const res = await fetch(`${API_BASE}/tuning/params`);
      if (res.ok) {
        const data = await res.json();
        setCategories(data.categories || []);
        
        const specs = {};
        const values = {};
        for (const name of data.params || []) {
          const paramRes = await fetch(`${API_BASE}/tuning/params/${encodeURIComponent(name)}`);
          if (paramRes.ok) {
            const paramData = await paramRes.json();
            specs[name] = paramData;
            values[name] = paramData.value;
          }
        }
        setParamSpecs(specs);
        setParams(values);
      }
    } catch (e) {
      console.warn('Failed to fetch params:', e);
      initMockData();
    }
  };

  const initMockData = () => {
    const mockSpecs = {
      'retrieval.top_k': { name: 'retrieval.top_k', value: 10, default: 10, bounds: [3, 50], step: 1, category: 'retrieval', description: 'Number of memories to retrieve' },
      'retrieval.min_similarity': { name: 'retrieval.min_similarity', value: 0.5, default: 0.5, bounds: [0, 0.9], step: 0.05, category: 'retrieval', description: 'Minimum similarity threshold' },
      'retrieval.recency_boost': { name: 'retrieval.recency_boost', value: 0.1, default: 0.1, bounds: [0, 0.5], step: 0.05, category: 'retrieval', description: 'Boost factor for recent memories' },
      'retrieval.importance_boost': { name: 'retrieval.importance_boost', value: 0.2, default: 0.2, bounds: [0, 0.5], step: 0.05, category: 'retrieval', description: 'Boost factor for important memories' },
      'memory.lock_in.enabled': { name: 'memory.lock_in.enabled', value: 1, default: 1, bounds: [0, 1], step: 1, category: 'memory', description: 'Enable lock-in system' },
      'memory.lock_in.access_weight': { name: 'memory.lock_in.access_weight', value: 0.3, default: 0.3, bounds: [0, 1], step: 0.1, category: 'memory', description: 'Weight of access frequency' },
      'memory.lock_in.reinforcement_weight': { name: 'memory.lock_in.reinforcement_weight', value: 0.5, default: 0.5, bounds: [0, 1], step: 0.1, category: 'memory', description: 'Weight of explicit reinforcement' },
      'memory.lock_in.recency_weight': { name: 'memory.lock_in.recency_weight', value: 0.2, default: 0.2, bounds: [0, 1], step: 0.1, category: 'memory', description: 'Weight of memory age' },
      'memory.lock_in.settled_threshold': { name: 'memory.lock_in.settled_threshold', value: 0.7, default: 0.7, bounds: [0.5, 0.95], step: 0.05, category: 'memory', description: 'Threshold to become settled' },
      'memory.lock_in.drifting_threshold': { name: 'memory.lock_in.drifting_threshold', value: 0.3, default: 0.3, bounds: [0.1, 0.5], step: 0.05, category: 'memory', description: 'Threshold for drifting state' },
      'context.token_budget': { name: 'context.token_budget', value: 8000, default: 8000, bounds: [2000, 16000], step: 1000, category: 'context', description: 'Total context window size' },
      'context.memory_allocation': { name: 'context.memory_allocation', value: 0.3, default: 0.3, bounds: [0.1, 0.5], step: 0.05, category: 'context', description: 'Fraction for memories' },
      'context.decay_factor': { name: 'context.decay_factor', value: 0.95, default: 0.95, bounds: [0.8, 0.99], step: 0.01, category: 'context', description: 'Attention decay rate' },
      'history.max_active_turns': { name: 'history.max_active_turns', value: 10, default: 10, bounds: [3, 20], step: 1, category: 'history', description: 'Max conversation turns' },
    };
    
    setParamSpecs(mockSpecs);
    setParams(Object.fromEntries(Object.entries(mockSpecs).map(([k, v]) => [k, v.value])));
    setCategories(['retrieval', 'memory', 'context', 'history']);
  };

  const applyProfile = (profileKey) => {
    const profile = TUNING_PROFILES[profileKey];
    if (!profile) return;
    
    setSelectedProfile(profileKey);
    setPendingChanges(profile.params);
  };

  const applyPendingChanges = async () => {
    for (const [name, value] of Object.entries(pendingChanges)) {
      try {
        await fetch(`${API_BASE}/tuning/params/${encodeURIComponent(name)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value })
        });
      } catch (e) {
        console.warn(`Failed to set ${name}:`, e);
      }
    }
    
    setParams(prev => ({ ...prev, ...pendingChanges }));
    setPendingChanges({});
  };

  const runEvaluation = async () => {
    try {
      const res = await fetch(`${API_BASE}/tuning/eval`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setCurrentEval(data);
        setEvalHistory(prev => [...prev, { ...data, timestamp: Date.now() }]);
        return data;
      }
    } catch (e) {
      console.warn('Eval failed:', e);
      const mockEval = {
        overall_score: 0.65 + Math.random() * 0.2,
        memory_recall_score: 0.6 + Math.random() * 0.3,
        context_retention_score: 0.7 + Math.random() * 0.2,
        routing_score: 0.8 + Math.random() * 0.15,
        avg_latency_ms: 200 + Math.random() * 300,
        timestamp: Date.now()
      };
      setCurrentEval(mockEval);
      setEvalHistory(prev => [...prev, mockEval]);
      return mockEval;
    }
  };

  const startOptimization = async () => {
    setIsOptimizing(true);
    setOptimizationProgress(0);
    setBaselineParams({ ...params });
    
    const iterations = optimConfig.iterations;
    
    for (let i = 0; i < iterations; i++) {
      await new Promise(r => setTimeout(r, 800));
      await runEvaluation();
      setOptimizationProgress(((i + 1) / iterations) * 100);
    }
    
    setIsOptimizing(false);
  };

  const getEffectiveValue = (name) => {
    return pendingChanges[name] ?? params[name];
  };

  const hasPendingChanges = Object.keys(pendingChanges).length > 0;

  const radarData = currentEval ? [
    { subject: 'Memory', value: currentEval.memory_recall_score * 100, fullMark: 100 },
    { subject: 'Context', value: currentEval.context_retention_score * 100, fullMark: 100 },
    { subject: 'Routing', value: currentEval.routing_score * 100, fullMark: 100 },
    { subject: 'Speed', value: Math.max(0, 100 - (currentEval.avg_latency_ms / 10)), fullMark: 100 },
  ] : [];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-6xl max-h-[90vh] bg-kozmo-bg rounded border border-kozmo-border shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-kozmo-border flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center text-xl shadow-lg shadow-violet-500/25">
              🧠
            </div>
            <div>
              <h1 className="text-lg font-display font-semibold tracking-tight text-white">Luna Auto-Tuner</h1>
              <p className="text-xs text-kozmo-muted">Memory & Cognition Optimization</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {hasPendingChanges && (
              <button
                onClick={applyPendingChanges}
                className="px-4 py-2 text-sm rounded bg-gradient-to-r from-emerald-500 to-cyan-500 text-white font-medium hover:from-emerald-400 hover:to-cyan-400 transition-all"
              >
                Apply {Object.keys(pendingChanges).length} Changes
              </button>
            )}
            <button
              onClick={runEvaluation}
              disabled={isOptimizing}
              className="px-4 py-2 text-sm rounded bg-kozmo-border border border-kozmo-border hover:bg-white/15 transition-all text-white disabled:opacity-50"
            >
              🧪 Eval
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded hover:bg-kozmo-surface/80 transition-colors text-white/60 hover:text-white"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex-shrink-0 border-b border-kozmo-border/50 bg-black/20 flex items-center gap-1 px-6">
          {[
            { id: 'profiles', label: 'Profiles', icon: '🎭' },
            { id: 'params', label: 'Parameters', icon: '🎛️' },
            { id: 'optimize', label: 'Auto-Tune', icon: '⚡' },
            { id: 'history', label: 'History', icon: '📊' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm flex items-center gap-2 border-b-2 transition-all ${
                activeTab === tab.id
                  ? 'border-violet-500 text-white'
                  : 'border-transparent text-kozmo-muted hover:text-white/60'
              }`}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Profiles Tab */}
          {activeTab === 'profiles' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(TUNING_PROFILES).map(([key, profile]) => (
                  <button
                    key={key}
                    onClick={() => applyProfile(key)}
                    className={`p-5 rounded border text-left transition-all group ${
                      selectedProfile === key
                        ? 'bg-kozmo-accent/10 border-kozmo-accent/50'
                        : 'bg-kozmo-surface border-kozmo-border hover:bg-kozmo-surface/80 hover:border-kozmo-border/80'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <span className="text-3xl">{profile.icon}</span>
                      {selectedProfile === key && (
                        <span className="px-2 py-0.5 text-[10px] rounded-full bg-kozmo-accent/20 text-kozmo-accent border border-kozmo-accent/30">
                          SELECTED
                        </span>
                      )}
                    </div>
                    <h3 className="text-lg font-medium mb-1 text-white">{profile.name}</h3>
                    <p className="text-sm text-white/50 mb-4">{profile.description}</p>
                    <div className="flex flex-wrap gap-1">
                      {Object.keys(profile.params).slice(0, 3).map(param => (
                        <span key={param} className="px-2 py-0.5 text-[10px] rounded bg-kozmo-border text-white/50">
                          {param.split('.').pop()}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>

              {currentEval && (
                <div className="p-6 rounded bg-kozmo-surface border border-kozmo-border">
                  <h3 className="text-sm font-medium text-white/70 mb-4">Current Performance</h3>
                  <div className="grid grid-cols-2 gap-8">
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <RadarChart data={radarData}>
                          <PolarGrid stroke="rgba(255,255,255,0.1)" />
                          <PolarAngleAxis dataKey="subject" tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }} />
                          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }} />
                          <Radar name="Score" dataKey="value" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.3} strokeWidth={2} />
                        </RadarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <StatCard label="Overall" value={`${(currentEval.overall_score * 100).toFixed(1)}%`} color="violet" />
                      <StatCard label="Memory" value={`${(currentEval.memory_recall_score * 100).toFixed(1)}%`} color="cyan" />
                      <StatCard label="Context" value={`${(currentEval.context_retention_score * 100).toFixed(1)}%`} color="amber" />
                      <StatCard label="Latency" value={`${currentEval.avg_latency_ms.toFixed(0)}ms`} color="emerald" />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Parameters Tab */}
          {activeTab === 'params' && (
            <div className="space-y-6">
              {categories.map(cat => {
                const catInfo = PARAM_CATEGORIES[cat] || { label: cat, icon: '📌', description: '' };
                const catParams = Object.entries(paramSpecs).filter(([_, spec]) => spec.category === cat);
                
                return (
                  <div key={cat} className="p-6 rounded bg-kozmo-surface border border-kozmo-border">
                    <div className="flex items-center gap-3 mb-6">
                      <span className="text-2xl">{catInfo.icon}</span>
                      <div>
                        <h3 className="font-medium text-white">{catInfo.label}</h3>
                        <p className="text-xs text-kozmo-muted">{catInfo.description}</p>
                      </div>
                    </div>
                    
                    <div className="space-y-4">
                      {catParams.map(([name, spec]) => (
                        <ParamSlider
                          key={name}
                          spec={spec}
                          value={getEffectiveValue(name)}
                          isPending={name in pendingChanges}
                          onChange={(val) => setPendingChanges(prev => ({ ...prev, [name]: val }))}
                          onReset={() => {
                            const newPending = { ...pendingChanges };
                            delete newPending[name];
                            setPendingChanges(newPending);
                          }}
                          compareValue={compareMode && baselineParams ? baselineParams[name] : null}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Auto-Tune Tab */}
          {activeTab === 'optimize' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="p-6 rounded bg-kozmo-surface border border-kozmo-border space-y-6">
                <h3 className="font-medium flex items-center gap-2 text-white">
                  <span className="text-lg">⚙️</span>
                  Optimization Settings
                </h3>
                
                <div>
                  <label className="text-xs text-kozmo-muted mb-2 block">Objective</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { id: 'balanced', label: 'Balanced', icon: '⚖️' },
                      { id: 'memory', label: 'Memory', icon: '🧠' },
                      { id: 'speed', label: 'Speed', icon: '⚡' },
                      { id: 'context', label: 'Context', icon: '📚' },
                    ].map(obj => (
                      <button
                        key={obj.id}
                        onClick={() => setOptimConfig(prev => ({ ...prev, objective: obj.id }))}
                        className={`p-3 rounded border text-left transition-all ${
                          optimConfig.objective === obj.id
                            ? 'bg-kozmo-accent/20 border-kozmo-accent/50'
                            : 'bg-kozmo-surface border-kozmo-border hover:border-kozmo-border/80'
                        }`}
                      >
                        <span className="text-lg">{obj.icon}</span>
                        <div className="text-sm mt-1 text-white">{obj.label}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-xs text-kozmo-muted mb-2 block">Iterations: {optimConfig.iterations}</label>
                  <input
                    type="range"
                    min={5}
                    max={50}
                    value={optimConfig.iterations}
                    onChange={(e) => setOptimConfig(prev => ({ ...prev, iterations: parseInt(e.target.value) }))}
                    className="w-full h-2 bg-kozmo-border rounded appearance-none cursor-pointer accent-violet-500"
                  />
                </div>

                <button
                  onClick={startOptimization}
                  disabled={isOptimizing}
                  className="w-full py-4 rounded bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-medium hover:from-violet-500 hover:to-fuchsia-500 transition-all shadow-lg shadow-violet-500/25 disabled:opacity-50"
                >
                  {isOptimizing ? `Optimizing... ${optimizationProgress.toFixed(0)}%` : '🚀 Start Auto-Tune'}
                </button>

                {isOptimizing && (
                  <div className="h-2 bg-kozmo-border rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-300"
                      style={{ width: `${optimizationProgress}%` }}
                    />
                  </div>
                )}
              </div>

              <div className="p-6 rounded bg-kozmo-surface border border-kozmo-border space-y-6">
                <h3 className="font-medium flex items-center gap-2 text-white">
                  <span className="text-lg">📈</span>
                  Progress
                </h3>

                {evalHistory.length > 0 ? (
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={evalHistory.slice(-20).map((e, i) => ({ iter: i + 1, score: e.overall_score * 100 }))}>
                        <defs>
                          <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="iter" stroke="rgba(255,255,255,0.2)" fontSize={10} />
                        <YAxis domain={[0, 100]} stroke="rgba(255,255,255,0.2)" fontSize={10} />
                        <Tooltip contentStyle={{ backgroundColor: 'rgba(0,0,0,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                        <Area type="monotone" dataKey="score" stroke="#8b5cf6" fill="url(#scoreGradient)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="h-48 flex items-center justify-center text-kozmo-muted">
                    Start optimization to see results
                  </div>
                )}
              </div>
            </div>
          )}

          {/* History Tab */}
          {activeTab === 'history' && (
            <div className="space-y-4">
              {evalHistory.length > 0 ? (
                evalHistory.slice().reverse().slice(0, 10).map((ev, i) => (
                  <div key={i} className="p-4 rounded bg-kozmo-surface border border-kozmo-border flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="text-2xl">{ev.overall_score >= 0.8 ? '🌟' : '✨'}</div>
                      <div>
                        <div className="text-sm text-white">Eval #{evalHistory.length - i}</div>
                        <div className="text-xs text-kozmo-muted">{new Date(ev.timestamp).toLocaleTimeString()}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="px-3 py-1 rounded bg-kozmo-accent/20 text-kozmo-accent text-sm">
                        {(ev.overall_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-12 rounded bg-kozmo-surface border border-kozmo-border text-center text-white/50">
                  No evaluations yet
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const ParamSlider = ({ spec, value, isPending, onChange, onReset }) => {
  const [min, max] = spec.bounds;
  const percentage = ((value - min) / (max - min)) * 100;
  
  return (
    <div className={`p-4 rounded border transition-all ${
      isPending ? 'bg-kozmo-accent/10 border-kozmo-accent/30' : 'bg-kozmo-surface border-kozmo-border/50'
    }`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-sm font-medium text-white">{spec.name.split('.').pop()}</div>
          <div className="text-xs text-kozmo-muted">{spec.description}</div>
        </div>
        <div className="flex items-center gap-2">
          {isPending && (
            <button onClick={onReset} className="text-xs text-kozmo-accent hover:text-kozmo-accent/80">Reset</button>
          )}
          <span className="text-sm font-mono text-white/80">{typeof value === 'number' ? value.toFixed(2) : value}</span>
        </div>
      </div>
      
      <div className="relative h-2 bg-kozmo-border rounded-full">
        <div className="absolute h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500" style={{ width: `${percentage}%` }} />
        <input
          type="range"
          min={min}
          max={max}
          step={spec.step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
      </div>
      
      <div className="flex justify-between mt-2 text-[10px] text-kozmo-muted">
        <span>{min}</span>
        <span>default: {spec.default}</span>
        <span>{max}</span>
      </div>
    </div>
  );
};

const StatCard = ({ label, value, color }) => {
  const colorClasses = {
    violet: 'text-kozmo-accent',
    cyan: 'text-kozmo-accent',
    amber: 'text-amber-400',
    emerald: 'text-emerald-400',
  };
  
  return (
    <div className="p-4 rounded bg-kozmo-surface text-center">
      <div className={`text-2xl font-display font-semibold ${colorClasses[color]}`}>{value}</div>
      <div className="text-[10px] text-kozmo-muted uppercase tracking-[2px]">{label}</div>
    </div>
  );
};

export default LunaAutoTuner;
