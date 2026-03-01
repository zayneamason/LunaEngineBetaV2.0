import React, { useState, useEffect, useCallback } from 'react';
import ShellHeader from './components/ShellHeader';
import WidgetDock from './components/WidgetDock';
import RightPanel from './components/RightPanel';
import EclissiHome from './EclissiHome';
import KozmoApp from '../kozmo/KozmoApp';
import ObservatoryApp from '../observatory/ObservatoryApp';
import PlaceholderView from './components/PlaceholderView';
import AibrarianView from './AibrarianView';
import { useNavigation } from '../hooks/useNavigation';
import { useIdentity } from '../hooks/useIdentity';
import { useLunaAPI } from '../hooks/useLunaAPI';

// Widget content components
import EngineWidget from './widgets/EngineWidget';
import VoiceWidget from './widgets/VoiceWidget';
import MemoryWidget from './widgets/MemoryWidget';
import QAWidget from './widgets/QAWidget';
import PromptWidget from './widgets/PromptWidget';
import DebugWidget from './widgets/DebugWidget';
import VKWidget from './widgets/VKWidget';
import CacheWidget from './widgets/CacheWidget';
import ThoughtWidget from './widgets/ThoughtWidget';

const TABS = ['eclissi', 'studio', 'kozmo', 'guardian', 'observatory'];

const WIDGET_COMPONENTS = {
  engine: EngineWidget,
  voice: VoiceWidget,
  memory: MemoryWidget,
  qa: QAWidget,
  prompt: PromptWidget,
  debug: DebugWidget,
  vk: VKWidget,
  cache: CacheWidget,
  thought: ThoughtWidget,
};

export default function EclissiShell() {
  const [activeTab, setActiveTab] = useState('eclissi');
  const [activeWidget, setActiveWidget] = useState(null);
  const [dockOpen, setDockOpen] = useState(true);
  const { pending: navPending, consume: navConsume } = useNavigation();

  // Identity + connection for header
  const identityHook = useIdentity();
  const { isConnected } = useLunaAPI();

  // Consume navigation bus events
  useEffect(() => {
    if (!navPending) return;
    if (navPending.to && TABS.includes(navPending.to)) {
      setActiveTab(navPending.to);
    }
    navConsume();
  }, [navPending]);

  const switchTab = (tab) => {
    setActiveTab(tab);
  };

  const toggleWidget = useCallback((widgetId) => {
    setActiveWidget((prev) => (prev === widgetId ? null : widgetId));
  }, []);

  const closeWidget = useCallback(() => {
    setActiveWidget(null);
  }, []);

  const toggleDock = useCallback(() => {
    setDockOpen((prev) => {
      if (prev) setActiveWidget(null);
      return !prev;
    });
  }, []);

  // Pass identity + connection state to header
  const headerIdentity = {
    ...identityHook,
    isConnected,
  };

  // Render active widget content
  const WidgetContent = activeWidget ? WIDGET_COMPONENTS[activeWidget] : null;

  const isEclissiTab = activeTab === 'eclissi';
  const showDock = isEclissiTab && dockOpen;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr',
        gridTemplateRows: 'var(--ec-header-height, 48px) 1fr',
        height: '100vh',
        width: '100vw',
        background: 'var(--ec-bg)',
        overflow: 'hidden',
      }}
    >
      {/* Row 1: Header */}
      <ShellHeader
        activeTab={activeTab}
        onTabChange={switchTab}
        identity={headerIdentity}
        dockOpen={dockOpen}
        isEclissiTab={isEclissiTab}
        onToggleDock={toggleDock}
      />

      {/* Row 2: Content area with optional widget dock + right panel */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: isEclissiTab
            ? `${showDock ? 'var(--ec-widget-rail-width, 52px)' : '0px'} 1fr${activeWidget && showDock ? ' var(--ec-right-panel-width, 320px)' : ''}`
            : '1fr',
          overflow: 'hidden',
          minHeight: 0,
          transition: 'grid-template-columns 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Widget Dock (only on eclissi tab) */}
        {isEclissiTab && (
          <div style={{
            overflow: 'hidden',
            transition: 'opacity 0.3s ease',
            opacity: showDock ? 1 : 0,
          }}>
            <WidgetDock
              activeWidget={activeWidget}
              onWidgetToggle={toggleWidget}
            />
          </div>
        )}

        {/* Main content */}
        <main style={{ overflow: 'hidden', position: 'relative', height: '100%' }}>
          {activeTab === 'eclissi' && <EclissiHome />}
          {activeTab === 'kozmo' && (
            <KozmoApp onBack={() => switchTab('eclissi')} />
          )}
          {activeTab === 'observatory' && (
            <ObservatoryApp onBack={() => switchTab('eclissi')} />
          )}
          {activeTab === 'studio' && <AibrarianView />}
          {activeTab === 'guardian' && (
            <PlaceholderView
              name="GUARDIAN"
              accent="var(--ec-accent-guardian)"
              description="Guardian service — sovereignty & permissions. Phase 6 integration."
            />
          )}
        </main>

        {/* Right Panel (only when a widget is active on eclissi tab) */}
        {showDock && activeWidget && (
          <RightPanel activeWidget={activeWidget} onClose={closeWidget}>
            {WidgetContent && <WidgetContent />}
          </RightPanel>
        )}
      </div>
    </div>
  );
}
