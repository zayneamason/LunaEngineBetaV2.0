/**
 * KOZMO App Root
 *
 * Three modes:
 *   SCRIBO — Writer's room, story navigation, mixed prose/Fountain editor
 *   CODEX  — World bible, entities, relationships, agent dispatch
 *   LAB    — Production studio, shots, camera, hero frames, timeline
 *
 * Shows ProjectSelector when no project is loaded.
 * Mode switcher + connection status in top nav.
 */
import React, { useState, useEffect } from 'react';
import { useMachine } from '@xstate/react';
import { navigationMachine } from './machines/navigationMachine';
import { KozmoProvider, useKozmo } from './KozmoProvider';
import KozmoCodex from './codex/KozmoCodex';
import KozmoLab from './lab/KozmoLab';
import KozmoScribo from './scribo/KozmoScribo';
import ProjectSelector from './codex/ProjectSelector';

const MODES = {
  SCRIBO: 'scribo',
  CODEX: 'codex',
  LAB: 'lab',
};

function KozmoInner() {
  // Load initial context from localStorage
  const loadedContext = React.useMemo(() => {
    try {
      const saved = localStorage.getItem('kozmo-navigation-state');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  }, []);

  const [state, send, service] = useMachine(navigationMachine, {
    context: {
      ...navigationMachine.context,
      ...loadedContext,
    },
  });
  const mode = state.value; // 'scribo' | 'codex' | 'lab'
  const { activeProject, engineConnected, edenConnected, error, setError, loading } = useKozmo();

  // Save to localStorage on every state change
  useEffect(() => {
    const subscription = service.subscribe((state) => {
      try {
        localStorage.setItem('kozmo-navigation-state', JSON.stringify({
          scriboState: state.context.scriboState,
          codexState: state.context.codexState,
          labState: state.context.labState,
          previousMode: state.context.previousMode,
        }));
      } catch (err) {
        console.error('Failed to save navigation state:', err);
      }
    });
    return () => subscription.unsubscribe();
  }, [service]);

  return (
    <div className="h-screen w-screen flex flex-col bg-kozmo-bg text-white font-mono overflow-hidden">
      {/* Top Bar */}
      <header className="flex items-center justify-between px-4 h-10 border-b border-kozmo-border flex-shrink-0"
        style={{ background: 'rgba(6, 6, 10, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}>
        <div className="flex items-center gap-3">
          <div style={{ width: 3, height: 28, background: '#c8ff00', borderRadius: 2, boxShadow: '0 0 12px rgba(200,255,0,0.5), 0 0 4px rgba(200,255,0,0.8)' }} />
          <span style={{ fontSize: 10, letterSpacing: 4, color: '#c8ff00', fontWeight: 800 }}>KOZMO</span>
          <span style={{ fontSize: 10, letterSpacing: 2, color: '#2a2a3a' }}>
            {mode === MODES.SCRIBO ? 'SCRIBO' : mode === MODES.CODEX ? 'CODEX' : 'LAB'}
          </span>
          {activeProject && (
            <>
              <div style={{ width: 1, height: 14, background: '#1a1a24', margin: '0 4px' }} />
              <span style={{ fontSize: 9, color: '#3a3a50' }}>{activeProject.name}</span>
            </>
          )}
        </div>

        {/* Mode Switcher */}
        {activeProject && (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-kozmo-surface rounded px-1 py-0.5">
              <button
                onClick={() => send({ type: 'TO_SCRIBO' })}
                className={`px-3 py-1 text-xs rounded transition-colors ${
                  mode === MODES.SCRIBO
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'text-kozmo-muted hover:text-white'
                }`}
              >
                SCRIBO
              </button>
              <button
                onClick={() => send({ type: 'TO_CODEX' })}
                className={`px-3 py-1 text-xs rounded transition-colors ${
                  mode === MODES.CODEX
                    ? 'bg-kozmo-accent/20 text-kozmo-accent'
                    : 'text-kozmo-muted hover:text-white'
                }`}
              >
                CODEX
              </button>
              <button
                onClick={() => send({ type: 'TO_LAB' })}
                className={`px-3 py-1 text-xs rounded transition-colors ${
                  mode === MODES.LAB
                    ? 'bg-kozmo-cinema/20 text-kozmo-cinema'
                    : 'text-kozmo-muted hover:text-white'
                }`}
              >
                LAB
              </button>
            </div>
            {state.context.previousMode && (
              <button
                onClick={() => send({ type: `TO_${state.context.previousMode.toUpperCase()}` })}
                className="px-2 py-1 text-xs rounded border border-kozmo-border bg-transparent text-kozmo-muted hover:text-white transition-colors"
                style={{ fontSize: 10 }}
              >
                ← {state.context.previousMode.toUpperCase()}
              </button>
            )}
          </div>
        )}

        {/* Connection Status */}
        <div className="flex items-center gap-4" style={{ fontSize: 8, color: '#3a3a50' }}>
          {loading && <span className="text-kozmo-warning animate-pulse">loading...</span>}
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${engineConnected ? 'bg-kozmo-eden' : 'bg-kozmo-danger animate-pulse'}`}
              style={{ boxShadow: engineConnected ? '0 0 8px #4ade8060' : 'none' }} />
            <span style={{ color: engineConnected ? '#4ade80' : '#f87171' }}>
              {engineConnected ? 'LUNA' : 'OFFLINE'}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${edenConnected ? 'bg-purple-400' : 'bg-gray-600'}`}
              style={{ boxShadow: edenConnected ? '0 0 8px #c084fc60' : 'none' }} />
            <span style={{ color: edenConnected ? '#c084fc' : '#4a4a5a' }}>
              EDEN
            </span>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="px-4 py-1.5 flex items-center justify-between"
          style={{ background: 'rgba(26, 10, 10, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', borderBottom: '1px solid #f8717130' }}>
          <span style={{ fontSize: 10, color: '#f87171' }}>{error}</span>
          <button onClick={() => setError(null)}
            style={{ fontSize: 9, color: '#f8717180', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
            dismiss
          </button>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {!activeProject ? (
          <ProjectSelector />
        ) : (
          mode === MODES.SCRIBO
            ? <KozmoScribo
                savedState={state.context.scriboState}
                onSaveState={(state) => send({ type: 'SAVE_SCRIBO_STATE', state })}
                onSetDirty={(value) => send({ type: 'SET_DIRTY', value })}
                onNavigateToEntity={(entitySlug, entityType) =>
                  send({ type: 'TO_CODEX', entitySlug, entityType })
                }
              />
            : mode === MODES.CODEX
            ? <KozmoCodex
                savedState={state.context.codexState}
                onSaveState={(state) => send({ type: 'SAVE_CODEX_STATE', state })}
              />
            : <KozmoLab
                savedState={state.context.labState}
                onSaveState={(state) => send({ type: 'SAVE_LAB_STATE', state })}
              />
        )}
      </main>
    </div>
  );
}

export default function KozmoApp() {
  return (
    <KozmoProvider>
      <KozmoInner />
    </KozmoProvider>
  );
}
