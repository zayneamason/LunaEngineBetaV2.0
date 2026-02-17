# KOZMO Phase 2/3 Architecture Diagram

## Component Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         KOZMO SCRIBO EDITOR                          │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   │
          ┌────────────────────────┴────────────────────────┐
          │                                                  │
          ▼                                                  ▼
┌─────────────────────┐                          ┌──────────────────────┐
│  FrontmatterEditor  │                          │    SceneEditor       │
│                     │                          │                      │
│  • characters_      │                          │  • Textarea w/ ref   │
│    present          │                          │  • Cursor tracking   │
│  • location         │                          │  • onChange handler  │
│  • time             │                          │                      │
│  • status           │                          │  ┌─────────────────┐ │
│  • tags             │                          │  │ PHASE 2:        │ │
│                     │                          │  │ EntityAutocomplete│ │
│  ┌────────────────┐│                          │  └─────────────────┘ │
│  │ PHASE 3:       ││                          │                      │
│  │ Validation     ││                          │  When user types @:  │
│  │ Feedback       ││                          │  1. Detect @ context │
│  └────────────────┘│                          │  2. Show dropdown    │
│                     │                          │  3. Filter entities  │
│  On draft change:   │                          │  4. Insert selected  │
│  1. validateFrontmatter                       │                      │
│  2. Show errors/warnings/suggestions          │                      │
│  3. Render action buttons                     │                      │
└─────────────────────┘                          └──────────────────────┘
          │                                                  │
          │                                                  │
          ▼                                                  ▼
┌─────────────────────┐                          ┌──────────────────────┐
│ frontmatterValidator│                          │ entityMentionDetector│
│                     │                          │                      │
│ validateFrontmatter()│                         │ detectEntityMentions()│
│ ├─ checkCharacters() │                         │ injectEntityLinks()  │
│ ├─ checkLocation()   │                         │ checkAtMentionContext()│
│ ├─ checkProps()      │                         │ filterEntitiesForAutocomplete()│
│ ├─ checkStatus()     │                         │                      │
│ ├─ warnDeadChars()   │                         │ Detects:             │
│ ├─ warnDestroyedProps()│                       │ • @EntityName        │
│ └─ suggestRelationships()│                     │ • Implicit mentions  │
│                     │                          │ • Orphaned entities  │
│ Returns:            │                          │                      │
│ {                   │                          │ Returns:             │
│   errors: [],       │                          │ [{                   │
│   warnings: [],     │                          │   entitySlug,        │
│   suggestions: []   │                          │   entityName,        │
│ }                   │                          │   positions,         │
└─────────────────────┘                          │   isOrphaned         │
                                                  │ }]                   │
                                                  └──────────────────────┘
          │                                                  │
          │                                                  │
          ▼                                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         KOZMO PROVIDER CONTEXT                       │
│                                                                       │
│  State:                                                               │
│  • entities: Array<Entity>                                           │
│  • selectedProject: Project                                          │
│                                                                       │
│  Methods:                                                             │
│  • createEntity(type, name, data)                                    │
│  • updateEntity(slug, updates)                                       │
│  • deleteEntity(slug)                                                │
│  • saveDocument(slug, content)                                       │
│  • navigateToCodex(entitySlug)                                       │
└─────────────────────────────────────────────────────────────────────┘
          │
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND API LAYER                            │
│                                                                       │
│  Routes:                                                              │
│  • GET    /kozmo/projects/{slug}/entities                            │
│  • POST   /kozmo/projects/{slug}/entities                            │
│  • PUT    /kozmo/projects/{slug}/entities/{entity_slug}              │
│  • DELETE /kozmo/projects/{slug}/entities/{entity_slug}              │
│  • GET    /kozmo/projects/{slug}/story/documents                     │
│  • POST   /kozmo/projects/{slug}/story/documents                     │
│                                                                       │
│  Services:                                                            │
│  • scribo_parser.py:                                                 │
│    - parse_scribo(text) → (frontmatter, body)                        │
│    - serialize_scribo(frontmatter, body) → text                      │
│    - extract_entity_references(body, entities) → references          │
│    - extract_fountain_elements(body) → elements                      │
│                                                                       │
│  • fountain.py: Fountain → JSON                                      │
│  • graph.py: Entity relationship graph                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Examples

### Phase 2: @Mention Autocomplete

```
USER ACTION: Types "@S" in scene editor
                │
                ▼
     SceneEditor.handleChange()
                │
                ├─ Updates draftBody
                ├─ Updates cursorPosition
                └─ setIsDirty(true)
                │
                ▼
     EntityAutocomplete component re-renders
                │
                ▼
     checkAtMentionContext(draftBody, cursorPosition)
                │
                ├─ Detects "@" at position
                ├─ Extracts query: "S"
                └─ Returns { shouldShowAutocomplete: true, query: "S" }
                │
                ▼
     filterEntitiesForAutocomplete(entities, "S", 5)
                │
                ├─ Filters: "Sam Vimes" ✅
                ├─ Filters: "Swamp Dragon" ✅
                └─ Returns filtered list
                │
                ▼
     Dropdown renders with 2 suggestions
                │
                ▼
     USER ACTION: Presses Enter or clicks "Sam Vimes"
                │
                ▼
     handleAutocompleteSelect(entity)
                │
                ├─ Finds "@S" in text
                ├─ Replaces with "@Sam Vimes"
                ├─ Updates cursor position
                └─ Closes dropdown
                │
                ▼
     RESULT: "@Sam Vimes" appears in editor
```

---

### Phase 2: Entity Navigation

```
USER ACTION: Views rendered scene body
                │
                ▼
     renderLine() for each line in body
                │
                ▼
     formatInlineText(line, { enableEntityLinks: true })
                │
                ▼
     detectEntityMentions(line, entities)
                │
                ├─ Finds "@Sam Vimes" at position 15
                ├─ Matches entity: { slug: 'sam-vimes', type: 'character', color: '#4ade80' }
                └─ Returns mention metadata
                │
                ▼
     injectEntityLinks(line, mentions)
                │
                └─ Wraps in <span class="entity-ref" data-entity="sam-vimes">
                │
                ▼
     RESULT: "@Sam Vimes" rendered with color glow
                │
                ▼
     USER ACTION: Clicks "@Sam Vimes"
                │
                ▼
     handleEntityClick(event)
                │
                ├─ Reads data-entity="sam-vimes"
                ├─ Calls navigateToCodex('sam-vimes')
                └─ Switches to Codex tab
                │
                ▼
     RESULT: Codex opens, scrolls to Sam Vimes entity card
```

---

### Phase 3: Frontmatter Validation

```
USER ACTION: Edits frontmatter (adds dead character to scene)
                │
                ▼
     FrontmatterEditor.handleChange(updatedFrontmatter)
                │
                ├─ Updates draftFrontmatter
                └─ setIsDirty(true)
                │
                ▼
     useEffect triggered on draftFrontmatter change
                │
                ▼
     validateFrontmatter(draftFrontmatter, entities, sceneContext)
                │
                ├─ Checks characters_present: ['sam-vimes', 'dead-person']
                ├─ Finds entity: { slug: 'dead-person', status: 'dead', last_appearance: 5 }
                ├─ Scene number: 10 (after death scene)
                └─ Returns warning: "Dead Person died in scene 5. Using in scene 10?"
                │
                ▼
     setValidation({ errors: [], warnings: [warning], suggestions: [] })
                │
                ▼
     ValidationFeedback component re-renders
                │
                ├─ Shows yellow warning banner
                ├─ Icon: ⚠️
                ├─ Message: "Dead Person died in scene 5..."
                └─ Button: "View Entity"
                │
                ▼
     USER ACTION: Clicks "View Entity" button
                │
                ▼
     handleValidationAction({ type: 'view_entity', slug: 'dead-person' })
                │
                ├─ Calls navigateToCodex('dead-person')
                └─ Switches to Codex tab
                │
                ▼
     RESULT: User reviews Dead Person entity, sees death in scene 5
                │
                ▼
     USER ACTION: Returns to Scribo, removes dead character from frontmatter
                │
                ▼
     Validation runs again
                │
                └─ Returns { errors: [], warnings: [], suggestions: [] }
                │
                ▼
     RESULT: ValidationFeedback disappears, save button enabled
```

---

## Validation Action Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      VALIDATION ACTION TYPES                         │
└─────────────────────────────────────────────────────────────────────┘

1. create_entity
   User clicks "Create" button
        │
        ▼
   handleValidationAction({ type: 'create_entity', name: 'Unknown Character' })
        │
        ▼
   Open entity creation modal with pre-filled name
        │
        ▼
   createEntity('character', 'Unknown Character', {})
        │
        ▼
   POST /kozmo/projects/{slug}/entities
        │
        ▼
   Entity created, frontmatter re-validated
        │
        ▼
   Error disappears

2. view_entity
   User clicks "View" button
        │
        ▼
   handleValidationAction({ type: 'view_entity', slug: 'dead-person' })
        │
        ▼
   navigateToCodex('dead-person')
        │
        ▼
   Switch to Codex tab, scroll to entity

3. add_props
   User clicks "Add Props" button
        │
        ▼
   handleValidationAction({ type: 'add_props', props: ['throne', 'royal-banner'] })
        │
        ▼
   setDraftFrontmatter({ ...draft, props: [...draft.props, ...action.props] })
        │
        ▼
   Frontmatter updated, suggestion disappears

4. set_time
   User clicks "Apply" button
        │
        ▼
   handleValidationAction({ type: 'set_time', time: '10:30 AM' })
        │
        ▼
   setDraftFrontmatter({ ...draft, time: action.time })
        │
        ▼
   Time updated, suggestion disappears

5. fix_status
   User clicks "Fix" button
        │
        ▼
   handleValidationAction({ type: 'fix_status', status: 'draft' })
        │
        ▼
   setDraftFrontmatter({ ...draft, status: action.status })
        │
        ▼
   Status corrected, error disappears

6. define_relationship
   User clicks "Define" button
        │
        ▼
   handleValidationAction({
     type: 'define_relationship',
     from: 'sam-vimes',
     to: 'lady-sybil',
     suggested: 'spouse'
   })
        │
        ▼
   Open relationship editor modal
        │
        ▼
   User defines relationship: "Sam Vimes → spouse → Lady Sybil"
        │
        ▼
   updateEntity('sam-vimes', { relationships: [...] })
        │
        ▼
   POST /kozmo/projects/{slug}/entities/sam-vimes
        │
        ▼
   Relationship saved, suggestion disappears
```

---

## Backend Entity Reference Extraction

```
┌─────────────────────────────────────────────────────────────────────┐
│                  scribo_parser.extract_entity_references()           │
└─────────────────────────────────────────────────────────────────────┘

INPUT:
  body = "@Sam Vimes walked into The Watch House. Sam Vimes sat down."
  entities = [
    { slug: 'sam-vimes', name: 'Sam Vimes', type: 'character', color: '#4ade80' },
    { slug: 'the-watch-house', name: 'The Watch House', type: 'location', color: '#60a5fa' }
  ]

PROCESSING:
  1. Explicit @mention detection:
     - Regex: r'@([A-Z][A-Za-z\s]+)'
     - Matches: "@Sam Vimes" at position 0

  2. Implicit mention detection:
     - Regex: r'\b' + re.escape('Sam Vimes') + r'\b'
     - Matches: "Sam Vimes" at position 46
     - Regex: r'\b' + re.escape('The Watch House') + r'\b'
     - Matches: "The Watch House" at position 24

  3. Position aggregation:
     - sam-vimes: [0, 46] (1 explicit, 1 implicit)
     - the-watch-house: [24] (1 implicit)

OUTPUT:
  [
    {
      entity_slug: 'sam-vimes',
      entity_name: 'Sam Vimes',
      entity_type: 'character',
      mention_type: 'explicit',  // First mention was @mention
      positions: [0, 46]
    },
    {
      entity_slug: 'the-watch-house',
      entity_name: 'The Watch House',
      entity_type: 'location',
      mention_type: 'implicit',
      positions: [24]
    }
  ]
```

---

## Error Handling

### Orphaned @Mentions

```
USER INPUT: "@UnknownCharacter walked in."

detectEntityMentions() checks entities list
   │
   ├─ "@UnknownCharacter" not found in entity map
   │
   └─ Returns: {
       text: 'UnknownCharacter',
       isOrphaned: true,
       position: 1
     }
   │
   ▼
formatInlineText() renders with red wavy underline
   │
   └─ <span style="text-decoration: wavy underline; color: #ef4444;">
        @UnknownCharacter
      </span>
   │
   ▼
Validation runs
   │
   └─ Returns error: "Entity not found: UnknownCharacter"
       Action: { type: 'create_entity', name: 'UnknownCharacter' }
   │
   ▼
USER ACTION: Clicks "Create" button
   │
   ▼
Opens entity creation modal with name pre-filled
```

---

## Performance Considerations

### Validation Debouncing (TODO)

```javascript
// Current: Validates on every keystroke
useEffect(() => {
  if (!isEditing) return;
  const results = validateFrontmatter(draftFrontmatter, entities, sceneContext);
  setValidation(results);
}, [draftFrontmatter, entities, sceneContext]);

// Optimized: Debounce validation by 300ms
useEffect(() => {
  if (!isEditing) return;

  const timer = setTimeout(() => {
    const results = validateFrontmatter(draftFrontmatter, entities, sceneContext);
    setValidation(results);
  }, 300);

  return () => clearTimeout(timer);
}, [draftFrontmatter, entities, sceneContext]);
```

### Entity Map Caching (TODO)

```javascript
// Current: Rebuilds entity map on every mention detection
const entity_map = {e['name'].lower(): e for e in entities}

// Optimized: Cache entity map, invalidate on entities change
const entityMapRef = useRef(null);

useMemo(() => {
  entityMapRef.current = entities.reduce((map, entity) => {
    map[entity.name.toLowerCase()] = entity;
    return map;
  }, {});
}, [entities]);
```

---

## Testing Checklist

### Phase 2 Manual Tests

- [ ] Type `@` in editor → autocomplete dropdown appears
- [ ] Type `@s` → filters to "Sam Vimes", "Swamp Dragon"
- [ ] Press Arrow Down → highlights next suggestion
- [ ] Press Enter → inserts entity name
- [ ] Click entity in dropdown → inserts entity name
- [ ] Type `@UnknownEntity` → red wavy underline appears
- [ ] Click highlighted `@Sam Vimes` → navigates to Codex
- [ ] Location in frontmatter → auto-highlights in body text

### Phase 3 Manual Tests

- [ ] Add non-existent character → error blocks save
- [ ] Add dead character to later scene → warning allows save
- [ ] Click "View Entity" button → navigates to Codex
- [ ] Click "Create Entity" button → opens creation modal
- [ ] Add location with scene template → suggestion for props
- [ ] Click "Add Props" button → adds props to frontmatter
- [ ] Invalid status value → error blocks save
- [ ] Click "Fix Status" button → corrects status value

---

## Future Enhancements

1. **Smart @Mention Suggestions**
   - Recently used entities appear first
   - Entities from current location
   - Entities from current chapter/act

2. **Inline Validation Preview**
   - Live validation as user types
   - Inline error messages next to fields
   - Color-coded field borders (red/yellow/blue)

3. **Relationship Suggestions**
   - Analyze dialogue patterns to suggest relationships
   - Detect repeated co-occurrence in scenes
   - Suggest relationship types based on interaction context

4. **Location Scene Templates**
   - Visual template editor
   - Props library per location
   - Lighting/camera preset suggestions

5. **Backend Validation Endpoint** (optional)
   - `POST /kozmo/projects/{slug}/continuity/validate`
   - Server-side validation for complex rules
   - Cross-scene continuity checks
   - Timeline validation

---

## File Reference

```
Tools/KOZMO-Prototype-V1/
├── src/
│   ├── utils/
│   │   ├── entityMentionDetector.js   ← PHASE 2: Detection logic
│   │   └── frontmatterValidator.js    ← PHASE 3: Validation logic
│   └── scribo/
│       ├── EntityAutocomplete.jsx     ← PHASE 2: Autocomplete UI
│       ├── ValidationFeedback.jsx     ← PHASE 3: Validation UI
│       └── KozmoScribo.jsx            ← INTEGRATION: Wired components
└── tests/
    └── phase2_phase3_integration.test.js  ← 20 comprehensive tests

src/luna/services/kozmo/
└── scribo_parser.py                   ← BACKEND: Reference extraction
```

---

**Status**: ✅ Architecture complete, implementation ready for testing
