/**
 * Entity Mention Detector
 *
 * Detects @mentions and implicit entity references in text.
 * Used by Scribo editor for autocomplete and validation.
 */

/**
 * Detect @mentions and implicit entity references in text
 * @param {string} text - The document body
 * @param {Array} entities - Array of entity objects {id, name, slug, type, color}
 * @returns {Array} Array of mention objects with position, entity, type, orphaned
 */
export function detectEntityMentions(text, entities) {
  const mentions = [];

  // Build entity lookup map (case-insensitive)
  const entityMap = new Map();
  entities.forEach(entity => {
    const key = entity.name.toLowerCase();
    entityMap.set(key, entity);
    // Also map by slug
    if (entity.slug) {
      entityMap.set(entity.slug.toLowerCase(), entity);
    }
    if (entity.id) {
      entityMap.set(entity.id.toLowerCase(), entity);
    }
  });

  // Regex patterns:
  // 1. Explicit @mentions: @EntityName or @Entity Name (multi-word)
  // 2. Implicit ALL CAPS: CHARACTER_NAME (standalone, Fountain convention)
  const patterns = [
    {
      regex: /@([A-Z][A-Za-z\s]+?)(?=\s|[.,!?]|$)/g,
      type: 'explicit'
    },
    {
      regex: /(?<=^|\s)([A-Z][A-Z\s]{2,})(?=\s|$)/gm,
      type: 'implicit'
    }
  ];

  patterns.forEach(({ regex, type }) => {
    let match;
    const regexCopy = new RegExp(regex.source, regex.flags);

    while ((match = regexCopy.exec(text)) !== null) {
      const rawName = match[1].trim();
      const entity = entityMap.get(rawName.toLowerCase());

      mentions.push({
        text: match[0],
        name: rawName,
        position: match.index,
        length: match[0].length,
        entity: entity || null,
        type: type,
        orphaned: !entity
      });
    }
  });

  // Sort by position for sequential processing
  return mentions.sort((a, b) => a.position - b.position);
}

/**
 * Inject entity link markup into text
 * @param {string} text - Original text
 * @param {Array} mentions - Mentions from detectEntityMentions
 * @returns {string} HTML string with entity links
 */
export function injectEntityLinks(text, mentions) {
  if (mentions.length === 0) return escapeHtml(text);

  let result = '';
  let lastIndex = 0;

  mentions.forEach(mention => {
    // Add text before mention
    result += escapeHtml(text.slice(lastIndex, mention.position));

    // Add mention with markup
    if (mention.entity) {
      const color = mention.entity.color || '#4ade80';
      result += `<span class="entity-ref ${mention.type}"
        data-entity-slug="${mention.entity.slug || mention.entity.id}"
        data-entity-type="${mention.entity.type}"
        style="color: ${color}; text-shadow: 0 0 6px ${color}60; cursor: pointer; text-decoration: underline dotted;">
        ${escapeHtml(mention.text)}
      </span>`;
    } else {
      // Orphaned reference
      result += `<span class="entity-ref orphaned"
        data-entity-name="${escapeHtml(mention.name)}"
        style="color: #ef4444; text-decoration: wavy underline; cursor: help;"
        title="Entity '${escapeHtml(mention.name)}' not found in Codex">
        ${escapeHtml(mention.text)}
      </span>`;
    }

    lastIndex = mention.position + mention.length;
  });

  // Add remaining text
  result += escapeHtml(text.slice(lastIndex));

  return result;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Check if cursor is after @ symbol (for autocomplete trigger)
 * @param {string} text - Text content
 * @param {number} cursorPos - Cursor position
 * @returns {{query: string, atPosition: number} | null}
 */
export function checkAtMentionContext(text, cursorPos) {
  const beforeCursor = text.slice(0, cursorPos);
  const atMatch = beforeCursor.match(/@([A-Za-z]*)$/);

  if (!atMatch) return null;

  return {
    query: atMatch[1].toLowerCase(),
    atPosition: cursorPos - atMatch[0].length
  };
}

/**
 * Filter entities by autocomplete query
 * @param {Array} entities - All entities
 * @param {string} query - Search query (lowercase)
 * @param {number} limit - Max results
 * @returns {Array} Filtered entities
 */
export function filterEntitiesForAutocomplete(entities, query, limit = 5) {
  if (!query) return entities.slice(0, limit);

  return entities
    .filter(e =>
      e.name.toLowerCase().startsWith(query) ||
      e.name.toLowerCase().includes(query)
    )
    .sort((a, b) => {
      // Prioritize exact start matches
      const aStarts = a.name.toLowerCase().startsWith(query);
      const bStarts = b.name.toLowerCase().startsWith(query);
      if (aStarts && !bStarts) return -1;
      if (!aStarts && bStarts) return 1;
      return 0;
    })
    .slice(0, limit);
}
