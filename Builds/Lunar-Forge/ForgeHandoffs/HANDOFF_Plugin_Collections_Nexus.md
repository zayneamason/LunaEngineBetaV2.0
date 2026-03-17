# HANDOFF — Plugin Collections (Nexus as External Modules)

**Date:** 2026-03-15
**Status:** Design only — not yet implemented
**Modifies:** `src/luna/substrate/aibrarian_engine.py`, `config/aibrarian_registry.yaml`, Forge profile YAML, Forge ConfigPreview UI, EclissiShell page mapping

---

## Problem

Aibrarian collections (Nexus) are currently baked into the build via `aibrarian_registry.yaml`. Every collection's `.db` file gets copied into the output. Collections like `kinoni_knowledge` (883 chunks, community-specific) and `dataroom` (investor docs) should never ship in a generic build — but there's no mechanism to install them after the fact.

Additionally, collections are tied to pages (Guardian needs kinoni, Eclissi needs luna_system) but the page mapping is static. A new collection can't present its own UI without modifying EclissiShell.

## Solution: Plugin Collections

Collections ship as installable modules that can be dropped into a `collections/` directory post-build. Each collection module brings its own data, registry entry, and optional page mapping.

## What Already Exists

The Aibrarian system is already modular:

- `aibrarian_registry.yaml` — declarative collection definitions, no code changes needed to add a new one
- `AiBrarianEngine.initialize()` — reads the registry, connects to each enabled collection's `.db`
- `AiBrarianEngine.list_collections()` — returns what's available at runtime
- Collections are independent SQLite databases — no shared state between them
- The Forge already has collection toggles and knows about collection sizes
- `EclissiShell.jsx` has `ALL_TABS` array and remap logic for page mapping

## Plugin Collection Structure

```
Luna.app/
├── run_luna.bin
├── collections/                          # NEW — plugin collection root
│   ├── kinoni-knowledge/
│   │   ├── manifest.yaml                 # collection metadata + page mapping
│   │   ├── kinoni.db                     # the actual data
│   │   └── README.md                     # optional description
│   ├── dataroom/
│   │   ├── manifest.yaml
│   │   ├── dataroom.db
│   │   └── README.md
│   └── my-custom-research/
│       ├── manifest.yaml
│       ├── research.db
│       └── README.md
├── config/
│   └── aibrarian_registry.yaml           # still has system collections (luna_system)
└── data/
    └── system/aibrarian/luna_system.db   # system collection stays compiled in
```

### manifest.yaml Format

```yaml
# collections/kinoni-knowledge/manifest.yaml
name: "Kinoni Community Knowledge"
description: "Cultural knowledge base for ICT Hub deployment"
version: "1.0.0"
author: "Luna Project"

collection:
  key: "kinoni_knowledge"               # registry key
  db_file: "kinoni.db"                  # relative to this directory
  schema_type: "standard"
  chunk_size: 300
  chunk_overlap: 75
  read_only: false
  tags: ["kinoni", "uganda", "community"]

# Optional: page mapping — tells EclissiShell to show a tab for this collection
page_mapping:
  enabled: true
  page_key: "guardian"                  # which tab to associate with
  # OR create a new tab:
  # page_key: "kinoni"
  # page_label: "KINONI"
  # page_component: "iframe"           # iframe | placeholder | custom
  # page_url: "/collections/kinoni-knowledge/ui/"  # if iframe
  # page_accent: "var(--ec-accent-guardian)"

# Optional: dependencies
requires_pages: ["guardian"]            # warn if guardian page is disabled
requires_collections: []                # other collections this one depends on
```

## Implementation

### 1. Collection Discovery in AiBrarianEngine

Add to `AiBrarianEngine.initialize()`:

```python
async def _discover_plugin_collections(self):
    """Scan collections/ directory for plugin collection manifests."""
    collections_dir = self.root / "collections"
    if not collections_dir.exists():
        return

    for entry in sorted(collections_dir.iterdir()):
        manifest_path = entry / "manifest.yaml"
        if not entry.is_dir() or not manifest_path.exists():
            continue

        try:
            with open(manifest_path) as f:
                manifest = yaml.safe_load(f) or {}

            coll_cfg = manifest.get("collection", {})
            key = coll_cfg.get("key", entry.name)

            if key in self._collections:
                logger.debug(f"[NEXUS] Plugin collection '{key}' overridden by registry")
                continue

            # Resolve db_path relative to plugin directory
            db_file = coll_cfg.get("db_file", f"{key}.db")
            db_path = entry / db_file

            if not db_path.exists():
                logger.warning(f"[NEXUS] Plugin '{key}': db not found at {db_path}")
                continue

            # Register as if it were in the YAML registry
            self._registry["collections"][key] = {
                "name": manifest.get("name", key),
                "description": manifest.get("description", ""),
                "db_path": str(db_path),
                "enabled": True,
                "schema_type": coll_cfg.get("schema_type", "standard"),
                "chunk_size": coll_cfg.get("chunk_size", 500),
                "chunk_overlap": coll_cfg.get("chunk_overlap", 50),
                "read_only": coll_cfg.get("read_only", False),
                "tags": coll_cfg.get("tags", []),
                "plugin": True,   # flag to distinguish from compiled collections
                "plugin_dir": str(entry),
            }

            logger.info(f"[NEXUS] Discovered plugin collection: {key} ({db_path})")
        except Exception as e:
            logger.warning(f"[NEXUS] Failed to load plugin {entry.name}: {e}")
```

Call `_discover_plugin_collections()` at the end of `initialize()`, after loading the YAML registry.

### 2. Page Mapping API

New endpoint in `server.py`:

```python
@app.get("/api/page-mappings")
async def page_mappings():
    """Return page mappings from plugin collection manifests."""
    mappings = []
    collections_dir = ENGINE_ROOT / "collections"
    if not collections_dir.exists():
        return mappings

    for entry in sorted(collections_dir.iterdir()):
        manifest_path = entry / "manifest.yaml"
        if not manifest_path.exists():
            continue
        manifest = yaml.safe_load(manifest_path.read_text()) or {}
        pm = manifest.get("page_mapping")
        if pm and pm.get("enabled"):
            mappings.append({
                "collection_key": manifest.get("collection", {}).get("key", entry.name),
                "page_key": pm["page_key"],
                "page_label": pm.get("page_label"),
                "page_component": pm.get("page_component", "placeholder"),
                "page_url": pm.get("page_url"),
                "page_accent": pm.get("page_accent"),
                "requires_pages": manifest.get("requires_pages", []),
            })
    return mappings
```

### 3. Frontend: Dynamic Page Registration

`EclissiShell.jsx` fetches `/api/page-mappings` on mount and merges plugin pages into the tab list:

```jsx
const [pluginPages, setPluginPages] = useState([]);

useEffect(() => {
  fetch('/api/page-mappings')
    .then(r => r.json())
    .then(setPluginPages)
    .catch(() => {});
}, []);

// Merge into ALL_TABS
const effectiveTabs = useMemo(() => {
  const base = [...ALL_TABS];
  for (const pp of pluginPages) {
    if (!base.includes(pp.page_key)) {
      // Insert before 'settings' (always last)
      const settingsIdx = base.indexOf('settings');
      base.splice(settingsIdx, 0, pp.page_key);
    }
  }
  return base;
}, [pluginPages]);
```

Plugin pages render as:
- `iframe` — loads `page_url` in an iframe (like Studio currently does)
- `placeholder` — shows a PlaceholderView with description
- `custom` — future: load a React component from the plugin directory

### 4. Forge Integration

The Forge profile YAML gets a collections section that distinguishes compiled vs plugin:

```yaml
collections:
  luna_system:
    enabled: true
    mode: compiled              # baked into the build
    source: data/system/aibrarian/luna_system.db

  kinoni_knowledge:
    enabled: true
    mode: plugin                # copied to collections/ directory, not compiled
    source: data/local/kinoni.db

  dataroom:
    enabled: false
    mode: plugin
    source: data/local/dataroom.db
```

Build pipeline behavior:
- `mode: compiled` — copies `.db` into `data/` inside the build (current behavior)
- `mode: plugin` — copies `.db` + generates `manifest.yaml` into `collections/{key}/` in the output
- Disabled collections with `mode: plugin` are excluded entirely but can be installed later

### 5. Forge ConfigPreview UI

The Collections section in ConfigPreview gets a mode dropdown per collection:

```
Collections
  ☑ luna_system       [compiled ▾]    27 chunks    27.0 MB    System knowledge (required)
  ☑ kinoni_knowledge  [plugin ▾]      883 chunks   4.2 MB     Kinoni community data
  ☐ dataroom          [plugin ▾]      27 chunks    1.1 MB     Investor documents
```

Plus a page mapping subsection:

```
Page Mapping
  kinoni_knowledge → guardian tab
  dataroom → (no page)      [assign to tab ▾]
```

The "assign to tab" dropdown lets you map a collection to an existing page or create a new tab name.

### 6. Post-Install Collection Management

Users can add collections after install by:

1. **Drop folder**: Copy a collection folder (with manifest.yaml + .db) into `collections/`
2. **Settings UI**: Future Collections section in Settings with "Add Collection" that accepts a `.zip` or folder path
3. **MCP tool**: `luna_install_collection(path)` — copies and registers

## Collection Classification

| Collection | Ship Mode | Page Mapping | Notes |
|---|---|---|---|
| luna_system | Always compiled | eclissi (implicit) | Required for Luna to function |
| kinoni_knowledge | Plugin (optional) | guardian | Community-specific |
| dataroom | Plugin (optional) | none (or custom) | Project-specific |
| bombay_beach | Plugin (optional) | custom tab | Future art archive |
| Any user collection | Plugin (install) | configurable | Created via Nexus ingest tools |

## Relationship to Skill Plugins

This follows the same pattern as skill plugins (see HANDOFF_Plugin_Skill_Architecture.md):

| Aspect | Skill Plugins | Collection Plugins |
|---|---|---|
| Directory | `plugins/` | `collections/` |
| Manifest | `__init__.py` + `requirements.txt` | `manifest.yaml` |
| Heavy resource | Python packages (sympy) | SQLite databases |
| Discovery | `SkillRegistry.register_plugins()` | `AiBrarianEngine._discover_plugin_collections()` |
| UI mapping | Skill toggles | Page mapping + tab assignment |
| Build impact | Reduces Nuitka compile time | Reduces build output size |

## Success Criteria

1. `luna_system` is compiled into every build — Luna always has self-knowledge
2. `kinoni_knowledge` ships as a plugin folder when mode=plugin — not compiled into binary
3. Dropping a new collection folder into `collections/` makes it appear in Nexus search
4. Page mapping in manifest.yaml creates a new tab in EclissiShell (or maps to existing tab)
5. Forge UI shows compiled/plugin dropdown per collection with page mapping options
6. Build size decreases when large collections use plugin mode instead of compiled
