/**
 * Shared formatting utilities for KOZMO components.
 */

/** Format seconds as M:SS timecode */
export const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

/** Voice entity color palette — matches Eclissi/prototype */
export const VOICE_COLORS = {
  bella: '#c8ff00',
  george: '#818cf8',
  gandala: '#22c55e',
  lily: '#f472b6',
  liam: '#fb923c',
  mohammed: '#38bdf8',
  lucy: '#a78bfa',
  chebel: '#fbbf24',
  maria_clara: '#f97316',
  miyomi: '#67e8f9',
  maggi: '#e879f9',
};
