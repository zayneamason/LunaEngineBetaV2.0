# KOZMO Phase 2/3 Testing Guide

**Quick Reference for Manual Testing**

---

## Setup

1. **Start Backend** (if not already running):
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python scripts/run.py  # Luna Engine
# or
uvicorn src.luna.api.server:app --reload  # Direct API
```

2. **Start Frontend**:
```bash
cd Tools/KOZMO-Prototype-V1
npm install  # if first time
npm run dev  # Should start on http://localhost:5173
```

3. **Open Browser**:
   - Navigate to http://localhost:5173
   - Select a test project
   - Open Scribo editor

---

## Phase 2 Tests: @Mention Autocomplete

### Test 1: Basic Autocomplete Trigger

**Steps**:
1. Open any scene in Scribo editor
2. Click "Edit" button
3. Type `@` in the body textarea
4. **Expected**: Dropdown appears with entity suggestions

**Pass Criteria**:
- ✅ Dropdown appears within 100ms
- ✅ Dropdown positioned near cursor
- ✅ Shows entities from current project

---

### Test 2: Autocomplete Filtering

**Steps**:
1. Type `@s` in editor
2. **Expected**: Dropdown filters to entities starting with "s"
3. Type `@sam`
4. **Expected**: Dropdown narrows to "Sam Vimes"

**Pass Criteria**:
- ✅ Real-time filtering as you type
- ✅ Case-insensitive matching
- ✅ Highlights matching characters

---

### Test 3: Autocomplete Selection (Keyboard)

**Steps**:
1. Type `@s`
2. Press **Arrow Down** key
3. **Expected**: First suggestion highlighted
4. Press **Arrow Down** again
5. **Expected**: Second suggestion highlighted
6. Press **Enter**
7. **Expected**: Entity name inserted at cursor

**Pass Criteria**:
- ✅ Arrow keys navigate suggestions
- ✅ Enter inserts selected entity
- ✅ Cursor moves to end of inserted name
- ✅ Dropdown closes after insertion

---

### Test 4: Autocomplete Selection (Mouse)

**Steps**:
1. Type `@s`
2. Hover over "Sam Vimes" in dropdown
3. **Expected**: Suggestion highlighted
4. Click suggestion
5. **Expected**: `@Sam Vimes` inserted at cursor

**Pass Criteria**:
- ✅ Hover highlights suggestion
- ✅ Click inserts entity name
- ✅ Dropdown closes after click

---

### Test 5: Autocomplete Cancellation

**Steps**:
1. Type `@s`
2. Press **Escape** key
3. **Expected**: Dropdown closes, `@s` remains in text

**Pass Criteria**:
- ✅ Escape closes dropdown
- ✅ Text not modified
- ✅ Cursor position unchanged

---

### Test 6: Orphaned Entity Detection

**Steps**:
1. Type `@UnknownCharacter` in editor
2. Click away from textarea (blur)
3. **Expected**: `@UnknownCharacter` rendered with red wavy underline

**Pass Criteria**:
- ✅ Red wavy underline appears
- ✅ Tooltip shows "Entity not found"
- ✅ Validation error in frontmatter section

---

### Test 7: Entity Navigation

**Steps**:
1. Type `@Sam Vimes` in editor
2. Click "Save" button
3. Exit edit mode (view mode)
4. **Expected**: `@Sam Vimes` highlighted with color glow
5. Click `@Sam Vimes` in rendered text
6. **Expected**: Navigate to Codex tab, scroll to Sam Vimes entity

**Pass Criteria**:
- ✅ Entity name highlighted with color
- ✅ Glow effect on entity mention
- ✅ Click navigates to Codex
- ✅ Codex scrolls to entity card
- ✅ Entity card highlighted/focused

---

### Test 8: Implicit Entity Highlighting

**Steps**:
1. Set frontmatter location to "The Watch House"
2. Type "The Watch House was quiet tonight." in body (without @)
3. Exit edit mode
4. **Expected**: "The Watch House" highlighted in body text

**Pass Criteria**:
- ✅ Location name highlighted
- ✅ Color matches location entity color
- ✅ Glow effect applied
- ✅ Click navigates to location in Codex

---

## Phase 3 Tests: Frontmatter Validation

### Test 9: Non-Existent Character Error

**Steps**:
1. Open frontmatter editor
2. In "Characters Present" field, add "unknown-character"
3. **Expected**: Red error banner appears below form
4. **Expected**: Save button disabled

**Pass Criteria**:
- ✅ Error shows: "Entity not found: unknown-character"
- ✅ Error severity: 🚫 (red)
- ✅ Action button: "Create Entity"
- ✅ Save button disabled while error exists

---

### Test 10: Create Entity Action

**Steps**:
1. Trigger non-existent character error (see Test 9)
2. Click "Create" button on error
3. **Expected**: Entity creation modal opens
4. **Expected**: Name field pre-filled with "unknown-character"
5. Fill in entity details, click "Save"
6. **Expected**: Error disappears, entity added

**Pass Criteria**:
- ✅ Modal opens on button click
- ✅ Name pre-filled correctly
- ✅ Entity created successfully
- ✅ Error removed from validation
- ✅ Save button re-enabled

---

### Test 11: Dead Character Warning

**Steps**:
1. Create a character entity with status "dead", last_appearance: 5
2. Open a scene with scene_number: 10
3. Add dead character to "Characters Present"
4. **Expected**: Yellow warning banner appears

**Pass Criteria**:
- ✅ Warning shows: "Character died in scene 5, using in scene 10?"
- ✅ Warning severity: ⚠️ (yellow)
- ✅ Action button: "View Entity"
- ✅ Save button still enabled (warnings don't block)

---

### Test 12: View Entity Action

**Steps**:
1. Trigger dead character warning (see Test 11)
2. Click "View" button on warning
3. **Expected**: Navigate to Codex tab
4. **Expected**: Scroll to dead character entity card

**Pass Criteria**:
- ✅ Codex tab activated
- ✅ Entity card visible
- ✅ Entity card highlighted/focused
- ✅ Can return to Scribo tab

---

### Test 13: Invalid Status Error

**Steps**:
1. Manually edit frontmatter YAML (or use dev tools)
2. Set status to "invalid-status-value"
3. **Expected**: Red error banner appears

**Pass Criteria**:
- ✅ Error shows: "Invalid status. Must be one of: draft, review, final"
- ✅ Action button: "Fix Status"
- ✅ Save button disabled

---

### Test 14: Fix Status Action

**Steps**:
1. Trigger invalid status error (see Test 13)
2. Click "Fix" button on error
3. **Expected**: Status automatically corrected to "draft"
4. **Expected**: Error disappears

**Pass Criteria**:
- ✅ Status field updates to "draft"
- ✅ Error removed
- ✅ Save button re-enabled

---

### Test 15: Location Scene Template Suggestion

**Steps**:
1. Create a location entity with scene_template:
   ```json
   {
     "props_always_present": ["throne", "royal-banner"],
     "lighting": "dramatic-overhead"
   }
   ```
2. Set scene location to this location
3. Leave props field empty
4. **Expected**: Blue suggestion banner appears

**Pass Criteria**:
- ✅ Suggestion shows: "Location suggests props: throne, royal-banner"
- ✅ Suggestion severity: 💡 (blue)
- ✅ Action button: "Add Props"
- ✅ Save button enabled (suggestions are optional)

---

### Test 16: Add Props Action

**Steps**:
1. Trigger location scene template suggestion (see Test 15)
2. Click "Add Props" button
3. **Expected**: Props field updated with suggested props
4. **Expected**: Suggestion disappears

**Pass Criteria**:
- ✅ Props added to frontmatter
- ✅ Suggestion removed
- ✅ No errors or warnings

---

### Test 17: Relationship Suggestion

**Steps**:
1. Add two characters with no defined relationship
2. Both characters in "Characters Present"
3. **Expected**: Blue suggestion banner appears

**Pass Criteria**:
- ✅ Suggestion shows: "Define relationship between Character A and Character B?"
- ✅ Action button: "Define"
- ✅ Save button enabled

---

### Test 18: Define Relationship Action

**Steps**:
1. Trigger relationship suggestion (see Test 17)
2. Click "Define" button
3. **Expected**: Relationship editor modal opens
4. Define relationship (e.g., "Character A → colleague → Character B")
5. Save relationship
6. **Expected**: Suggestion disappears

**Pass Criteria**:
- ✅ Relationship modal opens
- ✅ From/To characters pre-filled
- ✅ Relationship saved successfully
- ✅ Suggestion removed

---

### Test 19: Multiple Validation Issues

**Steps**:
1. Add non-existent character (error)
2. Add dead character to later scene (warning)
3. Add location with missing props (suggestion)
4. **Expected**: All three banners appear stacked

**Pass Criteria**:
- ✅ Errors displayed first (top)
- ✅ Warnings displayed second (middle)
- ✅ Suggestions displayed last (bottom)
- ✅ Each banner has correct color/icon
- ✅ Scrollable if more than 200px height

---

### Test 20: Validation Clear on Fix

**Steps**:
1. Trigger multiple validation issues (see Test 19)
2. Fix non-existent character error
3. **Expected**: Error disappears, warning and suggestion remain
4. Remove dead character
5. **Expected**: Warning disappears, suggestion remains
6. Accept suggestion or ignore it
7. **Expected**: All validation cleared

**Pass Criteria**:
- ✅ Validation updates in real-time
- ✅ Fixed issues disappear immediately
- ✅ Remaining issues stay visible
- ✅ Save button enabled when no errors

---

## Integration Tests

### Test 21: End-to-End Workflow

**Steps**:
1. Create new scene
2. Type body with `@Character1` and `@Character2`
3. Autocomplete suggests entities, select them
4. Add characters to frontmatter
5. Set location with scene template
6. Accept prop suggestions
7. Save scene
8. Exit edit mode
9. Click entity mentions in rendered text
10. Navigate to Codex, verify entity cards

**Pass Criteria**:
- ✅ Autocomplete works correctly
- ✅ Validation runs and clears
- ✅ Scene saves successfully
- ✅ Entity links work in view mode
- ✅ Navigation to Codex works

---

### Test 22: Backend Entity Reference Extraction

**Steps**:
1. Save a scene with multiple `@mentions` and implicit mentions
2. Use backend API or Python REPL:
   ```python
   from src.luna.services.kozmo.scribo_parser import extract_entity_references
   body = "@Sam Vimes walked into The Watch House. Sam Vimes sat down."
   entities = [
       {'slug': 'sam-vimes', 'name': 'Sam Vimes', 'type': 'character'},
       {'slug': 'the-watch-house', 'name': 'The Watch House', 'type': 'location'}
   ]
   refs = extract_entity_references(body, entities)
   print(refs)
   ```
3. **Expected**: Returns list of entity references with positions

**Pass Criteria**:
- ✅ Explicit @mentions detected
- ✅ Implicit mentions detected
- ✅ Positions tracked correctly
- ✅ mention_type field correct ('explicit' or 'implicit')

---

## Performance Tests

### Test 23: Large Entity List

**Steps**:
1. Import project with 500+ entities
2. Type `@` in editor
3. **Expected**: Autocomplete appears within 100ms

**Pass Criteria**:
- ✅ No lag when opening autocomplete
- ✅ Filtering is instant (<50ms)
- ✅ Dropdown shows only top 5 results

---

### Test 24: Validation Performance

**Steps**:
1. Create scene with complex frontmatter (10+ characters, 5+ props)
2. Edit frontmatter repeatedly
3. **Expected**: Validation runs instantly (<50ms)

**Pass Criteria**:
- ✅ No noticeable lag
- ✅ Validation updates in real-time
- ✅ No UI freezing

---

## Edge Cases

### Test 25: Entity Name with Special Characters

**Steps**:
1. Create entity: "O'Brien"
2. Type `@O'B` in editor
3. **Expected**: Autocomplete suggests "O'Brien"
4. Select entity
5. **Expected**: Correctly inserted

**Pass Criteria**:
- ✅ Apostrophe handled correctly
- ✅ Entity detectable in body text
- ✅ No regex errors

---

### Test 26: Very Long Entity Name

**Steps**:
1. Create entity: "The Honourable Lady Sybil Deidre Olgivanna Vimes née Ramkin"
2. Type `@The Hon` in editor
3. **Expected**: Autocomplete suggests long name
4. Select entity
5. **Expected**: Full name inserted, autocomplete closes

**Pass Criteria**:
- ✅ Long name displayed correctly in dropdown
- ✅ Dropdown doesn't overflow screen
- ✅ Full name inserted

---

### Test 27: Non-ASCII Entity Names

**Steps**:
1. Create entity: "Señor López"
2. Type `@Señor` in editor
3. **Expected**: Autocomplete suggests "Señor López"

**Pass Criteria**:
- ✅ Non-ASCII characters handled
- ✅ Autocomplete works correctly
- ✅ Entity detectable in body

---

### Test 28: @ in Email Address

**Steps**:
1. Type "contact@example.com" in editor
2. **Expected**: Autocomplete does NOT trigger

**Pass Criteria**:
- ✅ No autocomplete for email addresses
- ✅ No validation errors
- ✅ @ rendered as plain text

---

### Test 29: Multiple @Mentions Same Line

**Steps**:
1. Type "@Sam Vimes met @Lady Sybil and @Carrot at @The Watch House."
2. Exit edit mode
3. **Expected**: All four entities highlighted

**Pass Criteria**:
- ✅ All mentions detected
- ✅ All mentions highlighted with correct colors
- ✅ All mentions clickable

---

### Test 30: Nested Validation Actions

**Steps**:
1. Trigger "Create Entity" error
2. Click "Create" button
3. In creation modal, add invalid data
4. **Expected**: Modal shows its own validation
5. Fix modal validation, save entity
6. **Expected**: Return to Scribo, original error cleared

**Pass Criteria**:
- ✅ Nested validation works
- ✅ Modal validation independent
- ✅ Original validation updates after entity created

---

## Regression Tests

### Test 31: Existing Entity Highlighting Still Works

**Steps**:
1. Open scene with existing entity mentions (pre-Phase 2)
2. **Expected**: Entity mentions highlighted in view mode

**Pass Criteria**:
- ✅ Existing functionality not broken
- ✅ Entity click navigation works
- ✅ Colors applied correctly

---

### Test 32: Frontmatter Form Still Works

**Steps**:
1. Open frontmatter editor
2. Edit fields manually (without validation actions)
3. Save scene
4. **Expected**: Changes saved correctly

**Pass Criteria**:
- ✅ Manual editing works
- ✅ Save button functional
- ✅ No validation errors for valid data

---

## Bug Reporting Template

If you find a bug, report with:

```markdown
## Bug Report

**Test**: [Test number and name]

**Steps to Reproduce**:
1.
2.
3.

**Expected Behavior**:


**Actual Behavior**:


**Screenshots** (if applicable):


**Browser/Environment**:
- Browser:
- Version:
- OS:

**Console Errors** (if any):
```

---

## Success Criteria Summary

### Phase 2
- ✅ Autocomplete triggers on `@` within 100ms
- ✅ Keyboard navigation works (Arrow keys, Enter, Escape)
- ✅ Entity insertion works correctly
- ✅ Orphaned entities detected and highlighted
- ✅ Entity navigation to Codex works
- ✅ Implicit mentions highlighted from frontmatter

### Phase 3
- ✅ Validation runs in <50ms
- ✅ Errors block save with actionable buttons
- ✅ Warnings allow save with informative messages
- ✅ Suggestions provide optional enhancements
- ✅ All 6 action types work correctly
- ✅ Validation updates in real-time

---

**Total Tests**: 32
**Estimated Testing Time**: 2-3 hours

**Status**: Ready for testing ✅
