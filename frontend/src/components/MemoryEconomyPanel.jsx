import React, { useState, useEffect } from 'react';
import GlassCard from './GlassCard';

const MemoryEconomyPanel = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStats = async () => {
    try {
      const res = await fetch('/clusters/stats');
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      setStats(data);
      setError(null);
    } catch (e) {
      console.error('Failed to fetch cluster stats:', e);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // State color mapping
  const stateColors = {
    drifting: 'from-amber-400 to-orange-400',
    fluid: 'from-blue-400 to-cyan-400',
    settled: 'from-emerald-400 to-green-400',
    crystallized: 'from-violet-400 to-purple-400',
  };

  const stateBgColors = {
    drifting: 'bg-amber-400/20 text-amber-300',
    fluid: 'bg-blue-400/20 text-blue-300',
    settled: 'bg-emerald-400/20 text-emerald-300',
    crystallized: 'bg-violet-400/20 text-violet-300',
  };

  if (loading) {
    return (
      <GlassCard padding="p-6" hover={false}>
        <div className="text-white/30 text-sm">Loading Memory Economy...</div>
      </GlassCard>
    );
  }

  if (error || !stats) {
    return (
      <GlassCard padding="p-6" hover={false}>
        <div className="text-white/30 text-sm">
          Memory Economy unavailable {error && `(${error})`}
        </div>
      </GlassCard>
    );
  }

  const { cluster_count, total_nodes, state_distribution, avg_lock_in, top_clusters } = stats;

  // Calculate state percentages for the bar
  const stateOrder = ['drifting', 'fluid', 'settled', 'crystallized'];
  const totalClusters = cluster_count || 1;

  return (
    <GlassCard padding="p-0" hover={false}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-1 h-6 bg-gradient-to-b from-cyan-400 to-violet-400 rounded-full" />
            <h2 className="text-lg font-light tracking-wide text-white/90">Memory Economy</h2>
          </div>
          <div className="text-xs text-white/30">{cluster_count} clusters</div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Overview Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white/5 rounded-xl p-4 text-center">
            <div className="text-2xl font-light text-white/90">{cluster_count}</div>
            <div className="text-xs text-white/40 uppercase tracking-widest mt-1">Clusters</div>
          </div>

          <div className="bg-white/5 rounded-xl p-4 text-center">
            <div className="text-2xl font-light text-white/90">{total_nodes.toLocaleString()}</div>
            <div className="text-xs text-white/40 uppercase tracking-widest mt-1">Nodes</div>
          </div>

          <div className="bg-white/5 rounded-xl p-4 text-center">
            <div className="text-2xl font-light text-white/90">{Math.round(avg_lock_in * 100)}%</div>
            <div className="text-xs text-white/40 uppercase tracking-widest mt-1">Avg Lock-in</div>
          </div>
        </div>

        {/* State Distribution */}
        <div>
          <div className="text-xs text-white/40 uppercase tracking-widest mb-3">Lock-in States</div>

          {/* State bar */}
          <div className="h-4 flex rounded-lg overflow-hidden mb-3">
            {stateOrder.map((state) => {
              const count = state_distribution[state] || 0;
              const pct = (count / totalClusters) * 100;
              if (pct === 0) return null;
              return (
                <div
                  key={state}
                  className={`bg-gradient-to-r ${stateColors[state]} transition-all duration-500`}
                  style={{ width: `${pct}%` }}
                  title={`${state}: ${count} (${Math.round(pct)}%)`}
                />
              );
            })}
          </div>

          {/* State legend */}
          <div className="flex flex-wrap gap-3">
            {stateOrder.map((state) => {
              const count = state_distribution[state] || 0;
              return (
                <div key={state} className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full bg-gradient-to-r ${stateColors[state]}`} />
                  <span className="text-xs text-white/60 capitalize">{state}</span>
                  <span className="text-xs text-white/30">({count})</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Top Clusters */}
        <div>
          <div className="text-xs text-white/40 uppercase tracking-widest mb-3">Top Clusters</div>

          {top_clusters && top_clusters.length > 0 ? (
            <div className="space-y-2">
              {top_clusters.map((cluster) => (
                <div
                  key={cluster.cluster_id}
                  className="flex items-center gap-3 bg-white/5 rounded-lg p-3 hover:bg-white/10 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white/80 truncate">{cluster.name}</div>
                    <div className="text-xs text-white/40">{cluster.member_count} nodes</div>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded ${stateBgColors[cluster.state]}`}>
                    {cluster.state}
                  </span>
                  <div className="text-sm text-white/60 w-12 text-right">
                    {Math.round(cluster.lock_in * 100)}%
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-white/30 text-sm">No clusters yet</div>
          )}
        </div>
      </div>
    </GlassCard>
  );
};

export default MemoryEconomyPanel;
