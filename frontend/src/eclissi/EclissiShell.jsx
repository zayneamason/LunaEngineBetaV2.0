import React, { useState, useEffect, useCallback } from 'react';
import ShellHeader from './components/ShellHeader';
import WidgetDock from './components/WidgetDock';
import RightPanel from './components/RightPanel';
import EclissiHome from './EclissiHome';
import KozmoApp from '../kozmo/KozmoApp';
import ObservatoryApp from '../observatory/ObservatoryApp';
import PlaceholderView from './components/PlaceholderView';
import ProjectStrip from './components/ProjectStrip';
import SettingsApp from '../settings/SettingsApp';
import WelcomeWizard from '../components/WelcomeWizard';

import { useNavigation } from '../hooks/useNavigation';
import { useIdentity } from '../hooks/useIdentity';
import { useLunaAPI } from '../hooks/useLunaAPI';
import { useGuardianStore } from '../hooks/useGuardianLuna';
import { useFrontendConfig } from '../hooks/useFrontendConfig';

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
import LunaScriptWidget from './widgets/LunaScriptWidget';
import ArcadeWidget from './widgets/ArcadeWidget';
import RadioWidget from './widgets/RadioWidget';

const ALL_TABS = ['eclissi', 'studio', 'kozmo', 'guardian', 'observatory', 'settings'];

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
  lunascript: LunaScriptWidget,
  arcade: ArcadeWidget,
  radio: RadioWidget,
};

export default function EclissiShell() {
  const [activeTab, setActiveTab] = useState('eclissi');
  const [activeWidget, setActiveWidget] = useState(null);
  const [dockOpen, setDockOpen] = useState(true);
  const [activeProjectSlug, setActiveProjectSlug] = useState(null);
  const [isFirstRun, setIsFirstRun] = useState(null);
  const { pending: navPending, consume: navConsume } = useNavigation();
  const frontendConfig = useFrontendConfig();
  const enabledPages = frontendConfig.pages || {};
  const enabledWidgets = frontendConfig.widgets || {};
  const TABS = ALL_TABS.filter((t) => enabledPages[t] !== false);

  // First-run detection — respects wizard.enabled from frontend config
  useEffect(() => {
    if (frontendConfig.wizard?.enabled === false) {
      setIsFirstRun(false);
      return;
    }
    fetch('/api/status/first-run').then(r => r.json())
      .then(data => setIsFirstRun(data.is_first_run))
      .catch(() => setIsFirstRun(false));
  }, [frontendConfig]);

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

  const guardianToggle = useGuardianStore((s) => s.toggle);
  const guardianOpen = useGuardianStore((s) => s.open);

  const switchTab = (tab) => {
    if (tab === 'guardian') {
      // Guardian is a toggle on the eclissi tab, not a separate page
      setActiveTab('eclissi');
      guardianOpen();
      return;
    }
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
  const showProjectStrip = activeTab === 'eclissi' || activeTab === 'observatory';
  const showDock = isEclissiTab && dockOpen;

  if (isFirstRun === null) return null;
  if (isFirstRun) return <WelcomeWizard onComplete={() => setIsFirstRun(false)} />;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr',
        gridTemplateRows: showProjectStrip ? 'var(--ec-header-height, 48px) auto 1fr' : 'var(--ec-header-height, 48px) 1fr',
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
        enabledPages={enabledPages}
      />

      {/* Project Strip (eclissi + observatory tabs) */}
      {showProjectStrip && (
        <ProjectStrip onProjectChange={setActiveProjectSlug} />
      )}

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
              enabledWidgets={enabledWidgets}
            />
          </div>
        )}

        {/* Main content */}
        <main style={{ overflow: 'hidden', position: 'relative', height: '100%' }}>
          {activeTab === 'eclissi' && <EclissiHome activeProjectSlug={activeProjectSlug} />}
          {activeTab === 'kozmo' && (
            <KozmoApp onBack={() => switchTab('eclissi')} />
          )}
          {activeTab === 'observatory' && (
            <ObservatoryApp onBack={() => switchTab('eclissi')} activeProjectSlug={activeProjectSlug} />
          )}
          {activeTab === 'studio' && <iframe src="/studio/?v=2" style={{ width: '100%', height: '100%', border: 'none' }} />}
          {/* Guardian tab now redirects to eclissi + opens Guardian panel (see switchTab) */}
          {activeTab === 'settings' && <SettingsApp />}
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
