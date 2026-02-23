# HANDOFF: Fix C — Observatory Entities Knowledge Tab Filtering
## Priority: P2 (UI polish, depends on Fix B)
## Estimated Effort: 1-2 hours
## Owner: CC (Claude Code)

---

## Problem

The EntitiesView Knowledge tab renders ALL entity mentions with full content, no filtering or grouping. For entities with 100+ mentions, this creates an unreadable wall of text. Even after Fix B adds relevance scoring, the UI needs to surface high-signal mentions and collapse the noise.

## File to Modify

### `frontend/src/observatory/views/EntitiesView.jsx`

The Knowledge tab currently renders mentions in a flat list. Needs restructuring.

## Design Spec

### 1. Default View: Subject + Focus Mentions Only

Show only `mention_type: "subject"` and `"focus"` mentions by default. These are the nodes actually ABOUT the entity.

```jsx
// Filter mentions by type
const highSignalMentions = mentions.filter(
  m => m.mention_type === 'subject' || m.mention_type === 'focus'
);
const referenceCount = mentions.filter(
  m => m.mention_type === 'reference'
).length;
```

### 2. Sort by Confidence Descending

Most relevant mentions first:
```jsx
const sorted = [...highSignalMentions].sort(
  (a, b) => (b.confidence || 0) - (a.confidence || 0)
);
```

### 3. Mention Type Badges

Each mention card shows a small badge indicating type:

```
┌─────────────────────────────────────────────────┐
│ [SUBJECT 0.89]  FACT                            │
│ Eclissi architecture defines a modular          │
│ rendering pipeline using WebGL...               │
├─────────────────────────────────────────────────┤
│ [FOCUS 0.72]  DECISION                          │
│ Decided to use three.js for Eclissi's 3D        │
│ viewport instead of raw WebGL...                │
├─────────────────────────────────────────────────┤
│ ...and 87 passing references                    │
│ [Show all references ▼]                         │
└─────────────────────────────────────────────────┘
```

### 4. Collapsed Reference Section

Below the high-signal mentions, show a collapsible section:

```jsx
{referenceCount > 0 && (
  <div className="reference-collapse">
    <button onClick={() => setShowRefs(!showRefs)}>
      ...and {referenceCount} passing reference{referenceCount !== 1 ? 's' : ''}
      {showRefs ? ' ▲' : ' ▼'}
    </button>
    {showRefs && (
      <div className="reference-list">
        {referenceMentions.map(m => (
          <div key={m.node_id} className="reference-item">
            <span className="ref-confidence">{(m.confidence * 100).toFixed(0)}%</span>
            <span className="ref-snippet">{m.context_snippet || m.content?.slice(0, 80)}</span>
          </div>
        ))}
      </div>
    )}
  </div>
)}
```

### 5. Confidence Threshold Slider (Optional Enhancement)

Add a slider in the Knowledge tab header:

```
Relevance threshold: ═══●══════ 0.50
Showing 12 of 123 mentions
```

```jsx
const [threshold, setThreshold] = useState(0.3);
const filteredMentions = mentions.filter(m => (m.confidence || 0) >= threshold);
```

### 6. Node Type Grouping (Optional Enhancement)

Group mentions by node_type for better scanning:

```
📋 Decisions (3)
  - Decided to use three.js for Eclissi's 3D viewport...
  - Chose WebGL over Canvas2D for performance...

📌 Facts (5)  
  - Eclissi architecture defines a modular rendering pipeline...
  - Eclissi supports multiple viewports via container system...

🔧 Actions (2)
  - Implement Eclissi shader pipeline Phase 1...
```

## API Dependency

The Observatory API endpoint for entity mentions needs to return `mention_type` and `confidence` fields. Check that the `/api/entities/{id}/mentions` endpoint (proxied through Vite to `:8100`) includes these fields from the `entity_mentions` table join.

Current query in `EntityResolver.get_entity_mentions()`:
```sql
SELECT em.*, mn.content, mn.node_type
FROM entity_mentions em
JOIN memory_nodes mn ON em.node_id = mn.id
WHERE em.entity_id = ?
ORDER BY em.created_at DESC
```

This already returns `mention_type` and `confidence` from the `em.*` — verify the frontend is receiving and using them.

## Backward Compatibility

- Existing mentions with `mention_type="reference"` and `confidence=1.0` (pre-Fix-B) will all show as high-confidence references
- After Fix D migration runs, these get cleaned up
- The UI should handle the transitional state gracefully (old data + new data coexisting)

## Verification

1. Navigate to Observatory → Entities → select an entity with many mentions
2. Knowledge tab should show subject/focus mentions prominently
3. Reference mentions should be collapsed with count
4. Clicking "Show all references" expands them
5. Confidence badges should display correctly
6. After Fix D migration: reference count should drop dramatically
