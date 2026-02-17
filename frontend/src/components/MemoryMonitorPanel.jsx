import React, { useState, useEffect, useCallback } from 'react';
import GlassCard from './GlassCard';
import AnnotatedText from './AnnotatedText';

/**
 * Memory Monitor Panel — Live memory substrate dashboard
 *
 * Shows memory stats, extraction pipeline health, and cluster analytics.
 * Data comes from 4 existing API endpoints (no backend changes needed).
 */

const API_BASE = 'http://127.0.0.1:8000';

// --- Tabs ---
const TABS = [
  { id: 'overview', label: 'Overview', icon: '📊' },
  { id: 'memories', label: 'Memories', icon: '💾' },
  { id: 'extraction', label: 'Extraction', icon: '⛏️' },
  { id: 'clusters', label: 'Clusters', icon: '🔮' },
];

// --- Color Configs ---
const severityConfig = {
  critical: { color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', icon: '🔴' },
  warning: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', icon: '🟡' },
  info: { color: 'text-kozmo-accent', bg: 'bg-kozmo-accent/10', border: 'border-kozmo-accent/30', icon: '🔵' },
  ok: { color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30', icon: '🟢' },
};

const stateConfig = {
  emerging: { color: 'bg-blue-500', label: 'Emerging' },
  active: { color: 'bg-green-500', label: 'Active' },
  crystallized: { color: 'bg-violet-500', label: 'Crystallized' },
  archived: { color: 'bg-white/30', label: 'Archived' },
};

const typeColors = {
  PERSON: 'bg-violet-500',
  PLACE: 'bg-green-500',
  CONCEPT: 'bg-cyan-500',
  EMOTION: 'bg-pink-500',
  EVENT: 'bg-amber-500',
  FACT: 'bg-blue-500',
  OBJECT: 'bg-orange-500',
};

// --- Health Diagnostics ---
function diagnoseHealth(memStats, extStats) {
  const issues = [];

  // Check total nodes
  if ((memStats.total_nodes || 0) === 0) {
    issues.push({ severity: 'critical', message: 'Memory is empty — no nodes stored' });
  } else if ((memStats.total_nodes || 0) < 50) {
    issues.push({ severity: 'warning', message: `Only ${memStats.total_nodes} nodes — memory is sparse` });
  }

  // Check edges
  if ((memStats.total_edges || 0) === 0) {
    issues.push({ severity: 'critical', message: 'No edges — graph is disconnected' });
  }

  // Check lock-in
  if (memStats.avg_lock_in != null && memStats.avg_lock_in < 0.3) {
    issues.push({ severity: 'warning', message: `Low average lock-in (${(memStats.avg_lock_in * 100).toFixed(1)}%) — memories may be volatile` });
  }

  // Check extraction pipeline
  if (extStats.scribe) {
    if ((extStats.scribe.extractions_count || 0) === 0) {
      issues.push({ severity: 'warning', message: 'Scribe has 0 extractions — pipeline may not be running' });
    }
  } else {
    issues.push({ severity: 'info', message: 'Scribe stats unavailable' });
  }

  if (extStats.librarian) {
    if ((extStats.librarian.filings_count || 0) === 0) {
      issues.push({ severity: 'warning', message: 'Librarian has 0 filings — extraction results not being stored' });
    }
  } else {
    issues.push({ severity: 'info', message: 'Librarian stats unavailable' });
  }

  if (issues.length === 0) {
    issues.push({ severity: 'ok', message: 'All systems nominal — memory substrate healthy' });
  }

  return issues;
}

// --- Sub-components ---

const StatBox = ({ label, value, sub, color = 'text-white' }) => (
  <div className="p-3 bg-kozmo-surface rounded border border-kozmo-border text-center">
    <div className={`text-2xl font-bold ${color}`}>{value ?? '—'}</div>
    <div className="text-xs text-white/50 mt-1">{label}</div>
    {sub && <div className="text-[10px] text-kozmo-muted mt-0.5">{sub}</div>}
  </div>
);

const SectionHeader = ({ children, icon }) => (
  <div className="flex items-center gap-2 mb-3">
    {icon && <span className="text-sm">{icon}</span>}
    <h3 className="text-sm font-medium text-white/70">{children}</h3>
  </div>
);

const TypeDistributionBar = ({ nodesByType }) => {
  if (!nodesByType || Object.keys(nodesByType).length === 0) return null;

  const total = Object.values(nodesByType).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  return (
    <div>
      <SectionHeader icon="🏷️">Type Distribution</SectionHeader>
      <div className="h-6 rounded-full overflow-hidden flex">
        {Object.entries(nodesByType)
          .sort(([, a], [, b]) => b - a)
          .map(([type, count]) => (
            <div
              key={type}
              className={`h-full ${typeColors[type] || 'bg-white/20'} transition-all`}
              style={{ width: `${(count / total) * 100}%` }}
              title={`${type}: ${count}`}
            />
          ))}
      </div>
      <div className="flex flex-wrap gap-3 mt-2">
        {Object.entries(nodesByType)
          .sort(([, a], [, b]) => b - a)
          .map(([type, count]) => (
            <div key={type} className="flex items-center gap-1.5 text-xs text-white/60">
              <div className={`w-2.5 h-2.5 rounded-full ${typeColors[type] || 'bg-white/20'}`} />
              <span>{type}</span>
              <span className="text-kozmo-muted">{count}</span>
            </div>
          ))}
      </div>
    </div>
  );
};

const PipelineFlow = ({ extStats }) => {
  const scribe = extStats?.scribe;
  const librarian = extStats?.librarian;

  return (
    <div>
      <SectionHeader icon="⚙️">Pipeline Flow</SectionHeader>
      <div className="flex items-center gap-2">
        {/* Scribe */}
        <div className="flex-1 p-3 bg-kozmo-surface rounded border border-kozmo-border text-center">
          <div className="text-xs text-kozmo-muted mb-1">Scribe</div>
          <div className="text-lg font-bold text-kozmo-accent">
            {scribe?.extractions_count ?? '—'}
          </div>
          <div className="text-[10px] text-kozmo-muted">extractions</div>
          {scribe?.backend && (
            <div className="text-[10px] text-white/20 mt-1">{scribe.backend}</div>
          )}
        </div>

        <div className="text-white/20 text-xl">→</div>

        {/* Librarian */}
        <div className="flex-1 p-3 bg-kozmo-surface rounded border border-kozmo-border text-center">
          <div className="text-xs text-kozmo-muted mb-1">Librarian</div>
          <div className="text-lg font-bold text-kozmo-accent">
            {librarian?.filings_count ?? '—'}
          </div>
          <div className="text-[10px] text-kozmo-muted">filings</div>
        </div>

        <div className="text-white/20 text-xl">→</div>

        {/* Matrix */}
        <div className="flex-1 p-3 bg-kozmo-surface rounded border border-kozmo-border text-center">
          <div className="text-xs text-kozmo-muted mb-1">Matrix</div>
          <div className="text-lg font-bold text-green-400">
            {librarian?.filings_count != null && scribe?.extractions_count != null
              ? '✓'
              : '—'}
          </div>
          <div className="text-[10px] text-kozmo-muted">stored</div>
        </div>
      </div>
    </div>
  );
};

const LockInBar = ({ memStats }) => {
  const avg = memStats?.avg_lock_in;
  if (avg == null) return null;

  const percent = (avg * 100).toFixed(1);
  const color = avg >= 0.7 ? 'bg-green-500' : avg >= 0.4 ? 'bg-yellow-500' : 'bg-red-500';
  const textColor = avg >= 0.7 ? 'text-green-400' : avg >= 0.4 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div>
      <SectionHeader icon="🔒">Average Lock-In</SectionHeader>
      <div className="flex items-center gap-3">
        <div className="flex-1 h-3 bg-kozmo-border rounded-full overflow-hidden">
          <div className={`h-full ${color} transition-all`} style={{ width: `${percent}%` }} />
        </div>
        <span className={`text-sm font-bold ${textColor}`}>{percent}%</span>
      </div>
      {memStats.nodes_by_lock_in && (
        <div className="flex gap-4 mt-2 text-xs text-white/50">
          {Object.entries(memStats.nodes_by_lock_in).map(([bucket, count]) => (
            <span key={bucket}>{bucket}: {count}</span>
          ))}
        </div>
      )}
    </div>
  );
};

// --- Tab Views ---

const OverviewTab = ({ memStats, extStats, issues }) => (
  <div className="space-y-5">
    {/* Diagnostic Banner */}
    {issues.length > 0 && (
      <div className="space-y-2">
        {issues.map((issue, i) => {
          const cfg = severityConfig[issue.severity] || severityConfig.info;
          return (
            <div key={i} className={`p-3 rounded ${cfg.bg} border ${cfg.border} flex items-center gap-3`}>
              <span>{cfg.icon}</span>
              <span className={`text-sm ${cfg.color}`}>{issue.message}</span>
            </div>
          );
        })}
      </div>
    )}

    {/* Stats Grid */}
    <div className="grid grid-cols-4 gap-3">
      <StatBox label="Total Nodes" value={memStats?.total_nodes?.toLocaleString()} color="text-kozmo-accent" />
      <StatBox label="Total Edges" value={memStats?.total_edges?.toLocaleString()} color="text-kozmo-accent" />
      <StatBox
        label="Avg Lock-In"
        value={memStats?.avg_lock_in != null ? `${(memStats.avg_lock_in * 100).toFixed(1)}%` : '—'}
        color={memStats?.avg_lock_in >= 0.5 ? 'text-green-400' : 'text-yellow-400'}
      />
      <StatBox
        label="Extractions"
        value={extStats?.scribe?.extractions_count ?? '—'}
        color="text-amber-400"
      />
    </div>

    {/* Type Distribution */}
    <TypeDistributionBar nodesByType={memStats?.nodes_by_type} />

    {/* Pipeline Flow */}
    <PipelineFlow extStats={extStats} />

    {/* Lock-In Bar */}
    <LockInBar memStats={memStats} />
  </div>
);

const ExtractionTab = ({ extStats, extHistory }) => (
  <div className="space-y-5">
    {/* Scribe + Librarian Cards */}
    <div className="grid grid-cols-2 gap-4">
      {/* Scribe */}
      <div className="p-4 bg-kozmo-accent/5 rounded border border-kozmo-accent/20">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg">📝</span>
          <h3 className="text-sm font-medium text-kozmo-accent">Scribe (Ben)</h3>
        </div>
        {extStats?.scribe ? (
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-white/50">Backend</span>
              <span className="text-white/80">{extStats.scribe.backend || '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/50">Extractions</span>
              <span className="text-kozmo-accent font-medium">{extStats.scribe.extractions_count ?? 0}</span>
            </div>
            {extStats.scribe.avg_objects_per_extraction != null && (
              <div className="flex justify-between">
                <span className="text-white/50">Avg Objects/Extraction</span>
                <span className="text-white/80">{extStats.scribe.avg_objects_per_extraction.toFixed(1)}</span>
              </div>
            )}
            {extStats.scribe.avg_edges_per_extraction != null && (
              <div className="flex justify-between">
                <span className="text-white/50">Avg Edges/Extraction</span>
                <span className="text-white/80">{extStats.scribe.avg_edges_per_extraction.toFixed(1)}</span>
              </div>
            )}
            {extStats.scribe.last_extraction_at && (
              <div className="flex justify-between">
                <span className="text-white/50">Last Run</span>
                <span className="text-white/60 text-xs">
                  {new Date(extStats.scribe.last_extraction_at).toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="text-kozmo-muted text-sm">No scribe data</div>
        )}
      </div>

      {/* Librarian */}
      <div className="p-4 bg-kozmo-accent/5 rounded border border-kozmo-accent/20">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg">📚</span>
          <h3 className="text-sm font-medium text-kozmo-accent">Librarian (Dude)</h3>
        </div>
        {extStats?.librarian ? (
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-white/50">Filings</span>
              <span className="text-kozmo-accent font-medium">{extStats.librarian.filings_count ?? 0}</span>
            </div>
            {extStats.librarian.nodes_created != null && (
              <div className="flex justify-between">
                <span className="text-white/50">Nodes Created</span>
                <span className="text-white/80">{extStats.librarian.nodes_created}</span>
              </div>
            )}
            {extStats.librarian.edges_created != null && (
              <div className="flex justify-between">
                <span className="text-white/50">Edges Created</span>
                <span className="text-white/80">{extStats.librarian.edges_created}</span>
              </div>
            )}
            {extStats.librarian.duplicates_merged != null && (
              <div className="flex justify-between">
                <span className="text-white/50">Duplicates Merged</span>
                <span className="text-white/80">{extStats.librarian.duplicates_merged}</span>
              </div>
            )}
          </div>
        ) : (
          <div className="text-kozmo-muted text-sm">No librarian data</div>
        )}
      </div>
    </div>

    {/* Recent Extractions Feed */}
    <div>
      <SectionHeader icon="📜">Recent Extractions</SectionHeader>
      {extHistory?.extractions?.length > 0 ? (
        <div className="space-y-3">
          {extHistory.extractions.map((ext, i) => (
            <div key={ext.extraction_id || i} className="p-3 bg-kozmo-surface rounded border border-kozmo-border">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-kozmo-muted">#{ext.extraction_id || i + 1}</span>
                  {ext.extraction_time_ms != null && (
                    <span className="text-[10px] text-white/20">{ext.extraction_time_ms}ms</span>
                  )}
                </div>
                <span className="text-xs text-kozmo-muted">
                  {ext.timestamp ? new Date(ext.timestamp * 1000).toLocaleTimeString() : '—'}
                </span>
              </div>
              <div className="flex gap-4 text-xs mb-2">
                <span className="text-kozmo-accent">{Array.isArray(ext.objects) ? ext.objects.length : (ext.objects ?? 0)} objects</span>
                <span className="text-kozmo-accent">{Array.isArray(ext.edges) ? ext.edges.length : (ext.edges ?? 0)} edges</span>
                {ext.entity_updates?.length > 0 && (
                  <span className="text-green-400">{ext.entity_updates.length} entities</span>
                )}
              </div>

              {/* Extracted Objects */}
              {Array.isArray(ext.objects) && ext.objects.length > 0 && (
                <div className="mt-2 space-y-1">
                  {ext.objects.map((obj, j) => (
                    <div key={j} className="flex items-start gap-2 text-xs pl-2 border-l-2 border-kozmo-accent/30">
                      <span className="text-kozmo-accent/70 font-mono shrink-0">{obj.type}</span>
                      <span className="text-white/60 break-all">{obj.content?.slice(0, 120)}{obj.content?.length > 120 ? '...' : ''}</span>
                      {obj.confidence != null && (
                        <span className="text-white/20 shrink-0">{(obj.confidence * 100).toFixed(0)}%</span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Extracted Edges */}
              {Array.isArray(ext.edges) && ext.edges.length > 0 && (
                <div className="mt-2 space-y-1">
                  {ext.edges.map((edge, j) => (
                    <div key={j} className="flex items-center gap-1.5 text-xs pl-2 border-l-2 border-kozmo-accent/30">
                      <span className="text-white/50">{edge.from_ref}</span>
                      <span className="text-kozmo-accent/60">→</span>
                      <span className="text-kozmo-accent/80 font-mono text-[10px]">{edge.edge_type}</span>
                      <span className="text-kozmo-accent/60">→</span>
                      <span className="text-white/50">{edge.to_ref}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Entity Updates */}
              {Array.isArray(ext.entity_updates) && ext.entity_updates.length > 0 && (
                <div className="mt-2 space-y-1">
                  {ext.entity_updates.map((eu, j) => (
                    <div key={j} className="flex items-start gap-2 text-xs pl-2 border-l-2 border-green-500/30">
                      <span className="text-green-400/80 font-medium shrink-0">{eu.name}</span>
                      <span className="text-kozmo-muted shrink-0">({eu.entity_type})</span>
                      {eu.facts && Object.keys(eu.facts).length > 0 && (
                        <span className="text-kozmo-muted break-all">
                          {Object.entries(eu.facts).map(([k, v]) => `${k}: ${v}`).join(', ').slice(0, 100)}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-kozmo-muted text-sm p-4 text-center">No recent extractions</div>
      )}
      {extHistory?.total != null && (
        <div className="text-xs text-kozmo-muted text-center mt-2">
          Showing {extHistory.extractions?.length || 0} of {extHistory.total} total
        </div>
      )}
    </div>
  </div>
);

const ClustersTab = ({ clusterStats, entities = [] }) => (
  <div className="space-y-5">
    {/* Summary Row */}
    <div className="grid grid-cols-3 gap-3">
      <StatBox label="Clusters" value={clusterStats?.cluster_count ?? '—'} color="text-kozmo-accent" />
      <StatBox label="Nodes in Clusters" value={clusterStats?.total_nodes?.toLocaleString() ?? '—'} color="text-kozmo-accent" />
      <StatBox
        label="Avg Lock-In"
        value={clusterStats?.avg_lock_in != null ? `${(clusterStats.avg_lock_in * 100).toFixed(1)}%` : '—'}
        color="text-green-400"
      />
    </div>

    {/* State Distribution Bar */}
    {clusterStats?.state_distribution && Object.keys(clusterStats.state_distribution).length > 0 && (
      <div>
        <SectionHeader icon="📈">Cluster State Distribution</SectionHeader>
        {(() => {
          const total = Object.values(clusterStats.state_distribution).reduce((a, b) => a + b, 0);
          if (total === 0) return null;
          return (
            <>
              <div className="h-6 rounded-full overflow-hidden flex">
                {Object.entries(clusterStats.state_distribution).map(([state, count]) => {
                  const cfg = stateConfig[state] || { color: 'bg-white/20', label: state };
                  return (
                    <div
                      key={state}
                      className={`h-full ${cfg.color} transition-all`}
                      style={{ width: `${(count / total) * 100}%` }}
                      title={`${cfg.label}: ${count}`}
                    />
                  );
                })}
              </div>
              <div className="flex gap-4 mt-2">
                {Object.entries(clusterStats.state_distribution).map(([state, count]) => {
                  const cfg = stateConfig[state] || { color: 'bg-white/20', label: state };
                  return (
                    <div key={state} className="flex items-center gap-1.5 text-xs text-white/60">
                      <div className={`w-2.5 h-2.5 rounded-full ${cfg.color}`} />
                      <span>{cfg.label}</span>
                      <span className="text-kozmo-muted">{count}</span>
                    </div>
                  );
                })}
              </div>
            </>
          );
        })()}
      </div>
    )}

    {/* Top Clusters */}
    {clusterStats?.top_clusters?.length > 0 && (
      <div>
        <SectionHeader icon="🏆">Top Clusters</SectionHeader>
        <div className="space-y-2">
          {clusterStats.top_clusters.map((cluster, i) => (
            <div key={cluster.id || i} className="p-3 bg-kozmo-surface rounded border border-kozmo-border">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-kozmo-muted">#{i + 1}</span>
                  <span className="text-white/90 font-medium">
                    <AnnotatedText text={cluster.label || cluster.id || `Cluster ${i + 1}`} entities={entities} />
                  </span>
                  {cluster.state && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                      stateConfig[cluster.state]?.color || 'bg-white/20'
                    } text-white/80`}>
                      {cluster.state}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs text-white/50">
                  <span>{cluster.node_count ?? '?'} nodes</span>
                  {cluster.lock_in != null && (
                    <span className={cluster.lock_in >= 0.5 ? 'text-green-400' : 'text-yellow-400'}>
                      {(cluster.lock_in * 100).toFixed(0)}% lock-in
                    </span>
                  )}
                </div>
              </div>
              {cluster.top_types && (
                <div className="flex gap-2 mt-1">
                  {Object.entries(cluster.top_types).map(([type, count]) => (
                    <span key={type} className="text-[10px] text-kozmo-muted">
                      {type}: {count}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    )}

    {/* Node Lock-In Distribution */}
    {clusterStats?.lock_in_distribution && (
      <div>
        <SectionHeader icon="📊">Node Lock-In Distribution</SectionHeader>
        <div className="space-y-1.5">
          {Object.entries(clusterStats.lock_in_distribution).map(([bucket, count]) => {
            const maxCount = Math.max(...Object.values(clusterStats.lock_in_distribution));
            const width = maxCount > 0 ? (count / maxCount) * 100 : 0;
            return (
              <div key={bucket} className="flex items-center gap-3">
                <span className="text-xs text-white/50 w-16 text-right">{bucket}</span>
                <div className="flex-1 h-4 bg-kozmo-surface rounded overflow-hidden">
                  <div
                    className="h-full bg-kozmo-accent rounded transition-all"
                    style={{ width: `${width}%` }}
                  />
                </div>
                <span className="text-xs text-kozmo-muted w-8">{count}</span>
              </div>
            );
          })}
        </div>
      </div>
    )}

    {!clusterStats && (
      <div className="text-kozmo-muted text-sm text-center p-8">No cluster data available</div>
    )}
  </div>
);

// --- Memories Tab ---

const lockInColor = (li) => {
  if (li >= 0.7) return 'text-green-400';
  if (li >= 0.4) return 'text-yellow-400';
  return 'text-red-400';
};

const lockInBadge = (state) => {
  const colors = {
    settled: 'bg-green-500/20 text-green-400',
    fluid: 'bg-yellow-500/20 text-yellow-400',
    drifting: 'bg-red-500/20 text-red-400',
  };
  return colors[state] || 'bg-kozmo-border text-kozmo-muted';
};

const MemoriesTab = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [filterType, setFilterType] = useState('');
  const [filterState, setFilterState] = useState('');
  const [searching, setSearching] = useState(false);
  const [browseNodes, setBrowseNodes] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const doSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await fetch(`${API_BASE}/memory/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), limit: 30 }),
      });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
        setBrowseNodes(null);
      }
    } catch (e) {
      console.error('Search failed:', e);
    } finally {
      setSearching(false);
    }
  };

  const doBrowse = async () => {
    setSearching(true);
    try {
      const params = new URLSearchParams({ limit: '50' });
      if (filterType) params.set('node_type', filterType);
      if (filterState) params.set('lock_in_state', filterState);
      const res = await fetch(`${API_BASE}/memory/nodes?${params}`);
      if (res.ok) {
        const data = await res.json();
        setBrowseNodes(data);
        setResults(null);
      }
    } catch (e) {
      console.error('Browse failed:', e);
    } finally {
      setSearching(false);
    }
  };

  // Load initial browse on mount
  useEffect(() => { doBrowse(); }, []);

  const nodes = results || browseNodes || [];

  return (
    <div className="space-y-4">
      {/* Search Bar */}
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && doSearch()}
          placeholder="Search memories..."
          className="flex-1 px-3 py-2 bg-kozmo-surface border border-kozmo-border rounded text-sm text-white font-mono placeholder-kozmo-muted focus:outline-none focus:border-kozmo-accent/50"
        />
        <button
          onClick={doSearch}
          disabled={searching || !query.trim()}
          className="px-4 py-2 text-sm bg-kozmo-accent/20 border border-kozmo-accent/30 text-kozmo-accent rounded hover:bg-kozmo-accent/30 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          {searching ? '...' : 'Search'}
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2 items-center">
        <span className="text-xs text-kozmo-muted">Filter:</span>
        <select
          value={filterType}
          onChange={(e) => { setFilterType(e.target.value); }}
          className="px-2 py-1 text-xs bg-kozmo-surface border border-kozmo-border rounded text-white/70 focus:outline-none"
        >
          <option value="">All Types</option>
          <option value="FACT">FACT</option>
          <option value="ENTITY">ENTITY</option>
          <option value="OBSERVATION">OBSERVATION</option>
          <option value="PREFERENCE">PREFERENCE</option>
          <option value="QUESTION">QUESTION</option>
          <option value="DECISION">DECISION</option>
          <option value="PROBLEM">PROBLEM</option>
          <option value="ACTION">ACTION</option>
          <option value="OUTCOME">OUTCOME</option>
          <option value="MEMORY">MEMORY</option>
        </select>
        <select
          value={filterState}
          onChange={(e) => { setFilterState(e.target.value); }}
          className="px-2 py-1 text-xs bg-kozmo-surface border border-kozmo-border rounded text-white/70 focus:outline-none"
        >
          <option value="">All States</option>
          <option value="settled">Settled</option>
          <option value="fluid">Fluid</option>
          <option value="drifting">Drifting</option>
        </select>
        <button
          onClick={() => { setResults(null); setQuery(''); doBrowse(); }}
          className="px-3 py-1 text-xs bg-kozmo-surface border border-kozmo-border rounded text-white/50 hover:text-white hover:bg-kozmo-surface/80"
        >
          Browse
        </button>
        {results && (
          <span className="text-xs text-kozmo-accent ml-auto">{results.length} results for "{query}"</span>
        )}
      </div>

      {/* Results */}
      <div className="space-y-1.5 max-h-[50vh] overflow-y-auto pr-1">
        {nodes.length > 0 ? nodes.map((node) => {
          const id = node.id;
          const content = node.content || '';
          const nodeType = node.node_type || '?';
          const lockIn = node.lock_in ?? 0;
          const lockState = node.lock_in_state || 'drifting';
          const isExpanded = expandedId === id;

          return (
            <div
              key={id}
              onClick={() => setExpandedId(isExpanded ? null : id)}
              className="p-3 bg-kozmo-surface rounded border border-kozmo-border cursor-pointer hover:bg-kozmo-surface/80 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${typeColors[nodeType] || 'bg-white/20'} text-white/90`}>
                      {nodeType}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${lockInBadge(lockState)}`}>
                      {lockState}
                    </span>
                    <span className={`text-[10px] font-mono ${lockInColor(lockIn)}`}>
                      {(lockIn * 100).toFixed(0)}%
                    </span>
                    {node.score != null && (
                      <span className="text-[10px] text-kozmo-accent/60">score: {node.score.toFixed(3)}</span>
                    )}
                  </div>
                  <div className={`text-xs text-white/70 ${isExpanded ? '' : 'line-clamp-2'}`}>
                    {content}
                  </div>
                </div>
              </div>
              {isExpanded && (
                <div className="mt-2 pt-2 border-t border-white/5 grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] text-kozmo-muted">
                  <span>ID: <span className="text-white/50 font-mono">{id}</span></span>
                  <span>Source: <span className="text-white/50">{node.source || '—'}</span></span>
                  <span>Confidence: <span className="text-white/50">{(node.confidence ?? 0).toFixed(2)}</span></span>
                  <span>Importance: <span className="text-white/50">{(node.importance ?? 0).toFixed(2)}</span></span>
                  <span>Accesses: <span className="text-white/50">{node.access_count ?? 0}</span></span>
                  <span>Reinforced: <span className="text-white/50">{node.reinforcement_count ?? 0}</span></span>
                  {node.created_at && (
                    <span className="col-span-2">Created: <span className="text-white/50">{new Date(node.created_at).toLocaleString()}</span></span>
                  )}
                </div>
              )}
            </div>
          );
        }) : (
          <div className="text-kozmo-muted text-sm text-center p-8">
            {searching ? 'Searching...' : 'No memories found'}
          </div>
        )}
      </div>
    </div>
  );
};

// --- Main Component ---

const MemoryMonitorPanel = ({ isOpen, onClose, entities = [] }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [memStats, setMemStats] = useState(null);
  const [extStats, setExtStats] = useState(null);
  const [extHistory, setExtHistory] = useState(null);
  const [clusterStats, setClusterStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [memRes, extRes, histRes, clusterRes] = await Promise.all([
        fetch(`${API_BASE}/memory/stats`),
        fetch(`${API_BASE}/extraction/stats`),
        fetch(`${API_BASE}/extraction/history?limit=10`),
        fetch(`${API_BASE}/clusters/stats`),
      ]);

      if (memRes.ok) setMemStats(await memRes.json());
      if (extRes.ok) setExtStats(await extRes.json());
      if (histRes.ok) setExtHistory(await histRes.json());
      if (clusterRes.ok) setClusterStats(await clusterRes.json());

      setError(null);
    } catch (e) {
      console.error('Memory Monitor fetch failed:', e);
      setError(e.message);
    } finally {
      setLoading(false);
      setLastRefresh(new Date());
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    fetchAll();
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, [isOpen, fetchAll]);

  if (!isOpen) return null;

  // Error state — no data at all
  if (error && !memStats) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
        <GlassCard className="w-full max-w-md" padding="p-6" hover={false}>
          <div className="text-kozmo-muted text-sm text-center">
            Memory Monitor unavailable ({error})
          </div>
          <button
            onClick={onClose}
            className="mt-4 mx-auto block text-xs text-kozmo-muted hover:text-white/60"
          >
            Close
          </button>
        </GlassCard>
      </div>
    );
  }

  const issues = memStats && extStats ? diagnoseHealth(memStats, extStats) : [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <GlassCard className="w-full max-w-5xl max-h-[90vh] flex flex-col" padding="p-0" hover={false}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-kozmo-border bg-kozmo-accent/10 rounded-t">
          <div className="flex items-center gap-3">
            <span className="text-3xl">🧠</span>
            <div>
              <h2 className="text-lg font-medium text-white flex items-center gap-2">
                Memory Monitor
                <span className="text-xs px-2 py-0.5 bg-kozmo-eden/20 text-kozmo-eden rounded-full">Live</span>
              </h2>
              <p className="text-xs text-white/50">
                {lastRefresh
                  ? `Last refresh: ${lastRefresh.toLocaleTimeString()}`
                  : 'Loading...'}
                {loading && ' • Refreshing...'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchAll}
              disabled={loading}
              className={`px-3 py-1.5 text-xs rounded border transition-all ${
                loading
                  ? 'bg-kozmo-surface border-kozmo-border text-kozmo-muted cursor-wait'
                  : 'bg-kozmo-accent/20 border-kozmo-accent/30 text-kozmo-accent hover:bg-kozmo-accent/30'
              }`}
            >
              {loading ? '↻ Refreshing...' : '↻ Refresh'}
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
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm rounded transition-colors flex items-center gap-1.5 ${
                activeTab === tab.id
                  ? 'bg-kozmo-accent/20 text-kozmo-accent border border-kozmo-accent/30'
                  : 'text-white/50 hover:text-white hover:bg-kozmo-surface/80'
              }`}
            >
              <span className="text-xs">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto flex-1">
          {loading && !memStats && (
            <div className="text-center text-white/50 py-12">
              <div className="animate-spin text-4xl mb-4">🔄</div>
              Loading memory stats...
            </div>
          )}

          {!loading || memStats ? (
            <>
              {activeTab === 'overview' && (
                <OverviewTab memStats={memStats || {}} extStats={extStats || {}} issues={issues} />
              )}
              {activeTab === 'memories' && (
                <MemoriesTab />
              )}
              {activeTab === 'extraction' && (
                <ExtractionTab extStats={extStats || {}} extHistory={extHistory} />
              )}
              {activeTab === 'clusters' && (
                <ClustersTab clusterStats={clusterStats} entities={entities} />
              )}
            </>
          ) : null}
        </div>
      </GlassCard>
    </div>
  );
};

export default MemoryMonitorPanel;
