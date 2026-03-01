import React from 'react';
import ExtractionCard from './ExtractionCard';
import EntityCard from './EntityCard';
import RelationshipCard from './RelationshipCard';

/**
 * TPanels — two flanking panels that slide in from the edges of the spine.
 * Left (300px): Knowledge Created — extraction cards.
 * Right (300px): Connected Context — entity cards + graph neighbors.
 *
 * Overlays the conversation spine; independent from the widget right panel.
 */
export default function TPanels({ extractions, entities, relationships, onClose }) {
  const hasLeft = extractions && extractions.length > 0;
  const hasRight = (entities && entities.length > 0) || (relationships && relationships.length > 0);

  if (!hasLeft && !hasRight) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(0,0,0,0.25)',
          zIndex: 10,
        }}
      />

      {/* Left Panel — Knowledge Created */}
      {hasLeft && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: 300,
            zIndex: 11,
            display: 'flex',
            flexDirection: 'column',
            animation: 'tpanel-slide-left 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          <div
            className="ec-glass-panel"
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              borderRight: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            {/* Header */}
            <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span
                  className="ec-font-label"
                  style={{ fontSize: 10, color: 'var(--ec-text-faint)', letterSpacing: '1.5px' }}
                >
                  KNOWLEDGE CREATED
                </span>
                <span className="ec-font-mono" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>
                  {extractions.length}
                </span>
              </div>
            </div>

            {/* Cards */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '8px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              {extractions.map((ext, i) => (
                <ExtractionCard key={i} extraction={ext} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Right Panel — Connected Context */}
      {hasRight && (
        <div
          style={{
            position: 'absolute',
            right: 0,
            top: 0,
            bottom: 0,
            width: 300,
            zIndex: 11,
            display: 'flex',
            flexDirection: 'column',
            animation: 'tpanel-slide-right 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          <div
            className="ec-glass-panel"
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              borderLeft: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            {/* Header */}
            <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
              <span
                className="ec-font-label"
                style={{ fontSize: 10, color: 'var(--ec-text-faint)', letterSpacing: '1.5px' }}
              >
                CONNECTED CONTEXT
              </span>
            </div>

            {/* Content */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '8px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              {/* Entities */}
              {entities && entities.length > 0 && (
                <div>
                  <div
                    className="ec-font-label"
                    style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6, letterSpacing: '1px' }}
                  >
                    ENTITIES
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {entities.map((ent, i) => (
                      <EntityCard key={i} entity={ent} />
                    ))}
                  </div>
                </div>
              )}

              {/* Relationships */}
              {relationships && relationships.length > 0 && (
                <div>
                  <div
                    className="ec-font-label"
                    style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6, letterSpacing: '1px' }}
                  >
                    GRAPH NEIGHBORS
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    {relationships.map((rel, i) => (
                      <RelationshipCard key={i} relationship={rel} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
