# HANDOFF: Fix Forge Profile Dropdown

**Blocking Issue:** Template picker sends display name instead of filename slug.

## Fix (3 changes)
1. **core.py line 248**: Add `"slug": p.stem` to `list_profiles()` return
2. **BuildManager.jsx line 103**: Change `handleCreateDraft(p.name)` to `handleCreateDraft(p.slug)`
3. **Verify** `fetchPreview()` calls also use slug not display name

Rebuild Forge frontend after: `cd Builds/Lunar-Forge/frontend && npm run build`
