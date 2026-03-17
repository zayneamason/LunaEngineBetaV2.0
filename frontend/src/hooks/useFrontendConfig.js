import { useState, useEffect } from "react";

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
    cache: true,
    thought: true,
    lunascript: true,
  },
  remap: {},
};

export function useFrontendConfig() {
  const [config, setConfig] = useState(DEFAULT_CONFIG);

  useEffect(() => {
    fetch("/api/frontend-config")
      .then((r) => r.json())
      .then(setConfig)
      .catch(() => setConfig(DEFAULT_CONFIG));
  }, []);

  return config;
}
