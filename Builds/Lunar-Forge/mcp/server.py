"""
Lunar Forge MCP Server — Claude Code integration.

Exposes build system tools so Claude Code can trigger builds,
manage profiles, and preview configurations.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("lunar-forge")

FORGE_ROOT = Path(__file__).parent.parent
ENGINE_ROOT = Path(
    os.environ.get(
        "LUNA_ENGINE_ROOT",
        str(FORGE_ROOT.parent / "_LunaEngine_BetaProject_V2.0_Root"),
    )
)
PROFILES_DIR = FORGE_ROOT / "profiles"


def _get_pipeline(profile: str):
    """Get a BuildPipeline for the named profile."""
    from ..core import BuildPipeline
    profile_path = PROFILES_DIR / f"{profile}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile}")
    return BuildPipeline(profile_path, forge_root=FORGE_ROOT)


# ── Profile Tools ──

@mcp.tool()
async def build_list_profiles() -> str:
    """List all available build profiles with descriptions."""
    from ..core import list_profiles
    profiles = list_profiles(PROFILES_DIR)
    if not profiles:
        return "No profiles found."

    lines = ["Available profiles:\n"]
    for p in profiles:
        lines.append(f"  {p['file']:<20s}  {p['name']}")
        lines.append(f"  {'':20s}  {p['description']}")
        lines.append(f"  {'':20s}  db: {p['database_mode']} | collections: {p['collections_count']}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
async def build_preview(profile: str) -> str:
    """Preview resolved build config for a profile (dry run)."""
    pipeline = _get_pipeline(profile)
    manifest = pipeline.preview()
    return json.dumps(manifest, indent=2, default=str)


@mcp.tool()
async def build_run(profile: str, platform: str = "auto") -> str:
    """Run a full build for the specified profile."""
    from ..core import BuildPipeline
    profile_path = PROFILES_DIR / f"{profile}.yaml"
    if not profile_path.exists():
        return f"Profile not found: {profile}"

    log_lines = []

    def on_progress(message: str, pct: int) -> None:
        if pct >= 0:
            log_lines.append(f"[{pct:3d}%] {message}")
        else:
            log_lines.append(f"       {message}")

    pipeline = BuildPipeline(profile_path, platform, forge_root=FORGE_ROOT)
    report = pipeline.build(on_progress=on_progress)

    log_lines.append("")
    if report.status == "SUCCESS":
        log_lines.append(f"BUILD COMPLETE")
        log_lines.append(f"  Output: {report.binary_path.parent if report.binary_path else 'N/A'}")
        log_lines.append(f"  Binary: {report.binary_size/(1024*1024):.0f} MB")
        log_lines.append(f"  Total:  {report.total_size/(1024*1024):.0f} MB")
        log_lines.append(f"  Files:  {report.file_count}")
        log_lines.append(f"  Time:   {report.duration_seconds:.1f}s")
    else:
        log_lines.append(f"BUILD FAILED")
        for err in report.errors:
            log_lines.append(f"  ERROR: {err}")

    return "\n".join(log_lines)


@mcp.tool()
async def build_status() -> str:
    """Check status of the last build. Shows results summary."""
    output_dir = FORGE_ROOT / "output"
    if not output_dir.exists():
        return "No builds found."

    builds = sorted(output_dir.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True)
    if not builds:
        return "No builds found."

    latest = builds[0]
    report_path = latest / "BUILD_REPORT.md"
    if report_path.exists():
        return report_path.read_text()

    size_mb = sum(f.stat().st_size for f in latest.rglob("*") if f.is_file()) / (1024 * 1024)
    return f"Latest build: {latest.name} ({size_mb:.0f} MB)"


# ── Profile Management ──

@mcp.tool()
async def build_create_profile(name: str, base: str = "luna-only") -> str:
    """Create a new build profile from an existing one as template."""
    src = PROFILES_DIR / f"{base}.yaml"
    dst = PROFILES_DIR / f"{name}.yaml"

    if dst.exists():
        return f"Profile already exists: {name}"
    if not src.exists():
        return f"Base profile not found: {base}"

    shutil.copy2(str(src), str(dst))
    return f"Created: {dst}"


@mcp.tool()
async def build_get_profile(name: str) -> str:
    """Get the full YAML content of a build profile."""
    path = PROFILES_DIR / f"{name}.yaml"
    if not path.exists():
        return f"Profile not found: {name}"
    return path.read_text()


@mcp.tool()
async def build_update_profile(name: str, key: str, value: str) -> str:
    """Update a single key in a build profile. Key uses dot notation."""
    import yaml

    path = PROFILES_DIR / f"{name}.yaml"
    if not path.exists():
        return f"Profile not found: {name}"

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    # Navigate dot-notation key
    keys = key.split(".")
    target = data
    for k in keys[:-1]:
        if k not in target or not isinstance(target[k], dict):
            target[k] = {}
        target = target[k]

    # Parse value
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        parsed = value

    target[keys[-1]] = parsed

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return f"Updated {name}.yaml: {key} = {parsed}"


# ── Build Artifacts ──

@mcp.tool()
async def build_list_outputs() -> str:
    """List completed builds with sizes, dates, and profiles."""
    output_dir = FORGE_ROOT / "output"
    if not output_dir.exists():
        return "No builds found."

    lines = ["Completed builds:\n"]
    for d in sorted(output_dir.iterdir()):
        if d.is_dir():
            size_mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / (1024 * 1024)
            has_report = (d / "BUILD_REPORT.md").exists()
            lines.append(f"  {'[OK]' if has_report else '[??]'} {d.name}  ({size_mb:.0f} MB)")
    return "\n".join(lines) if len(lines) > 1 else "No builds found."


@mcp.tool()
async def build_get_report(build_id: str) -> str:
    """Get the BUILD_REPORT.md from a completed build."""
    report = FORGE_ROOT / "output" / build_id / "BUILD_REPORT.md"
    if not report.exists():
        return f"Report not found for: {build_id}"
    return report.read_text()


@mcp.tool()
async def build_clean(target: str = "staging") -> str:
    """Clean build artifacts. Target: staging, output, logs, or all. Reports freed space."""
    cleaned = []
    total_freed = 0

    targets = [target] if target != "all" else ["staging", "logs"]

    for t in targets:
        path = FORGE_ROOT / t
        if path.exists():
            size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            shutil.rmtree(path)
            path.mkdir()
            cleaned.append(t)
            total_freed += size

    if not cleaned:
        return "Nothing to clean."

    freed_mb = total_freed / (1024 * 1024)
    # Disk space remaining
    try:
        stat = os.statvfs(str(FORGE_ROOT))
        avail_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
        disk_info = f"\nDisk available: {avail_gb:.1f} GB"
    except Exception:
        disk_info = ""

    return f"Cleaned: {', '.join(cleaned)} (freed {freed_mb:.0f} MB){disk_info}"


# ── Frontend Config ──

@mcp.tool()
async def build_get_frontend_config(profile: str) -> str:
    """Preview the frontend_config.json that would be generated for a profile."""
    from ..core import load_profile, PROFILE_DEFAULTS

    path = PROFILES_DIR / f"{profile}.yaml"
    if not path.exists():
        return f"Profile not found: {profile}"

    p = load_profile(path)
    fe = p.get("frontend", {})
    config = {
        "pages": fe.get("pages", PROFILE_DEFAULTS["frontend"]["pages"]),
        "remap": fe.get("remap", {}),
        "widgets": fe.get("widgets", PROFILE_DEFAULTS["frontend"]["widgets"]),
    }
    return json.dumps(config, indent=2)


@mcp.tool()
async def build_toggle_page(profile: str, page: str, enabled: bool) -> str:
    """Toggle a page on/off in a profile."""
    return await build_update_profile(profile, f"frontend.pages.{page}", json.dumps(enabled))


@mcp.tool()
async def build_toggle_widget(profile: str, widget: str, enabled: bool) -> str:
    """Toggle a widget on/off in a profile."""
    return await build_update_profile(profile, f"frontend.widgets.{widget}", json.dumps(enabled))


@mcp.tool()
async def build_remap_module(profile: str, module: str, target_page: str, position: str = "header") -> str:
    """Remap a module from its default location to a different page."""
    import yaml

    path = PROFILES_DIR / f"{profile}.yaml"
    if not path.exists():
        return f"Profile not found: {profile}"

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    data.setdefault("frontend", {}).setdefault("remap", {})[module] = {
        "to": target_page,
        "position": position,
    }

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return f"Remapped {module} -> {target_page}.{position}"


if __name__ == "__main__":
    mcp.run()
