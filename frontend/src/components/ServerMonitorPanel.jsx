import React, { useState, useEffect, useCallback } from 'react';

/**
 * ServerMonitorPanel - Server management and monitoring UI
 *
 * Provides:
 * - Backend health status
 * - Provider availability (local, groq, claude)
 * - Restart backend / reload frontend controls
 * - Auto-refresh capability
 *
 * Access via /server slash command in chat.
 */
export function ServerMonitorPanel({ onClose }) {
  const [health, setHealth] = useState(null);
  const [providers, setProviders] = useState({});
  const [loading, setLoading] = useState(true);
  const [restarting, setRestarting] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/health');
      if (!res.ok) throw new Error('Backend unreachable');
      const data = await res.json();
      setHealth(data);
      setError(null);
      setLastUpdate(new Date());
    } catch (err) {
      setHealth(null);
      setError('Backend offline or unreachable');
    }
  }, []);

  const fetchProviders = useCallback(async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/llm/fallback-chain');
      if (res.ok) {
        const data = await res.json();
        setProviders(data.providers || {});
      }
    } catch (err) {
      // Providers info optional
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([fetchHealth(), fetchProviders()]);
    setLoading(false);
  }, [fetchHealth, fetchProviders]);

  // Initial load
  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // Auto-refresh every 5 seconds when enabled
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(refreshAll, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshAll]);

  const handleRestartBackend = async () => {
    setRestarting(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/slash/restart-backend', {
        method: 'POST',
      });
      if (res.ok) {
        // Wait for restart, then refresh
        setTimeout(async () => {
          await refreshAll();
          setRestarting(false);
        }, 3000);
      } else {
        throw new Error('Restart failed');
      }
    } catch (err) {
      setError('Failed to restart backend');
      setRestarting(false);
    }
  };

  const handleReloadFrontend = () => {
    window.location.reload();
  };

  const getStatusColor = (status) => {
    if (status === 'healthy' || status === true) return '#10b981';
    if (status === 'degraded') return '#f59e0b';
    return '#ef4444';
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
    <div className="server-monitor-panel glass-card" style={{
      padding: '1rem',
      minWidth: 340,
      maxWidth: 420,
      background: 'rgba(0, 0, 0, 0.85)',
      backdropFilter: 'blur(10px)',
      borderRadius: '12px',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      color: 'white',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>🖥️</span> Server Monitor
        </h3>
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
      {loading && !health ? (
        <div style={{ textAlign: 'center', padding: '2rem', opacity: 0.5 }}>
          Checking server status...
        </div>
      ) : (
        <>
          {/* Backend Status */}
          <div style={{
            padding: '0.75rem',
            marginBottom: '1rem',
            background: 'rgba(255, 255, 255, 0.05)',
            borderRadius: '8px',
            border: `1px solid ${health ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontWeight: '500' }}>Backend Server</span>
              <span style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
                fontSize: '0.75rem',
              }}>
                <span style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: getStatusColor(health?.status),
                }} />
                {health ? health.status : 'offline'}
              </span>
            </div>
            {health && (
              <div style={{ fontSize: '0.7rem', opacity: 0.6 }}>
                <div>Port: 8000</div>
                {health.engine_status && <div>Engine: {health.engine_status}</div>}
                {health.version && <div>Version: {health.version}</div>}
              </div>
            )}
          </div>

          {/* Inference Providers */}
          <div style={{ marginBottom: '1rem' }}>
            <div style={{ fontSize: '0.75rem', opacity: 0.6, marginBottom: '0.5rem' }}>
              Inference Providers
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {Object.entries(providers).length > 0 ? (
                Object.entries(providers).map(([name, info]) => (
                  <div
                    key={name}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.4rem 0.5rem',
                      background: 'rgba(255, 255, 255, 0.03)',
                      borderRadius: '6px',
                    }}
                  >
                    <span>{getProviderIcon(name)}</span>
                    <span style={{ flex: 1, fontSize: '0.85rem' }}>{name}</span>
                    <span style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: getStatusColor(info.available),
                    }} />
                    <span style={{ fontSize: '0.7rem', opacity: 0.6, minWidth: '4rem' }}>
                      {info.available ? 'ready' : 'unavailable'}
                    </span>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.75rem', opacity: 0.5, padding: '0.5rem' }}>
                  No provider info available
                </div>
              )}
            </div>
          </div>

          {/* Auto-refresh toggle */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.5rem',
            marginBottom: '1rem',
            background: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '6px',
          }}>
            <span style={{ fontSize: '0.75rem' }}>Auto-refresh (5s)</span>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              style={{
                padding: '0.25rem 0.5rem',
                fontSize: '0.7rem',
                background: autoRefresh ? 'rgba(16, 185, 129, 0.3)' : 'rgba(255, 255, 255, 0.1)',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                color: 'white',
              }}
            >
              {autoRefresh ? 'ON' : 'OFF'}
            </button>
          </div>

          {/* Last update */}
          {lastUpdate && (
            <div style={{ fontSize: '0.65rem', opacity: 0.4, marginBottom: '1rem', textAlign: 'center' }}>
              Last updated: {lastUpdate.toLocaleTimeString()}
            </div>
          )}

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={handleRestartBackend}
              disabled={restarting}
              style={{
                flex: 1,
                padding: '0.6rem',
                borderRadius: '6px',
                border: 'none',
                background: restarting ? '#6b7280' : '#a78bfa',
                color: 'white',
                cursor: restarting ? 'default' : 'pointer',
                fontWeight: 'bold',
                fontSize: '0.8rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.3rem',
              }}
            >
              🔃 {restarting ? 'Restarting...' : 'Restart Backend'}
            </button>
            <button
              onClick={handleReloadFrontend}
              style={{
                flex: 1,
                padding: '0.6rem',
                borderRadius: '6px',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                background: 'transparent',
                color: 'white',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '0.8rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.3rem',
              }}
            >
              🔄 Reload Frontend
            </button>
          </div>

          {/* Manual refresh */}
          <button
            onClick={refreshAll}
            disabled={loading}
            style={{
              width: '100%',
              marginTop: '0.5rem',
              padding: '0.4rem',
              borderRadius: '6px',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              background: 'transparent',
              color: 'white',
              cursor: 'pointer',
              fontSize: '0.75rem',
              opacity: 0.7,
            }}
          >
            ↻ Refresh Status
          </button>
        </>
      )}
    </div>
  );
}

export default ServerMonitorPanel;
