/**
 * KOZMO Camera System — Static Configuration
 *
 * Camera bodies, lens profiles, film stocks, movements.
 * These are the deterministic cinema controls that differentiate KOZMO.
 *
 * When generating via Eden, these settings are translated to prompt text.
 * When/if Higgsfield opens an API, they map to native camera controls.
 *
 * See: ARCHITECTURE_KOZMO.md § 7 (Camera System)
 */

export const CAMERA_BODIES = [
  {
    id: 'arri_alexa35',
    name: 'ARRI Alexa 35',
    sensor: 'S35',
    colorScience: 'ARRI LogC4',
    badge: 'CINEMA',
  },
  {
    id: 'red_v_raptor',
    name: 'RED V-Raptor',
    sensor: 'VV',
    colorScience: 'REDWideGamut',
    badge: 'CINEMA',
  },
  {
    id: 'sony_venice2',
    name: 'Sony Venice 2',
    sensor: 'FF',
    colorScience: 'S-Gamut3',
    badge: 'CINEMA',
  },
  {
    id: 'bmpcc_6k',
    name: 'Blackmagic 6K',
    sensor: 'S35',
    colorScience: 'Blackmagic Film',
    badge: 'INDIE',
  },
  {
    id: '16mm_bolex',
    name: '16mm Bolex',
    sensor: 'S16',
    colorScience: 'Kodak 7219',
    badge: 'FILM',
  },
  {
    id: 'vhs_camcorder',
    name: 'VHS Camcorder',
    sensor: '1/3"',
    colorScience: 'Composite',
    badge: 'LO-FI',
  },
];

export const LENS_PROFILES = [
  {
    id: 'cooke_s7i',
    name: 'Cooke S7/i',
    type: 'spherical',
    character: 'Warm, organic flares',
    focalRange: [18, 135],
  },
  {
    id: 'panavision_c',
    name: 'Panavision C-Series',
    type: 'anamorphic',
    character: 'Classic oval bokeh, blue streaks',
    focalRange: [35, 100],
  },
  {
    id: 'zeiss_supreme',
    name: 'Zeiss Supreme',
    type: 'spherical',
    character: 'Clean, clinical precision',
    focalRange: [15, 200],
  },
  {
    id: 'atlas_mercury',
    name: 'Atlas Mercury',
    type: 'anamorphic',
    character: 'Modern anamorphic, subtle flares',
    focalRange: [28, 100],
  },
  {
    id: 'canon_k35',
    name: 'Canon K35',
    type: 'spherical',
    character: '70s softness, vintage glow',
    focalRange: [18, 85],
  },
  {
    id: 'helios_44',
    name: 'Helios 44-2',
    type: 'spherical',
    character: 'Swirly bokeh, Soviet glass',
    focalRange: [58, 58], // fixed focal
  },
];

export const CAMERA_MOVEMENTS = [
  { id: 'static', name: 'Static' },
  { id: 'dolly_in', name: 'Dolly In' },
  { id: 'dolly_out', name: 'Dolly Out' },
  { id: 'pan_left', name: 'Pan Left' },
  { id: 'pan_right', name: 'Pan Right' },
  { id: 'tilt_up', name: 'Tilt Up' },
  { id: 'tilt_down', name: 'Tilt Down' },
  { id: 'crane_up', name: 'Crane Up' },
  { id: 'crane_down', name: 'Crane Down' },
  { id: 'orbit_cw', name: 'Orbit CW' },
  { id: 'orbit_ccw', name: 'Orbit CCW' },
  { id: 'handheld', name: 'Handheld' },
  { id: 'fpv', name: 'FPV Drone' },
  { id: 'steadicam', name: 'Steadicam' },
];
// Max 3 combined per shot

export const FILM_STOCKS = [
  {
    id: 'kodak_5219',
    name: 'Kodak 5219 (500T)',
    character: 'Warm tungsten, cinema standard',
  },
  {
    id: 'kodak_5207',
    name: 'Kodak 5207 (250D)',
    character: 'Daylight, neutral palette',
  },
  {
    id: 'fuji_eterna',
    name: 'Fuji Eterna Vivid',
    character: 'Rich greens, cooler shadows',
  },
  {
    id: 'cinestill_800',
    name: 'CineStill 800T',
    character: 'Halation halos, neon warmth',
  },
  {
    id: 'ilford_hp5',
    name: 'Ilford HP5+ (B&W)',
    character: 'Punchy contrast, classic grain',
  },
];

/**
 * Build prompt suffix from camera configuration.
 * Used by useEdenAdapter when generating images.
 */
export function buildCameraPrompt(config) {
  const parts = [];

  if (config.body) {
    const cam = CAMERA_BODIES.find(c => c.id === config.body);
    if (cam) parts.push(`Shot on ${cam.name}`);
  }

  if (config.lens) {
    const lens = LENS_PROFILES.find(l => l.id === config.lens);
    if (lens) parts.push(`${lens.name} ${lens.type} lens`);
  }

  if (config.focalMm) parts.push(`${config.focalMm}mm`);
  if (config.aperture) parts.push(`f/${config.aperture}`);

  if (config.filmStock && config.filmStock !== 'none') {
    const stock = FILM_STOCKS.find(s => s.id === config.filmStock);
    if (stock) parts.push(`${stock.name} film stock`);
  }

  if (config.movements?.length) {
    const names = config.movements
      .map(id => CAMERA_MOVEMENTS.find(m => m.id === id)?.name)
      .filter(Boolean);
    if (names.length) parts.push(`camera movement: ${names.join(', ')}`);
  }

  return parts.join('. ');
}
