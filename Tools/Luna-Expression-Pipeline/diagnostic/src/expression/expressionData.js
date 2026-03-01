// Expression pipeline type colors
export const TYPES = {
  trigger:    { bg: '#0d1520', accent: '#06b6d4', glow: 'rgba(6,182,212,0.15)',    label: 'Trigger' },
  dimension:  { bg: '#100d1a', accent: '#a78bfa', glow: 'rgba(167,139,250,0.15)',   label: 'Dimension' },
  blend:      { bg: '#0d1520', accent: '#818cf8', glow: 'rgba(129,140,248,0.15)',   label: 'Blender' },
  gesture:    { bg: '#1a1018', accent: '#fb7185', glow: 'rgba(251,113,133,0.15)',   label: 'Gesture' },
  priority:   { bg: '#121218', accent: '#94a3b8', glow: 'rgba(148,163,184,0.1)',    label: 'Priority' },
  mapping:    { bg: '#0d1518', accent: '#38bdf8', glow: 'rgba(56,189,248,0.12)',    label: 'Mapping' },
  emoji:      { bg: '#18140d', accent: '#fbbf24', glow: 'rgba(251,191,36,0.1)',     label: 'Emoji' },
};

const mk = (id, x, y, type, icon, label, fields, desc) => ({
  id,
  type: 'expression',
  position: { x, y },
  data: { nodeType: type, icon, label, fields: fields || [], desc: desc || '' },
});

export const initialNodes = [
  mk('t_sent', 30, 30, 'trigger', '💬', 'Sentiment', [
    { key: 'weight', label: 'Weight', type: 'slider', value: 0.7, min: 0, max: 1 },
    { key: 'sig', label: 'Signal', type: 'readonly', value: '—' },
  ], 'User message emotional valence.'),

  mk('t_mem', 30, 185, 'trigger', '🧠', 'Memory Hit', [
    { key: 'boost', label: 'Hit Boost', type: 'slider', value: 0.3, min: 0, max: 1 },
    { key: 'sig', label: 'Signal', type: 'readonly', value: '—' },
  ], 'Memory retrieval success/failure.'),

  mk('t_id', 30, 340, 'trigger', '👤', 'Identity', [
    { key: 'warmth', label: 'Familiarity', type: 'slider', value: 0.4, min: 0, max: 1 },
    { key: 'sig', label: 'Signal', type: 'readonly', value: '—' },
  ], 'FaceID recognition.'),

  mk('t_topic', 30, 495, 'trigger', '🏷️', 'Topic', [
    { key: 'personal', label: 'Personal W.', type: 'slider', value: 0.6, min: 0, max: 1 },
    { key: 'sig', label: 'Signal', type: 'readonly', value: '—' },
  ], 'Topic type detection.'),

  mk('t_flow', 30, 650, 'trigger', '⚡', 'Flow', [
    { key: 'ramp', label: 'Ramp', type: 'slider', value: 0.15, min: 0, max: 0.5 },
    { key: 'sig', label: 'Signal', type: 'readonly', value: '—' },
  ], 'Conversation momentum.'),

  mk('t_time', 30, 805, 'trigger', '🕐', 'Time', [
    { key: 'mod', label: 'Energy Mod', type: 'slider', value: 0.1, min: -0.3, max: 0.3 },
    { key: 'sig', label: 'Signal', type: 'readonly', value: '—' },
  ], 'Time of day energy.'),

  mk('blend', 300, 390, 'blend', '🔀', 'Blender', [
    { key: 'mode', label: 'Mode', type: 'select', value: 'weighted_avg', options: ['weighted_avg', 'max_wins', 'momentum'] },
    { key: 'smooth', label: 'Smoothing', type: 'slider', value: 0.3, min: 0, max: 1 },
  ], 'Combines triggers → dimensions.'),

  mk('d_val', 560, 30, 'dimension', '☀️', 'Valence', [
    { key: 'value', label: 'Current', type: 'slider', value: 0.6, min: -1, max: 1 },
    { key: 'base', label: 'Baseline', type: 'slider', value: 0.3, min: -1, max: 1 },
  ], 'Positive ↔ Negative. → hue, glow, core brightness'),

  mk('d_aro', 560, 195, 'dimension', '🔥', 'Arousal', [
    { key: 'value', label: 'Current', type: 'slider', value: 0.4, min: 0, max: 1 },
    { key: 'base', label: 'Baseline', type: 'slider', value: 0.35, min: 0, max: 1 },
  ], 'Calm ↔ Excited. → breathe speed, drift speed, pulse'),

  mk('d_cert', 560, 360, 'dimension', '🎯', 'Certainty', [
    { key: 'value', label: 'Current', type: 'slider', value: 0.7, min: 0, max: 1 },
    { key: 'hedge', label: 'Hedge Below', type: 'slider', value: 0.3, min: 0, max: 1 },
  ], 'Confidence. → ring opacity, flicker, phase offset'),

  mk('d_eng', 560, 520, 'dimension', '🌊', 'Engagement', [
    { key: 'value', label: 'Current', type: 'slider', value: 0.5, min: 0, max: 1 },
    { key: 'deep', label: 'Deep At', type: 'slider', value: 0.7, min: 0, max: 1 },
  ], 'Depth. → corona, ring subdivision, drift radius'),

  mk('d_warm', 560, 680, 'dimension', '💛', 'Warmth', [
    { key: 'value', label: 'Current', type: 'slider', value: 0.7, min: 0, max: 1 },
    { key: 'known', label: 'Known Base', type: 'slider', value: 0.6, min: 0, max: 1 },
  ], 'Interpersonal. → hue shift, saturation, corona tint'),

  mk('map_render', 840, 100, 'mapping', '📐', 'Dim→Renderer', [
    { key: 'hue_range', label: 'Hue Range', type: 'readonly', value: '240–280' },
    { key: 'breathe', label: 'Breathe Spd', type: 'readonly', value: '—' },
    { key: 'glow', label: 'Glow Max', type: 'readonly', value: '—' },
    { key: 'opacity', label: 'Opacity Mul', type: 'readonly', value: '—' },
  ], 'Continuous mapping: 5 dimensions → ring params'),

  mk('g_override', 840, 400, 'gesture', '⚡', 'Gesture Override', [
    { key: 'active', label: 'Active', type: 'readonly', value: '—' },
    { key: 'gesture', label: 'Gesture', type: 'readonly', value: '—' },
    { key: 'count', label: 'Survivors', type: 'readonly', value: '12' },
  ], 'P2 override. 12 survivors punch through.'),

  mk('g_emoji', 840, 580, 'emoji', '✨', 'Emoji Signal', [
    { key: 'active', label: 'Active', type: 'readonly', value: '—' },
    { key: 'emoji', label: 'Detected', type: 'readonly', value: '—' },
  ], 'P1.5 signal. 💜 ⚡ 🌙 in text.'),

  mk('priority', 1110, 350, 'priority', '🔒', 'Priority Stack', [
    { key: 'p4', label: 'P4 ERROR', type: 'readonly', value: 'system' },
    { key: 'p3', label: 'P3 SYSTEM', type: 'readonly', value: 'system' },
    { key: 'p2', label: 'P2 GESTURE', type: 'readonly', value: 'text' },
    { key: 'p15', label: 'P1.5 EMOJI', type: 'readonly', value: 'text' },
    { key: 'p1', label: 'P1 DIMENSION', type: 'readonly', value: 'engine' },
    { key: 'winner', label: 'Winner', type: 'readonly', value: 'P1 DIMENSION' },
  ], 'Higher priority wins. Falls back to dimensions, not idle.'),
];

export const EDGE_DEFS = [
  ['t_sent', 'blend'], ['t_mem', 'blend'], ['t_id', 'blend'],
  ['t_topic', 'blend'], ['t_flow', 'blend'], ['t_time', 'blend'],
  ['blend', 'd_val'], ['blend', 'd_aro'], ['blend', 'd_cert'], ['blend', 'd_eng'], ['blend', 'd_warm'],
  ['d_val', 'map_render'], ['d_aro', 'map_render'], ['d_cert', 'map_render'], ['d_eng', 'map_render'], ['d_warm', 'map_render'],
  ['map_render', 'priority'],
  ['g_override', 'priority'], ['g_emoji', 'priority'],
];

// Build @xyflow edges from EDGE_DEFS
export const initialEdges = EDGE_DEFS.map(([source, target]) => ({
  id: `e-${source}-${target}`,
  source,
  target,
  type: 'expression',
  data: { animated: true },
}));

// Gesture triage data
export const TRIAGE = {
  survives: [
    { gesture: '*splits*', anim: 'SPLIT', why: 'Ring separation. No dimension produces this.' },
    { gesture: '*searches*', anim: 'ORBIT+cyan', why: 'Deliberate "looking for something" with color shift.' },
    { gesture: '*dims*', anim: 'FLICKER@0.6', why: 'Intentional withdrawal. Instant, not gradual.' },
    { gesture: '*gasps*', anim: 'PULSE_FAST@1.4', why: 'Sudden spike dimensions take 2+ turns to reach.' },
    { gesture: '*startles*', anim: 'FLICKER@1.3', why: 'Surprise interrupt. Not a smooth arousal climb.' },
    { gesture: '*sparks*', anim: 'FLICKER@1.4', why: 'Creative ignition. Arousal is too smooth for this.' },
    { gesture: '*lights up*', anim: 'GLOW@1.45', why: 'Peak brightness snap. Dimensions cap ~1.2.' },
    { gesture: '*spins*', anim: 'SPIN', why: 'Rotational motion. No dimension maps to rotation.' },
    { gesture: '*spins fast*', anim: 'SPIN_FAST', why: 'Excited rotation. Not pulse speed — spin.' },
    { gesture: '*wobbles*', anim: 'WOBBLE', why: "Physical instability. Certainty dims but doesn't wobble." },
    { gesture: '*settles*', anim: 'IDLE@0.9', why: 'Explicit "done moving." Decay does this slowly.' },
    { gesture: '*flickers*', anim: 'FLICKER', why: 'Deliberate uncertainty display. Sharp, not gradual.' },
  ],
  absorbed: [
    { gesture: '*smiles*', by: 'valence', why: 'valence > 0.5 already glows warmly' },
    { gesture: '*beams*', by: 'valence+warmth', why: 'high valence + warmth = bright glow' },
    { gesture: '*frowns*', by: 'valence', why: 'valence < 0.2 already dims' },
    { gesture: '*softens*', by: 'valence', why: 'valence trending positive = gentle glow' },
    { gesture: '*pulses*', by: 'arousal', why: 'arousal > 0.5 drives pulse rate directly' },
    { gesture: '*pulses excitedly*', by: 'arousal', why: 'arousal > 0.7 = faster pulse' },
    { gesture: '*pulses rapidly*', by: 'arousal', why: 'arousal > 0.8 = fast pulse' },
    { gesture: '*pulses warmly*', by: 'arousal+warmth', why: 'gentle arousal + warmth' },
    { gesture: '*vibrates*', by: 'arousal', why: 'arousal > 0.85 = max pulse rate' },
    { gesture: '*buzzes*', by: 'arousal', why: 'arousal > 0.8 = fast pulse' },
    { gesture: '*bounces*', by: 'arousal', why: 'arousal > 0.7 = fast pulse' },
    { gesture: '*hesitates*', by: 'certainty', why: 'certainty < 0.35 triggers hedging' },
    { gesture: '*worries*', by: 'certainty+valence', why: 'low certainty + low valence = dim drift' },
    { gesture: '*winces*', by: 'certainty', why: 'certainty drop = flicker via snap threshold' },
    { gesture: '*perks up*', by: 'engagement', why: 'engagement spike = glow increase' },
    { gesture: '*leans in*', by: 'engagement', why: 'engagement > 0.6 = brighter' },
    { gesture: '*focuses*', by: 'engagement', why: 'engagement > 0.7 = steady bright' },
    { gesture: '*nods*', by: 'warmth', why: 'warmth > 0.5 = gentle pulse' },
    { gesture: '*hugs*', by: 'warmth', why: 'warmth > 0.8 = max glow' },
    { gesture: '*glows*', by: 'valence+arousal', why: 'natural glow from positive calm' },
    { gesture: '*brightens*', by: 'valence', why: 'valence increase = brightness increase' },
    { gesture: '*radiates*', by: 'valence+warmth', why: 'high valence + warmth = full radiance' },
    { gesture: '*giggles*', by: 'arousal+valence', why: 'high both = spin + bright' },
    { gesture: '*dances*', by: 'arousal+valence', why: 'very high both = fast spin' },
    { gesture: '*drifts*', by: 'arousal', why: 'arousal < 0.3 = natural drift' },
    { gesture: '*floats*', by: 'arousal', why: 'arousal < 0.3 = drift' },
    { gesture: '*exhales*', by: 'arousal', why: 'arousal decreasing = drift toward calm' },
    { gesture: '*relaxes*', by: 'arousal', why: 'low arousal = idle territory' },
    { gesture: '*thinks*', by: 'certainty+engagement', why: 'low certainty + engagement = orbit' },
    { gesture: '*considers*', by: 'certainty+engagement', why: 'low certainty + engagement = slow orbit' },
    { gesture: '*ponders*', by: 'certainty+arousal', why: 'low certainty + low arousal = drift' },
    { gesture: '*reflects*', by: 'engagement+arousal', why: 'engagement + low arousal = gentle glow' },
    { gesture: '*processes*', by: 'SYSTEM', why: 'absorbed by processing_query event' },
  ],
  killed: [
    { gesture: '*eyes widen*', why: "Luna doesn't have eyes." },
    { gesture: '*tilts*', why: "Orbs don't tilt." },
    { gesture: '*leans in*', why: "Orbs don't lean." },
    { gesture: '*nods*', why: "Orbs don't nod." },
    { gesture: '*hugs*', why: "Orbs don't hug." },
    { gesture: '*holds space*', why: 'Therapy-speak. Not a visual.' },
  ],
};

// Simulation scenarios
export const SCENARIOS = {
  warm: { label: '👋 Warm Greeting', color: '#4ade80', steps: [
    { at: 0, fire: ['t_sent', 't_id', 't_flow', 't_time', 't_topic', 't_mem'], sigs: { t_sent: 0.6, t_id: 0.9, t_flow: 0.1, t_time: 0.2, t_topic: 0.3, t_mem: 0.5 } },
    { at: 600, fire: ['blend'], dims: { d_val: 0.72, d_warm: 0.85, d_aro: 0.45, d_cert: 0.8, d_eng: 0.45 } },
    { at: 1100, fire: ['map_render'] },
    { at: 1500, fire: ['priority'], pri: { winner: 'P1 DIMENSION' } },
  ]},
  miss: { label: '❌ Memory Miss', color: '#f87171', steps: [
    { at: 0, fire: ['t_sent', 't_id', 't_mem', 't_topic', 't_flow', 't_time'], sigs: { t_sent: 0.3, t_id: 0.9, t_mem: -0.4, t_topic: 0.5, t_flow: 0.3, t_time: 0 } },
    { at: 600, fire: ['blend'], dims: { d_val: 0.3, d_warm: 0.6, d_aro: 0.3, d_cert: 0.18, d_eng: 0.5 } },
    { at: 1100, fire: ['map_render'] },
    { at: 1500, fire: ['priority'], pri: { winner: 'P1 DIMENSION' } },
  ]},
  deep: { label: '🌊 Deep Personal', color: '#a78bfa', steps: [
    { at: 0, fire: ['t_sent', 't_id', 't_topic', 't_mem', 't_flow', 't_time'], sigs: { t_sent: 0.5, t_id: 0.9, t_topic: 0.8, t_mem: 0.7, t_flow: 0.6, t_time: 0 } },
    { at: 600, fire: ['blend'], dims: { d_val: 0.65, d_warm: 0.8, d_aro: 0.55, d_cert: 0.75, d_eng: 0.88 } },
    { at: 1100, fire: ['map_render'] },
    { at: 1500, fire: ['priority'], pri: { winner: 'P1 DIMENSION' } },
  ]},
  splits: { label: '💔 *splits*', color: '#fb7185', steps: [
    { at: 0, fire: ['t_sent', 't_id', 't_mem', 't_topic', 't_flow', 't_time'], sigs: { t_sent: 0.4, t_id: 0.9, t_mem: 0.5, t_topic: 0.6, t_flow: 0.4, t_time: 0 } },
    { at: 600, fire: ['blend'], dims: { d_val: 0.45, d_warm: 0.65, d_aro: 0.5, d_cert: 0.6, d_eng: 0.6 } },
    { at: 1000, fire: ['g_override'], gest: { active: '✅ FIRING', gesture: '*splits*' } },
    { at: 1300, fire: ['priority'], pri: { winner: '⚡ P2 GESTURE' } },
  ]},
  gasps: { label: '😱 *gasps*', color: '#fb7185', steps: [
    { at: 0, fire: ['t_sent', 't_id', 't_mem', 't_topic', 't_flow', 't_time'], sigs: { t_sent: 0.7, t_id: 0.9, t_mem: 0.8, t_topic: 0.4, t_flow: 0.3, t_time: 0 } },
    { at: 600, fire: ['blend'], dims: { d_val: 0.6, d_warm: 0.7, d_aro: 0.5, d_cert: 0.7, d_eng: 0.5 } },
    { at: 1000, fire: ['g_override'], gest: { active: '✅ FIRING', gesture: '*gasps*' } },
    { at: 1300, fire: ['priority'], pri: { winner: '⚡ P2 GESTURE' } },
  ]},
  emoji: { label: '⚡ Emoji', color: '#fbbf24', steps: [
    { at: 0, fire: ['t_sent', 't_id', 't_mem', 't_topic', 't_flow', 't_time'], sigs: { t_sent: 0.5, t_id: 0.9, t_mem: 0.4, t_topic: 0.3, t_flow: 0.2, t_time: 0 } },
    { at: 600, fire: ['blend'], dims: { d_val: 0.5, d_warm: 0.6, d_aro: 0.4, d_cert: 0.6, d_eng: 0.4 } },
    { at: 1000, fire: ['g_emoji'], emoj: { active: '✅ DETECTED', emoji: '⚡' } },
    { at: 1300, fire: ['priority'], pri: { winner: '✨ P1.5 EMOJI' } },
  ]},
  night: { label: '🌙 Late Night', color: '#818cf8', steps: [
    { at: 0, fire: ['t_sent', 't_id', 't_time', 't_topic', 't_mem', 't_flow'], sigs: { t_sent: 0.3, t_id: 0.9, t_time: -0.2, t_topic: 0.6, t_mem: 0.5, t_flow: 0.7 } },
    { at: 600, fire: ['blend'], dims: { d_val: 0.5, d_warm: 0.75, d_aro: 0.2, d_cert: 0.6, d_eng: 0.72 } },
    { at: 1100, fire: ['map_render'] },
    { at: 1500, fire: ['priority'], pri: { winner: 'P1 DIMENSION' } },
  ]},
};
