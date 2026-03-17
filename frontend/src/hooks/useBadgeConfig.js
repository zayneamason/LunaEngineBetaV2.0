import { useState, useEffect, useCallback } from 'react';

const DEFAULTS = {
  route: true,
  model: false,
  tokens: false,
  latency: true,
  access_filter: true,
  lunascript: true,
  show_knowledge_events: true,
};

/**
 * useBadgeConfig — fetches and manages chat badge visibility settings.
 *
 * Returns { config, update } where config is a map of badge keys to booleans,
 * and update(key, value) persists the change to /api/settings/display.
 */
export function useBadgeConfig() {
  const [config, setConfig] = useState(DEFAULTS);

  useEffect(() => {
    fetch('/api/settings/display')
      .then((r) => r.json())
      .then((data) => {
        if (data?.badges) setConfig({ ...DEFAULTS, ...data.badges });
      })
      .catch(() => {});
  }, []);

  const update = useCallback(async (key, value) => {
    const next = { ...config, [key]: value };
    setConfig(next);
    try {
      await fetch('/api/settings/display', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ badges: { [key]: value } }),
      });
    } catch {
      // Revert on failure
      setConfig(config);
    }
  }, [config]);

  return { config, update };
}
