import React, { useState, useEffect } from 'react';

export default function VoiceWidget() {
  const [voiceStatus, setVoiceStatus] = useState(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('/voice/status');
        if (res.ok) setVoiceStatus(await res.json());
      } catch {}
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  if (!voiceStatus) {
    return (
      <div style={{ color: 'var(--ec-text-faint)', fontSize: 12, textAlign: 'center', padding: 20 }}>
        Voice system idle
      </div>
    );
  }

  const running = voiceStatus.running;
  const stt = voiceStatus.stt_provider || 'none';
  const tts = voiceStatus.tts_provider || 'none';
  const turns = voiceStatus.turn_count || 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Status ring */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: '50%',
            border: `2px solid ${running ? 'var(--ec-accent-voice)' : 'var(--ec-text-faint)'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 18,
            background: running ? 'rgba(167,139,250,0.1)' : 'transparent',
          }}
        >
          {running ? '🎤' : '🔇'}
        </div>
        <div>
          <div className="ec-font-label" style={{ fontSize: 10, color: running ? 'var(--ec-accent-voice)' : 'var(--ec-text-faint)' }}>
            {running ? 'RECORDING' : 'IDLE'}
          </div>
          <div className="ec-font-mono" style={{ fontSize: 11, color: 'var(--ec-text-soft)' }}>
            {turns} turns
          </div>
        </div>
      </div>

      {/* Provider info */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="ec-glass-interactive" style={{ padding: '6px 10px', borderRadius: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
            <span className="ec-font-body" style={{ color: 'var(--ec-text-soft)' }}>STT</span>
            <span className="ec-font-mono" style={{ color: stt !== 'none' ? 'var(--ec-accent-voice)' : 'var(--ec-text-faint)' }}>
              {stt}
            </span>
          </div>
        </div>
        <div className="ec-glass-interactive" style={{ padding: '6px 10px', borderRadius: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
            <span className="ec-font-body" style={{ color: 'var(--ec-text-soft)' }}>TTS</span>
            <span className="ec-font-mono" style={{ color: tts !== 'none' ? 'var(--ec-accent-voice)' : 'var(--ec-text-faint)' }}>
              {tts}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
