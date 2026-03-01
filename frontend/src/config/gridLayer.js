/**
 * Grid Layer Configuration
 *
 * Tuning constants for the viewport spatial index grid.
 * The grid subdivides hierarchically: L0 (10×6) → L1 (20×12) → L2 (40×24) → L3 (80×48)
 */

export const GRID_LAYER_CONFIG = {
  baseCols: 10,
  baseRows: 6,
  maxLevel: 3,

  // Zone thresholds (normalized 0-1 viewport coordinates)
  zones: {
    knowledge: { maxNx: 0.33 },
    meta: { minNx: 0.66 },
    input: { minNy: 0.92 },
    nav: { maxNy: 0.05 },
    // 'conversation' is the default/center zone
  },

  // Debug overlay styling
  debug: {
    gridLineColor: 'rgba(180, 170, 210, 0.12)',
    gridLineWidth: 0.5,
    dotRadius: 1,
    dotColor: 'rgba(160, 152, 184, 0.18)',
    childDotRadius: 2,
    childDotColor: 'rgba(109, 69, 200, 0.25)',
    hitDotRadius: 4,
    hitColor: '#6d45c8',
    crosshairDash: [3, 3],
    labelFont: '9px "JetBrains Mono", monospace',
    zoneColor: '#059669',
    childColor: '#d97706',
    coordColor: '#0891b2',
  },
};
