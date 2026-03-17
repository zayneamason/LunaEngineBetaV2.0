import React, { useState, useMemo } from 'react';
import katex from 'katex';

/* ── Shared Shell ────────────────────────────────────────────── */

function WidgetShell({ title, icon, children, collapsible = true }) {
  const [open, setOpen] = useState(true);
  return (
    <div style={{
      borderRadius: 8,
      border: '1px solid rgba(192,132,252,0.2)',
      borderLeft: '3px solid rgba(192,132,252,0.5)',
      background: 'rgba(255,255,255,0.03)',
      overflow: 'hidden',
      marginTop: 8,
    }}>
      <div
        onClick={() => collapsible && setOpen(o => !o)}
        style={{
          cursor: collapsible ? 'pointer' : 'default',
          padding: '8px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          userSelect: 'none',
        }}
      >
        <span>{icon}</span>
        <span style={{
          fontSize: 11,
          color: 'rgba(255,255,255,0.5)',
          fontFamily: 'monospace',
        }}>
          {title}
        </span>
        {collapsible && (
          <span style={{
            marginLeft: 'auto',
            fontSize: 10,
            color: 'rgba(255,255,255,0.3)',
          }}>
            {open ? '\u25B2' : '\u25BC'}
          </span>
        )}
      </div>
      {open && <div style={{ padding: '0 12px 12px' }}>{children}</div>}
    </div>
  );
}

/* ── LaTeX Widget (math skill) ───────────────────────────────── */

function LaTeXWidget({ data, latex }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(latex || data?.latex || '', {
        displayMode: true,
        throwOnError: false,
      });
    } catch {
      return null;
    }
  }, [latex, data]);

  return (
    <WidgetShell
      title={`${data?.operation || 'result'} \u00B7 math`}
      icon="\u2211"
    >
      {html ? (
        <div
          dangerouslySetInnerHTML={{ __html: html }}
          style={{ color: 'rgba(255,255,255,0.85)' }}
        />
      ) : (
        <code style={{
          fontSize: 12,
          color: 'rgba(255,255,255,0.7)',
          display: 'block',
          padding: '4px 0',
        }}>
          {data?.result_str || latex || '(no result)'}
        </code>
      )}
      {data?.input && (
        <div style={{
          fontSize: 10,
          color: 'rgba(255,255,255,0.3)',
          marginTop: 4,
          fontFamily: 'monospace',
        }}>
          {data.operation}: {data.input}
        </div>
      )}
    </WidgetShell>
  );
}

/* ── Diagnostic Widget ───────────────────────────────────────── */

const STATUS_CONFIG = {
  healthy:  { icon: '\u2705', color: '#34d399' },
  degraded: { icon: '\u26A0\uFE0F', color: '#fbbf24' },
  broken:   { icon: '\u274C', color: '#f87171' },
  unknown:  { icon: '\u2753', color: '#6b7280' },
};

function DiagnosticWidget({ data }) {
  const [expanded, setExpanded] = useState(null);
  return (
    <WidgetShell
      title={`system health \u00B7 ${data?.overall || 'unknown'}`}
      icon="\uD83D\uDD2C"
    >
      {data?.components?.map((c) => {
        const cfg = STATUS_CONFIG[c.status] || STATUS_CONFIG.unknown;
        return (
          <div key={c.name}>
            <div
              onClick={() =>
                setExpanded(expanded === c.name ? null : c.name)
              }
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '4px 0',
                cursor: 'pointer',
              }}
            >
              <span>{cfg.icon}</span>
              <span style={{
                fontSize: 11,
                color: cfg.color,
                fontFamily: 'monospace',
                minWidth: 110,
              }}>
                {c.name}
              </span>
              <span style={{
                fontSize: 10,
                color: 'rgba(255,255,255,0.4)',
              }}>
                {c.message}
              </span>
            </div>
            {expanded === c.name && c.metrics && (
              <pre style={{
                fontSize: 10,
                color: 'rgba(255,255,255,0.4)',
                marginLeft: 24,
                marginBottom: 4,
                whiteSpace: 'pre-wrap',
              }}>
                {JSON.stringify(c.metrics, null, 2)}
              </pre>
            )}
          </div>
        );
      })}
    </WidgetShell>
  );
}

/* ── Table Widget (logic skill) ───────────────────────────────── */

function TableWidget({ data }) {
  return (
    <WidgetShell
      title={`truth table \u00B7 logic${data?.verdict ? ` \u00B7 ${data.verdict}` : ''}`}
      icon="\u22A8"
    >
      {data?.expression && (
        <div style={{
          fontSize: 10,
          color: 'rgba(255,255,255,0.4)',
          marginBottom: 6,
          fontFamily: 'monospace',
        }}>
          {data.expression}
        </div>
      )}
      {data?.verdict && (
        <span style={{
          display: 'inline-block',
          fontSize: 10,
          fontWeight: 600,
          padding: '2px 8px',
          borderRadius: 4,
          marginBottom: 6,
          background: data.verdict === 'tautology' ? 'rgba(52,211,153,0.15)'
            : data.verdict === 'contradiction' ? 'rgba(248,113,113,0.15)'
            : 'rgba(251,191,36,0.15)',
          color: data.verdict === 'tautology' ? '#34d399'
            : data.verdict === 'contradiction' ? '#f87171'
            : '#fbbf24',
        }}>
          {data.verdict.toUpperCase()}
        </span>
      )}
      {data?.headers?.length > 0 && data?.rows?.length > 0 && (
        <table style={{ fontSize: 11, borderCollapse: 'collapse', width: '100%', marginTop: 4 }}>
          <thead>
            <tr>
              {data.headers.map((h) => (
                <th key={h} style={{
                  padding: '4px 8px',
                  color: 'rgba(192,132,252,0.8)',
                  borderBottom: '1px solid rgba(255,255,255,0.1)',
                  textAlign: 'center',
                  fontFamily: 'monospace',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j} style={{
                    padding: '3px 8px',
                    textAlign: 'center',
                    fontFamily: 'monospace',
                    color: cell === true ? '#34d399'
                      : cell === false ? 'rgba(255,255,255,0.25)'
                      : 'rgba(255,255,255,0.7)',
                  }}>
                    {String(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </WidgetShell>
  );
}

/* ── Document Widget (reading skill) ─────────────────────────── */

function DocumentWidget({ data }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <WidgetShell
      title={`${data?.file_name || 'document'} \u00B7 ${data?.char_count?.toLocaleString() || '?'} chars`}
      icon="\uD83D\uDCC4"
    >
      <pre style={{
        fontSize: 11,
        color: 'rgba(255,255,255,0.6)',
        whiteSpace: 'pre-wrap',
        maxHeight: expanded ? 300 : 80,
        overflow: 'hidden',
        margin: 0,
        fontFamily: 'inherit',
      }}>
        {expanded ? data?.content : data?.preview}
      </pre>
      <button
        onClick={() => setExpanded((e) => !e)}
        style={{
          marginTop: 6,
          fontSize: 10,
          color: 'rgba(192,132,252,0.6)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 0,
        }}
      >
        {expanded
          ? '\u25B2 collapse'
          : `\u25BC expand (${data?.char_count?.toLocaleString()} chars)`}
      </button>
    </WidgetShell>
  );
}

/* ── Image Widget (eden skill / type: image) ─────────────────── */

function ImageWidget({ data }) {
  const [lightbox, setLightbox] = useState(false);
  return (
    <WidgetShell title="generated image \u00B7 eden" icon="\uD83C\uDFA8" collapsible={false}>
      {data?.url ? (
        <>
          <img
            src={data.url}
            alt={data?.prompt || 'generated'}
            onClick={() => setLightbox(true)}
            style={{
              width: '100%',
              borderRadius: 6,
              cursor: 'zoom-in',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          />
          {data?.prompt && (
            <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginTop: 4, marginBottom: 0 }}>
              {data.prompt}
            </p>
          )}
          {lightbox && (
            <div
              onClick={() => setLightbox(false)}
              style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0,0,0,0.85)',
                zIndex: 9999,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'zoom-out',
              }}
            >
              <img
                src={data.url}
                alt={data?.prompt || 'generated'}
                style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8 }}
              />
            </div>
          )}
        </>
      ) : (
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>No image URL</span>
      )}
    </WidgetShell>
  );
}

/* ── Video Widget (eden skill / type: video) ─────────────────── */

function VideoWidget({ data }) {
  const isPlayable = data?.url && /\.(mp4|webm|mov)$/i.test(data.url);
  return (
    <WidgetShell title="generated video \u00B7 eden" icon="\uD83C\uDFAC" collapsible={false}>
      {isPlayable ? (
        <video
          controls
          src={data.url}
          style={{
            width: '100%',
            borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        />
      ) : data?.url ? (
        <a
          href={data.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ fontSize: 11, color: 'rgba(192,132,252,0.8)' }}
        >
          {data.url}
        </a>
      ) : (
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>No video URL</span>
      )}
      {data?.prompt && (
        <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginTop: 4, marginBottom: 0 }}>
          {data.prompt}
        </p>
      )}
    </WidgetShell>
  );
}

/* ── Chart Widget (analytics skill) ──────────────────────────── */

function ChartWidget({ data }) {
  // Simple CSS bar chart (no recharts dependency needed for Phase 3)
  const maxVal = Math.max(...(data?.values || [1]));
  return (
    <WidgetShell
      title={`${data?.title || 'analytics'} \u00B7 chart`}
      icon="\uD83D\uDCCA"
    >
      {data?.labels?.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {data.labels.map((label, i) => {
            const value = data.values[i] || 0;
            const pct = maxVal > 0 ? (value / maxVal) * 100 : 0;
            return (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  fontSize: 10,
                  color: 'rgba(255,255,255,0.5)',
                  fontFamily: 'monospace',
                  minWidth: 90,
                  textAlign: 'right',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {label}
                </span>
                <div style={{
                  flex: 1,
                  height: 14,
                  background: 'rgba(255,255,255,0.05)',
                  borderRadius: 3,
                  overflow: 'hidden',
                }}>
                  <div style={{
                    width: `${pct}%`,
                    height: '100%',
                    background: 'rgba(192,132,252,0.5)',
                    borderRadius: 3,
                    transition: 'width 0.3s',
                  }} />
                </div>
                <span style={{
                  fontSize: 10,
                  color: 'rgba(255,255,255,0.4)',
                  fontFamily: 'monospace',
                  minWidth: 40,
                }}>
                  {typeof value === 'number' ? value.toLocaleString() : value}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>No data</span>
      )}
    </WidgetShell>
  );
}

/* ── Options Widget (interactive choices) ──────────────────── */

function OptionsWidget({ data, onSelect }) {
  const [selected, setSelected] = useState(null);

  const handleClick = (option) => {
    if (selected !== null) return;
    setSelected(option.value);
    onSelect?.(option.value);
  };

  return (
    <WidgetShell
      title={data?.prompt || "choose an option"}
      icon="◇"
      collapsible={false}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {(data?.options || []).map((opt, i) => (
          <button
            key={i}
            onClick={() => handleClick(opt)}
            disabled={selected !== null}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              border: selected === opt.value
                ? '1px solid rgba(192,132,252,0.6)'
                : '1px solid rgba(255,255,255,0.1)',
              background: selected === opt.value
                ? 'rgba(192,132,252,0.15)'
                : 'rgba(255,255,255,0.04)',
              color: selected === opt.value
                ? '#c084fc'
                : selected !== null
                ? 'rgba(255,255,255,0.25)'
                : 'rgba(255,255,255,0.7)',
              fontSize: 11,
              fontFamily: 'var(--ec-font-mono, monospace)',
              cursor: selected !== null ? 'default' : 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {opt.icon && <span style={{ marginRight: 4 }}>{opt.icon}</span>}
            {opt.label}
          </button>
        ))}
      </div>
    </WidgetShell>
  );
}

/* ── Widget Router ───────────────────────────────────────────── */

const WIDGET_COMPONENTS = {
  latex:      LaTeXWidget,
  table:      TableWidget,
  document:   DocumentWidget,
  diagnostic: DiagnosticWidget,
  image:      ImageWidget,
  video:      VideoWidget,
  chart:      ChartWidget,
  options:    OptionsWidget,
};

export default function WidgetAnchor({ widget, onSelect }) {
  if (!widget?.type) return null;
  const Component = WIDGET_COMPONENTS[widget.type];
  if (!Component) return null;

  return (
    <div className="mt-2 ml-0 max-w-[80%]">
      <Component
        data={widget.data}
        latex={widget.latex}
        skill={widget.skill}
        onSelect={onSelect}
      />
    </div>
  );
}
