import React, { useState, useEffect } from 'react';

/**
 * FallbackChainPanel - UI for configuring inference provider fallback order
 *
 * Displays the current fallback chain and allows reordering.
 * Uses up/down buttons for simple reordering (v1).
 *
 * See: Docs/HANDOFF_Inference_Fallback_Chain.md
 */
export function FallbackChainPanel({ onClose }) {
  const [chain, setChain] = useState([]);
  const [providers, setProviders] = useState({});
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Fetch current chain configuration
  useEffect(() => {
    fetchChainData();
    fetchStats();
  }, []);

  const fetchChainData = async () => {
    try {
      setLoading(true);
      const res = await fetch('http://localhost:8000/llm/fallback-chain');
      if (!res.ok) throw new Error('Failed to fetch chain');
      const data = await res.json();
      setChain(data.chain || []);
      setProviders(data.providers || {});
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch('http://localhost:8000/llm/fallback-chain/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      // Stats are optional, don't show error
    }
  };

  const moveProvider = (index, direction) => {
    const newChain = [...chain];
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= newChain.length) return;

    // Swap
    [newChain[index], newChain[newIndex]] = [newChain[newIndex], newChain[index]];
    setChain(newChain);
  };

  const saveChain = async () => {
    try {
      setSaving(true);
      const res = await fetch('http://localhost:8000/llm/fallback-chain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chain }),
      });
      if (!res.ok) throw new Error('Failed to save chain');
      setError(null);
      // Refresh to confirm
      await fetchChainData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const getProviderStatus = (name) => {
    const provider = providers[name];
    if (!provider) return { available: false, label: 'Unknown' };
    return {
      available: provider.available,
      label: provider.available ? 'Available' : 'Unavailable',
    };
  };

  const getProviderStats = (name) => {
    const providerStats = stats.by_provider?.[name];
    if (!providerStats) return null;
    const successRate = providerStats.attempts > 0
      ? ((providerStats.successes / providerStats.attempts) * 100).toFixed(0)
      : '-';
    return {
      attempts: providerStats.attempts || 0,
      successes: providerStats.successes || 0,
      successRate,
    };
  };

  const getProviderIcon = (name) => {
    const icons = {
      local: '🏠',
      groq: '⚡',
      claude: '🧠',
      openai: '🤖',
      together: '🔗',
    };
    return icons[name] || '📦';
  };

  return (
    <div className="fallback-panel glass-card" style={{
      padding: '1rem',
      minWidth: 320,
      maxWidth: 400,
      background: 'rgba(0, 0, 0, 0.85)',
      backdropFilter: 'blur(10px)',
      borderRadius: '12px',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      color: 'white',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem' }}>⛓️ Fallback Chain</h3>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'white',
            fontSize: '1.2rem',
            opacity: 0.7,
          }}
        >
          ×
        </button>
      </div>

      {/* Description */}
      <p style={{ fontSize: '0.75rem', opacity: 0.6, marginBottom: '1rem' }}>
        Configure provider order. First available provider handles the request.
      </p>

      {/* Error display */}
      {error && (
        <div style={{
          padding: '0.5rem',
          marginBottom: '1rem',
          background: 'rgba(239, 68, 68, 0.2)',
          border: '1px solid rgba(239, 68, 68, 0.5)',
          borderRadius: '6px',
          fontSize: '0.75rem',
          color: '#fca5a5',
        }}>
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem', opacity: 0.5 }}>
          Loading...
        </div>
      ) : (
        <>
          {/* Chain list */}
          <div style={{ marginBottom: '1rem' }}>
            {chain.map((name, index) => {
              const status = getProviderStatus(name);
              const providerStats = getProviderStats(name);

              return (
                <div
                  key={name}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    padding: '0.5rem',
                    marginBottom: '0.5rem',
                    background: 'rgba(255, 255, 255, 0.05)',
                    borderRadius: '8px',
                    border: status.available
                      ? '1px solid rgba(167, 139, 250, 0.3)'
                      : '1px solid rgba(255, 255, 255, 0.1)',
                  }}
                >
                  {/* Priority number */}
                  <span style={{
                    width: '1.5rem',
                    height: '1.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(167, 139, 250, 0.2)',
                    borderRadius: '50%',
                    fontSize: '0.75rem',
                    fontWeight: 'bold',
                  }}>
                    {index + 1}
                  </span>

                  {/* Provider icon and name */}
                  <span style={{ fontSize: '1.1rem' }}>{getProviderIcon(name)}</span>
                  <span style={{ flex: 1, fontWeight: '500' }}>{name}</span>

                  {/* Status indicator */}
                  <span style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: status.available ? '#10b981' : '#6b7280',
                  }} title={status.label} />

                  {/* Stats (if available) */}
                  {providerStats && (
                    <span style={{
                      fontSize: '0.65rem',
                      opacity: 0.5,
                      minWidth: '3rem',
                      textAlign: 'right',
                    }}>
                      {providerStats.successRate}%
                    </span>
                  )}

                  {/* Up/Down buttons */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <button
                      onClick={() => moveProvider(index, -1)}
                      disabled={index === 0}
                      style={{
                        padding: '2px 6px',
                        fontSize: '0.6rem',
                        background: index === 0 ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.1)',
                        border: 'none',
                        borderRadius: '3px',
                        cursor: index === 0 ? 'default' : 'pointer',
                        color: 'white',
                        opacity: index === 0 ? 0.3 : 1,
                      }}
                    >
                      ▲
                    </button>
                    <button
                      onClick={() => moveProvider(index, 1)}
                      disabled={index === chain.length - 1}
                      style={{
                        padding: '2px 6px',
                        fontSize: '0.6rem',
                        background: index === chain.length - 1 ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.1)',
                        border: 'none',
                        borderRadius: '3px',
                        cursor: index === chain.length - 1 ? 'default' : 'pointer',
                        color: 'white',
                        opacity: index === chain.length - 1 ? 0.3 : 1,
                      }}
                    >
                      ▼
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Stats summary */}
          {stats.total_requests > 0 && (
            <div style={{
              padding: '0.5rem',
              marginBottom: '1rem',
              background: 'rgba(255, 255, 255, 0.03)',
              borderRadius: '6px',
              fontSize: '0.7rem',
              opacity: 0.7,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Total requests:</span>
                <span>{stats.total_requests}</span>
              </div>
              {stats.fallback_count > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Fallbacks triggered:</span>
                  <span>{stats.fallback_count}</span>
                </div>
              )}
            </div>
          )}

          {/* Save button */}
          <button
            onClick={saveChain}
            disabled={saving}
            style={{
              width: '100%',
              padding: '0.6rem',
              borderRadius: '6px',
              border: 'none',
              background: saving ? '#6b7280' : '#a78bfa',
              color: 'white',
              cursor: saving ? 'default' : 'pointer',
              fontWeight: 'bold',
              fontSize: '0.85rem',
            }}
          >
            {saving ? 'Saving...' : 'Save Chain Order'}
          </button>

          {/* Refresh button */}
          <button
            onClick={() => { fetchChainData(); fetchStats(); }}
            style={{
              width: '100%',
              marginTop: '0.5rem',
              padding: '0.4rem',
              borderRadius: '6px',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              background: 'transparent',
              color: 'white',
              cursor: 'pointer',
              fontSize: '0.75rem',
              opacity: 0.7,
            }}
          >
            ↻ Refresh
          </button>
        </>
      )}
    </div>
  );
}

export default FallbackChainPanel;
