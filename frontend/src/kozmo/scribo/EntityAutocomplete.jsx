/**
 * Entity Autocomplete
 *
 * Dropdown that appears when typing @ in Scribo editor.
 * Supports keyboard navigation and entity selection.
 */
import React, { useState, useEffect, useRef } from 'react';
import { checkAtMentionContext, filterEntitiesForAutocomplete } from '../utils/entityMentionDetector';

export function EntityAutocomplete({
  textareaRef,
  entities,
  onSelect,
  cursorPosition
}) {
  const [suggestions, setSuggestions] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const [context, setContext] = useState(null);
  const dropdownRef = useRef(null);

  useEffect(() => {
    if (!textareaRef.current) return;

    const textarea = textareaRef.current;
    const text = textarea.value;
    const cursorPos = textarea.selectionStart;

    // Check if cursor is after @ symbol
    const atContext = checkAtMentionContext(text, cursorPos);

    if (atContext) {
      setContext(atContext);

      // Filter entities by query
      const filtered = filterEntitiesForAutocomplete(entities, atContext.query, 5);

      setSuggestions(filtered);
      setSelectedIndex(0);

      // Calculate dropdown position
      const coords = getCaretCoordinates(textarea, cursorPos);
      setPosition({
        top: coords.top + coords.height,
        left: coords.left
      });
    } else {
      setSuggestions([]);
      setContext(null);
    }
  }, [cursorPosition, textareaRef, entities]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (suggestions.length === 0) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(i => Math.min(i + 1, suggestions.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(i => Math.max(i - 1, 0));
          break;
        case 'Enter':
        case 'Tab':
          e.preventDefault();
          if (suggestions[selectedIndex]) {
            onSelect(suggestions[selectedIndex], context);
          }
          break;
        case 'Escape':
          setSuggestions([]);
          setContext(null);
          break;
        default:
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [suggestions, selectedIndex, onSelect, context]);

  // Scroll selected item into view
  useEffect(() => {
    if (dropdownRef.current && selectedIndex >= 0) {
      const selected = dropdownRef.current.children[selectedIndex];
      if (selected) {
        selected.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }, [selectedIndex]);

  if (suggestions.length === 0) return null;

  return (
    <div
      ref={dropdownRef}
      className="entity-autocomplete"
      style={{
        position: 'absolute',
        top: position.top + 'px',
        left: position.left + 'px',
        zIndex: 1000,
        background: 'rgba(10, 10, 15, 0.6)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid #2a2a3a',
        borderRadius: '6px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
        minWidth: '200px',
        maxHeight: '200px',
        overflow: 'auto'
      }}
    >
      {suggestions.map((entity, index) => {
        const color = entity.color || '#4ade80';
        const isSelected = index === selectedIndex;

        return (
          <div
            key={entity.slug || entity.id}
            onClick={() => onSelect(entity, context)}
            className={`autocomplete-item ${isSelected ? 'selected' : ''}`}
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              background: isSelected ? 'rgba(192, 132, 252, 0.1)' : 'transparent',
              borderLeft: `3px solid ${color}`
            }}
            onMouseEnter={() => setSelectedIndex(index)}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: color,
                flexShrink: 0
              }}
            />
            <div style={{ flex: 1 }}>
              <div style={{
                color: '#e2e8f0',
                fontSize: '13px',
                fontFamily: "'Space Grotesk', sans-serif"
              }}>
                {entity.name}
              </div>
              <div style={{
                color: '#64748b',
                fontSize: '10px',
                fontFamily: "'JetBrains Mono', monospace"
              }}>
                {entity.type}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Helper: Get caret coordinates in textarea
function getCaretCoordinates(element, position) {
  const div = document.createElement('div');
  const style = getComputedStyle(element);

  // Copy textarea styles to div
  ['fontFamily', 'fontSize', 'fontWeight', 'lineHeight',
   'padding', 'border', 'width'].forEach(prop => {
    div.style[prop] = style[prop];
  });

  div.style.position = 'absolute';
  div.style.visibility = 'hidden';
  div.style.whiteSpace = 'pre-wrap';
  div.style.wordWrap = 'break-word';

  document.body.appendChild(div);

  const text = element.value.substring(0, position);
  div.textContent = text;

  const span = document.createElement('span');
  span.textContent = element.value.substring(position) || '.';
  div.appendChild(span);

  const rect = element.getBoundingClientRect();
  const spanRect = span.getBoundingClientRect();

  document.body.removeChild(div);

  return {
    top: spanRect.top - rect.top,
    left: spanRect.left - rect.left,
    height: spanRect.height
  };
}
