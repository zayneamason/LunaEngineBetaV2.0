/**
 * Orb Canvas Renderer Configuration
 *
 * Tuning constants for the Canvas 2D ring-based orb renderer.
 * Ported from grid_layer_prototype.html.
 */

export const ORB_CANVAS_CONFIG = {
  // === Ring Model ===
  baseRadius: 44,
  initialRingCount: 5,

  // === Fairy Float (Lissajous drift) ===
  driftSpeed: 0.0006,
  driftRadiusX: 12,
  driftRadiusY: 8,
  easeFactor: 0.04,          // Position lerp toward drift target

  // === Breathing ===
  breatheSpeed: 0.015,
  breatheAmplitude: 2.5,
  breatheSecondaryAmplitude: 1.2,
  ringPhaseOffset: 0.7,      // Phase stagger between rings

  // === Glow ===
  glowAmbientMax: 0.08,      // Big soft halo
  glowCoronaMax: 0.12,       // Medium corona
  glowPulseSpeed: 0.8,       // Sine speed for glow oscillation

  // === Core Dot ===
  coreMinRadius: 3,
  coreMaxRadius: 5,
  corePulseSpeed: 1.2,

  // === Anchor Tether ===
  anchorTetherMaxOpacity: 0.08,
  anchorTetherDistScale: 0.003,

  // === Colors (HSL defaults) ===
  defaultHue: 262,
  defaultSaturation: 60,
  defaultLightness: 45,

  // === Drag ===
  dragHitPadding: 10,         // Extra px beyond baseRadius for click detection
};

/**
 * Tuning Guide:
 *
 * | Want This                | Adjust This                          |
 * |--------------------------|---------------------------------------|
 * | Slower fairy drift       | Lower driftSpeed (try 0.0003)        |
 * | Wider float range        | Higher driftRadiusX/Y                |
 * | Faster breathing         | Higher breatheSpeed (try 0.025)      |
 * | More ring stagger        | Higher ringPhaseOffset (try 1.2)     |
 * | Brighter glow            | Higher glowAmbientMax/CoronaMax      |
 * | Snappier position easing | Higher easeFactor (try 0.08)         |
 * | Larger core dot          | Higher coreMaxRadius                 |
 */
