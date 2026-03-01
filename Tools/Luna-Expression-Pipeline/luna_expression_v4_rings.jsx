import { useState, useRef, useCallback, useEffect, useMemo } from "react";

// ═══════════════════════════════════════════════════════════════
// LUNA EXPRESSION PIPELINE v4 — Gesture Triage + Ring Orb
// Dimensional heartbeat + gesture override + real Canvas 2D orb
// ═══════════════════════════════════════════════════════════════

const TYPES = {
  trigger:    { bg:'#0d1520', accent:'#06b6d4', glow:'rgba(6,182,212,0.15)',    label:'Trigger' },
  dimension:  { bg:'#100d1a', accent:'#a78bfa', glow:'rgba(167,139,250,0.15)',   label:'Dimension' },
  channel:    { bg:'#0d1a12', accent:'#4ade80', glow:'rgba(74,222,128,0.15)',    label:'Channel' },
  transition: { bg:'#1a170d', accent:'#fbbf24', glow:'rgba(251,191,36,0.15)',    label:'Transition' },
  orb:        { bg:'#1a0d18', accent:'#f0abfc', glow:'rgba(240,171,252,0.2)',    label:'Orb' },
  blend:      { bg:'#0d1520', accent:'#818cf8', glow:'rgba(129,140,248,0.15)',   label:'Blender' },
  gesture:    { bg:'#1a1018', accent:'#fb7185', glow:'rgba(251,113,133,0.15)',   label:'Gesture' },
  priority:   { bg:'#121218', accent:'#94a3b8', glow:'rgba(148,163,184,0.1)',    label:'Priority' },
  mapping:    { bg:'#0d1518', accent:'#38bdf8', glow:'rgba(56,189,248,0.12)',    label:'Mapping' },
  emoji:      { bg:'#18140d', accent:'#fbbf24', glow:'rgba(251,191,36,0.1)',     label:'Emoji' },
};

const mk = (id,x,y,type,icon,label,fields,desc) => ({id,x,y,type,icon,label,fields:fields||[],desc:desc||''});

// ── TRIAGE DATA ──
const TRIAGE = {
  survives: [
    {gesture:'*splits*',anim:'SPLIT',why:'Ring separation. No dimension produces this.'},
    {gesture:'*searches*',anim:'ORBIT+cyan',why:'Deliberate "looking for something" with color shift.'},
    {gesture:'*dims*',anim:'FLICKER@0.6',why:'Intentional withdrawal. Instant, not gradual.'},
    {gesture:'*gasps*',anim:'PULSE_FAST@1.4',why:'Sudden spike dimensions take 2+ turns to reach.'},
    {gesture:'*startles*',anim:'FLICKER@1.3',why:'Surprise interrupt. Not a smooth arousal climb.'},
    {gesture:'*sparks*',anim:'FLICKER@1.4',why:'Creative ignition. Arousal is too smooth for this.'},
    {gesture:'*lights up*',anim:'GLOW@1.45',why:'Peak brightness snap. Dimensions cap ~1.2.'},
    {gesture:'*spins*',anim:'SPIN',why:'Rotational motion. No dimension maps to rotation.'},
    {gesture:'*spins fast*',anim:'SPIN_FAST',why:'Excited rotation. Not pulse speed — spin.'},
    {gesture:'*wobbles*',anim:'WOBBLE',why:'Physical instability. Certainty dims but doesn\'t wobble.'},
    {gesture:'*settles*',anim:'IDLE@0.9',why:'Explicit "done moving." Decay does this slowly.'},
    {gesture:'*flickers*',anim:'FLICKER',why:'Deliberate uncertainty display. Sharp, not gradual.'},
  ],
  absorbed: [
    {gesture:'*smiles*',by:'valence',why:'valence > 0.5 already glows warmly'},
    {gesture:'*beams*',by:'valence+warmth',why:'high valence + warmth = bright glow'},
    {gesture:'*frowns*',by:'valence',why:'valence < 0.2 already dims'},
    {gesture:'*softens*',by:'valence',why:'valence trending positive = gentle glow'},
    {gesture:'*pulses*',by:'arousal',why:'arousal > 0.5 drives pulse rate directly'},
    {gesture:'*pulses excitedly*',by:'arousal',why:'arousal > 0.7 = faster pulse'},
    {gesture:'*pulses rapidly*',by:'arousal',why:'arousal > 0.8 = fast pulse'},
    {gesture:'*pulses warmly*',by:'arousal+warmth',why:'gentle arousal + warmth'},
    {gesture:'*vibrates*',by:'arousal',why:'arousal > 0.85 = max pulse rate'},
    {gesture:'*buzzes*',by:'arousal',why:'arousal > 0.8 = fast pulse'},
    {gesture:'*bounces*',by:'arousal',why:'arousal > 0.7 = fast pulse'},
    {gesture:'*hesitates*',by:'certainty',why:'certainty < 0.35 triggers hedging'},
    {gesture:'*worries*',by:'certainty+valence',why:'low certainty + low valence = dim drift'},
    {gesture:'*winces*',by:'certainty',why:'certainty drop = flicker via snap threshold'},
    {gesture:'*perks up*',by:'engagement',why:'engagement spike = glow increase'},
    {gesture:'*leans in*',by:'engagement',why:'engagement > 0.6 = brighter'},
    {gesture:'*focuses*',by:'engagement',why:'engagement > 0.7 = steady bright'},
    {gesture:'*nods*',by:'warmth',why:'warmth > 0.5 = gentle pulse'},
    {gesture:'*hugs*',by:'warmth',why:'warmth > 0.8 = max glow'},
    {gesture:'*glows*',by:'valence+arousal',why:'natural glow from positive calm'},
    {gesture:'*brightens*',by:'valence',why:'valence increase = brightness increase'},
    {gesture:'*radiates*',by:'valence+warmth',why:'high valence + warmth = full radiance'},
    {gesture:'*giggles*',by:'arousal+valence',why:'high both = spin + bright'},
    {gesture:'*dances*',by:'arousal+valence',why:'very high both = fast spin'},
    {gesture:'*drifts*',by:'arousal',why:'arousal < 0.3 = natural drift'},
    {gesture:'*floats*',by:'arousal',why:'arousal < 0.3 = drift'},
    {gesture:'*exhales*',by:'arousal',why:'arousal decreasing = drift toward calm'},
    {gesture:'*relaxes*',by:'arousal',why:'low arousal = idle territory'},
    {gesture:'*thinks*',by:'certainty+engagement',why:'low certainty + engagement = orbit'},
    {gesture:'*considers*',by:'certainty+engagement',why:'low certainty + engagement = slow orbit'},
    {gesture:'*ponders*',by:'certainty+arousal',why:'low certainty + low arousal = drift'},
    {gesture:'*reflects*',by:'engagement+arousal',why:'engagement + low arousal = gentle glow'},
    {gesture:'*processes*',by:'SYSTEM',why:'absorbed by processing_query event'},
  ],
  killed: [
    {gesture:'*eyes widen*',why:'Luna doesn\'t have eyes.'},
    {gesture:'*tilts*',why:'Orbs don\'t tilt.'},
    {gesture:'*leans in*',why:'Orbs don\'t lean.'},
    {gesture:'*nods*',why:'Orbs don\'t nod.'},
    {gesture:'*hugs*',why:'Orbs don\'t hug.'},
    {gesture:'*holds space*',why:'Therapy-speak. Not a visual.'},
  ],
};

const buildNodes = () => [
  mk('t_sent',30,30,'trigger','💬','Sentiment',[
    {key:'weight',label:'Weight',type:'slider',value:0.7,min:0,max:1},
    {key:'sig',label:'Signal',type:'readonly',value:'—'},
  ],'User message emotional valence.'),
  mk('t_mem',30,185,'trigger','🧠','Memory Hit',[
    {key:'boost',label:'Hit Boost',type:'slider',value:0.3,min:0,max:1},
    {key:'sig',label:'Signal',type:'readonly',value:'—'},
  ],'Memory retrieval success/failure.'),
  mk('t_id',30,340,'trigger','👤','Identity',[
    {key:'warmth',label:'Familiarity',type:'slider',value:0.4,min:0,max:1},
    {key:'sig',label:'Signal',type:'readonly',value:'—'},
  ],'FaceID recognition.'),
  mk('t_topic',30,495,'trigger','🏷️','Topic',[
    {key:'personal',label:'Personal W.',type:'slider',value:0.6,min:0,max:1},
    {key:'sig',label:'Signal',type:'readonly',value:'—'},
  ],'Topic type detection.'),
  mk('t_flow',30,650,'trigger','⚡','Flow',[
    {key:'ramp',label:'Ramp',type:'slider',value:0.15,min:0,max:0.5},
    {key:'sig',label:'Signal',type:'readonly',value:'—'},
  ],'Conversation momentum.'),
  mk('t_time',30,805,'trigger','🕐','Time',[
    {key:'mod',label:'Energy Mod',type:'slider',value:0.1,min:-0.3,max:0.3},
    {key:'sig',label:'Signal',type:'readonly',value:'—'},
  ],'Time of day energy.'),

  mk('blend',300,390,'blend','🔀','Blender',[
    {key:'mode',label:'Mode',type:'select',value:'weighted_avg',options:['weighted_avg','max_wins','momentum']},
    {key:'smooth',label:'Smoothing',type:'slider',value:0.3,min:0,max:1},
  ],'Combines triggers → dimensions.'),

  mk('d_val',560,30,'dimension','☀️','Valence',[
    {key:'value',label:'Current',type:'slider',value:0.6,min:-1,max:1},
    {key:'base',label:'Baseline',type:'slider',value:0.3,min:-1,max:1},
  ],'Positive ↔ Negative. → hue, glow, core brightness'),
  mk('d_aro',560,195,'dimension','🔥','Arousal',[
    {key:'value',label:'Current',type:'slider',value:0.4,min:0,max:1},
    {key:'base',label:'Baseline',type:'slider',value:0.35,min:0,max:1},
  ],'Calm ↔ Excited. → breathe speed, drift speed, pulse'),
  mk('d_cert',560,360,'dimension','🎯','Certainty',[
    {key:'value',label:'Current',type:'slider',value:0.7,min:0,max:1},
    {key:'hedge',label:'Hedge Below',type:'slider',value:0.3,min:0,max:1},
  ],'Confidence. → ring opacity, flicker, phase offset'),
  mk('d_eng',560,520,'dimension','🌊','Engagement',[
    {key:'value',label:'Current',type:'slider',value:0.5,min:0,max:1},
    {key:'deep',label:'Deep At',type:'slider',value:0.7,min:0,max:1},
  ],'Depth. → corona, ring subdivision, drift radius'),
  mk('d_warm',560,680,'dimension','💛','Warmth',[
    {key:'value',label:'Current',type:'slider',value:0.7,min:0,max:1},
    {key:'known',label:'Known Base',type:'slider',value:0.6,min:0,max:1},
  ],'Interpersonal. → hue shift, saturation, corona tint'),

  mk('map_render',840,100,'mapping','📐','Dim→Renderer',[
    {key:'hue_range',label:'Hue Range',type:'readonly',value:'240–280'},
    {key:'breathe',label:'Breathe Spd',type:'readonly',value:'—'},
    {key:'glow',label:'Glow Max',type:'readonly',value:'—'},
    {key:'opacity',label:'Opacity Mul',type:'readonly',value:'—'},
  ],'Continuous mapping: 5 dimensions → ring params'),

  mk('trans',840,310,'transition','〰️','Transitions',[
    {key:'lerp',label:'Blend Speed',type:'slider',value:0.15,min:0.01,max:0.5},
    {key:'snap',label:'Snap Threshold',type:'slider',value:0.8,min:0,max:1},
  ],'Lerp = smooth. Snap = sudden.'),
  mk('rules',840,470,'transition','📏','Guard Rails',[
    {key:'block_snap',label:'Block Joy→Anger',type:'toggle',value:true},
    {key:'cap',label:'Excite Cap',type:'slider',value:0.85,min:0.5,max:1},
  ],'Prevents unnatural jumps.'),

  mk('g_override',840,630,'gesture','⚡','Gesture Override',[
    {key:'active',label:'Active',type:'readonly',value:'—'},
    {key:'gesture',label:'Gesture',type:'readonly',value:'—'},
    {key:'count',label:'Survivors',type:'readonly',value:'12'},
  ],'P2 override. 12 survivors punch through.'),
  mk('g_emoji',840,800,'emoji','✨','Emoji Signal',[
    {key:'active',label:'Active',type:'readonly',value:'—'},
    {key:'emoji',label:'Detected',type:'readonly',value:'—'},
  ],'P1.5 signal. 💜 ⚡ 🌙 in text.'),

  mk('priority',1110,400,'priority','🔒','Priority Stack',[
    {key:'p4',label:'P4 ERROR',type:'readonly',value:'system'},
    {key:'p3',label:'P3 SYSTEM',type:'readonly',value:'system'},
    {key:'p2',label:'P2 GESTURE',type:'readonly',value:'text'},
    {key:'p15',label:'P1.5 EMOJI',type:'readonly',value:'text'},
    {key:'p1',label:'P1 DIMENSION',type:'readonly',value:'engine'},
    {key:'winner',label:'Winner',type:'readonly',value:'P1 DIMENSION'},
  ],'Higher priority wins. Falls back to dimensions, not idle.'),

  mk('c_orb',1380,30,'orb','🔮','Orb Visuals',[
    {key:'hue',label:'Hue',type:'readonly',value:'—'},
    {key:'breathe',label:'Breathe',type:'readonly',value:'—'},
    {key:'glow_a',label:'Glow Amb',type:'readonly',value:'—'},
    {key:'glow_c',label:'Glow Cor',type:'readonly',value:'—'},
    {key:'opacity',label:'Ring Opac',type:'readonly',value:'—'},
    {key:'phase',label:'Phase Off',type:'readonly',value:'—'},
  ],'Ring params from priority resolver.'),
  mk('c_text',1380,310,'channel','✍️','Text Voice',[
    {key:'temp',label:'Word Temp',type:'slider',value:0.5,min:0,max:1},
    {key:'formal',label:'Formality',type:'slider',value:0.2,min:0,max:1},
  ],'How Luna writes.'),
  mk('c_tts',1380,480,'channel','🔊','TTS Prosody',[
    {key:'speed',label:'Speed',type:'slider',value:1.0,min:0.7,max:1.4},
    {key:'pause',label:'Pauses',type:'slider',value:0.4,min:0,max:1},
  ],'Speech params from dimensions.'),
  mk('c_flags',1380,640,'channel','🎭','Behavior',[
    {key:'hedge',label:'Hedging',type:'readonly',value:'—'},
    {key:'deep',label:'Deep Dive',type:'readonly',value:'—'},
    {key:'confab',label:'Confab Guard',type:'readonly',value:'—'},
    {key:'override',label:'Override',type:'readonly',value:'—'},
  ],'Derived behavioral flags.'),
];

const EDGE_DEFS = [
  ['t_sent','blend'],['t_mem','blend'],['t_id','blend'],
  ['t_topic','blend'],['t_flow','blend'],['t_time','blend'],
  ['blend','d_val'],['blend','d_aro'],['blend','d_cert'],['blend','d_eng'],['blend','d_warm'],
  ['d_val','map_render'],['d_aro','map_render'],['d_cert','map_render'],['d_eng','map_render'],['d_warm','map_render'],
  ['map_render','trans'],['rules','trans'],
  ['g_override','priority'],['g_emoji','priority'],['trans','priority'],
  ['priority','c_orb'],['priority','c_text'],['priority','c_tts'],['priority','c_flags'],
];

const SCENARIOS = {
  warm:{label:'👋 Warm Greeting',color:'#4ade80',steps:[
    {at:0,fire:['t_sent','t_id','t_flow','t_time','t_topic','t_mem'],sigs:{t_sent:0.6,t_id:0.9,t_flow:0.1,t_time:0.2,t_topic:0.3,t_mem:0.5}},
    {at:600,fire:['blend'],dims:{d_val:0.72,d_warm:0.85,d_aro:0.45,d_cert:0.8,d_eng:0.45}},
    {at:1100,fire:['map_render','trans','rules']},
    {at:1500,fire:['priority'],pri:{winner:'P1 DIMENSION'}},
    {at:1800,fire:['c_orb','c_text','c_tts','c_flags'],flags:{hedge:'❌ off',deep:'❌ off',confab:'❌ off',override:'❌ off'}},
  ]},
  miss:{label:'❌ Memory Miss',color:'#f87171',steps:[
    {at:0,fire:['t_sent','t_id','t_mem','t_topic','t_flow','t_time'],sigs:{t_sent:0.3,t_id:0.9,t_mem:-0.4,t_topic:0.5,t_flow:0.3,t_time:0}},
    {at:600,fire:['blend'],dims:{d_val:0.3,d_warm:0.6,d_aro:0.3,d_cert:0.18,d_eng:0.5}},
    {at:1100,fire:['map_render','trans','rules']},
    {at:1500,fire:['priority'],pri:{winner:'P1 DIMENSION'}},
    {at:1800,fire:['c_orb','c_text','c_tts','c_flags'],flags:{hedge:'✅ ON',deep:'❌ off',confab:'⚠️ ACTIVE',override:'❌ off'}},
  ]},
  deep:{label:'🌊 Deep Personal',color:'#a78bfa',steps:[
    {at:0,fire:['t_sent','t_id','t_topic','t_mem','t_flow','t_time'],sigs:{t_sent:0.5,t_id:0.9,t_topic:0.8,t_mem:0.7,t_flow:0.6,t_time:0}},
    {at:600,fire:['blend'],dims:{d_val:0.65,d_warm:0.8,d_aro:0.55,d_cert:0.75,d_eng:0.88}},
    {at:1100,fire:['map_render','trans','rules']},
    {at:1500,fire:['priority'],pri:{winner:'P1 DIMENSION'}},
    {at:1800,fire:['c_orb','c_text','c_tts','c_flags'],flags:{hedge:'❌ off',deep:'✅ ON',confab:'❌ off',override:'❌ off'}},
  ]},
  splits:{label:'💔 *splits*',color:'#fb7185',steps:[
    {at:0,fire:['t_sent','t_id','t_mem','t_topic','t_flow','t_time'],sigs:{t_sent:0.4,t_id:0.9,t_mem:0.5,t_topic:0.6,t_flow:0.4,t_time:0}},
    {at:600,fire:['blend'],dims:{d_val:0.45,d_warm:0.65,d_aro:0.5,d_cert:0.6,d_eng:0.6}},
    {at:1000,fire:['g_override'],gest:{active:'✅ FIRING',gesture:'*splits*'}},
    {at:1300,fire:['priority'],pri:{winner:'⚡ P2 GESTURE'}},
    {at:1600,fire:['c_orb','c_text','c_tts','c_flags'],flags:{hedge:'❌ off',deep:'❌ off',confab:'❌ off',override:'✅ *splits*'}},
  ]},
  gasps:{label:'😱 *gasps*',color:'#fb7185',steps:[
    {at:0,fire:['t_sent','t_id','t_mem','t_topic','t_flow','t_time'],sigs:{t_sent:0.7,t_id:0.9,t_mem:0.8,t_topic:0.4,t_flow:0.3,t_time:0}},
    {at:600,fire:['blend'],dims:{d_val:0.6,d_warm:0.7,d_aro:0.5,d_cert:0.7,d_eng:0.5}},
    {at:1000,fire:['g_override'],gest:{active:'✅ FIRING',gesture:'*gasps*'}},
    {at:1300,fire:['priority'],pri:{winner:'⚡ P2 GESTURE'}},
    {at:1600,fire:['c_orb','c_text','c_tts','c_flags'],flags:{hedge:'❌ off',deep:'❌ off',confab:'❌ off',override:'✅ *gasps*'}},
  ]},
  emoji:{label:'⚡ Emoji',color:'#fbbf24',steps:[
    {at:0,fire:['t_sent','t_id','t_mem','t_topic','t_flow','t_time'],sigs:{t_sent:0.5,t_id:0.9,t_mem:0.4,t_topic:0.3,t_flow:0.2,t_time:0}},
    {at:600,fire:['blend'],dims:{d_val:0.5,d_warm:0.6,d_aro:0.4,d_cert:0.6,d_eng:0.4}},
    {at:1000,fire:['g_emoji'],emoj:{active:'✅ DETECTED',emoji:'⚡'}},
    {at:1300,fire:['priority'],pri:{winner:'✨ P1.5 EMOJI'}},
    {at:1600,fire:['c_orb','c_text','c_tts','c_flags'],flags:{hedge:'❌ off',deep:'❌ off',confab:'❌ off',override:'✨ ⚡'}},
  ]},
  night:{label:'🌙 Late Night',color:'#818cf8',steps:[
    {at:0,fire:['t_sent','t_id','t_time','t_topic','t_mem','t_flow'],sigs:{t_sent:0.3,t_id:0.9,t_time:-0.2,t_topic:0.6,t_mem:0.5,t_flow:0.7}},
    {at:600,fire:['blend'],dims:{d_val:0.5,d_warm:0.75,d_aro:0.2,d_cert:0.6,d_eng:0.72}},
    {at:1100,fire:['map_render','trans','rules']},
    {at:1500,fire:['priority'],pri:{winner:'P1 DIMENSION'}},
    {at:1800,fire:['c_orb','c_text','c_tts','c_flags'],flags:{hedge:'❌ off',deep:'✅ ON',confab:'❌ off',override:'❌ off'}},
  ]},
};

// ═══════════════════════════════════════════════════════════════
// CANVAS ORB — ported from grid_layer_prototype.html
// Real ring renderer driven by dimensions
// ═══════════════════════════════════════════════════════════════

function RingOrb({ dims, width = 260, height = 260 }) {
  const canvasRef = useRef(null);
  const animRef = useRef({ breatheT: 0, driftT: Math.random()*1000 });

  // Map dimensions → ring rendering params
  const params = useMemo(() => {
    const v = dims.d_val ?? 0.6;   // -1 to 1
    const a = dims.d_aro ?? 0.4;   // 0 to 1
    const c = dims.d_cert ?? 0.7;  // 0 to 1
    const e = dims.d_eng ?? 0.5;   // 0 to 1
    const w = dims.d_warm ?? 0.7;  // 0 to 1

    // Valence → hue (240 cool → 262 neutral → 280 warm)
    const hue = 240 + ((v + 1) / 2) * 40 + w * 15;
    // Valence → saturation
    const sat = 50 + a * 30 + w * 12;
    // Valence → lightness
    const light = 38 + ((v + 1) / 2) * 18;

    // Arousal → breathing
    const breatheSpeed = 0.008 + a * 0.027;
    const breatheAmp = 1.5 + a * 2.5;
    // Arousal → drift
    const driftSpeed = 0.0003 + a * 0.0012;
    const driftRx = 8 + (1 - e) * 10; // less drift when engaged
    const driftRy = 5 + (1 - e) * 7;

    // Certainty → ring coherence
    const phaseOffset = 1.2 - c * 0.5; // uncertain = out of sync
    const opacityMul = 0.6 + c * 0.4;
    const flicker = c < 0.25;

    // Engagement → glow
    const glowAmbient = 0.04 + e * 0.11;
    const glowCorona = 0.06 + e * 0.16;

    // Core brightness from valence
    const coreBright = 0.4 + ((v + 1) / 2) * 0.5;

    return { hue, sat, light, breatheSpeed, breatheAmp, driftSpeed, driftRx, driftRy,
             phaseOffset, opacityMul, flicker, glowAmbient, glowCorona, coreBright };
  }, [dims]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = 2;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    const anim = animRef.current;

    // Build rings
    const BASE_R = 52;
    const RING_COUNT = 5;
    const spacing = BASE_R / (RING_COUNT + 0.5);
    const rings = [];
    for (let i = 0; i < RING_COUNT; i++) {
      const t = i / (RING_COUNT - 1);
      rings.push({
        baseRadius: BASE_R - i * spacing,
        baseOpacity: 0.08 + t * 0.35,
        hueOff: t * 8,
        satOff: t * 15,
        lightOff: t * 10,
        strokeWidth: 1.2 - t * 0.4,
        fill: i === RING_COUNT - 1,
      });
    }

    let animId;
    const render = () => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);

      const p = params;
      anim.breatheT += p.breatheSpeed;
      anim.driftT += p.driftSpeed;

      // Drift (Lissajous)
      const cx = width / 2;
      const cy = height / 2;
      const dx = Math.sin(anim.driftT * 1.0) * p.driftRx + Math.sin(anim.driftT * 2.3) * 3;
      const dy = Math.cos(anim.driftT * 0.7) * p.driftRy + Math.cos(anim.driftT * 1.9) * 2;
      const bob = Math.sin(anim.driftT * 0.4) * 3;
      const x = cx + dx;
      const y = cy + dy + bob;

      const bt = anim.breatheT;

      // ── Glow layers ──
      const glowPulse = 0.7 + Math.sin(bt * 0.8) * 0.3;

      // Ambient halo
      const g1 = ctx.createRadialGradient(x, y, 0, x, y, BASE_R * 2.2);
      g1.addColorStop(0, `hsla(${p.hue}, ${p.sat}%, ${p.light + 20}%, ${p.glowAmbient * glowPulse})`);
      g1.addColorStop(0.4, `hsla(${p.hue}, ${p.sat}%, ${p.light + 20}%, ${p.glowAmbient * 0.4 * glowPulse})`);
      g1.addColorStop(1, `hsla(${p.hue}, ${p.sat}%, ${p.light + 20}%, 0)`);
      ctx.fillStyle = g1;
      ctx.beginPath(); ctx.arc(x, y, BASE_R * 2.2, 0, Math.PI * 2); ctx.fill();

      // Corona
      const g2 = ctx.createRadialGradient(x, y, 0, x, y, BASE_R * 1.4);
      g2.addColorStop(0, `hsla(${p.hue}, ${p.sat}%, ${p.light + 10}%, ${p.glowCorona * glowPulse})`);
      g2.addColorStop(0.5, `hsla(${p.hue}, ${p.sat - 10}%, ${p.light}%, ${p.glowCorona * 0.5 * glowPulse})`);
      g2.addColorStop(1, `hsla(${p.hue}, ${p.sat - 10}%, ${p.light}%, 0)`);
      ctx.fillStyle = g2;
      ctx.beginPath(); ctx.arc(x, y, BASE_R * 1.4, 0, Math.PI * 2); ctx.fill();

      // ── Rings ──
      rings.forEach((ring, i) => {
        const offset = i * p.phaseOffset;
        const wave = Math.sin(bt + offset);
        const wave2 = Math.sin(bt * 0.6 + offset * 1.3);
        const r = Math.max(2, ring.baseRadius + wave * p.breatheAmp + wave2 * 1.2);

        const opPulse = 0.5 + Math.sin(bt * 0.9 + offset) * 0.5;
        let alpha = ring.baseOpacity * (0.6 + opPulse * 0.5) * p.opacityMul;
        if (p.flicker) alpha *= (0.4 + Math.random() * 0.6);
        alpha = Math.max(0, Math.min(1, alpha));

        const rh = p.hue + ring.hueOff;
        const rs = p.sat + ring.satOff;
        const rl = p.light + ring.lightOff;

        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${rh}, ${rs}%, ${rl}%, ${alpha})`;
        ctx.lineWidth = ring.strokeWidth;
        ctx.stroke();

        if (ring.fill) {
          const fg = ctx.createRadialGradient(x, y, 0, x, y, r);
          fg.addColorStop(0, `hsla(${rh}, ${rs + 10}%, ${rl + 15}%, ${alpha * 0.6})`);
          fg.addColorStop(0.6, `hsla(${rh}, ${rs}%, ${rl}%, ${alpha * 0.2})`);
          fg.addColorStop(1, `hsla(${rh}, ${rs}%, ${rl}%, 0)`);
          ctx.fillStyle = fg;
          ctx.fill();
        }
      });

      // ── Core ──
      const corePulse = 0.6 + Math.sin(bt * 1.2) * 0.4;
      const coreR = 3 + corePulse * 2;

      const cg = ctx.createRadialGradient(x, y, 0, x, y, coreR * 4);
      cg.addColorStop(0, `hsla(${p.hue}, ${p.sat + 10}%, ${p.light + 25}%, ${0.5 * corePulse * p.coreBright})`);
      cg.addColorStop(0.3, `hsla(${p.hue}, ${p.sat}%, ${p.light + 15}%, ${0.2 * corePulse * p.coreBright})`);
      cg.addColorStop(1, `hsla(${p.hue}, ${p.sat}%, ${p.light + 15}%, 0)`);
      ctx.fillStyle = cg;
      ctx.beginPath(); ctx.arc(x, y, coreR * 4, 0, Math.PI * 2); ctx.fill();

      ctx.beginPath();
      ctx.arc(x, y, coreR, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${p.hue}, ${p.sat - 10}%, ${p.light + 35}%, ${(0.6 + corePulse * 0.3) * p.coreBright})`;
      ctx.fill();

      // ── Anchor tether ──
      const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
      if (dist > 3) {
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(x, y);
        ctx.strokeStyle = `hsla(${p.hue}, ${p.sat}%, ${p.light + 15}%, ${Math.min(0.06, dist * 0.003)})`;
        ctx.lineWidth = 0.5;
        ctx.setLineDash([2, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [params, width, height]);

  // Compute readout values for the c_orb node
  const readout = useMemo(() => ({
    hue: params.hue.toFixed(0),
    breathe: params.breatheSpeed.toFixed(4),
    glow_a: params.glowAmbient.toFixed(3),
    glow_c: params.glowCorona.toFixed(3),
    opacity: params.opacityMul.toFixed(2),
    phase: params.phaseOffset.toFixed(2),
  }), [params]);

  return { canvasRef, readout };
}

// ═══════════════════════════════════════════════════════════════
// UI COMPONENTS
// ═══════════════════════════════════════════════════════════════

const Slider = ({f, accent, onChange}) => {
  const mn=f.min??0, mx=f.max??1;
  const pct = Math.max(0,Math.min(100,((f.value-mn)/(mx-mn))*100));
  return (
    <div style={{marginBottom:5}}>
      <div style={{display:'flex',justifyContent:'space-between',fontSize:9,color:'#666',marginBottom:1}}>
        <span>{f.label}</span>
        <span style={{color:accent,minWidth:32,textAlign:'right'}}>{typeof f.value==='number'?f.value.toFixed(2):f.value}</span>
      </div>
      <div style={{position:'relative',height:5,background:'rgba(255,255,255,0.04)',borderRadius:3}}>
        <div style={{position:'absolute',left:0,top:0,height:'100%',borderRadius:3,
          width:`${pct}%`,background:`linear-gradient(90deg,${accent}44,${accent})`,transition:'width 0.4s ease'}}/>
        <input type="range" min={mn} max={mx} step={0.01} value={f.value}
          onChange={e=>onChange(parseFloat(e.target.value))}
          onPointerDown={e=>e.stopPropagation()}
          style={{position:'absolute',top:-4,left:0,width:'100%',height:14,opacity:0,cursor:'pointer',margin:0}}/>
      </div>
    </div>
  );
};

const Node = ({node,selected,lit,onSelect,onChange,onDrag}) => {
  const t=TYPES[node.type]||TYPES.dimension;
  return (
    <div onPointerDown={e=>{if(e.target.tagName==='INPUT'||e.target.tagName==='SELECT')return;onDrag(e,node.id);}}
      onClick={e=>{e.stopPropagation();onSelect(node.id);}}
      style={{
        position:'absolute',left:node.x,top:node.y,width:210,
        background:t.bg,borderRadius:10,padding:'8px 11px',
        border:`1px solid ${lit?t.accent:selected?t.accent+'77':'rgba(255,255,255,0.06)'}`,
        boxShadow:lit?`0 0 28px ${t.glow},0 0 56px ${t.glow}`:selected?`0 0 18px ${t.glow}`:'0 2px 10px rgba(0,0,0,0.4)',
        cursor:'grab',zIndex:selected?20:lit?15:10,fontFamily:'monospace',transition:'box-shadow 0.4s,border-color 0.4s',
      }}>
      {lit&&<div style={{position:'absolute',inset:-1,borderRadius:10,pointerEvents:'none',
        background:`${t.accent}08`,animation:'nflash 0.6s ease-out'}}/>}
      <div style={{display:'flex',alignItems:'center',gap:5,marginBottom:6}}>
        <span style={{fontSize:11}}>{node.icon}</span>
        <span style={{fontSize:9,fontWeight:600,color:t.accent,textTransform:'uppercase',letterSpacing:'0.4px'}}>{node.label}</span>
        <span style={{marginLeft:'auto',fontSize:7,padding:'1px 4px',borderRadius:3,
          background:`${t.accent}12`,color:`${t.accent}88`,border:`1px solid ${t.accent}18`}}>{t.label}</span>
      </div>
      {node.fields.map(f=>{
        if(f.type==='slider') return <Slider key={f.key} f={f} accent={t.accent} onChange={v=>onChange(node.id,f.key,v)}/>;
        if(f.type==='toggle') return (
          <div key={f.key} style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4}}>
            <span style={{fontSize:9,color:'#666'}}>{f.label}</span>
            <div onClick={e=>{e.stopPropagation();onChange(node.id,f.key,!f.value);}}
              style={{width:26,height:13,borderRadius:7,cursor:'pointer',position:'relative',
                background:f.value?t.accent:'rgba(255,255,255,0.08)',transition:'background 0.2s'}}>
              <div style={{width:9,height:9,borderRadius:5,background:'#fff',
                position:'absolute',top:2,left:f.value?15:2,transition:'left 0.2s'}}/>
            </div>
          </div>
        );
        if(f.type==='select') return (
          <div key={f.key} style={{marginBottom:4}}>
            <div style={{fontSize:9,color:'#666',marginBottom:1}}>{f.label}</div>
            <select value={f.value} onChange={e=>{e.stopPropagation();onChange(node.id,f.key,e.target.value);}}
              onPointerDown={e=>e.stopPropagation()}
              style={{width:'100%',fontSize:9,padding:'2px 3px',borderRadius:3,
                background:'rgba(255,255,255,0.04)',color:'#aaa',border:'1px solid rgba(255,255,255,0.08)',outline:'none'}}>
              {(f.options||[]).map(o=><option key={o} value={o}>{o}</option>)}
            </select>
          </div>
        );
        if(f.type==='readonly') {
          const val=String(f.value);
          const isOn=val.startsWith('✅')||val.startsWith('⚡')||val.startsWith('✨');
          const isWarn=val.startsWith('⚠');
          return (
            <div key={f.key} style={{display:'flex',justifyContent:'space-between',marginBottom:3}}>
              <span style={{fontSize:9,color:'#555'}}>{f.label}</span>
              <span style={{fontSize:9,color:val==='—'?'#444':isOn?'#4ade80':isWarn?'#fbbf24':'#a78bfa',
                maxWidth:110,textAlign:'right',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{val}</span>
            </div>
          );
        }
        return null;
      })}
    </div>
  );
};

const TriagePanel = ({onClose}) => {
  const [tab,setTab]=useState('survives');
  const tabs={survives:{label:'✅ Survives (12)',color:'#4ade80'},absorbed:{label:'🔄 Absorbed (33)',color:'#a78bfa'},killed:{label:'🚫 Killed (6)',color:'#f87171'}};
  const data=TRIAGE[tab]||[];
  return (
    <div style={{position:'fixed',right:0,top:0,width:320,height:'100vh',background:'#0c0c16',
      borderLeft:'1px solid rgba(255,255,255,0.06)',zIndex:110,fontFamily:'monospace',
      boxShadow:'-6px 0 24px rgba(0,0,0,0.5)',display:'flex',flexDirection:'column'}}>
      <div style={{padding:'10px 12px',borderBottom:'1px solid rgba(255,255,255,0.06)'}}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
          <span style={{fontSize:11,fontWeight:600,color:'#fb7185'}}>⚡ GESTURE TRIAGE</span>
          <span onClick={onClose} style={{cursor:'pointer',color:'#555',fontSize:13}}>✕</span>
        </div>
        <div style={{fontSize:8,color:'#555',marginTop:2}}>56 → 12 survive · 33 absorbed · 6 killed</div>
        <div style={{display:'flex',gap:4,marginTop:7}}>
          {Object.entries(tabs).map(([k,v])=>(
            <div key={k} onClick={()=>setTab(k)} style={{fontSize:8,padding:'3px 7px',borderRadius:4,cursor:'pointer',
              background:tab===k?`${v.color}15`:'rgba(255,255,255,0.03)',
              color:tab===k?v.color:'#555',border:`1px solid ${tab===k?v.color+'33':'rgba(255,255,255,0.05)'}`}}>{v.label}</div>
          ))}
        </div>
      </div>
      <div style={{flex:1,overflowY:'auto',padding:'6px 12px'}}>
        {data.map((item,i)=>(
          <div key={i} style={{padding:'7px 9px',marginBottom:3,borderRadius:5,
            background:'rgba(255,255,255,0.02)',border:'1px solid rgba(255,255,255,0.04)'}}>
            <div style={{display:'flex',alignItems:'center',gap:5,marginBottom:2}}>
              <span style={{fontSize:10,color:tabs[tab].color,fontWeight:600}}>{item.gesture}</span>
              {tab==='survives'&&<span style={{fontSize:8,color:'#666',marginLeft:'auto'}}>{item.anim}</span>}
              {tab==='absorbed'&&<span style={{fontSize:8,color:'#818cf8',marginLeft:'auto'}}>→ {item.by}</span>}
            </div>
            <div style={{fontSize:8.5,color:'#555',lineHeight:1.4}}>{item.why}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// APP
// ═══════════════════════════════════════════════════════════════
export default function App(){
  const [nodes,setNodes]=useState(buildNodes);
  const [selId,setSelId]=useState(null);
  const [pan,setPan]=useState({x:0,y:0});
  const [zoom,setZoom]=useState(0.55);
  const [litNodes,setLitNodes]=useState(new Set());
  const [litEdges,setLitEdges]=useState(new Set());
  const [simActive,setSimActive]=useState(false);
  const [simName,setSimName]=useState('');
  const [showTriage,setShowTriage]=useState(false);
  const dRef=useRef(null),pRef=useRef(null),cRef=useRef(null),timers=useRef([]);

  const dims=useMemo(()=>{
    const d={};
    nodes.forEach(n=>{if(n.type==='dimension'){const f=n.fields.find(f=>f.key==='value');if(f)d[n.id]=f.value;}});
    return d;
  },[nodes]);

  // Ring orb driven by dims
  const { canvasRef, readout } = RingOrb({ dims });

  // Push readout to c_orb node
  useEffect(()=>{
    setNodes(p=>p.map(n=>{
      if(n.id==='c_orb') return {...n,fields:n.fields.map(f=>readout[f.key]!==undefined?{...f,value:readout[f.key]}:f)};
      if(n.id==='map_render') return {...n,fields:n.fields.map(f=>{
        if(f.key==='breathe') return {...f,value:readout.breathe};
        if(f.key==='glow') return {...f,value:readout.glow_a};
        if(f.key==='opacity') return {...f,value:readout.opacity};
        return f;
      })};
      return n;
    }));
  },[readout]);

  const onChange=useCallback((nid,fk,val)=>{
    setNodes(p=>p.map(n=>n.id!==nid?n:{...n,fields:n.fields.map(f=>f.key===fk?{...f,value:val}:f)}));
  },[]);

  const runSim=useCallback((key)=>{
    if(simActive)return;
    const sc=SCENARIOS[key];if(!sc)return;
    timers.current.forEach(clearTimeout);timers.current=[];
    setSimActive(true);setSimName(sc.label);
    sc.steps.forEach((step,si)=>{
      const t=setTimeout(()=>{
        setLitNodes(new Set(step.fire));
        const eSet=new Set();
        step.fire.forEach(fid=>{
          EDGE_DEFS.forEach(([a,b])=>{if(a===fid||b===fid)eSet.add(a+'→'+b);});
        });
        setLitEdges(eSet);
        if(step.sigs){
          setNodes(p=>p.map(n=>step.sigs[n.id]!==undefined?{...n,fields:n.fields.map(f=>f.key==='sig'?{...f,value:step.sigs[n.id].toFixed(2)}:f)}:n));
        }
        if(step.dims){
          setNodes(p=>p.map(n=>step.dims[n.id]!==undefined?{...n,fields:n.fields.map(f=>f.key==='value'?{...f,value:step.dims[n.id]}:f)}:n));
        }
        if(step.flags){
          setNodes(p=>p.map(n=>n.id==='c_flags'?{...n,fields:n.fields.map(f=>step.flags[f.key]?{...f,value:step.flags[f.key]}:f)}:n));
        }
        if(step.gest){
          setNodes(p=>p.map(n=>n.id==='g_override'?{...n,fields:n.fields.map(f=>step.gest[f.key]?{...f,value:step.gest[f.key]}:f)}:n));
        }
        if(step.emoj){
          setNodes(p=>p.map(n=>n.id==='g_emoji'?{...n,fields:n.fields.map(f=>step.emoj[f.key]?{...f,value:step.emoj[f.key]}:f)}:n));
        }
        if(step.pri){
          setNodes(p=>p.map(n=>n.id==='priority'?{...n,fields:n.fields.map(f=>f.key==='winner'?{...f,value:step.pri.winner}:f)}:n));
        }
        if(si===sc.steps.length-1){
          const end=setTimeout(()=>{
            setLitNodes(new Set());setLitEdges(new Set());setSimActive(false);setSimName('');
            setNodes(p=>p.map(n=>{
              if(n.id==='g_override') return {...n,fields:n.fields.map(f=>['active','gesture'].includes(f.key)?{...f,value:'—'}:f)};
              if(n.id==='g_emoji') return {...n,fields:n.fields.map(f=>['active','emoji'].includes(f.key)?{...f,value:'—'}:f)};
              if(n.id==='priority') return {...n,fields:n.fields.map(f=>f.key==='winner'?{...f,value:'P1 DIMENSION'}:f)};
              if(n.id==='c_flags') return {...n,fields:n.fields.map(f=>f.key==='override'?{...f,value:'—'}:f)};
              return n;
            }));
          },2400);
          timers.current.push(end);
        }
      },step.at);
      timers.current.push(t);
    });
  },[simActive]);

  const toW=useCallback((cx,cy)=>{
    const r=cRef.current?.getBoundingClientRect();
    return r?{x:(cx-r.left-pan.x)/zoom,y:(cy-r.top-pan.y)/zoom}:{x:0,y:0};
  },[pan,zoom]);

  const onDrag=useCallback((e,nid)=>{
    e.stopPropagation();
    const w=toW(e.clientX,e.clientY);
    const n=nodes.find(nn=>nn.id===nid);if(!n)return;
    dRef.current={id:nid,ox:w.x-n.x,oy:w.y-n.y};
    const mv=ev=>{if(!dRef.current)return;const ww=toW(ev.clientX,ev.clientY);
      setNodes(p=>p.map(nn=>nn.id===dRef.current.id?{...nn,x:Math.round((ww.x-dRef.current.ox)/10)*10,y:Math.round((ww.y-dRef.current.oy)/10)*10}:nn));};
    const up=()=>{dRef.current=null;window.removeEventListener('pointermove',mv);window.removeEventListener('pointerup',up);};
    window.addEventListener('pointermove',mv);window.addEventListener('pointerup',up);
  },[toW,nodes]);

  const onPan=useCallback(e=>{
    if(e.target!==cRef.current&&!e.target.closest('svg'))return;
    pRef.current={sx:e.clientX-pan.x,sy:e.clientY-pan.y};
    const mv=ev=>{if(pRef.current)setPan({x:ev.clientX-pRef.current.sx,y:ev.clientY-pRef.current.sy});};
    const up=()=>{pRef.current=null;window.removeEventListener('pointermove',mv);window.removeEventListener('pointerup',up);};
    window.addEventListener('pointermove',mv);window.addEventListener('pointerup',up);
  },[pan]);

  useEffect(()=>{
    const el=cRef.current;
    const h=e=>{e.preventDefault();setZoom(z=>Math.max(0.15,Math.min(3,z-e.deltaY*0.001)));};
    if(el)el.addEventListener('wheel',h,{passive:false});
    return()=>{if(el)el.removeEventListener('wheel',h);};
  },[]);

  useEffect(()=>{return()=>{timers.current.forEach(clearTimeout);};},[]);

  const edges=useMemo(()=>EDGE_DEFS.map(([fid,tid])=>{
    const from=nodes.find(n=>n.id===fid);
    const to=nodes.find(n=>n.id===tid);
    if(!from||!to)return null;
    const x1=from.x+210,y1=from.y+30,x2=to.x,y2=to.y+30;
    const cp=Math.max(35,(x2-x1)*0.4);
    const path=`M${x1},${y1} C${x1+cp},${y1} ${x2-cp},${y2} ${x2},${y2}`;
    const ekey=fid+'→'+tid;
    const hot=litEdges.has(ekey);
    const c=(TYPES[from.type]||TYPES.dimension).accent;
    return (
      <g key={ekey}>
        <path d={path} fill="none" stroke={hot?c+'66':c+'16'} strokeWidth={hot?2:1}
          strokeDasharray={hot?undefined:'4 3'} style={{transition:'stroke 0.4s,stroke-width 0.3s'}}/>
        <circle r={hot?3:1.8} fill={c} opacity={hot?0.8:0.3}>
          <animateMotion dur={hot?'0.7s':'2.5s'} repeatCount="indefinite" path={path}/>
        </circle>
        {hot&&<circle r={2} fill={c} opacity={0.4}>
          <animateMotion dur="1.1s" repeatCount="indefinite" path={path} begin="0.35s"/>
        </circle>}
      </g>
    );
  }),[nodes,litEdges]);

  const selNode=nodes.find(n=>n.id===selId);

  return (
    <div style={{width:'100vw',height:'100vh',background:'#08080f',overflow:'hidden',fontFamily:'monospace',color:'#e0e0f0'}}>

      <div style={{position:'fixed',top:10,left:12,zIndex:50}}>
        <div style={{fontSize:12,fontWeight:700,letterSpacing:'0.5px'}}>◈ LUNA EXPRESSION — TRIAGE + RING ORB</div>
        <div style={{fontSize:8,color:'#555',marginTop:2}}>Dimensions drive rings live · 56→12 gestures · scroll/drag to navigate</div>
        <div style={{display:'flex',gap:5,marginTop:6,flexWrap:'wrap'}}>
          {Object.entries(TYPES).map(([k,v])=>(
            <div key={k} style={{display:'flex',alignItems:'center',gap:2,fontSize:7,color:'#444'}}>
              <div style={{width:5,height:5,borderRadius:2,background:v.accent}}/>{v.label}
            </div>
          ))}
        </div>
        <div onClick={()=>setShowTriage(!showTriage)} style={{
          marginTop:7,fontSize:9,padding:'3px 10px',borderRadius:5,cursor:'pointer',display:'inline-block',
          background:showTriage?'rgba(251,113,133,0.12)':'rgba(255,255,255,0.04)',
          color:showTriage?'#fb7185':'#666',border:`1px solid ${showTriage?'rgba(251,113,133,0.3)':'rgba(255,255,255,0.06)'}`,
        }}>⚡ {showTriage?'HIDE':'VIEW'} TRIAGE</div>
      </div>

      <div style={{position:'fixed',bottom:10,left:12,zIndex:50,display:'flex',gap:4,flexWrap:'wrap',maxWidth:700,alignItems:'center'}}>
        <div style={{fontSize:8,color:'#555',marginRight:2}}>▶</div>
        {Object.entries(SCENARIOS).map(([k,sc])=>(
          <div key={k} onClick={()=>runSim(k)} style={{
            fontSize:8,padding:'3px 8px',borderRadius:5,cursor:simActive?'not-allowed':'pointer',
            background:simActive?'rgba(255,255,255,0.02)':`${sc.color}08`,
            color:simActive?'#333':sc.color,
            border:`1px solid ${simActive?'rgba(255,255,255,0.04)':sc.color+'33'}`,
          }}>{sc.label}</div>
        ))}
      </div>

      {simActive&&(
        <div style={{position:'fixed',bottom:42,left:'50%',transform:'translateX(-50%)',zIndex:50,
          fontSize:10,padding:'4px 12px',borderRadius:14,
          background:'rgba(167,139,250,0.08)',color:'#a78bfa',border:'1px solid rgba(167,139,250,0.2)',
          display:'flex',alignItems:'center',gap:6}}>
          <div style={{width:6,height:6,borderRadius:'50%',background:'#a78bfa',animation:'lp 0.8s infinite'}}/>{simName}
        </div>
      )}

      {/* Ring Orb — real Canvas 2D */}
      <div style={{position:'fixed',top:10,right:showTriage?334:12,zIndex:50,transition:'right 0.3s'}}>
        <div style={{fontSize:8,color:'#444',marginBottom:2,textAlign:'center'}}>RING ORB · dim-driven</div>
        <div style={{borderRadius:10,overflow:'hidden',background:'#06060c',border:'1px solid rgba(255,255,255,0.06)'}}>
          <canvas ref={canvasRef} style={{display:'block'}} />
        </div>
        <div style={{fontSize:7,color:'#333',marginTop:3,textAlign:'center'}}>
          drag dimension sliders to morph
        </div>
      </div>

      <div ref={cRef} onPointerDown={onPan} onClick={()=>{setSelId(null);}}
        style={{width:'100%',height:'100%',position:'relative',cursor:'grab'}}>
        <div style={{transform:`translate(${pan.x}px,${pan.y}px) scale(${zoom})`,transformOrigin:'0 0',position:'absolute',top:0,left:0}}>
          <svg style={{position:'absolute',top:-2000,left:-2000,width:8000,height:5000,pointerEvents:'none'}}>
            <defs><pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="0.5" fill="rgba(255,255,255,0.02)"/></pattern></defs>
            <rect x="-2000" y="-2000" width="8000" height="5000" fill="url(#g)"/>
          </svg>
          <svg style={{position:'absolute',top:0,left:0,width:2200,height:1100,pointerEvents:'none',overflow:'visible'}}>
            {edges}
          </svg>
          {nodes.map(n=>(
            <Node key={n.id} node={n} selected={selId===n.id} lit={litNodes.has(n.id)}
              onSelect={id=>setSelId(id)} onChange={onChange} onDrag={onDrag}/>
          ))}
        </div>
      </div>

      {selId&&selNode&&!showTriage&&(
        <div style={{position:'fixed',right:0,top:0,width:260,height:'100vh',background:'#0c0c16',
          borderLeft:'1px solid rgba(255,255,255,0.06)',zIndex:100,padding:'12px',overflowY:'auto',
          fontFamily:'monospace',boxShadow:'-6px 0 24px rgba(0,0,0,0.5)'}}>
          <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:8}}>
            <span style={{fontSize:14}}>{selNode.icon}</span>
            <span style={{fontSize:11,fontWeight:600,color:(TYPES[selNode.type]||TYPES.dimension).accent}}>{selNode.label}</span>
            <span onClick={()=>setSelId(null)} style={{marginLeft:'auto',cursor:'pointer',color:'#555',fontSize:13}}>✕</span>
          </div>
          <div style={{fontSize:10,color:'#888',lineHeight:1.6,padding:'8px',
            background:'rgba(255,255,255,0.02)',borderRadius:6,border:'1px solid rgba(255,255,255,0.04)',
            whiteSpace:'pre-wrap'}}>{selNode.desc}</div>
        </div>
      )}

      {showTriage&&<TriagePanel onClose={()=>setShowTriage(false)}/>}

      <style>{`
        @keyframes lp{0%,100%{opacity:1}50%{opacity:.3}}
        @keyframes nflash{0%{opacity:.3}100%{opacity:0}}
      `}</style>
    </div>
  );
}
