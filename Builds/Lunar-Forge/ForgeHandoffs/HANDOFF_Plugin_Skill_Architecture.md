# HANDOFF — Plugin Skill Architecture

**Date:** 2026-03-15
**Status:** Design only — not yet implemented
**Modifies:** `src/luna/skills/registry.py`, `src/luna/skills/base.py`, new `plugins/` directory, Forge profile YAML, Forge UI

---

## Problem

Heavy skills like MathSkill (sympy, ~600 modules) and LogicSkill (also sympy) add 10-15 minutes to Nuitka compilation. Every skill's dependencies get compiled into the binary regardless of whether the end user needs them. This creates a tradeoff: fast builds with fewer skills, or full skills with hour-long builds.

## Solution: Plugin Skills

Skills with heavy dependencies ship as runtime plugins loaded alongside the compiled binary, not compiled into it. The Nuitka binary stays lean. Plugins install into a `plugins/` directory and are discovered at startup.

## What Already Exists

The skill system is 80% ready for plugins:

- `Skill` base class (`skills/base.py`) — clean interface: `name`, `triggers`, `is_available()`, `execute()`, `narration_hint()`
- `SkillRegistry.register(skill)` — takes any Skill instance, checks availability
- Every skill already does lazy `import sympy` inside `execute()` with graceful `fallthrough=True` on ImportError
- `register_defaults()` wraps each skill import in try/except — missing skills just get skipped
- `SkillsConfig` and `config/skills.yaml` already have per-skill enable/disable toggles

## What's Missing

### 1. Plugin Directory Convention

```
Luna.app/                        # or engine root for dev
├── run_luna.bin                  # compiled binary
├── plugins/                     # NEW — plugin root
│   ├── luna-skill-math/
│   │   ├── __init__.py          # exports MathSkill class
│   │   ├── skill.py             # the actual skill code
│   │   └── requirements.txt     # sympy>=1.12
│   ├── luna-skill-logic/
│   │   ├── __init__.py
│   │   ├── skill.py
│   │   └── requirements.txt
│   └── _venv/                   # isolated venv for plugin deps
│       └── lib/python3.12/site-packages/
│           └── sympy/           # installed here, not in main env
└── config/
    └── skills.yaml              # still controls enable/disable
```

### 2. Plugin Loader in Registry

Add to `SkillRegistry`:

```python
def register_plugins(self, plugin_dir: Path) -> None:
    """Discover and register plugin skills from a directory."""
    if not plugin_dir.exists():
        return

    # Add plugin venv to sys.path if it exists
    venv_site = plugin_dir / "_venv" / "lib"
    if venv_site.exists():
        # Find the python version subdir
        for pydir in venv_site.iterdir():
            sp = pydir / "site-packages"
            if sp.exists() and str(sp) not in sys.path:
                sys.path.insert(0, str(sp))

    for entry in sorted(plugin_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith(("_", ".")):
            continue
        try:
            # Each plugin dir must have __init__.py exporting a Skill subclass
            spec = importlib.util.spec_from_file_location(
                entry.name, entry / "__init__.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Convention: __init__.py exports `SkillClass`
            skill_cls = getattr(module, "SkillClass", None)
            if skill_cls and issubclass(skill_cls, Skill):
                skill_cfg = getattr(self.config, skill_cls.name, {})
                if skill_cfg.get("enabled", True):
                    self.register(skill_cls(skill_cfg))
                    logger.info(f"[PLUGINS] Loaded: {skill_cls.name} from {entry.name}")
            else:
                logger.warning(f"[PLUGINS] {entry.name} has no SkillClass export")
        except Exception as e:
            logger.warning(f"[PLUGINS] Failed to load {entry.name}: {e}")
```

### 3. Plugin __init__.py Convention

Each plugin's `__init__.py` exports `SkillClass`:

```python
# plugins/luna-skill-math/__init__.py
from .skill import MathSkill as SkillClass
```

The actual `skill.py` is identical to the current `src/luna/skills/math/skill.py` — just moved.

### 4. Plugin Install/Uninstall

A helper script or Settings panel action:

```bash
# Install a plugin's dependencies into the plugin venv
python3 -m venv plugins/_venv  # create once
plugins/_venv/bin/pip install -r plugins/luna-skill-math/requirements.txt
```

Could also support pip-installable plugin packages:
```bash
plugins/_venv/bin/pip install luna-skill-math
```

### 5. Startup Flow Change

In `engine.py` boot sequence, after `register_defaults()`:

```python
# Register built-in skills (lightweight ones compiled into binary)
self.skill_registry.register_defaults()

# Discover and register plugin skills (heavy deps loaded at runtime)
plugin_dir = self.data_dir / "plugins"  # or engine_root / "plugins"
self.skill_registry.register_plugins(plugin_dir)
```

### 6. Forge Integration

The Forge profile YAML gets a new section:

```yaml
plugins:
  bundle_mode: "external"   # "compiled" | "external" | "none"
  include:
    - luna-skill-math
    - luna-skill-logic
```

- `compiled` — include in Nuitka build (current behavior, slow)
- `external` — copy to `plugins/` directory in output, don't compile (fast)
- `none` — don't include, user installs manually

When `bundle_mode: external`, the Forge build pipeline:
1. Copies plugin directories to `output/plugins/`
2. Creates the plugin venv
3. Runs `pip install -r requirements.txt` for each plugin
4. Adds the plugin packages to Nuitka's `exclude_packages` list

### 7. Forge UI Changes

The existing Skills section in ConfigPreview gets a new column:

```
Skills
  ☑ math          [compiled ▾]     sympy — solve, integrate, factor
  ☑ logic         [compiled ▾]     sympy — truth tables, satisfiability
  ☑ diagnostic    [compiled ▾]     (no heavy deps)
  ☑ reading       [compiled ▾]     (no heavy deps)
  ☑ eden          [compiled ▾]     eden API
  ☑ analytics     [compiled ▾]     (no heavy deps)
```

The dropdown per skill: `compiled | plugin | exclude`

Switching math from "compiled" to "plugin" moves sympy from the Nuitka compile to the `plugins/` directory, saving ~10 min build time.

## Migration Path

1. **Phase 1 (no code changes):** Move `skills/math/` and `skills/logic/` to `plugins/luna-skill-math/` and `plugins/luna-skill-logic/`. Add plugin loader to registry. Add sympy to Nuitka exclusions. Test that math/logic skills still work via plugin loading.

2. **Phase 2:** Add Forge UI dropdown (compiled/plugin/exclude). Update `assemble_data()` to handle plugin bundling.

3. **Phase 3:** Add Settings panel "Plugins" tab with install/uninstall. Support pip-installable third-party skills.

## Skills Classification

| Skill | Heavy Deps | Compile Cost | Plugin Candidate? |
|---|---|---|---|
| math | sympy (~600 modules) | +10-15 min | YES |
| logic | sympy (shared with math) | +0 if math included | YES (bundle with math) |
| diagnostic | none | ~0 | No — keep compiled |
| reading | none | ~0 | No — keep compiled |
| eden | httpx (already included) | ~0 | No — keep compiled |
| analytics | none | ~0 | No — keep compiled |
| formatting | none | ~0 | No — keep compiled |

## Estimated Build Time Impact

| Config | Estimated Time |
|---|---|
| Current (all compiled) | ~45-60 min |
| Math + Logic as plugins | ~30-45 min |
| + exclude scipy, sklearn | ~20-30 min |
