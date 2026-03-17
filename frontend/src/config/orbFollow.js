/**
 * Luna Orb Follow Behavior Configuration
 *
 * Spring physics + fairy float for organic movement.
 * Mutable at runtime via updateOrbPhysics() — sliders write here directly.
 */

export const ORB_FOLLOW_CONFIG = {
  // === Spring Physics ===
  followSpeed: 0,           // How fast orb catches up (0.001-0.05)
  deceleration: 0.999,      // Velocity decay per frame (0.95-0.999)
  velocityThreshold: 0.1,   // Stop calculating when velocity below this

  // === Fairy Float (idle drift) ===
  floatAmplitudeX: 0,       // Pixels of horizontal drift
  floatAmplitudeY: 0,       // Pixels of vertical drift
  floatSpeedX: 0,           // Horizontal oscillation speed (radians per ms)
  floatSpeedY: 0,           // Vertical (slightly different = organic feel)

  // === Positioning ===
  marginFromEdge: 40,       // Pixels from right edge of chat container
  verticalOffset: 0,        // Offset from anchor point (+ = down)
  anchorMode: 'latest',     // 'latest' | 'viewport' | 'scroll'

  // === Constraints ===
  minY: 100,                // Don't float above this (pixels from container top)
  maxYFromBottom: 150,      // Don't float below this (pixels from container bottom)
};

// Slider definitions for the UI panel
export const ORB_PHYSICS_RANGES = {
  followSpeed:    { label: 'Pull Strength',    min: 0.001, max: 0.05,  step: 0.001 },
  deceleration:   { label: 'Friction',         min: 0.95,  max: 0.999, step: 0.001 },
  floatAmplitudeX:{ label: 'Drift X (px)',     min: 0,     max: 20,    step: 0.5   },
  floatAmplitudeY:{ label: 'Drift Y (px)',     min: 0,     max: 20,    step: 0.5   },
  floatSpeedX:    { label: 'Oscillation X',    min: 0.0001,max: 0.003, step: 0.0001},
  floatSpeedY:    { label: 'Oscillation Y',    min: 0.0001,max: 0.003, step: 0.0001},
};

const listeners = new Set();

export function updateOrbPhysics(patch) {
  Object.assign(ORB_FOLLOW_CONFIG, patch);
  listeners.forEach(fn => fn(ORB_FOLLOW_CONFIG));
}

export function onOrbPhysicsChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
