/**
 * Frontmatter Validator
 *
 * Validates scene frontmatter against Codex entities.
 * Returns errors, warnings, and suggestions.
 */

/**
 * Validate scene frontmatter against Codex entities
 * @param {Object} frontmatter - Scene frontmatter {characters_present, location, time, status, tags}
 * @param {Array} entities - All entities from Codex
 * @param {Object} sceneContext - Additional context {sceneNumber, scenePath}
 * @returns {Object} { errors, warnings, suggestions }
 */
export function validateFrontmatter(frontmatter, entities, sceneContext = {}) {
  const errors = [];
  const warnings = [];
  const suggestions = [];

  // Build entity lookup maps
  const entityById = new Map();
  const entityBySlug = new Map();
  entities.forEach(e => {
    if (e.id) entityById.set(e.id, e);
    if (e.slug) entityBySlug.set(e.slug, e);
  });

  const getEntity = (ref) => entityById.get(ref) || entityBySlug.get(ref);

  const characterEntities = entities.filter(e => e.type === 'character' || e.type === 'characters');
  const locationEntities = entities.filter(e => e.type === 'location' || e.type === 'locations');
  const propEntities = entities.filter(e => e.type === 'prop' || e.type === 'props');

  // === VALIDATE CHARACTERS ===
  if (frontmatter.characters_present && frontmatter.characters_present.length > 0) {
    frontmatter.characters_present.forEach(charRef => {
      const entity = getEntity(charRef);

      if (!entity) {
        errors.push({
          field: 'characters_present',
          value: charRef,
          severity: 'error',
          message: `Character "${charRef}" not found in Codex`,
          action: {
            type: 'create_entity',
            entityType: 'character',
            entityName: charRef
          }
        });
      } else if (entity.status === 'dead' || entity.data?.status === 'dead') {
        // Check if this scene comes after character's death
        const lastAppearance = entity.data?.last_appearance || entity.last_appearance;
        if (lastAppearance && sceneContext.sceneNumber) {
          const deathSceneNum = extractSceneNumber(lastAppearance);
          if (deathSceneNum && sceneContext.sceneNumber > deathSceneNum) {
            warnings.push({
              field: 'characters_present',
              value: charRef,
              severity: 'warning',
              message: `${entity.name} is marked as deceased (died in ${lastAppearance})`,
              action: {
                type: 'view_entity',
                entitySlug: entity.slug || entity.id
              }
            });
          }
        }
      }
    });
  }

  // === VALIDATE LOCATION ===
  if (frontmatter.location) {
    const location = getEntity(frontmatter.location);

    if (!location) {
      errors.push({
        field: 'location',
        value: frontmatter.location,
        severity: 'error',
        message: `Location "${frontmatter.location}" not found in Codex`,
        action: {
          type: 'create_entity',
          entityType: 'location',
          entityName: frontmatter.location
        }
      });
    } else if (location.data?.scene_template) {
      // Suggest missing props for this location
      const template = location.data.scene_template;
      const expectedProps = template.props_always_present || [];
      const currentProps = frontmatter.props || [];

      const missingProps = expectedProps.filter(prop =>
        !currentProps.includes(prop)
      );

      if (missingProps.length > 0) {
        suggestions.push({
          field: 'props',
          severity: 'suggestion',
          message: `Consider adding typical ${location.name} props`,
          values: missingProps,
          action: {
            type: 'add_props',
            props: missingProps
          }
        });
      }

      // Suggest lighting based on location template
      if (template.lighting && !frontmatter.time) {
        suggestions.push({
          field: 'time',
          severity: 'suggestion',
          message: `${location.name} is typically shot during ${template.lighting}`,
          value: template.lighting,
          action: {
            type: 'set_time',
            time: template.lighting
          }
        });
      }
    }
  }

  // === VALIDATE PROPS ===
  if (frontmatter.props && frontmatter.props.length > 0) {
    frontmatter.props.forEach(propRef => {
      const entity = getEntity(propRef);

      if (!entity) {
        warnings.push({
          field: 'props',
          value: propRef,
          severity: 'warning',
          message: `Prop "${propRef}" not found in Codex (will be created automatically)`,
          action: {
            type: 'create_entity',
            entityType: 'prop',
            entityName: propRef
          }
        });
      } else if (entity.status === 'destroyed' || entity.data?.status === 'destroyed') {
        warnings.push({
          field: 'props',
          value: propRef,
          severity: 'warning',
          message: `${entity.name} is marked as destroyed`,
          action: {
            type: 'view_entity',
            entitySlug: entity.slug || entity.id
          }
        });
      }
    });
  }

  // === VALIDATE STATUS ===
  const validStatuses = ['idea', 'draft', 'in-progress', 'revised', 'polished'];
  if (frontmatter.status && !validStatuses.includes(frontmatter.status)) {
    errors.push({
      field: 'status',
      value: frontmatter.status,
      severity: 'error',
      message: `Invalid status "${frontmatter.status}". Must be one of: ${validStatuses.join(', ')}`,
      action: {
        type: 'fix_status',
        validValues: validStatuses
      }
    });
  }

  // === CHARACTER RELATIONSHIP SUGGESTIONS ===
  // If 2+ characters present, check if they have defined relationships
  if (frontmatter.characters_present && frontmatter.characters_present.length >= 2) {
    const chars = frontmatter.characters_present
      .map(ref => getEntity(ref))
      .filter(Boolean);

    for (let i = 0; i < chars.length; i++) {
      for (let j = i + 1; j < chars.length; j++) {
        const char1 = chars[i];
        const char2 = chars[j];

        const hasRelationship =
          char1.relationships?.[char2.slug] ||
          char1.relationships?.[char2.id] ||
          char2.relationships?.[char1.slug] ||
          char2.relationships?.[char1.id];

        if (!hasRelationship) {
          suggestions.push({
            field: 'characters_present',
            severity: 'suggestion',
            message: `${char1.name} and ${char2.name} have no defined relationship in Codex`,
            action: {
              type: 'define_relationship',
              entity1: char1.slug || char1.id,
              entity2: char2.slug || char2.id
            }
          });
        }
      }
    }
  }

  return { errors, warnings, suggestions };
}

/**
 * Get suggestions for autocomplete based on context
 * @param {string} field - Field name (characters_present, location, time, status)
 * @param {string} currentValue - Current field value
 * @param {Array} entities - All entities
 * @param {Object} frontmatter - Current frontmatter for context
 * @returns {Array} Suggestion objects {value, label, meta}
 */
export function getSuggestions(field, currentValue, entities, frontmatter) {
  switch (field) {
    case 'characters_present':
      return entities
        .filter(e => (e.type === 'character' || e.type === 'characters') && e.status !== 'dead')
        .map(e => ({
          value: e.slug || e.id,
          label: e.name,
          meta: e.data?.role || e.role || e.type
        }));

    case 'location':
      // Sort by recent usage (if scene data available)
      return entities
        .filter(e => e.type === 'location' || e.type === 'locations')
        .map(e => ({
          value: e.slug || e.id,
          label: e.name,
          meta: e.data?.atmosphere || e.data?.mood || ''
        }));

    case 'time':
      return [
        { value: 'DAY', label: 'DAY' },
        { value: 'NIGHT', label: 'NIGHT' },
        { value: 'DAWN', label: 'DAWN' },
        { value: 'DUSK', label: 'DUSK' },
        { value: 'CONTINUOUS', label: 'CONTINUOUS' }
      ];

    case 'status':
      return [
        { value: 'idea', label: 'Idea', color: '#64748b' },
        { value: 'draft', label: 'Draft', color: '#fbbf24' },
        { value: 'in-progress', label: 'In Progress', color: '#c084fc' },
        { value: 'revised', label: 'Revised', color: '#818cf8' },
        { value: 'polished', label: 'Polished', color: '#4ade80' }
      ];

    default:
      return [];
  }
}

function extractSceneNumber(sceneRef) {
  // Extract scene number from slug (e.g., "scene_012" → 12)
  const match = sceneRef.match(/(\d+)/);
  return match ? parseInt(match[1], 10) : null;
}
