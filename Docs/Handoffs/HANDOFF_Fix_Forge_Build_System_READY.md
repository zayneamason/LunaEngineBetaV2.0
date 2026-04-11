# HANDOFF: Fix Forge Build System — BLOCKING

Three bugs preventing builds:

1. **Doubled engine root** — core.py appends `_LunaEngine_BetaProject_V2.0_Root` to a path that already IS that directory. Fix: `self.engine_root = self.forge_root.parent.parent` (remove the append)

2. **CLI relative import** — build.py uses `from .core import` which fails when run as a script. Fix: try/except to fall back to absolute import.

3. **Dropdown sends display name** — Forge UI sends "Hai Dai Ambassador" instead of "hai-dai". Fix: add `slug: p.stem` to `list_profiles()` in core.py, use `p.slug` in BuildManager.jsx.

After fixes, rebuild Forge frontend: `cd Builds/Lunar-Forge/frontend && npm run build`
