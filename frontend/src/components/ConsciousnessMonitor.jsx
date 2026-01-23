import React from 'react';
import GlassCard from './GlassCard';
import StatusDot from './StatusDot';

const ConsciousnessMonitor = ({ consciousness }) => {
  if (!consciousness) {
    return (
      <GlassCard padding="p-6" hover={false}>
        <div className="text-white/30 text-sm">Waiting for consciousness data...</div>
      </GlassCard>
    );
  }

  const {
    mood = 'neutral',
    coherence = 0,
    attention_topics = 0,
    focused_topics = [],
    top_traits = [],
    tick_count = 0,
  } = consciousness;

  // Personality trait display names
  const traitEmoji = {
    curious: '?',
    warm: '<3',
    analytical: '>>',
    creative: '*',
    patient: '...',
    direct: '->',
    playful: '~',
    thoughtful: '...',
  };

  return (
    <GlassCard padding="p-0" hover={false}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-1 h-6 bg-gradient-to-b from-pink-400 to-violet-400 rounded-full" />
            <h2 className="text-lg font-light tracking-wide text-white/90">Consciousness</h2>
          </div>
          <div className="text-xs text-white/30">tick #{tick_count}</div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Mood & Coherence */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white/5 rounded-xl p-4">
            <div className="text-xs text-white/40 uppercase tracking-widest mb-2">Mood</div>
            <div className="flex items-center gap-2">
              <StatusDot status={mood} size="w-3 h-3" />
              <span className="text-white/90 capitalize">{mood}</span>
            </div>
          </div>

          <div className="bg-white/5 rounded-xl p-4">
            <div className="text-xs text-white/40 uppercase tracking-widest mb-2">Coherence</div>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-violet-400 to-cyan-400 rounded-full transition-all duration-500"
                  style={{ width: `${coherence * 100}%` }}
                />
              </div>
              <span className="text-white/60 text-sm w-10 text-right">{Math.round(coherence * 100)}%</span>
            </div>
          </div>
        </div>

        {/* Attention Topics */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs text-white/40 uppercase tracking-widest">Active Attention</div>
            <div className="text-xs text-white/30">{attention_topics} topics</div>
          </div>

          {focused_topics.length > 0 ? (
            <div className="space-y-2">
              {focused_topics.map((topic, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="flex-1 flex items-center gap-2">
                    <span className="text-white/70 text-sm">{topic.name}</span>
                  </div>
                  <div className="w-24 h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-cyan-400 to-violet-400 rounded-full"
                      style={{ width: `${topic.weight * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-white/40 w-10 text-right">
                    {Math.round(topic.weight * 100)}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-white/30 text-sm">No focused topics</div>
          )}
        </div>

        {/* Personality Traits */}
        <div>
          <div className="text-xs text-white/40 uppercase tracking-widest mb-3">Top Traits</div>
          <div className="flex flex-wrap gap-2">
            {top_traits.map(([trait, weight], i) => (
              <div
                key={trait}
                className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5"
              >
                <span className="text-xs text-white/40">{traitEmoji[trait] || '.'}</span>
                <span className="text-sm text-white/70 capitalize">{trait}</span>
                <span className="text-xs text-white/40">{Math.round(weight * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </GlassCard>
  );
};

export default ConsciousnessMonitor;
