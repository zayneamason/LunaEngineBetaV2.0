import { useState, useEffect, useCallback, useSyncExternalStore } from "react";

const DEFAULT_CONFIG = {
  pages: {
    eclissi: true,
    studio: true,
    kozmo: true,
    guardian: true,
    observatory: true,
    settings: true,
  },
  widgets: {
    engine: true,
    voice: true,
    memory: true,
    qa: true,
    prompt: true,
    debug: true,
    vk: true,
    arcade: true,
    cache: true,
    thought: true,
    lunascript: true,
  },
  remap: {},
  settings: {},
  debug_mode: true,
  demo_mode: false,
  has_preloaded_keys: false,
};

// Shared config store — all useFrontendConfig() hooks share the same state
let _config = DEFAULT_CONFIG;
const _listeners = new Set();

function notify() {
  _listeners.forEach((fn) => fn());
}

function subscribe(listener) {
  _listeners.add(listener);
  return () => _listeners.delete(listener);
}

function getSnapshot() {
  return _config;
}

// Fetch config from backend and update shared state
let _fetched = false;
function ensureFetched() {
  if (_fetched) return;
  _fetched = true;
  fetch("/api/frontend-config")
    .then((r) => r.json())
    .then((data) => {
      _config = data;
      notify();
    })
    .catch(() => {
      _config = DEFAULT_CONFIG;
      notify();
    });
}

/**
 * Update a key in the frontend config and persist via POST.
 * All useFrontendConfig() consumers will re-render.
 */
export async function updateFrontendConfig(updates) {
  _config = { ..._config, ...updates };
  notify();
  try {
    await fetch("/api/frontend-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
  } catch (e) {
    console.error("Failed to persist frontend config", e);
  }
}

export function useFrontendConfig() {
  ensureFetched();
  return useSyncExternalStore(subscribe, getSnapshot);
}
