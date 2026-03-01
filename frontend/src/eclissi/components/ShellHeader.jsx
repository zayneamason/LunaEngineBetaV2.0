import React from 'react';
import TabButton from './TabButton';
import { IdentityBadge, FaceIDCapture, StatusDot } from '../../components';

const TAB_CONFIG = [
  { id: 'eclissi',     label: 'ECLISSI',     accent: 'var(--ec-accent-luna)' },
  { id: 'studio',      label: 'LUNAR STUDIO', accent: 'var(--ec-accent-voice)', href: '/studio' },
  { id: 'kozmo',       label: 'KOZMO',       accent: '#c8ff00' },
  { id: 'guardian',    label: 'GUARDIAN',     accent: 'var(--ec-accent-guardian)', href: '/guardian' },
  { id: 'observatory', label: 'OBSERVATORY', accent: 'var(--ec-accent-memory)' },
];

export default function ShellHeader({ activeTab, onTabChange, identity, dockOpen, isEclissiTab, onToggleDock }) {
  const {
    isPresent, entityName, lunaTier, confidence,
    captureState, startRecognition, stopRecognition,
    resetIdentity, startEnrollment, enrollCount,
    bypassIdentity, revokeBypass, isBypassed,
    videoRef, bboxes,
  } = identity;

  return (
    <header
      className="ec-glass-panel"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        height: 'var(--ec-header-height)',
        background: 'var(--ec-bg-raised)',
        borderBottom: '1px solid var(--ec-border)',
        borderTop: 'none',
        borderLeft: 'none',
        borderRight: 'none',
        zIndex: 100,
      }}
    >
      {/* Left: Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 140 }}>
        {isEclissiTab && (
          <button
            onClick={onToggleDock}
            title={dockOpen ? 'Hide widget dock' : 'Show widget dock'}
            style={{
              width: 28,
              height: 28,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 4,
              border: `1px solid ${dockOpen ? 'rgba(192,132,252,0.3)' : 'var(--ec-border, rgba(255,255,255,0.06))'}`,
              background: dockOpen ? 'rgba(192,132,252,0.08)' : 'transparent',
              color: dockOpen ? 'var(--ec-accent-luna)' : 'var(--ec-text-faint)',
              cursor: 'pointer',
              fontSize: 14,
              transition: 'all 0.2s ease',
              flexShrink: 0,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        )}
        <div
          style={{
            width: 3,
            height: 24,
            background: 'var(--ec-accent-luna)',
            borderRadius: 2,
            boxShadow: '0 0 12px rgba(192,132,252,0.5), 0 0 4px rgba(192,132,252,0.8)',
          }}
        />
        <span
          className="ec-font-label"
          style={{
            fontSize: 11,
            letterSpacing: 4,
            color: 'var(--ec-accent-luna)',
            fontWeight: 800,
          }}
        >
          ECLISSI
        </span>
        <span
          className="ec-font-label"
          style={{
            fontSize: 9,
            letterSpacing: 2,
            color: 'var(--ec-text-muted)',
          }}
        >
          LUNA ENGINE v2.0
        </span>
      </div>

      {/* Center: Nav Tabs */}
      <nav style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {TAB_CONFIG.map((tab) => (
          <TabButton
            key={tab.id}
            label={tab.label}
            accent={tab.accent}
            isActive={activeTab === tab.id}
            onClick={() => {
              if (tab.href) {
                window.open(tab.href, '_blank');
              } else {
                onTabChange(tab.id);
              }
            }}
          />
        ))}
      </nav>

      {/* Right: Identity + Connection */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 140, justifyContent: 'flex-end' }}>
        {isPresent ? (
          <IdentityBadge
            isPresent={isPresent}
            entityName={entityName}
            lunaTier={lunaTier}
            dataroomTier={identity.identity?.dataroom_tier}
            confidence={confidence}
            onReset={(pin) => startEnrollment(entityName || 'Ahab', pin)}
            isBypassed={isBypassed}
            onRevokeBypass={revokeBypass}
          />
        ) : (
          <FaceIDCapture
            captureState={captureState}
            onStart={startRecognition}
            onStop={stopRecognition}
            onReset={resetIdentity}
            onEnroll={(pin) => startEnrollment(entityName || 'Ahab', pin)}
            onBypass={bypassIdentity}
            videoRef={videoRef}
            bboxes={bboxes}
            enrollCount={enrollCount}
          />
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <StatusDot status={identity.isConnected ? 'connected' : 'disconnected'} />
          <span
            className="ec-font-mono"
            style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}
          >
            {identity.isConnected ? 'ONLINE' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </header>
  );
}
