/**
 * KOZMO Phase 2/3 Integration Tests
 *
 * Tests for:
 * - Phase 2: Entity reference detection, autocomplete, navigation
 * - Phase 3: Frontmatter validation, warnings, suggestions
 */

import { detectEntityMentions, injectEntityLinks, checkAtMentionContext, filterEntitiesForAutocomplete } from '../src/utils/entityMentionDetector';
import { validateFrontmatter } from '../src/utils/frontmatterValidator';
import { extract_entity_references } from '../../../src/luna/services/kozmo/scribo_parser.py'; // Backend function

// =============================================================================
// Test Data
// =============================================================================

const mockEntities = [
  { slug: 'sam-vimes', name: 'Sam Vimes', type: 'character', color: '#4ade80' },
  { slug: 'the-watch-house', name: 'The Watch House', type: 'location', color: '#60a5fa' },
  { slug: 'swamp-dragon', name: 'Swamp Dragon', type: 'prop', color: '#f59e0b' },
  { slug: 'lady-sybil', name: 'Lady Sybil', type: 'character', color: '#ec4899' },
  { slug: 'carrot-ironfoundersson', name: 'Carrot Ironfoundersson', type: 'character', color: '#8b5cf6', status: 'alive' },
];

// =============================================================================
// Phase 2 Tests: Entity Reference Detection
// =============================================================================

describe('Phase 2: Entity Reference Detection', () => {
  test('detects explicit @mentions', () => {
    const text = '@Sam Vimes entered @The Watch House carrying a @Swamp Dragon.';
    const mentions = detectEntityMentions(text, mockEntities);

    expect(mentions.length).toBe(3);
    expect(mentions.find(m => m.entitySlug === 'sam-vimes')).toBeTruthy();
    expect(mentions.find(m => m.entitySlug === 'the-watch-house')).toBeTruthy();
    expect(mentions.find(m => m.entitySlug === 'swamp-dragon')).toBeTruthy();
  });

  test('detects implicit entity mentions', () => {
    const text = 'Sam Vimes walked into The Watch House.';
    const mentions = detectEntityMentions(text, mockEntities);

    expect(mentions.length).toBe(2);
    expect(mentions.find(m => m.entitySlug === 'sam-vimes')).toBeTruthy();
    expect(mentions.find(m => m.entitySlug === 'the-watch-house')).toBeTruthy();
  });

  test('does not detect partial matches', () => {
    const text = 'Samuel is not Sam Vimes.';
    const mentions = detectEntityMentions(text, mockEntities);

    // Should only detect "Sam Vimes", not "Samuel"
    expect(mentions.length).toBe(1);
    expect(mentions[0].entitySlug).toBe('sam-vimes');
  });

  test('detects orphaned @mentions', () => {
    const text = '@Sam Vimes met @UnknownCharacter at the tavern.';
    const mentions = detectEntityMentions(text, mockEntities);

    // Should detect Sam Vimes but flag UnknownCharacter as orphaned
    expect(mentions.find(m => m.entitySlug === 'sam-vimes')).toBeTruthy();

    const orphans = mentions.filter(m => m.isOrphaned);
    expect(orphans.length).toBe(1);
    expect(orphans[0].text).toBe('UnknownCharacter');
  });
});

// =============================================================================
// Phase 2 Tests: Autocomplete
// =============================================================================

describe('Phase 2: Autocomplete', () => {
  test('detects @ trigger for autocomplete', () => {
    const text = 'Hello @S';
    const cursorPos = text.length;

    const context = checkAtMentionContext(text, cursorPos);

    expect(context.shouldShowAutocomplete).toBe(true);
    expect(context.query).toBe('S');
    expect(context.mentionStart).toBe(6);
  });

  test('filters entities by query', () => {
    const filtered = filterEntitiesForAutocomplete(mockEntities, 'sam', 5);

    expect(filtered.length).toBe(1);
    expect(filtered[0].slug).toBe('sam-vimes');
  });

  test('filters entities by type', () => {
    const filtered = filterEntitiesForAutocomplete(mockEntities, 'watch', 5);

    expect(filtered.length).toBe(1);
    expect(filtered[0].slug).toBe('the-watch-house');
    expect(filtered[0].type).toBe('location');
  });

  test('does not show autocomplete in middle of word', () => {
    const text = 'email@example.com';
    const cursorPos = text.length;

    const context = checkAtMentionContext(text, cursorPos);

    expect(context.shouldShowAutocomplete).toBe(false);
  });
});

// =============================================================================
// Phase 2 Tests: Entity Navigation
// =============================================================================

describe('Phase 2: Entity Navigation', () => {
  test('injects clickable entity links', () => {
    const text = '@Sam Vimes entered the room.';
    const mentions = detectEntityMentions(text, mockEntities);
    const linked = injectEntityLinks(text, mentions);

    expect(linked).toContain('data-entity="sam-vimes"');
    expect(linked).toContain('data-entity-type="character"');
    expect(linked).toContain('class="entity-ref"');
  });

  test('highlights location mentions from frontmatter', () => {
    const text = 'The Watch House was quiet tonight.';
    const mentions = detectEntityMentions(text, mockEntities, { frontmatterLocation: 'the-watch-house' });

    expect(mentions.find(m => m.entitySlug === 'the-watch-house' && m.isHighlighted)).toBeTruthy();
  });
});

// =============================================================================
// Phase 3 Tests: Frontmatter Validation - Errors
// =============================================================================

describe('Phase 3: Frontmatter Validation - Errors', () => {
  test('blocks save for non-existent character', () => {
    const frontmatter = {
      type: 'scene',
      characters_present: ['sam-vimes', 'unknown-character'],
      location: 'the-watch-house',
      status: 'draft',
    };

    const validation = validateFrontmatter(frontmatter, mockEntities);

    expect(validation.errors.length).toBeGreaterThan(0);
    expect(validation.errors[0].field).toBe('characters_present');
    expect(validation.errors[0].message).toContain('unknown-character');
  });

  test('blocks save for invalid status', () => {
    const frontmatter = {
      type: 'scene',
      characters_present: ['sam-vimes'],
      location: 'the-watch-house',
      status: 'invalid-status',
    };

    const validation = validateFrontmatter(frontmatter, mockEntities);

    expect(validation.errors.length).toBeGreaterThan(0);
    expect(validation.errors[0].field).toBe('status');
  });

  test('blocks save for non-existent location', () => {
    const frontmatter = {
      type: 'scene',
      characters_present: ['sam-vimes'],
      location: 'unknown-location',
      status: 'draft',
    };

    const validation = validateFrontmatter(frontmatter, mockEntities);

    expect(validation.errors.length).toBeGreaterThan(0);
    expect(validation.errors[0].field).toBe('location');
  });
});

// =============================================================================
// Phase 3 Tests: Frontmatter Validation - Warnings
// =============================================================================

describe('Phase 3: Frontmatter Validation - Warnings', () => {
  test('warns about dead character in later scene', () => {
    const deadCharacter = {
      slug: 'dead-person',
      name: 'Dead Person',
      type: 'character',
      status: 'dead',
      last_appearance: 5,
    };

    const frontmatter = {
      type: 'scene',
      characters_present: ['dead-person'],
      location: 'the-watch-house',
      status: 'draft',
    };

    const sceneContext = { sceneNumber: 10 };

    const validation = validateFrontmatter(
      frontmatter,
      [...mockEntities, deadCharacter],
      sceneContext
    );

    expect(validation.warnings.length).toBeGreaterThan(0);
    expect(validation.warnings[0].field).toBe('characters_present');
    expect(validation.warnings[0].message).toContain('dead');
  });

  test('warns about destroyed prop in later scene', () => {
    const destroyedProp = {
      slug: 'destroyed-sword',
      name: 'Destroyed Sword',
      type: 'prop',
      status: 'destroyed',
      last_appearance: 3,
    };

    const frontmatter = {
      type: 'scene',
      characters_present: [],
      location: 'the-watch-house',
      props: ['destroyed-sword'],
      status: 'draft',
    };

    const sceneContext = { sceneNumber: 8 };

    const validation = validateFrontmatter(
      frontmatter,
      [...mockEntities, destroyedProp],
      sceneContext
    );

    expect(validation.warnings.length).toBeGreaterThan(0);
    expect(validation.warnings[0].message).toContain('destroyed');
  });
});

// =============================================================================
// Phase 3 Tests: Frontmatter Validation - Suggestions
// =============================================================================

describe('Phase 3: Frontmatter Validation - Suggestions', () => {
  test('suggests defining relationship for characters with no connection', () => {
    const frontmatter = {
      type: 'scene',
      characters_present: ['sam-vimes', 'lady-sybil'],
      location: 'the-watch-house',
      status: 'draft',
    };

    // Assume no relationship exists between Sam and Sybil
    const validation = validateFrontmatter(frontmatter, mockEntities);

    const relationshipSuggestion = validation.suggestions.find(
      s => s.action?.type === 'define_relationship'
    );

    expect(relationshipSuggestion).toBeTruthy();
  });

  test('suggests adding props from location scene template', () => {
    const locationWithTemplate = {
      slug: 'throne-room',
      name: 'Throne Room',
      type: 'location',
      scene_template: {
        props_always_present: ['throne', 'royal-banner'],
        lighting: 'dramatic-overhead',
        camera_suggestion: 'wide-establishing',
      },
    };

    const frontmatter = {
      type: 'scene',
      characters_present: ['sam-vimes'],
      location: 'throne-room',
      props: [],
      status: 'draft',
    };

    const validation = validateFrontmatter(
      frontmatter,
      [...mockEntities, locationWithTemplate]
    );

    const propsSuggestion = validation.suggestions.find(
      s => s.action?.type === 'add_props'
    );

    expect(propsSuggestion).toBeTruthy();
    expect(propsSuggestion.action.props).toContain('throne');
  });
});

// =============================================================================
// Backend Integration Tests
// =============================================================================

describe('Backend: Entity Reference Detection', () => {
  test('extract_entity_references finds @mentions', () => {
    const body = '@Sam Vimes walked into @The Watch House.';

    const references = extract_entity_references(body, mockEntities);

    expect(references.length).toBe(2);
    expect(references.find(r => r.entity_slug === 'sam-vimes')).toBeTruthy();
    expect(references.find(r => r.entity_slug === 'the-watch-house')).toBeTruthy();
  });

  test('extract_entity_references finds implicit mentions', () => {
    const body = 'Sam Vimes entered The Watch House.';

    const references = extract_entity_references(body, mockEntities);

    expect(references.length).toBe(2);
    expect(references.every(r => r.mention_type === 'implicit')).toBe(true);
  });

  test('extract_entity_references tracks positions', () => {
    const body = '@Sam Vimes met Sam Vimes again.';

    const references = extract_entity_references(body, mockEntities);

    const samRef = references.find(r => r.entity_slug === 'sam-vimes');
    expect(samRef.positions.length).toBe(2);
  });
});
