/**
 * MediaLibrary — Asset Library panel for KOZMO Codex
 *
 * Grid of generated/imported media assets with filtering,
 * status management, and thumbnails.
 * Wired to GET/PUT /kozmo/projects/{slug}/media endpoints.
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useKozmo } from '../KozmoProvider';
import { useMediaAPI } from '../hooks/useMediaAPI';
import { heroUrl } from '../utils/heroUrl';
import { fmt, VOICE_COLORS } from '../utils/format';

// --- Status Badge ---
const STATUS_CFG = {
  generated: { bg: '#64748b22', fg: '#94a3b8', icon: '\u25cf' },
  approved: { bg: '#4ade8022', fg: '#4ade80', icon: '\u2713' },
  synced: { bg: '#c8ff0022', fg: '#c8ff00', icon: '\u21c4' },
  archived: { bg: '#64748b22', fg: '#64748b', icon: '\u25a3' },
  orphan: { bg: '#f8717122', fg: '#f87171', icon: '\u26a0' },
};

function StatusBadge({ status }) {
  const cfg = STATUS_CFG[status] || { bg: '#64748b22', fg: '#64748b', icon: '?' };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 8px', borderRadius: 3,
      background: cfg.bg, color: cfg.fg,
      fontSize: 10, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace",
    }}>
      {cfg.icon} {status}
    </span>
  );
}

// --- Asset Card ---
function AssetCard({ asset, slug, onUpdateStatus }) {
  const [imgError, setImgError] = useState(false);
  const src = heroUrl(asset.path, slug);

  // Derive voice from audio_track_id or scene_slug
  const voice = asset.scene_slug?.split('_')[2] || null;
  const voiceColor = voice ? (VOICE_COLORS[voice] || '#666') : '#666';

  return (
    <div style={{
      borderRadius: 6, overflow: 'hidden',
      background: '#0a0a14', border: '1px solid #1a1a2e',
      transition: 'border-color 0.15s',
    }}>
      {/* Thumbnail */}
      <div style={{
        aspectRatio: '21/9', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: `linear-gradient(135deg, ${voiceColor}10, #0a0a14)`,
        position: 'relative', overflow: 'hidden',
      }}>
        {src && !imgError ? (
          <img
            src={src}
            alt={asset.filename}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onError={() => setImgError(true)}
          />
        ) : (
          <span style={{ fontSize: 10, color: '#2a2a3e', fontFamily: "'JetBrains Mono', monospace" }}>
            no preview
          </span>
        )}
        <div style={{ position: 'absolute', top: 4, right: 4 }}>
          <StatusBadge status={asset.status} />
        </div>
      </div>

      {/* Info */}
      <div style={{ padding: 8 }}>
        <div style={{
          fontSize: 9, color: '#e2e8f0', marginBottom: 4,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {asset.prompt?.slice(0, 50) || asset.filename}
          {asset.prompt?.length > 50 ? '...' : ''}
        </div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
          {voice && (
            <span style={{
              fontSize: 7, padding: '1px 5px', borderRadius: 2,
              background: `${voiceColor}15`, color: voiceColor,
              fontFamily: "'JetBrains Mono', monospace", fontWeight: 600,
            }}>{voice}</span>
          )}
          {asset.scene_slug && (
            <span style={{
              fontSize: 7, padding: '1px 5px', borderRadius: 2,
              background: 'rgba(200,255,0,0.08)', color: '#c8ff0090',
              fontFamily: "'JetBrains Mono', monospace",
            }}>{asset.scene_slug}</span>
          )}
          {asset.audio_start != null && (
            <span style={{
              fontSize: 7, color: '#3a3a4e',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {fmt(asset.audio_start)}
            </span>
          )}
          <span style={{
            fontSize: 7, color: '#2a2a3e', marginLeft: 'auto',
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {asset.id?.slice(-8)}
          </span>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 3 }}>
          {asset.status !== 'approved' && asset.status !== 'synced' && (
            <button onClick={() => onUpdateStatus(asset.id, 'approved')} style={{
              flex: 1, padding: '3px 0', borderRadius: 3,
              border: '1px solid rgba(74,222,128,0.2)',
              background: 'rgba(74,222,128,0.05)', color: '#4ade80',
              fontSize: 8, cursor: 'pointer', fontFamily: "'JetBrains Mono', monospace",
            }}>Approve</button>
          )}
          {asset.status === 'approved' && (
            <button onClick={() => onUpdateStatus(asset.id, 'synced')} style={{
              flex: 1, padding: '3px 0', borderRadius: 3,
              border: '1px solid rgba(200,255,0,0.2)',
              background: 'rgba(200,255,0,0.05)', color: '#c8ff00',
              fontSize: 8, cursor: 'pointer', fontFamily: "'JetBrains Mono', monospace",
            }}>Sync</button>
          )}
          {asset.status !== 'archived' && (
            <button onClick={() => onUpdateStatus(asset.id, 'archived')} style={{
              padding: '3px 6px', borderRadius: 3,
              border: '1px solid #1a1a2e', background: 'transparent',
              color: '#3a3a4e', fontSize: 8, cursor: 'pointer',
              fontFamily: "'JetBrains Mono', monospace",
            }}>{'\u25a3'}</button>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Main Component ---
export default function MediaLibrary() {
  const { activeProject } = useKozmo();
  const { listAssets, updateAsset, loading } = useMediaAPI();
  const [assets, setAssets] = useState([]);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');

  const slug = activeProject?.slug;

  // Fetch on mount / project change
  useEffect(() => {
    if (!slug) return;
    listAssets().then(setAssets);
  }, [slug, listAssets]);

  const handleUpdateStatus = useCallback(async (assetId, newStatus) => {
    const result = await updateAsset(assetId, { status: newStatus });
    if (result) {
      setAssets(prev => prev.map(a => a.id === assetId ? { ...a, status: newStatus } : a));
    }
  }, [updateAsset]);

  const filtered = useMemo(() => {
    let list = assets;
    if (filter !== 'all') list = list.filter(a => a.status === filter);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(a =>
        (a.prompt || '').toLowerCase().includes(q) ||
        (a.filename || '').toLowerCase().includes(q) ||
        (a.scene_slug || '').toLowerCase().includes(q) ||
        (a.brief_id || '').toLowerCase().includes(q)
      );
    }
    return list;
  }, [assets, filter, search]);

  // Unique scenes for potential future filter
  const scenes = useMemo(() => {
    const set = new Set(assets.map(a => a.scene_slug).filter(Boolean));
    return [...set].sort();
  }, [assets]);

  const statusCounts = useMemo(() => {
    const counts = { all: assets.length };
    assets.forEach(a => { counts[a.status] = (counts[a.status] || 0) + 1; });
    return counts;
  }, [assets]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Filter Bar */}
      <div style={{
        padding: '8px 12px', borderBottom: '1px solid #1a1a2e',
        display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap', flexShrink: 0,
      }}>
        {['all', 'generated', 'approved', 'synced', 'archived'].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: '3px 8px', borderRadius: 3, border: 'none', cursor: 'pointer',
            background: filter === f ? 'rgba(200,255,0,0.12)' : 'transparent',
            color: filter === f ? '#c8ff00' : '#4a4a6a',
            fontSize: 9, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600,
          }}>
            {f} ({statusCounts[f] || 0})
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search assets..."
          style={{
            padding: '4px 8px', borderRadius: 4, border: '1px solid #1a1a2e',
            background: '#0a0a14', color: '#c8cad0', fontSize: 9,
            fontFamily: "'JetBrains Mono', monospace", outline: 'none', width: 160,
          }}
          onFocus={e => e.target.style.borderColor = '#c8ff0030'}
          onBlur={e => e.target.style.borderColor = '#1a1a2e'}
        />
      </div>

      {/* Grid */}
      <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        {filtered.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#2a2a3e', fontSize: 10 }}>
            {assets.length === 0
              ? 'No assets registered. Generate images in LAB to populate.'
              : 'No assets match filter.'}
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            gap: 8,
          }}>
            {filtered.map(asset => (
              <AssetCard
                key={asset.id}
                asset={asset}
                slug={slug}
                onUpdateStatus={handleUpdateStatus}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer Stats */}
      <div style={{
        padding: '6px 12px', borderTop: '1px solid #1a1a2e',
        fontSize: 8, color: '#3a3a4e', fontFamily: "'JetBrains Mono', monospace",
        display: 'flex', gap: 12, flexShrink: 0,
      }}>
        <span>{assets.length} assets</span>
        <span>{scenes.length} scenes</span>
        {loading && <span style={{ color: '#c8ff00' }}>loading...</span>}
      </div>
    </div>
  );
}
