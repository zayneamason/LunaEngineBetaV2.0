import React, { useState, useEffect, useCallback } from 'react';
import GlassCard from './GlassCard';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

const API_BASE = 'http://localhost:8000';

// Topic colors for charts
const TOPIC_COLORS = {
  communication_style: '#8b5cf6',
  domain_opinion: '#06b6d4',
  relationship_dynamic: '#ec4899',
  emotional_response: '#f97316',
  technical_preference: '#22c55e',
  philosophical_view: '#eab308',
  behavioral_pattern: '#6366f1',
};

// Lock-in state colors
const LOCKIN_COLORS = {
  settled: '#22c55e',
  fluid: '#eab308',
  drifting: '#ef4444',
};

// Mood state indicators
const MOOD_INDICATORS = {
  curious: { emoji: '🤔', color: 'cyan' },
  engaged: { emoji: '✨', color: 'violet' },
  neutral: { emoji: '😌', color: 'gray' },
  focused: { emoji: '🎯', color: 'blue' },
  reflective: { emoji: '💭', color: 'purple' },
  excited: { emoji: '⚡', color: 'yellow' },
};

const PersonalityMonitorPanel = ({ isOpen, onClose }) => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPatch, setSelectedPatch] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  const fetchPersonalityData = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/debug/personality`);
      if (!res.ok) throw new Error('Failed to fetch personality data');
      const result = await res.json();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Poll data when open
  useEffect(() => {
    if (!isOpen) return;

    fetchPersonalityData();
    const interval = setInterval(fetchPersonalityData, 3000);
    return () => clearInterval(interval);
  }, [isOpen, fetchPersonalityData]);

  if (!isOpen) return null;

  // Prepare chart data
  const topicChartData = data?.stats?.patches_by_topic
    ? Object.entries(data.stats.patches_by_topic)
        .filter(([, count]) => count > 0)
        .map(([topic, count]) => ({
          name: topic.replace(/_/g, ' '),
          value: count,
          color: TOPIC_COLORS[topic] || '#8b5cf6',
        }))
    : [];

  const lockInChartData = data?.stats?.patches_by_lock_in_state
    ? Object.entries(data.stats.patches_by_lock_in_state).map(([state, count]) => ({
        name: state.charAt(0).toUpperCase() + state.slice(1),
        count,
        color: LOCKIN_COLORS[state] || '#6b7280',
      }))
    : [];

  const moodIndicator = MOOD_INDICATORS[data?.mood_state] || MOOD_INDICATORS.neutral;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <GlassCard className="w-full max-w-5xl max-h-[90vh] flex flex-col" padding="p-0" hover={false}>
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-1 h-6 bg-gradient-to-b from-violet-500 to-pink-500 rounded-full" />
            <h2 className="text-lg font-light tracking-wide text-white/90">Personality Monitor</h2>
            <span className="text-xs text-white/40 bg-violet-500/20 px-2 py-1 rounded border border-violet-500/30">
              {data?.bootstrap_status === 'bootstrapped' ? 'ACTIVE' : 'INITIALIZING'}
            </span>
          </div>
          <div className="flex items-center gap-4">
            {/* Mood indicator */}
            <div className="flex items-center gap-2">
              <span className="text-xl">{moodIndicator.emoji}</span>
              <span className={`text-sm text-${moodIndicator.color}-400`}>
                {data?.mood_state || 'neutral'}
              </span>
            </div>
            <button
              onClick={onClose}
              className="text-white/50 hover:text-white/90 transition-colors text-xl"
            >
              ×
            </button>
          </div>
        </div>

        {/* Stats Bar */}
        {data && (
          <div className="flex-shrink-0 px-6 py-3 bg-white/5 border-b border-white/10 flex items-center gap-6 text-sm">
            <div>
              <span className="text-white/40">Total Patches:</span>{' '}
              <span className="text-white/90 font-mono">{data.stats.total_patches}</span>
            </div>
            <div>
              <span className="text-white/40">Active:</span>{' '}
              <span className="text-green-400 font-mono">{data.stats.active_patches}</span>
            </div>
            <div>
              <span className="text-white/40">Avg Lock-in:</span>{' '}
              <span className="text-violet-400 font-mono">
                {(data.stats.average_lock_in * 100).toFixed(1)}%
              </span>
            </div>
            <div>
              <span className="text-white/40">Session Messages:</span>{' '}
              <span className="text-cyan-400 font-mono">{data.session.messages_tracked}</span>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex-shrink-0 px-6 py-2 border-b border-white/10 flex items-center gap-2">
          {['overview', 'patches', 'maintenance'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm rounded-lg border transition-all ${
                activeTab === tab
                  ? 'bg-violet-500/20 border-violet-500/50 text-violet-400'
                  : 'bg-transparent border-white/10 text-white/40 hover:border-white/20'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4">
          {isLoading && !data && (
            <div className="flex items-center justify-center h-32 text-white/40">
              Loading personality data...
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-400/30 text-red-300 text-sm">
              {error}
            </div>
          )}

          {data && activeTab === 'overview' && (
            <div className="grid grid-cols-2 gap-6">
              {/* Topic Distribution Chart */}
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="text-sm font-medium text-white/70 mb-4">Patch Distribution by Topic</h3>
                {topicChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={topicChartData}
                        cx="50%"
                        cy="50%"
                        innerRadius={40}
                        outerRadius={80}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {topicChartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(15, 23, 42, 0.9)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: '8px',
                        }}
                      />
                      <Legend
                        wrapperStyle={{ fontSize: '11px' }}
                        formatter={(value) => <span className="text-white/70">{value}</span>}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[200px] flex items-center justify-center text-white/40">
                    No patches yet
                  </div>
                )}
              </div>

              {/* Lock-in State Distribution */}
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="text-sm font-medium text-white/70 mb-4">Lock-in State Distribution</h3>
                {lockInChartData.some((d) => d.count > 0) ? (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={lockInChartData} layout="vertical">
                      <XAxis type="number" stroke="#4b5563" fontSize={11} />
                      <YAxis type="category" dataKey="name" stroke="#4b5563" fontSize={11} width={60} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(15, 23, 42, 0.9)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: '8px',
                        }}
                      />
                      <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                        {lockInChartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[200px] flex items-center justify-center text-white/40">
                    No patches yet
                  </div>
                )}
              </div>

              {/* Quick Stats Cards */}
              <div className="col-span-2 grid grid-cols-4 gap-4">
                <StatCard
                  label="Settled"
                  value={data.stats.patches_by_lock_in_state?.settled || 0}
                  color="green"
                  icon="🔒"
                />
                <StatCard
                  label="Fluid"
                  value={data.stats.patches_by_lock_in_state?.fluid || 0}
                  color="yellow"
                  icon="💧"
                />
                <StatCard
                  label="Drifting"
                  value={data.stats.patches_by_lock_in_state?.drifting || 0}
                  color="red"
                  icon="🌊"
                />
                <StatCard
                  label="Session Patches"
                  value={data.session.patches_created_this_session}
                  color="cyan"
                  icon="✨"
                />
              </div>

              {/* Recent Activity */}
              <div className="col-span-2 bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="text-sm font-medium text-white/70 mb-3">Top Patches by Lock-in</h3>
                <div className="space-y-2">
                  {data.patches.slice(0, 5).map((patch) => (
                    <div
                      key={patch.patch_id}
                      className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/5 hover:bg-white/10 cursor-pointer transition-colors"
                      onClick={() => {
                        setSelectedPatch(patch);
                        setActiveTab('patches');
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-lg">{getTopicEmoji(patch.topic)}</span>
                        <div>
                          <div className="text-sm text-white/80">{patch.subtopic}</div>
                          <div className="text-xs text-white/40">{patch.topic.replace(/_/g, ' ')}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              patch.lock_in >= 0.7
                                ? 'bg-green-500'
                                : patch.lock_in >= 0.4
                                ? 'bg-yellow-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${patch.lock_in * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-white/50 font-mono w-10 text-right">
                          {(patch.lock_in * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                  {data.patches.length === 0 && (
                    <div className="text-center py-4 text-white/40">
                      No patches created yet. Start a conversation!
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {data && activeTab === 'patches' && (
            <div className="space-y-3">
              {data.patches.map((patch) => (
                <PatchCard
                  key={patch.patch_id}
                  patch={patch}
                  isSelected={selectedPatch?.patch_id === patch.patch_id}
                  onClick={() => setSelectedPatch(selectedPatch?.patch_id === patch.patch_id ? null : patch)}
                />
              ))}
              {data.patches.length === 0 && (
                <div className="text-center py-8 text-white/40">
                  No personality patches yet. Patches are created through conversation reflection.
                </div>
              )}
            </div>
          )}

          {data && activeTab === 'maintenance' && (
            <div className="space-y-6">
              {/* Maintenance Stats */}
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="text-sm font-medium text-white/70 mb-4">Lifecycle Maintenance</h3>
                <div className="grid grid-cols-3 gap-4">
                  <MaintenanceStat
                    label="Decay Operations"
                    value={data.maintenance.total_decay_operations}
                    subValue={`${data.maintenance.total_patches_decayed} patches decayed`}
                  />
                  <MaintenanceStat
                    label="Consolidations"
                    value={data.maintenance.total_consolidation_operations}
                    subValue={`${data.maintenance.total_patches_consolidated} patches merged`}
                  />
                  <MaintenanceStat
                    label="Cleanups"
                    value={data.maintenance.total_cleanup_operations}
                    subValue={`${data.maintenance.total_patches_cleaned} patches removed`}
                  />
                </div>
                {data.maintenance.last_maintenance_run && (
                  <div className="mt-4 text-xs text-white/40">
                    Last maintenance: {new Date(data.maintenance.last_maintenance_run).toLocaleString()}
                  </div>
                )}
              </div>

              {/* Session Info */}
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="text-sm font-medium text-white/70 mb-4">Session Reflection</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-2xl font-light text-cyan-400">
                      {data.session.messages_tracked}
                    </div>
                    <div className="text-xs text-white/40">Messages tracked this session</div>
                  </div>
                  <div>
                    <div className="text-2xl font-light text-violet-400">
                      {data.session.patches_created_this_session}
                    </div>
                    <div className="text-xs text-white/40">Patches created this session</div>
                  </div>
                </div>
                {data.session.last_reflection && (
                  <div className="mt-4 text-xs text-white/40">
                    Last reflection: {new Date(data.session.last_reflection).toLocaleString()}
                  </div>
                )}
              </div>

              {/* Bootstrap Status */}
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="text-sm font-medium text-white/70 mb-3">Bootstrap Status</h3>
                <div className="flex items-center gap-3">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      data.bootstrap_status === 'bootstrapped' ? 'bg-green-500' : 'bg-yellow-500'
                    }`}
                  />
                  <span className="text-white/70">
                    {data.bootstrap_status === 'bootstrapped'
                      ? 'Personality bootstrapped with seed patches'
                      : 'Awaiting bootstrap'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 px-6 py-3 border-t border-white/10 flex items-center justify-between text-xs text-white/40">
          <div>Luna's emergent personality - patches evolve through conversation</div>
          <button
            onClick={fetchPersonalityData}
            className="px-3 py-1 rounded bg-white/10 hover:bg-white/20 transition-colors text-white/60"
          >
            Refresh
          </button>
        </div>
      </GlassCard>
    </div>
  );
};

// Helper Components

const StatCard = ({ label, value, color, icon }) => (
  <div className="bg-white/5 rounded-xl p-4 border border-white/10">
    <div className="flex items-center justify-between mb-2">
      <span className="text-xl">{icon}</span>
      <span className={`text-2xl font-light text-${color}-400`}>{value}</span>
    </div>
    <div className="text-xs text-white/40">{label}</div>
  </div>
);

const MaintenanceStat = ({ label, value, subValue }) => (
  <div>
    <div className="text-xl font-light text-white/80">{value}</div>
    <div className="text-sm text-white/60">{label}</div>
    <div className="text-xs text-white/40">{subValue}</div>
  </div>
);

const PatchCard = ({ patch, isSelected, onClick }) => {
  const lockInColor =
    patch.lock_in >= 0.7 ? 'green' : patch.lock_in >= 0.4 ? 'yellow' : 'red';

  return (
    <div
      className={`rounded-xl border transition-all cursor-pointer ${
        isSelected
          ? 'bg-violet-500/10 border-violet-500/30'
          : 'bg-white/5 border-white/10 hover:border-white/20'
      }`}
      onClick={onClick}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl">{getTopicEmoji(patch.topic)}</span>
          <div>
            <div className="text-sm font-medium text-white/80">{patch.subtopic}</div>
            <div className="flex items-center gap-2 text-xs text-white/40">
              <span className="capitalize">{patch.topic.replace(/_/g, ' ')}</span>
              <span>•</span>
              <span>{patch.trigger.replace(/_/g, ' ')}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className={`text-sm font-mono text-${lockInColor}-400`}>
              {(patch.lock_in * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-white/40">lock-in</div>
          </div>
          <div className="text-right">
            <div className="text-sm font-mono text-cyan-400">{patch.reinforcement_count}</div>
            <div className="text-xs text-white/40">reinforced</div>
          </div>
          <span className="text-white/40">{isSelected ? '−' : '+'}</span>
        </div>
      </div>

      {/* Expanded Content */}
      {isSelected && (
        <div className="px-4 pb-4 pt-2 border-t border-white/10 space-y-3">
          {/* States */}
          <div className="grid grid-cols-2 gap-4">
            {patch.before_state && (
              <div>
                <div className="text-xs text-white/40 mb-1">Before State</div>
                <div className="text-sm text-white/60 bg-red-500/10 p-2 rounded">
                  {patch.before_state}
                </div>
              </div>
            )}
            <div>
              <div className="text-xs text-white/40 mb-1">After State</div>
              <div className="text-sm text-white/80 bg-green-500/10 p-2 rounded">
                {patch.after_state}
              </div>
            </div>
          </div>

          {/* Content */}
          <div>
            <div className="text-xs text-white/40 mb-1">Full Content</div>
            <div className="text-sm text-white/70 bg-white/5 p-2 rounded">{patch.content}</div>
          </div>

          {/* Metadata */}
          <div className="flex items-center gap-4 text-xs text-white/40">
            <span>Created: {new Date(patch.created_at).toLocaleDateString()}</span>
            <span>•</span>
            <span>Last reinforced: {new Date(patch.last_reinforced).toLocaleDateString()}</span>
            <span>•</span>
            <span>Confidence: {(patch.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
      )}
    </div>
  );
};

const getTopicEmoji = (topic) => {
  const emojis = {
    communication_style: '💬',
    domain_opinion: '🎯',
    relationship_dynamic: '🤝',
    emotional_response: '💫',
    technical_preference: '⚙️',
    philosophical_view: '🌌',
    behavioral_pattern: '🔄',
  };
  return emojis[topic] || '📝';
};

export default PersonalityMonitorPanel;
