# HANDOFF: Mimos Project Data Import into KOZMO

## TASK SUMMARY
Populate the existing `mimos` KOZMO project with rich entity data, SCRIBO script documents, and overlay annotations for the "Raccooning at the Moon" 90-second commercial.

## CONTEXT
The `mimos` project was created via the UI but entities are empty stubs (just `type` + `name`). The full data (character details, location descriptions, relationships, script, shot breakdowns) exists — needs to be imported via direct YAML writes + SCRIBO API calls.

## PROJECT ROOT
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/
```

## RECOMMENDED APPROACH: Direct YAML Write (Phase 1) + API (Phase 2)

Phase 1 writes YAML entity files directly to disk (simpler, guaranteed correct).
Phase 2 uses the SCRIBO API to create story containers and documents.

---

## PHASE 1: Entity Import (Overwrite stubs with full YAML)

Write full YAML files directly to:
```
data/kozmo_projects/mimos/entities/characters/willie.yaml
data/kozmo_projects/mimos/entities/characters/staff.yaml
data/kozmo_projects/mimos/entities/characters/patrons.yaml
data/kozmo_projects/mimos/entities/locations/mimos.yaml
data/kozmo_projects/mimos/entities/lore/raccoon_cosmology.yaml
```

### Key insight from `parse_entity()` (entity.py)
Known fields extracted into Entity model: `type`, `name`, `slug`, `status`, `relationships`, `references`, `scenes`, `tags`, `luna_notes`
EVERYTHING ELSE goes into `entity.data` dict. So `physical`, `wardrobe`, `voice`, `arc`, `blocking`, `mood`, `lighting`, `desc`, `camera_suggestion` — all arbitrary keys in `data`.

### Willie (characters/willie.yaml)
```yaml
type: characters
name: Willie
role: The Mascot
color: "#c8ff00"
physical:
  age: Timeless
  build: "Lean, weathered, comfortable in his skin"
  hair: "Long braids, red headband — signature"
  distinguishing: "Holds a drink like it's a prop he's always had. Deadpan eye contact that lingers one beat too long."
wardrobe:
  default: "Period-adjacent, weathered layers. Red headband always. Fits the desert like he grew here."
  counter: "Same. Drink in hand. Neon MIMOS sign behind him."
  walking: "Same. The costume doesn't change — he does."
traits:
  - deadpan
  - committal
  - trustworthy-but-suspicious
arc:
  summary: "Appears → Commits → Walks → Belongs"
  turning_point: SC02
voice:
  speech_pattern: "Deadpan delivery. Treats the absurd as mundane. Direct to camera, zero irony in the performance — the irony is structural."
  verbal_tics:
    - "'Howdy'"
    - "'Totally normal'"
    - "'Nothing to see here'"
blocking:
  intro: "Faces camera at counter. 'Howdy, I'm Willie.'"
  transition: "Turns to his right, walks into the space. Side profile from counter position."
  through_space: "Walks through Mimos interior — past red couch, blue water jugs, shelves."
  close: "Back in frame with group. Belonging but still slightly off."
relationships:
  - entity: mimos
    type: mascot
    detail: "He belongs to this place. Or it belongs to him. Unclear."
  - entity: staff
    type: colleague
    detail: "They all operate at the same frequency of competent absurdity."
  - entity: patrons
    type: host
    detail: "Willie is the reason people feel welcome. And slightly uneasy."
references:
  images: []
  lora: null
scenes: [SC01, SC02, SC03, SC04, SC05, SC06]
tags: [main_cast, on_camera, narrator]
luna_notes: "Human-presenting. NO raccoon features — no ears, tail, or visual hints. The dialogue commitment sells the raccoon-ness. Performance over prosthetics."
```

### Staff (characters/staff.yaml)
```yaml
type: characters
name: Staff
role: The Ensemble
color: "#4ade80"
physical:
  age: Mixed
  build: "Various — real people"
  hair: n/a
  distinguishing: "Nothing visually off. The wrongness is in competence level — everything runs too smoothly for a place with exposed wiring."
wardrobe:
  default: "Casual, desert-appropriate. No uniforms. They just work here."
traits: [friendly, impossibly competent, seamless]
arc:
  summary: "Background → Noticed → Suspicious → Endearing"
  turning_point: SC03
voice:
  speech_pattern: "Non-speaking. Their actions speak."
  verbal_tics: []
relationships:
  - entity: willie
    type: colleague
    detail: Same frequency.
  - entity: mimos
    type: operates
    detail: "They run this place. Impossibly well."
references:
  images: []
  lora: null
scenes: [SC03, SC04, SC05]
tags: [ensemble, background]
luna_notes: "The joke is the contrast: ramshackle space, flawless service. Don't oversell it — let the camera catch it."
```

### Patrons (characters/patrons.yaml)
```yaml
type: characters
name: Patrons
role: The Community
color: "#22d3ee"
physical:
  age: Mixed
  build: "Various — real Bombay Beach energy"
  hair: n/a
  distinguishing: "They look like they belong here. Desert people, artists, wanderers."
wardrobe:
  default: "Whatever people actually wear in Bombay Beach."
traits: [gathered, connected, community, real]
arc:
  summary: "Absent → Gathering → Present → The Point"
  turning_point: SC04
voice:
  speech_pattern: "Background chatter. Laughter. The sound of a place that works."
  verbal_tics: []
relationships:
  - entity: willie
    type: hosted_by
    detail: Willie draws them in.
  - entity: mimos
    type: frequents
    detail: "This is their third place."
references:
  images: []
  lora: null
scenes: [SC03, SC04, SC05, SC06]
tags: [ensemble, community]
luna_notes: "Omega Mart DNA: group shots with extras doing normal things. The normalcy IS the performance."
```

### Mimos (locations/mimos.yaml)
```yaml
type: locations
name: Mimos
mood: "Already strange → Willie just appears"
time: "golden hour → dusk → night"
desc: "Ramshackle desert structure. Weathered wood, exposed wiring, mismatched furniture, red cooler, books scattered, fan, weird signs. MIMOS sign hand-painted. Off-grid, jury-rigged, lived-in. Scrap-built, functional, beautiful in its imperfection. Real Mars culture."
lighting: "Naturalistic desert light. Golden hour does the work. Interior: warm practicals, neon MIMOS sign glow. Dusk: structure warm against cool blue hour."
camera_suggestion: "ARRI Alexa Mini, Panavision C-Series. Wide glass for exterior (24mm), warmer lenses for interior (50mm). Don't oversaturate what's naturally beautiful."
color: "#f59e0b"
