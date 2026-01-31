import React, { useState, useEffect } from 'react';

/**
 * LLM Provider Dropdown
 *
 * Allows hot-swapping between Groq, Gemini, and Claude providers.
 * Shows availability status (green = configured, gray = no API key).
 */
export function LLMProviderDropdown({ className = '' }) {
  const [providers, setProviders] = useState({});
  const [currentProvider, setCurrentProvider] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch providers on mount
  useEffect(() => {
    fetchProviders();
  }, []);

  const fetchProviders = async () => {
    try {
      const [providersRes, currentRes] = await Promise.all([
        fetch('/llm/providers'),
        fetch('/llm/current'),
      ]);
      const providersData = await providersRes.json();
      const currentData = await currentRes.json();

      if (providersData.success) {
        setProviders(providersData.providers);
      }
      if (currentData.success) {
        setCurrentProvider(currentData.provider);
      }
    } catch (err) {
      console.error('Failed to fetch LLM providers:', err);
    }
  };

  const switchProvider = async (name) => {
    if (name === currentProvider) {
      setIsOpen(false);
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch('/llm/provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: name }),
      });
      const data = await res.json();

      if (data.success) {
        setCurrentProvider(name);
      } else {
        console.error('Switch failed:', data.error);
      }
    } catch (err) {
      console.error('Failed to switch provider:', err);
    } finally {
      setIsLoading(false);
      setIsOpen(false);
    }
  };

  const currentInfo = providers[currentProvider];

  return (
    <div className={`relative ${className}`}>
      {/* Trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        className="flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-sm text-white/80 transition-all"
      >
        {/* Status dot */}
        <span
          className={`w-2 h-2 rounded-full ${
            currentInfo?.is_available ? 'bg-emerald-400' : 'bg-gray-500'
          }`}
        />
        {/* Provider name */}
        <span className="capitalize">
          {currentProvider || 'Select LLM'}
        </span>
        {/* Model */}
        {currentInfo?.default_model && (
          <span className="text-white/40 text-xs">
            ({currentInfo.default_model.split('-').slice(0, 2).join('-')})
          </span>
        )}
        {/* Chevron */}
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-56 bg-gray-900/95 backdrop-blur-xl border border-white/10 rounded-xl overflow-hidden shadow-2xl z-50">
          <div className="px-3 py-2 border-b border-white/10">
            <span className="text-xs text-white/40">LLM Provider</span>
          </div>
          {Object.entries(providers).map(([name, info]) => (
            <button
              key={name}
              onClick={() => switchProvider(name)}
              disabled={!info.is_available}
              className={`w-full px-3 py-2.5 flex items-center gap-3 text-left transition-all ${
                name === currentProvider
                  ? 'bg-violet-500/20 border-l-2 border-violet-400'
                  : info.is_available
                    ? 'hover:bg-white/5 border-l-2 border-transparent'
                    : 'opacity-50 cursor-not-allowed border-l-2 border-transparent'
              }`}
            >
              {/* Status dot */}
              <span
                className={`w-2 h-2 rounded-full ${
                  info.is_available ? 'bg-emerald-400' : 'bg-gray-500'
                }`}
              />
              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-white/90 capitalize">{name}</span>
                  {info.limits?.requires_payment && (
                    <span className="text-xs text-amber-400">$</span>
                  )}
                </div>
                <p className="text-xs text-white/50 truncate">
                  {info.is_available ? info.default_model : 'No API key'}
                </p>
              </div>
              {/* Current indicator */}
              {name === currentProvider && (
                <span className="text-xs text-white/30 px-1.5 py-0.5 bg-white/10 rounded">
                  active
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}

export default LLMProviderDropdown;
