/**
 * Luna Orb Follow Behavior Configuration
 *
 * Spring physics + fairy float for organic movement
 */

export const ORB_FOLLOW_CONFIG = {
  // === Spring Physics ===
  followSpeed: 0.08,        // How fast orb catches up (0.01-0.2, lower = more lag)
  deceleration: 0.92,       // Velocity decay per frame (0.85-0.98, higher = longer glide)
  velocityThreshold: 0.1,   // Stop calculating when velocity below this

  // === Fairy Float (idle drift) ===
  floatAmplitudeX: 8,       // Pixels of horizontal drift
  floatAmplitudeY: 12,      // Pixels of vertical drift
  floatSpeedX: 0.0015,      // Horizontal oscillation speed (radians per ms)
  floatSpeedY: 0.0023,      // Vertical (slightly different = organic feel)

  // === Positioning ===
  marginFromEdge: 40,       // Pixels from right edge of chat container
  verticalOffset: 0,        // Offset from anchor point (+ = down)
  anchorMode: 'latest',     // 'latest' | 'viewport' | 'scroll'

  // === Constraints ===
  minY: 100,                // Don't float above this (pixels from container top)
  maxYFromBottom: 150,      // Don't float below this (pixels from container bottom)
};

/**
 * Tuning Guide:
 *
 * | Want This              | Adjust This                        |
 * |------------------------|-------------------------------------|
 * | More lag behind scroll | Lower followSpeed (try 0.04)       |
 * | Longer glide/coast     | Higher deceleration (try 0.95)     |
 * | Snappier response      | Higher followSpeed (try 0.12)      |
 * | More floaty idle       | Higher floatAmplitude values       |
 * | Slower fairy drift     | Lower floatSpeed values            |
 * | Less organic           | Set both floatSpeed values equal   |
 */
