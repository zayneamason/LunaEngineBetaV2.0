import React, { useState, useRef, useEffect } from 'react';
import { useFrontendConfig } from '../hooks/useFrontendConfig';

const ALL_PROVIDERS = [
  { id: 'groq', label: 'Groq', env: 'GROQ_API_KEY', desc: 'Free, fast (Llama 3.3 70B)', color: '#f97316' },
  { id: 'claude', label: 'Claude', env: 'ANTHROPIC_API_KEY', desc: 'Smart, paid (Anthropic)', color: '#8b5cf6' },
  { id: 'gemini', label: 'Gemini', env: 'GOOGLE_API_KEY', desc: 'Balanced, free tier (Google)', color: '#3b82f6' },
];

const PERSONALITY_PRESETS = [
  { id: 'concise', label: 'Concise', desc: 'Short replies, minimal flourish', token: 'minimal', gesture: 'low' },
  { id: 'balanced', label: 'Balanced', desc: 'Default — clear and expressive', token: 'balanced', gesture: 'moderate' },
  { id: 'expressive', label: 'Expressive', desc: 'Rich, detailed, more personality', token: 'rich', gesture: 'high' },
];

const FALLBACK_GREETING = "Hi! I'm Luna. I'm still warming up, but I'm here. Let's start fresh in the chat.";

export default function WelcomeWizard({ onComplete }) {
  const frontendConfig = useFrontendConfig();
  const wizardCfg = frontendConfig.wizard || {};

  // Filter providers based on wizard config
  const enabledProviderIds = wizardCfg.providers || ALL_PROVIDERS.map(p => p.id);
  const PROVIDERS = ALL_PROVIDERS.filter(p => enabledProviderIds.includes(p.id));

  // Determine which optional steps are shown
  const showVoice = wizardCfg.show_voice_step !== false;
  const showPersonality = wizardCfg.show_personality_step !== false;
  const customWelcome = wizardCfg.custom_welcome || '';

  // Build step list dynamically
  // 1=Name, 2=LLM, (3=Voice?), (4=Personality?), last=Greeting
  const steps = ['name', 'llm'];
  if (showVoice) steps.push('voice');
  if (showPersonality) steps.push('personality');
  steps.push('greeting');
  const totalSteps = steps.length;

  const [stepIndex, setStepIndex] = useState(0);
  const currentStep = steps[stepIndex];

  const advance = () => {
    const next = stepIndex + 1;
    if (next < totalSteps) {
      setStepIndex(next);
      if (steps[next] === 'greeting') streamGreeting();
    }
  };

  // ── Step 1: Name ──
  const [name, setName] = useState('');
  const [nameError, setNameError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleNameSubmit = async () => {
    const trimmed = name.trim();
    if (!trimmed) { setNameError('Please enter your name'); return; }
    setSaving(true);
    setNameError('');
    try {
      const res = await fetch('/api/onboarding/owner', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setNameError(err.detail || 'Failed to save');
        return;
      }
      advance();
    } catch (e) {
      setNameError('Connection error');
    } finally {
      setSaving(false);
    }
  };

  // ── Step 2: LLM Key ──
  const defaultProvider = wizardCfg.default_provider
    ? PROVIDERS.find(p => p.id === wizardCfg.default_provider) || null
    : null;
  const [selectedProvider, setSelectedProvider] = useState(defaultProvider);
  const [apiKey, setApiKey] = useState('');
  const [keyStatus, setKeyStatus] = useState(null);
  const [keyError, setKeyError] = useState('');

  const handleTestKey = async () => {
    if (!selectedProvider || !apiKey.trim()) return;
    setKeyStatus('testing');
    setKeyError('');
    try {
      await fetch('/api/settings/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_keys: { [selectedProvider.env]: apiKey.trim() } }),
      });
      const res = await fetch('/api/settings/llm/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: selectedProvider.id }),
      });
      const data = await res.json();
      if (data.success) {
        setKeyStatus('valid');
      } else {
        setKeyStatus('invalid');
        setKeyError(data.error || 'Key verification failed');
      }
    } catch {
      setKeyStatus('invalid');
      setKeyError('Connection error');
    }
  };

  // ── Step 3: Voice ──
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [ttsEngine, setTtsEngine] = useState(() => {
    const ua = navigator.userAgent.toLowerCase();
    return ua.includes('mac') ? 'apple' : 'piper';
  });

  const handleVoiceContinue = async () => {
    try {
      await fetch('/api/settings/voice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          expression: {
            voice_enabled: voiceEnabled,
            tts_engine: voiceEnabled ? ttsEngine : 'none',
          },
        }),
      });
    } catch { /* non-fatal */ }
    advance();
  };

  // ── Step 4: Personality ──
  const [personalityPreset, setPersonalityPreset] = useState('balanced');

  const handlePersonalityContinue = async () => {
    const preset = PERSONALITY_PRESETS.find(p => p.id === personalityPreset) || PERSONALITY_PRESETS[1];
    try {
      await fetch('/api/settings/personality', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token_budget: { default_preset: preset.token },
          expression: { gesture_frequency: preset.gesture },
        }),
      });
    } catch { /* non-fatal */ }
    advance();
  };

  // ── Final Step: Greeting (with retry) ──
  const [greeting, setGreeting] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const abortRef = useRef(null);

  const streamGreeting = async (attempt = 0) => {
    setStreaming(true);
    setGreeting(attempt > 0 ? 'Luna is waking up...' : '');
    try {
      const controller = new AbortController();
      abortRef.current = controller;
      const res = await fetch('/persona/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: '[SYSTEM: This is the very first message in a brand new conversation. The user just completed the welcome wizard. Say hello to them warmly. Keep it brief — 2-3 sentences. Do not reference past memories.]',
          stream: true,
        }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let gotTokens = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6);
          if (raw === '[DONE]') continue;
          try {
            const evt = JSON.parse(raw);
            if (evt.type === 'token' && evt.token) {
              if (!gotTokens) { setGreeting(''); gotTokens = true; }
              setGreeting(prev => prev + evt.token);
            }
          } catch { /* skip malformed */ }
        }
      }

      if (!gotTokens) throw new Error('No tokens received');
    } catch (e) {
      if (e.name === 'AbortError') return;
      // Retry up to 3 times with 2s delay
      if (attempt < 2) {
        setRetryCount(attempt + 1);
        setGreeting('Luna is waking up...');
        await new Promise(r => setTimeout(r, 2000));
        return streamGreeting(attempt + 1);
      }
      // All retries exhausted — show fallback
      setGreeting(FALLBACK_GREETING);
    } finally {
      setStreaming(false);
    }
  };

  // ── Styles ──
  const container = {
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    height: '100vh', width: '100vw', background: '#0a0a0f', color: '#e0e0e0',
    fontFamily: "'Inter', -apple-system, sans-serif",
  };
  const card = {
    maxWidth: 480, width: '90%', padding: 40, borderRadius: 16,
    background: '#13131a', border: '1px solid #2a2a3a',
  };
  const inputStyle = {
    width: '100%', padding: '12px 16px', fontSize: 16, borderRadius: 8,
    border: '1px solid #3a3a4a', background: '#1a1a24', color: '#e0e0e0',
    outline: 'none', boxSizing: 'border-box', marginTop: 12,
  };
  const btn = (active = true) => ({
    padding: '12px 28px', fontSize: 15, fontWeight: 600, borderRadius: 8, border: 'none',
    cursor: active ? 'pointer' : 'default', marginTop: 20,
    background: active ? '#6366f1' : '#2a2a3a', color: active ? '#fff' : '#666',
    opacity: active ? 1 : 0.6, transition: 'all 0.2s',
  });
  const stepDots = { display: 'flex', gap: 8, marginBottom: 24, justifyContent: 'center' };
  const dot = (active) => ({
    width: 8, height: 8, borderRadius: '50%',
    background: active ? '#6366f1' : '#3a3a4a', transition: 'background 0.3s',
  });
  const optionCard = (selected, color = '#2a2a3a') => ({
    padding: '12px 16px', borderRadius: 8, cursor: 'pointer',
    border: `1px solid ${selected ? color : '#2a2a3a'}`,
    background: selected ? '#1a1a2e' : '#13131a',
    transition: 'all 0.2s',
  });

  return (
    <div style={container}>
      <div style={card}>
        {/* Step indicators */}
        <div style={stepDots}>
          {steps.map((_, i) => <div key={i} style={dot(i <= stepIndex)} />)}
        </div>

        {/* ── Step: Name ── */}
        {currentStep === 'name' && (
          <>
            <h2 style={{ margin: '0 0 8px', fontSize: 22, fontWeight: 600 }}>
              Luna is yours.
            </h2>
            <p style={{ margin: '0 0 4px', color: '#888', fontSize: 14 }}>
              {customWelcome || "Let's get you set up."}
            </p>
            <input
              style={inputStyle}
              placeholder="What's your name?"
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleNameSubmit()}
              autoFocus
            />
            {nameError && <p style={{ color: '#ef4444', fontSize: 13, margin: '8px 0 0' }}>{nameError}</p>}
            <button style={btn(!saving && name.trim())} onClick={handleNameSubmit} disabled={saving || !name.trim()}>
              {saving ? 'Saving...' : 'Continue'}
            </button>
          </>
        )}

        {/* ── Step: LLM Key ── */}
        {currentStep === 'llm' && (
          <>
            <h2 style={{ margin: '0 0 8px', fontSize: 22, fontWeight: 600 }}>
              Connect a brain.
            </h2>
            <p style={{ margin: '0 0 16px', color: '#888', fontSize: 14 }}>
              Luna needs an LLM. Pick one (you can change later).
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {PROVIDERS.map(p => (
                <div
                  key={p.id}
                  onClick={() => { setSelectedProvider(p); setKeyStatus(null); setApiKey(''); setKeyError(''); }}
                  style={optionCard(selectedProvider?.id === p.id, p.color)}
                >
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{p.label}</div>
                  <div style={{ color: '#888', fontSize: 12 }}>{p.desc}</div>
                </div>
              ))}
            </div>
            {selectedProvider && (
              <>
                <input
                  style={{ ...inputStyle, fontFamily: 'monospace', fontSize: 13 }}
                  placeholder={`Paste your ${selectedProvider.label} API key`}
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  type="password"
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
                  <button style={btn(apiKey.trim())} onClick={handleTestKey} disabled={!apiKey.trim() || keyStatus === 'testing'}>
                    {keyStatus === 'testing' ? 'Testing...' : 'Verify Key'}
                  </button>
                  {keyStatus === 'valid' && <span style={{ color: '#22c55e', fontSize: 18 }}>✓</span>}
                  {keyStatus === 'invalid' && <span style={{ color: '#ef4444', fontSize: 13 }}>{keyError}</span>}
                </div>
              </>
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20 }}>
              <button
                style={{ ...btn(true), background: 'transparent', color: '#888', fontSize: 13 }}
                onClick={advance}
              >
                Skip for now
              </button>
              {keyStatus === 'valid' && (
                <button style={btn(true)} onClick={advance}>Continue</button>
              )}
            </div>
          </>
        )}

        {/* ── Step: Voice ── */}
        {currentStep === 'voice' && (
          <>
            <h2 style={{ margin: '0 0 8px', fontSize: 22, fontWeight: 600 }}>
              Give Luna a voice.
            </h2>
            <p style={{ margin: '0 0 16px', color: '#888', fontSize: 14 }}>
              Enable voice chat so Luna can speak and listen.
            </p>
            <div
              onClick={() => setVoiceEnabled(!voiceEnabled)}
              style={{
                ...optionCard(voiceEnabled, '#22c55e'),
                display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12,
              }}
            >
              <div style={{
                width: 20, height: 20, borderRadius: 4,
                border: `2px solid ${voiceEnabled ? '#22c55e' : '#3a3a4a'}`,
                background: voiceEnabled ? '#22c55e' : 'transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 14, color: '#fff', fontWeight: 700, transition: 'all 0.2s',
              }}>
                {voiceEnabled ? '✓' : ''}
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Enable voice chat</div>
                <div style={{ color: '#888', fontSize: 12 }}>Luna can speak responses and listen to you</div>
              </div>
            </div>
            {voiceEnabled && (
              <div style={{ marginTop: 8 }}>
                <div style={{ color: '#888', fontSize: 13, marginBottom: 8 }}>TTS Engine:</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {[
                    { id: 'apple', label: 'Apple TTS', desc: 'macOS native' },
                    { id: 'piper', label: 'Piper', desc: 'Cross-platform, offline' },
                  ].map(eng => (
                    <div
                      key={eng.id}
                      onClick={() => setTtsEngine(eng.id)}
                      style={{ ...optionCard(ttsEngine === eng.id, '#6366f1'), flex: 1 }}
                    >
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{eng.label}</div>
                      <div style={{ color: '#888', fontSize: 11 }}>{eng.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <button style={btn(true)} onClick={handleVoiceContinue}>Continue</button>
          </>
        )}

        {/* ── Step: Personality ── */}
        {currentStep === 'personality' && (
          <>
            <h2 style={{ margin: '0 0 8px', fontSize: 22, fontWeight: 600 }}>
              Set the tone.
            </h2>
            <p style={{ margin: '0 0 16px', color: '#888', fontSize: 14 }}>
              How should Luna communicate? You can fine-tune this later.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {PERSONALITY_PRESETS.map(p => (
                <div
                  key={p.id}
                  onClick={() => setPersonalityPreset(p.id)}
                  style={optionCard(personalityPreset === p.id, '#6366f1')}
                >
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{p.label}</div>
                  <div style={{ color: '#888', fontSize: 12 }}>{p.desc}</div>
                </div>
              ))}
            </div>
            <button style={btn(true)} onClick={handlePersonalityContinue}>Continue</button>
          </>
        )}

        {/* ── Step: Greeting ── */}
        {currentStep === 'greeting' && (
          <>
            <h2 style={{ margin: '0 0 16px', fontSize: 22, fontWeight: 600 }}>
              Luna
            </h2>
            <div style={{
              minHeight: 80, padding: 16, borderRadius: 8,
              background: '#1a1a24', border: '1px solid #2a2a3a',
              fontSize: 15, lineHeight: 1.6, whiteSpace: 'pre-wrap',
            }}>
              {greeting || (streaming ? '...' : 'Connecting...')}
              {streaming && <span style={{ opacity: 0.5 }}>▌</span>}
            </div>
            {!streaming && greeting && (
              <button style={btn(true)} onClick={onComplete}>
                Start chatting
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
