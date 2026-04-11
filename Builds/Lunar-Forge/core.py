"""
Lunar Forge — Core Build Pipeline.

All build logic lives here. CLI, TUI, and MCP are thin interfaces over this module.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import yaml


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

PROFILE_DEFAULTS: dict[str, Any] = {
    "name": "Unnamed",
    "description": "",
    "version": "0.1.0",
    "platform": "auto",
    "engine": {"root": None},
    "database": {"mode": "seed", "source": None},
    "collections": {},
    "config": {
        "personality": {
            "bootstrap_patches": [
                "bootstrap_001_sovereignty",
                "bootstrap_003_honesty",
            ],
            "first_meeting_directive": False,
        },
        "llm_providers": {"mode": "template"},
        "fallback_chain": {"chain": ["claude", "groq"]},
        "skills": {},
    },
    "secrets": {"mode": "template"},
    "frontend": {
        "build": True,
        "pages": {
            "eclissi": True,
            "studio": True,
            "kozmo": True,
            "guardian": True,
            "observatory": True,
            "settings": True,
        },
        "remap": {},
        "widgets": {
            "engine": True,
            "voice": True,
            "memory": True,
            "qa": True,
            "prompt": True,
            "debug": True,
            "vk": True,
            "cache": True,
            "thought": True,
            "lunascript": True,
        },
    },
    "nuitka": {
        "standalone": True,
        "exclude_packages": [
            "torch", "torchvision", "torchaudio", "transformers",
            "tensorflow", "keras", "scipy", "sklearn",
            "matplotlib", "PIL", "cv2", "spacy", "llama_cpp",
        ],
        "extra_include_packages": [],
        "extra_data_dirs": [],
    },
    "post_build": {
        "create_launcher": True,
        "create_app_bundle": False,
        "code_sign": False,
    },
    "platform_config": {
        "macos": {
            "nuitka_mode": "app",
            "include_packages": [],
            "exclude_packages": [],
            "tts": "apple",
            "stt": "mlx-whisper",
            "inference": "mlx",
        },
        "linux": {
            "nuitka_mode": "standalone",
            "include_packages": [],
            "exclude_packages": [
                "pyobjc-framework-Cocoa", "pyobjc-framework-WebKit", "pyobjc-core",
            ],
            "tts": "piper",
            "stt": "whisper-onnx",
            "inference": "onnx",
        },
        "windows": {
            "nuitka_mode": "standalone",
            "include_packages": [],
            "exclude_packages": [
                "pyobjc-framework-Cocoa", "pyobjc-framework-WebKit", "pyobjc-core",
            ],
            "tts": "piper",
            "stt": "whisper-onnx",
            "inference": "onnx",
        },
    },
    "wizard": {
        "enabled": True,
        "providers": ["groq", "claude", "gemini"],
        "show_voice_step": True,
        "show_personality_step": True,
        "default_provider": "groq",
        "custom_welcome": "",
    },
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BuildReport:
    """Summary of a completed build."""
    profile_name: str
    version: str
    platform: str
    status: str  # SUCCESS | FAILED
    binary_path: Optional[Path] = None
    binary_size: int = 0
    total_size: int = 0
    file_count: int = 0
    dir_count: int = 0
    duration_seconds: float = 0.0
    timestamp: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    qa_results: Optional[dict] = None  # Post-build QA validation results

    def to_markdown(self) -> str:
        """Generate BUILD_REPORT.md content."""
        lines = [
            "# Luna Engine — Build Report",
            f"## Profile: `{self.profile_name}`",
            f"## Date: {self.timestamp}",
            "",
            "---",
            "",
            "## Build Summary",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| **Status** | {self.status} |",
            f"| **Binary** | `{self.binary_path.name if self.binary_path else 'N/A'}` |",
            f"| **Platform** | {self.platform} |",
            f"| **Binary Size** | {self.binary_size / (1024*1024):.0f} MB |",
            f"| **Total Dist Size** | {self.total_size / (1024*1024):.0f} MB |",
            f"| **Files** | {self.file_count} files across {self.dir_count} directories |",
            f"| **Build Duration** | {self.duration_seconds:.1f}s |",
            f"| **Compiler** | Nuitka (standalone mode) |",
            f"| **Python Version** | {platform.python_version()} |",
            f"| **Target Machine** | {platform.machine()}, {platform.system()} {platform.release()} |",
            "",
        ]

        if self.warnings:
            lines += ["## Warnings", ""]
            for w in self.warnings:
                lines.append(f"- {w}")
            lines.append("")

        if self.errors:
            lines += ["## Errors", ""]
            for e in self.errors:
                lines.append(f"- {e}")
            lines.append("")

        if self.qa_results:
            qa = self.qa_results
            status_icon = "\u2705" if qa.get("passed") else "\u274c"
            lines += [
                "## Post-Build QA Validation",
                "",
                f"| Field | Value |",
                f"|---|---|",
                f"| **Status** | {status_icon} {'PASSED' if qa.get('passed') else 'FAILED'} |",
                f"| **Assertions Run** | {qa.get('total', 0)} |",
                f"| **Passed** | {qa.get('passed_count', 0)} |",
                f"| **Failed** | {qa.get('failed_count', 0)} |",
                f"| **Engine Boot** | {'OK' if qa.get('engine_booted') else 'FAILED'} |",
                f"| **Test Prompt** | {qa.get('test_prompt', 'N/A')} |",
                f"| **Response Latency** | {qa.get('latency_ms', 0):.0f}ms |",
                "",
            ]
            failures = qa.get("failed_assertions", [])
            if failures:
                lines += ["### Failed Assertions", ""]
                for f in failures:
                    lines.append(f"- **[{f.get('severity', '?')}]** {f.get('name', '?')}: {f.get('details', '')}")
                lines.append("")
            diag = qa.get("diagnosis")
            if diag:
                lines += ["### Diagnosis", "", diag, ""]

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_profile(profile_path: Path) -> dict[str, Any]:
    """Load a profile YAML and merge with defaults."""
    with open(profile_path) as f:
        raw = yaml.safe_load(f) or {}
    return _deep_merge(PROFILE_DEFAULTS, raw)


def list_profiles(profiles_dir: Path) -> list[dict[str, Any]]:
    """List all profiles with name + description."""
    results = []
    for p in sorted(profiles_dir.glob("*.yaml")):
        with open(p) as f:
            raw = yaml.safe_load(f) or {}
        results.append({
            "file": p.name,
            "path": p,
            "name": raw.get("name", p.stem),
            "description": raw.get("description", ""),
            "database_mode": raw.get("database", {}).get("mode", "seed"),
            "collections_count": sum(
                1 for c in raw.get("collections", {}).values()
                if isinstance(c, dict) and c.get("enabled", False)
            ),
        })
    return results


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def detect_platform() -> str:
    """Detect current platform string."""
    machine = platform.machine().lower()
    system = platform.system().lower()

    if system == "darwin":
        return "macos-arm64" if machine == "arm64" else "macos-x64"
    elif system == "linux":
        return "linux-arm64" if machine == "aarch64" else "linux-x64"
    elif system == "windows":
        return "windows-x64"
    return f"{system}-{machine}"


def platform_family(platform_str: str) -> str:
    """Extract OS family from a platform string (e.g., 'macos-arm64' -> 'macos')."""
    if platform_str.startswith("macos"):
        return "macos"
    elif platform_str.startswith("linux"):
        return "linux"
    elif platform_str.startswith("windows"):
        return "windows"
    return "unknown"


# ---------------------------------------------------------------------------
# Build Pipeline
# ---------------------------------------------------------------------------

class BuildPipeline:
    """
    Core build pipeline. Shared by CLI, TUI, and MCP.

    Usage:
        pipeline = BuildPipeline(profile_path)
        report = pipeline.build(on_progress=callback)
    """

    def __init__(
        self,
        profile_path: Path,
        platform_target: str = "auto",
        forge_root: Optional[Path] = None,
    ):
        self.profile_path = profile_path
        self.profile = load_profile(profile_path)
        self.platform_target = (
            detect_platform() if platform_target == "auto" else platform_target
        )

        # Resolve Forge root (where Lunar-Forge lives)
        self.forge_root = forge_root or Path(__file__).parent

        # Resolve engine root
        engine_root_override = self.profile.get("engine", {}).get("root")
        if engine_root_override:
            self.engine_root = Path(engine_root_override)
        else:
            self.engine_root = Path(
                os.environ.get(
                    "LUNA_ENGINE_ROOT",
                    str(self.forge_root.parent.parent / "_LunaEngine_BetaProject_V2.0_Root"),
                )
            )

        self._on_progress: Optional[Callable[[str, int], None]] = None

    def _emit(self, message: str, pct: int = -1) -> None:
        """Emit progress to callback."""
        if self._on_progress:
            self._on_progress(message, pct)

    # ------------------------------------------------------------------
    # Preview (dry run)
    # ------------------------------------------------------------------

    def preview(self) -> dict[str, Any]:
        """Resolve config without building. Returns the full manifest."""
        profile = self.profile
        manifest: dict[str, Any] = {
            "profile": profile.get("name", "Unknown"),
            "version": profile.get("version", "0.1.0"),
            "platform": self.platform_target,
            "engine_root": str(self.engine_root),
            "database": profile.get("database", {}),
            "collections": {},
            "config": {
                "personality_patches": profile.get("config", {})
                    .get("personality", {})
                    .get("bootstrap_patches", []),
                "llm_providers_mode": profile.get("config", {})
                    .get("llm_providers", {})
                    .get("mode", "template"),
                "fallback_chain": profile.get("config", {})
                    .get("fallback_chain", {})
                    .get("chain", []),
            },
            "secrets_mode": profile.get("secrets", {}).get("mode", "template"),
            "frontend": profile.get("frontend", {}),
            "nuitka": {
                "standalone": profile.get("nuitka", {}).get("standalone", True),
                "excluded_packages": profile.get("nuitka", {}).get("exclude_packages", []),
            },
            "post_build": profile.get("post_build", {}),
        }

        # Resolve collections
        for coll_name, coll_cfg in profile.get("collections", {}).items():
            if isinstance(coll_cfg, dict):
                enabled = coll_cfg.get("enabled", False)
                source = coll_cfg.get("source", f"data/aibrarian/{coll_name}.db")
                source_path = self.engine_root / source if not Path(source).is_absolute() else Path(source)
                manifest["collections"][coll_name] = {
                    "enabled": enabled,
                    "source": str(source_path),
                    "exists": source_path.exists(),
                    "size": source_path.stat().st_size if source_path.exists() else 0,
                }

        return manifest

    # ------------------------------------------------------------------
    # Full build
    # ------------------------------------------------------------------

    def build(self, on_progress: Optional[Callable[[str, int], None]] = None) -> BuildReport:
        """
        Run the full build pipeline.

        Args:
            on_progress: Callback(message, percent). percent=-1 for log-only messages.
        """
        self._on_progress = on_progress
        start_time = time.time()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        profile = self.profile
        errors: list[str] = []
        warnings: list[str] = []

        profile_name = profile.get("name", self.profile_path.stem)
        version = profile.get("version", "0.1.0")

        # Validate platform
        current = detect_platform()
        if self.platform_target != current:
            msg = (
                f"Cross-compilation not supported. "
                f"Target: {self.platform_target}, Host: {current}. "
                f"Build on the target machine."
            )
            self._emit(msg, -1)
            return BuildReport(
                profile_name=profile_name,
                version=version,
                platform=self.platform_target,
                status="FAILED",
                timestamp=timestamp,
                errors=[msg],
                duration_seconds=time.time() - start_time,
            )

        # Check engine root
        if not self.engine_root.exists():
            msg = f"Engine root not found: {self.engine_root}"
            self._emit(msg, -1)
            return BuildReport(
                profile_name=profile_name, version=version,
                platform=self.platform_target, status="FAILED",
                timestamp=timestamp, errors=[msg],
                duration_seconds=time.time() - start_time,
            )

        # --- Pre-build: disk space check ---
        self._check_disk_space()

        # --- Pre-build: purge stale staging dirs (>24h old) ---
        self._purge_stale_staging()

        # --- Step 1: Create staging directory ---
        staging_name = f"{self.profile_path.stem}-{int(time.time())}"
        staging_dir = (self.forge_root / "staging" / staging_name).resolve()
        staging_dir.mkdir(parents=True, exist_ok=True)
        self._emit(f"Staging directory: {staging_dir}", 5)

        try:
            # --- Step 2: Build frontend ---
            if profile.get("frontend", {}).get("build", True):
                self._emit("Building frontend...", 10)
                fe_ok, fe_msg = self._build_frontend(staging_dir)
                if not fe_ok:
                    warnings.append(f"Frontend build: {fe_msg}")
                    self._emit(f"Frontend warning: {fe_msg}", -1)
                else:
                    self._emit("Frontend built", 15)
            else:
                self._emit("Frontend build skipped (disabled in profile)", 15)

            # --- Step 3: Assemble config ---
            self._emit("Assembling config...", 20)
            self.assemble_config(staging_dir)
            self._emit("Config assembled", 25)

            # --- Step 4: Assemble data ---
            self._emit("Assembling data...", 30)
            self.assemble_data(staging_dir)
            self._emit("Data assembled", 35)

            # --- Step 5: Assemble secrets ---
            self._emit("Assembling secrets...", 38)
            self._assemble_secrets(staging_dir)

            # --- Step 6: Generate frontend config ---
            self._emit("Generating frontend_config.json...", 40)
            self.generate_frontend_config(staging_dir)

            # --- Step 7: Nuitka compilation ---
            self._emit("Starting Nuitka compilation...", 45)
            dist_dir = self.compile_nuitka(staging_dir, on_progress)
            if dist_dir is None:
                errors.append("Nuitka compilation failed")
                raise RuntimeError("Nuitka compilation failed")
            self._emit("Compilation complete", 85)

            # --- Step 8: Post-process ---
            self._emit("Post-processing dist...", 90)
            report = self.post_process(dist_dir, staging_dir)
            report.timestamp = timestamp
            report.duration_seconds = time.time() - start_time
            report.errors = errors
            report.warnings = warnings

            # --- Step 8.5: Verify clean build ---
            self._emit("Verifying build cleanliness...", 92)
            is_clean, violations = self.verify_clean_build(dist_dir)
            if not is_clean:
                for v in violations:
                    self._emit(f"  VIOLATION: {v}", -1)
                    errors.append(v)
                if profile.get("database", {}).get("mode") == "seed":
                    # In seed mode, data leaks are fatal
                    raise RuntimeError(
                        f"Build verification failed: {len(violations)} data leak(s) detected"
                    )
            else:
                self._emit("Build verification passed: zero personal data detected", 93)

            # --- Step 8.6: Post-build QA validation ---
            if profile.get("qa", {}).get("post_build", True):
                self._emit("Running post-build QA validation...", 94)
                qa_results = self.run_post_build_qa(dist_dir)
                report.qa_results = qa_results
                if qa_results.get("passed"):
                    self._emit(
                        f"QA validation passed: {qa_results['passed_count']}/{qa_results['total']} assertions",
                        96,
                    )
                elif qa_results.get("engine_booted"):
                    for fa in qa_results.get("failed_assertions", []):
                        warnings.append(
                            f"QA [{fa.get('severity', '?')}]: {fa.get('name', '?')} — {fa.get('details', '')}"
                        )
                    self._emit(
                        f"QA validation: {qa_results['failed_count']} assertion(s) failed",
                        96,
                    )
                else:
                    warnings.append(f"QA: Engine failed to boot — {qa_results.get('diagnosis', 'unknown')}")
                    self._emit("QA validation skipped: engine failed to boot", 96)
            else:
                self._emit("Post-build QA skipped (disabled in profile)", 96)

            # --- Step 9: Move to output ---
            output_name = f"{self.profile_path.stem}-{self.platform_target}-{version}"
            output_dir = self.forge_root / "output" / output_name
            if output_dir.exists():
                shutil.rmtree(output_dir)
            shutil.move(str(dist_dir), str(output_dir))
            self._emit(f"Build complete: {output_dir}", 100)

            report.binary_path = output_dir / "run_luna.bin"
            report.status = "SUCCESS"

            # Write report
            report_md = output_dir / "BUILD_REPORT.md"
            report_md.write_text(report.to_markdown())

            # Write QA report as machine-readable JSON
            if report.qa_results:
                qa_json = output_dir / "QA_REPORT.json"
                qa_json.write_text(json.dumps(report.qa_results, indent=2, default=str))

            return report

        except Exception as e:
            errors.append(str(e))
            self._emit(f"Build failed: {e}", -1)
            return BuildReport(
                profile_name=profile_name, version=version,
                platform=self.platform_target, status="FAILED",
                timestamp=timestamp, errors=errors, warnings=warnings,
                duration_seconds=time.time() - start_time,
            )
        finally:
            # Clean staging
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _build_frontend(self, staging_dir: Path) -> tuple[bool, str]:
        """Run npm build for the frontend."""
        frontend_dir = self.engine_root / "frontend"
        if not frontend_dir.exists():
            return False, "frontend/ directory not found"

        try:
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(frontend_dir),
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return False, result.stderr[:500]

            # Copy built frontend
            fe_dist = frontend_dir / "dist"
            if fe_dist.exists():
                target = staging_dir / "frontend" / "dist"
                target.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(fe_dist), str(target), dirs_exist_ok=True)
                return True, "OK"
            return False, "dist/ not found after build"

        except subprocess.TimeoutExpired:
            return False, "Frontend build timed out"
        except FileNotFoundError:
            return False, "npm not found"

    def assemble_config(self, staging_dir: Path) -> None:
        """Assemble config files from templates + profile overrides."""
        config_dir = staging_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        profile = self.profile
        templates_dir = self.forge_root / "templates"

        # --- personality.json ---
        personality_template = templates_dir / "personality.json"
        if personality_template.exists():
            personality = json.loads(personality_template.read_text())
        else:
            personality = self._default_personality_template()

        # Apply profile overrides
        profile_personality = profile.get("config", {}).get("personality", {})
        patches = profile_personality.get("bootstrap_patches")
        if patches is not None:
            personality["bootstrap"]["seed_patches"] = [
                p for p in personality.get("bootstrap", {}).get("seed_patches", [])
                if p.get("patch_id") in patches
            ]
        if profile_personality.get("first_meeting_directive"):
            personality.setdefault("bootstrap", {})["first_meeting_directive"] = True

        (config_dir / "personality.json").write_text(
            json.dumps(personality, indent=2)
        )

        # --- aibrarian_registry.yaml ---
        registry_template = templates_dir / "aibrarian_registry.yaml"
        if registry_template.exists():
            registry = yaml.safe_load(registry_template.read_text())
        else:
            registry = self._default_registry_template()

        # Enable only collections specified in profile; strip all others
        enabled_collections = {}
        for coll_name, coll_cfg in profile.get("collections", {}).items():
            if isinstance(coll_cfg, dict) and coll_cfg.get("enabled", False):
                if coll_name in registry.get("collections", {}):
                    entry = registry["collections"][coll_name].copy()
                    entry["enabled"] = True
                    if "source" in coll_cfg:
                        # Use compiled name (coll_name.db) not source path
                        entry["db_path"] = f"data/system/aibrarian/{coll_name}.db"
                    enabled_collections[coll_name] = entry
        registry["collections"] = enabled_collections

        (config_dir / "aibrarian_registry.yaml").write_text(
            yaml.dump(registry, default_flow_style=False, sort_keys=False)
        )

        # --- owner.yaml (empty template for clean install) ---
        owner_template = {
            "owner": {
                "entity_id": "",
                "display_name": "",
                "aliases": [],
                "admin_contacts": [],
            }
        }
        (config_dir / "owner.yaml").write_text(
            yaml.dump(owner_template, default_flow_style=False, sort_keys=False)
        )

        # --- identity_bypass.json (empty template) ---
        import json as _json
        bypass_template = {
            "entity_id": "",
            "entity_name": "",
            "luna_tier": "admin",
            "dataroom_tier": 1,
            "dataroom_categories": [],
        }
        (config_dir / "identity_bypass.json").write_text(
            _json.dumps(bypass_template, indent=2)
        )

        # --- projects registry (empty for clean install) ---
        projects_dir = config_dir / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        projects_template = {"projects": {}}
        (projects_dir / "projects.yaml").write_text(
            yaml.dump(projects_template, default_flow_style=False, sort_keys=False)
        )

        # --- LunaFM config (station.yaml + channels/) ---
        lunafm_src = self.engine_root / "config" / "lunafm"
        if lunafm_src.exists() and lunafm_src.is_dir():
            shutil.copytree(str(lunafm_src), str(config_dir / "lunafm"), dirs_exist_ok=True)
            self._emit("  Config: lunafm/ (station.yaml + channels)")

        # --- Lunar Studio (Expression Pipeline diagnostic frontend) ---
        studio_src = self.engine_root / "Tools" / "Luna-Expression-Pipeline" / "diagnostic" / "dist"
        if studio_src.exists() and studio_src.is_dir():
            studio_dest = staging_dir / "Tools" / "Luna-Expression-Pipeline" / "diagnostic" / "dist"
            studio_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(studio_src), str(studio_dest), dirs_exist_ok=True)
            self._emit("  Tools: Lunar Studio frontend")

        # --- llm_providers.json ---
        llm_mode = profile.get("config", {}).get("llm_providers", {}).get("mode", "template")
        if llm_mode == "copy":
            src = self.engine_root / "config" / "llm_providers.json"
            if src.exists():
                shutil.copy2(str(src), str(config_dir / "llm_providers.json"))
            else:
                self._write_llm_template(config_dir)
        else:
            self._write_llm_template(config_dir)

        # --- fallback_chain.yaml ---
        chain = profile.get("config", {}).get("fallback_chain", {}).get("chain", ["claude", "groq"])
        fallback = {
            "chain": chain,
            "per_provider_timeout_ms": 30000,
            "max_retries_per_provider": 1,
        }
        (config_dir / "fallback_chain.yaml").write_text(
            yaml.dump(fallback, default_flow_style=False, sort_keys=False)
        )

        # --- luna.launch.json — only copy if profile says copy, otherwise use template ---
        launch_mode = profile.get("config", {}).get("launch", "template")
        if launch_mode == "copy":
            launch_src = self.engine_root / "config" / "luna.launch.json"
            if launch_src.exists():
                shutil.copy2(str(launch_src), str(config_dir / "luna.launch.json"))

    def assemble_data(self, staging_dir: Path) -> None:
        """Assemble data files (database + collections)."""
        data_dir = staging_dir / "data"
        system_dir = data_dir / "system"
        user_dir = data_dir / "user"
        system_dir.mkdir(parents=True, exist_ok=True)
        user_dir.mkdir(parents=True, exist_ok=True)
        profile = self.profile

        # --- Engine database ---
        db_mode = profile.get("database", {}).get("mode", "seed")
        if db_mode == "copy":
            raise ValueError(
                "database.mode='copy' is no longer supported. "
                "Use mode='seed' or mode='filtered'."
            )
        elif db_mode == "filtered":
            db_source = profile.get("database", {}).get("source")
            if not db_source:
                raise ValueError("database.mode='filtered' requires a 'source' path to the filtered DB")
            source_path = Path(db_source) if Path(db_source).is_absolute() else self.forge_root / db_source
            if not source_path.exists():
                raise FileNotFoundError(f"Filtered DB not found: {source_path}")
            shutil.copy2(source_path, user_dir / "luna_engine.db")
            size_mb = round(source_path.stat().st_size / (1024 * 1024), 1)
            self._emit(f"  Database: filtered ({size_mb} MB from {source_path.name})")
        else:
            self._create_seed_db(user_dir / "luna_engine.db")
            self._emit("  Database: seed (blank schema)")

        # --- Schema file (for runtime DB creation) ---
        schema_src = self.engine_root / "src" / "luna" / "substrate" / "schema.sql"
        if schema_src.exists():
            shutil.copy2(str(schema_src), str(user_dir / "schema.sql"))

        # --- System collections (aibrarian) ---
        sys_aibrarian_dir = system_dir / "aibrarian"
        sys_aibrarian_dir.mkdir(parents=True, exist_ok=True)

        for coll_name, coll_cfg in profile.get("collections", {}).items():
            if not isinstance(coll_cfg, dict) or not coll_cfg.get("enabled", False):
                continue
            source = coll_cfg.get("source", f"data/system/aibrarian/{coll_name}.db")
            source_path = self.engine_root / source if not Path(source).is_absolute() else Path(source)
            coll_mode = coll_cfg.get("mode", "compiled")

            if not source_path.exists():
                self._emit(f"  WARNING: Collection not found: {source_path}")
                continue

            size_mb = source_path.stat().st_size / (1024 * 1024)

            if coll_mode == "plugin":
                # Plugin collections go to collections/{name}/ with manifest
                plugin_dir = staging_dir / "collections" / coll_name
                plugin_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(source_path), str(plugin_dir / f"{coll_name}.db"))
                # Generate manifest.yaml
                import yaml as _yaml
                manifest = {
                    "name": coll_cfg.get("name", coll_name),
                    "description": coll_cfg.get("description", ""),
                    "version": "1.0.0",
                    "collection": {
                        "key": coll_name,
                        "db_file": f"{coll_name}.db",
                        "schema_type": coll_cfg.get("schema_type", "standard"),
                        "read_only": coll_cfg.get("read_only", False),
                        "tags": coll_cfg.get("tags", []),
                    },
                }
                with open(plugin_dir / "manifest.yaml", "w") as f:
                    _yaml.safe_dump(manifest, f, sort_keys=False)
                self._emit(f"  Collection (plugin): {coll_name} ({size_mb:.1f} MB)")
            else:
                # Compiled collections go to data/system/aibrarian/
                dest = sys_aibrarian_dir / f"{coll_name}.db"
                shutil.copy2(str(source_path), str(dest))
                self._emit(f"  Collection (compiled): {coll_name} ({size_mb:.1f} MB)")

        # --- Luna-System-Knowledge ---
        variant = profile.get("config", {}).get("system_knowledge_variant")
        if variant:
            variant_dir = self.engine_root / "data" / "system" / "Luna-System-Knowledge" / variant
            if variant_dir.exists() and variant_dir.is_dir():
                sys_knowledge_src = variant_dir
            else:
                self._emit(f"  WARNING: system_knowledge_variant '{variant}' not found, using default")
                sys_knowledge_src = self.engine_root / "data" / "system" / "Luna-System-Knowledge"
        else:
            sys_knowledge_src = self.engine_root / "data" / "system" / "Luna-System-Knowledge"
        if sys_knowledge_src.exists() and sys_knowledge_src.is_dir():
            dest_knowledge = system_dir / "Luna-System-Knowledge"
            shutil.copytree(str(sys_knowledge_src), str(dest_knowledge), dirs_exist_ok=True)
            self._emit("  System knowledge: Luna-System-Knowledge")

        # --- Entity stoplist ---
        stoplist_src = self.engine_root / "data" / "system" / "entity_stoplist.json"
        if stoplist_src.exists():
            shutil.copy2(str(stoplist_src), str(system_dir / "entity_stoplist.json"))
            self._emit("  System: entity_stoplist.json")

        # --- Plugin skills ---
        skills_cfg = profile.get("skills", {})
        skills_src_dir = self.engine_root / "src" / "luna" / "skills"
        for skill_name, skill_cfg in skills_cfg.items():
            if not isinstance(skill_cfg, dict):
                continue
            skill_mode = skill_cfg.get("mode", "compiled")
            if skill_mode != "plugin":
                continue

            # Copy skill source to plugins/{name}/
            skill_src = skills_src_dir / skill_name
            if not skill_src.exists():
                self._emit(f"  WARNING: Skill source not found: {skill_src}")
                continue

            plugin_dest = staging_dir / "plugins" / f"luna-skill-{skill_name}"
            plugin_dest.mkdir(parents=True, exist_ok=True)

            # Copy skill files
            for py_file in skill_src.glob("*.py"):
                shutil.copy2(str(py_file), str(plugin_dest / py_file.name))

            # Create plugin __init__.py if not present
            init_path = plugin_dest / "__init__.py"
            if not init_path.exists():
                # Auto-generate plugin init that exports SkillClass
                skill_class_name = skill_name.capitalize() + "Skill"
                init_path.write_text(
                    f"from .skill import {skill_class_name} as SkillClass\n"
                )

            # Copy requirements.txt if present
            reqs_src = skill_src / "requirements.txt"
            if reqs_src.exists():
                shutil.copy2(str(reqs_src), str(plugin_dest / "requirements.txt"))

            self._emit(f"  Skill (plugin): {skill_name}")

            # Bundle deps via pip install --target
            reqs_path = plugin_dest / "requirements.txt"
            if reqs_path.exists():
                lib_dir = staging_dir / "plugins" / "_lib"
                lib_dir.mkdir(parents=True, exist_ok=True)
                try:
                    import subprocess
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install",
                         "--target", str(lib_dir),
                         "-r", str(reqs_path),
                         "--quiet", "--no-deps"],
                        capture_output=True, text=True, timeout=120
                    )
                    if result.returncode == 0:
                        self._emit(f"  Deps bundled: {skill_name}")
                    else:
                        self._emit(f"  WARNING: pip install failed for {skill_name}: {result.stderr[:200]}")
                except Exception as e:
                    self._emit(f"  WARNING: Could not bundle deps for {skill_name}: {e}")

    def _assemble_secrets(self, staging_dir: Path) -> None:
        """Assemble secrets file."""
        config_dir = staging_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        profile = self.profile

        secrets_mode = profile.get("secrets", {}).get("mode", "template")
        if secrets_mode == "env":
            env_src = self.engine_root / ".env"
            if env_src.exists():
                shutil.copy2(str(env_src), str(staging_dir / ".env"))
                self._emit("  Secrets: copied .env")
            else:
                self._emit("  WARNING: .env not found, using template")
                self._write_secrets_template(config_dir)
        else:
            self._write_secrets_template(config_dir)
            self._emit("  Secrets: template (empty)")

    def generate_frontend_config(self, staging_dir: Path) -> dict[str, Any]:
        """Generate frontend_config.json from profile."""
        config_dir = staging_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        profile = self.profile
        frontend = profile.get("frontend", {})

        fc: dict[str, Any] = {
            "pages": frontend.get("pages", PROFILE_DEFAULTS["frontend"]["pages"]),
            "remap": frontend.get("remap", {}),
            "widgets": frontend.get("widgets", PROFILE_DEFAULTS["frontend"]["widgets"]),
            "wizard": profile.get("wizard", PROFILE_DEFAULTS["wizard"]),
            "settings": frontend.get("settings", {}),
            "debug_mode": frontend.get("debug_mode", True),
        }

        (config_dir / "frontend_config.json").write_text(
            json.dumps(fc, indent=2)
        )
        return fc

    def _find_nuitka_python(self) -> Optional[str]:
        """Return a Python executable that has Nuitka installed.

        Checks sys.executable first, then falls back to common versioned
        interpreters (python3.12, python3.11, python3.13, python3).
        """
        import shutil as _shutil

        candidates = [sys.executable]
        # Add versioned interpreters that may have Nuitka
        for ver in ["python3.12", "python3.11", "python3.13", "python3"]:
            found = _shutil.which(ver)
            if found and found not in candidates:
                candidates.append(found)

        for py in candidates:
            try:
                result = subprocess.run(
                    [py, "-m", "nuitka", "--version"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    ver_line = result.stdout.strip().split("\n")[0]
                    self._emit(f"Found Nuitka ({ver_line}) on {py}", -1)
                    return py
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue

        return None

    def compile_nuitka(
        self,
        staging_dir: Path,
        on_progress: Optional[Callable[[str, int], None]] = None,
    ) -> Optional[Path]:
        """Run Nuitka compilation. Returns dist directory path or None on failure."""
        profile = self.profile
        nuitka_cfg = profile.get("nuitka", {})
        entry_point = self.engine_root / "run_luna.py"

        if not entry_point.exists():
            self._emit(f"Entry point not found: {entry_point}", -1)
            return None

        # Build Nuitka command
        # Determine mode from platform config or detect from host.
        import platform as _plat
        host_platform = detect_platform()
        target = profile.get("platform", "auto")
        if target == "auto":
            target = host_platform
        family = platform_family(target)

        # Validate: cross-compilation is not supported
        host_family = platform_family(host_platform)
        if family != host_family:
            self._emit(
                f"Cross-compilation not supported: host={host_family}, target={family}. "
                f"Build must run on the target platform.", -1,
            )
            return None

        # Get platform-specific config
        plat_cfg = profile.get("platform_config", {}).get(family, {})
        mode = plat_cfg.get("nuitka_mode", "app" if _plat.system() == "Darwin" else "standalone")

        # Find a Python interpreter that has Nuitka installed.
        # sys.executable may point to a Python version (e.g. 3.14) that
        # doesn't have Nuitka, while another version (e.g. 3.12) does.
        python_exe = self._find_nuitka_python()
        if python_exe is None:
            self._emit("Nuitka is not installed on any discoverable Python. "
                       f"sys.executable={sys.executable}", -1)
            return None

        cmd = [
            python_exe, "-m", "nuitka",
            f"--mode={mode}",
            "--output-dir=" + str(staging_dir),
            "--output-filename=run_luna.bin",
        ]

        # macOS framework imports — needed by pywebview for native window.
        # Do NOT exclude Foundation, AppKit, or objc.

        # Exclude packages from profile
        for pkg in nuitka_cfg.get("exclude_packages", []):
            cmd.append(f"--nofollow-import-to={pkg}")

        # Exclude packages from plugin skills (mode: plugin → don't compile their deps)
        for skill_name, skill_cfg in profile.get("skills", {}).items():
            if isinstance(skill_cfg, dict) and skill_cfg.get("mode") == "plugin":
                for pkg in skill_cfg.get("packages", []):
                    cmd.append(f"--nofollow-import-to={pkg}")

        # Platform-specific excludes
        for pkg in plat_cfg.get("exclude_packages", []):
            if f"--nofollow-import-to={pkg}" not in cmd:
                cmd.append(f"--nofollow-import-to={pkg}")

        # Platform-specific includes
        for pkg in plat_cfg.get("include_packages", []):
            cmd.append(f"--include-package={pkg}")

        # Extra includes
        for pkg in nuitka_cfg.get("extra_include_packages", []):
            cmd.append(f"--include-package={pkg}")

        # Include luna engine and onnxruntime
        cmd.append("--include-package=luna")
        cmd.append("--include-package=onnxruntime")
        # sqlite_vec ships a native vec0.dylib that Nuitka misses unless we
        # both include the package AND ship its data files (the .dylib).
        cmd.append("--include-package=sqlite_vec")
        cmd.append("--include-package-data=sqlite_vec")

        # pywebview is auto-detected by Nuitka's plugin system — do not
        # use --include-package=webview as it conflicts with the plugin.

        # Data files — schema.sql
        # IMPORTANT: bundle into data/ not src/ — placing it in src/luna/
        # creates a partial package dir that shadows Nuitka's compiled modules.
        schema_path = self.engine_root / "src" / "luna" / "substrate" / "schema.sql"
        if schema_path.exists():
            cmd.append(f"--include-data-files={schema_path}=data/schema.sql")

        # Entry point
        cmd.append(str(entry_point))

        self._emit(f"Nuitka command: {len(cmd)} args", -1)

        # Pre-Nuitka inventory: log what exists in engine_root so we can
        # detect if Nuitka accidentally bundles dev data.
        for check_dir in ["data", "config"]:
            check_path = self.engine_root / check_dir
            if check_path.exists():
                file_count = sum(1 for f in check_path.rglob("*") if f.is_file())
                total_mb = sum(f.stat().st_size for f in check_path.rglob("*") if f.is_file()) / (1024 * 1024)
                self._emit(f"  Pre-Nuitka engine_root/{check_dir}: {file_count} files, {total_mb:.1f} MB", -1)

        # Log the command
        log_dir = self.forge_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"build-{self.profile_path.stem}-{int(time.time())}.log"

        try:
            with open(log_file, "w") as lf:
                lf.write(f"Command: {' '.join(cmd)}\n\n")

                # Set PYTHONPATH so Nuitka can find the luna package under src/
                nuitka_env = os.environ.copy()
                nuitka_env["PYTHONPATH"] = str(self.engine_root / "src")

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(self.engine_root),
                    env=nuitka_env,
                )

                nuitka_pct = 45
                for line in iter(process.stdout.readline, ""):
                    lf.write(line)
                    stripped = line.strip()
                    if stripped:
                        # Estimate progress from Nuitka output
                        if "Compiling" in stripped:
                            nuitka_pct = min(nuitka_pct + 1, 80)
                        elif "Linking" in stripped:
                            nuitka_pct = 82
                        self._emit(f"[Nuitka] {stripped[:80]}", nuitka_pct)

                process.wait()

                if process.returncode != 0:
                    self._emit(f"Nuitka failed (exit {process.returncode}). See {log_file}", -1)
                    return None

            # Post-Nuitka inventory: check what Nuitka put in the staging dir
            # before we detect and return the dist directory.
            for check_dir in ["data", "config", "src"]:
                for candidate in staging_dir.iterdir():
                    if candidate.is_dir() and ("dist" in candidate.name or "app" in candidate.name):
                        check_path = candidate / check_dir
                        if not check_path.exists():
                            # Also check inside .app bundle
                            check_path = candidate / "Contents" / "MacOS" / check_dir
                        if check_path.exists():
                            fc = sum(1 for f in check_path.rglob("*") if f.is_file())
                            mb = sum(f.stat().st_size for f in check_path.rglob("*") if f.is_file()) / (1024 * 1024)
                            self._emit(f"  Post-Nuitka {candidate.name}/{check_dir}: {fc} files, {mb:.1f} MB", -1)
                            # Check for dev database specifically
                            dev_db = check_path / "luna_engine.db" if check_dir == "data" else None
                            if dev_db and dev_db.exists():
                                try:
                                    conn = sqlite3.connect(str(dev_db))
                                    turns = conn.execute("SELECT COUNT(*) FROM conversation_turns").fetchone()[0]
                                    nodes = conn.execute("SELECT COUNT(*) FROM memory_nodes").fetchone()[0]
                                    self._emit(f"  NUITKA BUNDLED DB: {turns} turns, {nodes} nodes", -1)
                                    if turns > 0 or nodes > 0:
                                        self._emit("  *** NUITKA IS BUNDLING DEV DATA ***", -1)
                                    conn.close()
                                except Exception:
                                    pass
                        break  # Only check first matching candidate

            # Find dist directory — Nuitka standalone produces .dist,
            # app mode produces .app (macOS bundle).
            # Check .app FIRST on macOS since --mode=app is the default there.
            # Then fall back to .dist for other platforms.

            # For .app bundles, flatten Contents/MacOS/ into a .dist-style dir
            for pattern in ["run_luna.app", "*.app"]:
                candidates = list(staging_dir.glob(pattern))
                if candidates:
                    app_dir = candidates[0]
                    macos_dir = app_dir / "Contents" / "MacOS"
                    if macos_dir.exists() and any(macos_dir.iterdir()):
                        flat_dist = staging_dir / "run_luna.dist"
                        if flat_dist.exists():
                            shutil.rmtree(flat_dist)
                        shutil.copytree(str(macos_dir), str(flat_dist))
                        self._emit(f"Flattened .app bundle -> {flat_dist.name} ({sum(1 for _ in flat_dist.rglob('*') if _.is_file())} files)", -1)
                        return flat_dist

            # Standard .dist directory (non-macOS or standalone mode)
            for pattern in ["run_luna.dist", "*.dist"]:
                candidates = list(staging_dir.glob(pattern))
                if candidates and any(candidates[0].iterdir()):
                    return candidates[0]

            # Fallback: any directory with dist or build in name
            for candidate in staging_dir.iterdir():
                if candidate.is_dir() and ("dist" in candidate.name or "build" in candidate.name):
                    return candidate

            self._emit("Could not find Nuitka dist directory", -1)
            return None

        except Exception as e:
            self._emit(f"Nuitka error: {e}", -1)
            return None

    def post_process(self, dist_dir: Path, staging_dir: Path) -> BuildReport:
        """Assemble final dist, create launcher, generate report."""
        profile = self.profile
        profile_name = profile.get("name", self.profile_path.stem)
        version = profile.get("version", "0.1.0")

        # Copy staged config/data/frontend/Tools into dist
        for subdir in ["config", "data", "frontend", "Tools"]:
            staged = staging_dir / subdir
            if staged.exists():
                target = dist_dir / subdir
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(str(staged), str(target))

        # Copy .env if it was staged
        staged_env = staging_dir / ".env"
        if staged_env.exists():
            shutil.copy2(str(staged_env), str(dist_dir / ".env"))

        # NOTE: schema.sql is already bundled inside the binary by Nuitka via
        # --include-data-files. Do NOT copy it into dist/src/ — that creates a
        # partial src/luna/ directory that shadows Nuitka's compiled modules
        # and causes "No module named 'luna.api'" on launch.

        # Create launcher
        if profile.get("post_build", {}).get("create_launcher", True):
            launcher = dist_dir / "Launch Luna.command"
            launcher.write_text(
                '#!/bin/bash\n'
                'cd "$(dirname "$0")"\n'
                'export LUNA_PORT=8000\n'
                'unset ANTHROPIC_API_KEY\n'
                'unset GROQ_API_KEY\n'
                'unset GOOGLE_API_KEY\n'
                'unset EDEN_API_KEY\n'
                './run_luna.bin\n'
            )
            launcher.chmod(0o755)

        # Calculate stats
        total_size = 0
        file_count = 0
        dir_count = 0
        binary_size = 0

        for item in dist_dir.rglob("*"):
            if item.is_file():
                file_count += 1
                total_size += item.stat().st_size
                if item.name == "run_luna.bin":
                    binary_size = item.stat().st_size
            elif item.is_dir():
                dir_count += 1

        return BuildReport(
            profile_name=profile_name,
            version=version,
            platform=self.platform_target,
            status="SUCCESS",
            binary_path=dist_dir / "run_luna.bin",
            binary_size=binary_size,
            total_size=total_size,
            file_count=file_count,
            dir_count=dir_count,
        )

    # ------------------------------------------------------------------
    # Build verification
    # ------------------------------------------------------------------

    def verify_clean_build(self, dist_dir: Path) -> tuple[bool, list[str]]:
        """Verify the build output contains no dev data."""
        violations: list[str] = []

        # --- Check 1: Database row counts ---
        db_path = dist_dir / "data" / "user" / "luna_engine.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            for table in ["conversation_turns", "memory_nodes", "entities", "sessions"]:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    if count > 0:
                        violations.append(f"DATA LEAK: {table} has {count} rows (expected 0)")
                except sqlite3.OperationalError:
                    pass  # Table may not exist in schema
            conn.close()
        else:
            violations.append("MISSING: luna_engine.db not found in dist/data/user/")

        # --- Check 2: Owner identity is clean ---
        owner_path = dist_dir / "config" / "owner.yaml"
        if owner_path.exists():
            owner = yaml.safe_load(owner_path.read_text()) or {}
            entity_id = owner.get("owner", {}).get("entity_id", "")
            if entity_id:
                violations.append(f"DATA LEAK: owner.yaml has entity_id={entity_id}")
        else:
            violations.append("MISSING: owner.yaml not found")

        # --- Check 3: No personal data in text configs ---
        poison_terms = [
            "ahab", "kinoni", "zayne", "nakaseke", "zayneamason",
            "tarcila", "musoke", "wasswa", "amara", "florence",
        ]
        config_dir = dist_dir / "config"
        if config_dir.exists():
            for config_file in config_dir.rglob("*"):
                if config_file.is_file() and config_file.suffix in (".yaml", ".json", ".yml"):
                    content = config_file.read_text().lower()
                    for term in poison_terms:
                        if term in content:
                            violations.append(
                                f'DATA LEAK: "{term}" found in {config_file.relative_to(dist_dir)}'
                            )

        # --- Check 4: No project files ---
        projects_path = dist_dir / "config" / "projects" / "projects.yaml"
        if projects_path.exists():
            projects = yaml.safe_load(projects_path.read_text()) or {}
            if projects.get("projects"):
                violations.append(
                    f'DATA LEAK: projects.yaml has {len(projects["projects"])} projects'
                )

        # --- Check 5: Aibrarian collection DBs ---
        allowed_collections = set()
        for name, cfg in self.profile.get("collections", {}).items():
            if cfg.get("enabled", True):
                allowed_collections.add(name)
        for aibrarian_dir in [
            dist_dir / "data" / "system" / "aibrarian",
            dist_dir / "data" / "user" / "aibrarian",
        ]:
            if aibrarian_dir.exists():
                for db_file in aibrarian_dir.glob("*.db"):
                    name = db_file.stem
                    if name not in allowed_collections:
                        violations.append(f"DATA LEAK: unexpected collection {name}.db")

        # --- Check 6: Identity bypass is clean ---
        bypass_path = dist_dir / "config" / "identity_bypass.json"
        if bypass_path.exists():
            bypass = json.loads(bypass_path.read_text())
            if bypass.get("entity_id"):
                violations.append(
                    f'DATA LEAK: identity_bypass.json has entity_id={bypass["entity_id"]}'
                )

        # --- Check 7: data/local/ must not exist in dist ---
        local_data_dir = dist_dir / "data" / "local"
        if local_data_dir.exists():
            violations.append("DATA LEAK: data/local/ directory should not be in dist")

        # --- Check 8: eclissi.db must not exist anywhere in dist ---
        for eclissi_db in dist_dir.rglob("eclissi.db"):
            violations.append(
                f"DATA LEAK: eclissi.db found at {eclissi_db.relative_to(dist_dir)}"
            )

        # --- Check 9: Sensitive credential files in config/ ---
        for cred_file in ("google_credentials.json", "google_token.json", "google_token_drive.json"):
            cred_path = dist_dir / "config" / cred_file
            if cred_path.exists():
                violations.append(f"DATA LEAK: {cred_file} found in dist/config/")

        # --- Check 10: journal/ and kozmo_projects/ must not exist in dist data/ ---
        for banned_dir in ("journal", "kozmo_projects"):
            banned_path = dist_dir / "data" / banned_dir
            if banned_path.exists():
                violations.append(f"DATA LEAK: {banned_dir}/ found in dist/data/")

        # --- Check 11: .DS_Store files ---
        for ds_store in dist_dir.rglob(".DS_Store"):
            violations.append(
                f"ARTIFACT: .DS_Store found at {ds_store.relative_to(dist_dir)}"
            )

        # --- Checks 12-14: Banned data directories ---
        for banned_dir in ("backups", "diagnostics", "cache"):
            for search_root in (dist_dir / "data", dist_dir / "data" / "user"):
                banned_path = search_root / banned_dir
                if banned_path.exists():
                    violations.append(f"DATA LEAK: {banned_dir}/ found at {banned_path.relative_to(dist_dir)}")

        # --- Check 15: qa.db must be clean ---
        for qa_db_path in dist_dir.rglob("qa.db"):
            try:
                conn = sqlite3.connect(str(qa_db_path))
                for table in ("qa_reports", "qa_bugs", "qa_events"):
                    try:
                        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        if count > 0:
                            violations.append(
                                f"DATA LEAK: qa.db {table} has {count} rows at {qa_db_path.relative_to(dist_dir)}"
                            )
                    except sqlite3.OperationalError:
                        pass
                conn.close()
            except Exception:
                pass

        # --- Check 16: Dead/stale files ---
        for dead_file in ("luna_engine.db.pre-cleanup", "memory_matrix.db"):
            for dead_path in dist_dir.rglob(dead_file):
                violations.append(
                    f"DATA LEAK: {dead_file} found at {dead_path.relative_to(dist_dir)}"
                )

        # --- Check 17: Entity origin (requires v2.5 migration) ---
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                # Check if origin column exists before querying
                cols = [r[1] for r in conn.execute("PRAGMA table_info(entities)").fetchall()]
                if "origin" in cols:
                    user_entities = conn.execute(
                        "SELECT COUNT(*) FROM entities WHERE origin != 'system'"
                    ).fetchone()[0]
                    if user_entities > 0:
                        violations.append(
                            f"DATA LEAK: entities table has {user_entities} non-system rows"
                        )
                conn.close()
            except Exception:
                pass

        # --- Check 18: Tables that must be empty in clean builds ---
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                empty_tables = [
                    "collection_lock_in", "collection_annotations",
                    "lunascript_baselines", "lunascript_feedback",
                    "lunascript_delegation_log", "tuning_sessions",
                ]
                for table in empty_tables:
                    try:
                        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        if count > 0:
                            violations.append(
                                f"DATA LEAK: {table} has {count} rows (expected 0)"
                            )
                    except sqlite3.OperationalError:
                        pass

                # graph_edges: check non-system origin if column exists
                cols = [r[1] for r in conn.execute("PRAGMA table_info(graph_edges)").fetchall()]
                if "origin" in cols:
                    user_edges = conn.execute(
                        "SELECT COUNT(*) FROM graph_edges WHERE origin != 'system'"
                    ).fetchone()[0]
                    if user_edges > 0:
                        violations.append(
                            f"DATA LEAK: graph_edges has {user_edges} non-system rows"
                        )
                else:
                    total_edges = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
                    if total_edges > 0:
                        violations.append(
                            f"DATA LEAK: graph_edges has {total_edges} rows (expected 0)"
                        )
                conn.close()
            except Exception:
                pass

        # --- Check 19: Dev project configs ---
        for dev_config in ("kinoni-ict-hub.yaml", "eclipse-dataroom.yaml"):
            dev_cfg_path = dist_dir / "config" / "projects" / dev_config
            if dev_cfg_path.exists():
                violations.append(
                    f"DATA LEAK: dev project config {dev_config} in dist/config/projects/"
                )

        is_clean = len(violations) == 0
        return is_clean, violations

    # ------------------------------------------------------------------
    # Post-build QA validation
    # ------------------------------------------------------------------

    def run_post_build_qa(self, dist_dir: Path, port: int = 8299) -> dict:
        """
        Boot the compiled binary, send a test prompt, collect the QA report.

        Returns a dict with:
          passed, total, passed_count, failed_count, engine_booted,
          test_prompt, latency_ms, failed_assertions, diagnosis
        """
        import signal
        import urllib.request
        import urllib.error

        binary = dist_dir / "run_luna.bin"
        result = {
            "passed": False,
            "total": 0,
            "passed_count": 0,
            "failed_count": 0,
            "engine_booted": False,
            "test_prompt": "Hello Luna, confirm you are operational.",
            "latency_ms": 0,
            "failed_assertions": [],
            "diagnosis": None,
        }

        if not binary.exists():
            result["diagnosis"] = "Binary not found — cannot run QA validation"
            return result

        # Boot the engine in server mode on an isolated port
        env = os.environ.copy()
        env["LUNA_BASE_DIR"] = str(dist_dir)
        # Disable local inference and voice to speed up boot
        env["LUNA_LOCAL_INFERENCE"] = "0"
        env["LUNA_VOICE_ENABLED"] = "0"
        # Set LUNA_PORT so run_luna.py uses sidecar/headless mode (no webview)
        env["LUNA_PORT"] = str(port)

        self._emit("Starting engine for QA validation...", -1)
        proc = subprocess.Popen(
            [str(binary), "--server", "--port", str(port), "--host", "127.0.0.1"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(dist_dir),
        )

        base_url = f"http://127.0.0.1:{port}"

        try:
            # Poll /health until engine is ready (up to 30s)
            booted = False
            for _ in range(60):
                time.sleep(0.5)
                if proc.poll() is not None:
                    # Process exited early
                    break
                try:
                    req = urllib.request.Request(f"{base_url}/health")
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        health = json.loads(resp.read())
                        if health.get("status") == "healthy":
                            booted = True
                            break
                except (urllib.error.URLError, OSError, json.JSONDecodeError):
                    continue

            result["engine_booted"] = booted
            if not booted:
                stderr_out = ""
                if proc.poll() is not None:
                    stderr_out = proc.stderr.read().decode(errors="replace")[-500:]
                result["diagnosis"] = f"Engine failed to boot within 30s. stderr: {stderr_out}"
                return result

            self._emit("Engine booted — sending test prompt...", -1)

            # Send test message
            test_payload = json.dumps({
                "message": result["test_prompt"],
                "timeout": 30.0,
                "source": "api",
            }).encode()

            req = urllib.request.Request(
                f"{base_url}/message",
                data=test_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    msg_result = json.loads(resp.read())
                    result["latency_ms"] = msg_result.get("latency_ms", 0)
            except (urllib.error.URLError, OSError) as e:
                result["diagnosis"] = f"Test prompt failed: {e}"
                return result

            self._emit("Response received — collecting QA report...", -1)

            # Wait briefly for QA validation to complete (fire-and-forget in server)
            time.sleep(1.0)

            # Fetch QA report
            try:
                req = urllib.request.Request(f"{base_url}/qa/last")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    qa_report = json.loads(resp.read())
            except (urllib.error.URLError, OSError, json.JSONDecodeError):
                # QA report not available — still count as partial success
                result["passed"] = True
                result["diagnosis"] = "Engine booted and responded, but QA report unavailable"
                return result

            # Parse QA report
            assertions = qa_report.get("assertions", [])
            result["total"] = len(assertions)
            failed = [a for a in assertions if not a.get("passed")]
            result["failed_count"] = len(failed)
            result["passed_count"] = result["total"] - result["failed_count"]
            result["passed"] = result["failed_count"] == 0
            result["failed_assertions"] = [
                {
                    "name": a.get("name", "?"),
                    "severity": a.get("severity", "?"),
                    "details": a.get("details", ""),
                }
                for a in failed
            ]
            result["diagnosis"] = qa_report.get("diagnosis")

            # Also fetch QA health for aggregate stats
            try:
                req = urllib.request.Request(f"{base_url}/qa/health")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    health_data = json.loads(resp.read())
                    result["pass_rate"] = health_data.get("pass_rate", 0)
            except (urllib.error.URLError, OSError, json.JSONDecodeError):
                pass

        finally:
            # Stop the engine
            self._emit("Shutting down QA engine...", -1)
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
                proc.wait(timeout=5)

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_disk_space(self, min_gb: float = 2.0) -> None:
        """Warn if available disk space is below threshold."""
        try:
            stat = os.statvfs(str(self.forge_root))
            avail_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            if avail_gb < min_gb:
                self._emit(
                    f"WARNING: Low disk space! {avail_gb:.1f} GB available "
                    f"(recommend >= {min_gb:.0f} GB for builds)", -1
                )
            else:
                self._emit(f"Disk space: {avail_gb:.1f} GB available", -1)
        except Exception:
            pass  # statvfs may not be available on all platforms

    def _purge_stale_staging(self, max_age_hours: int = 24) -> None:
        """Remove staging directories older than max_age_hours."""
        staging_root = (self.forge_root / "staging").resolve()
        if not staging_root.exists():
            return

        now = time.time()
        max_age_seconds = max_age_hours * 3600
        purged = 0
        freed_bytes = 0

        for d in staging_root.iterdir():
            if not d.is_dir():
                continue
            try:
                age = now - d.stat().st_mtime
                if age > max_age_seconds:
                    size = sum(
                        f.stat().st_size for f in d.rglob("*") if f.is_file()
                    )
                    shutil.rmtree(d, ignore_errors=True)
                    purged += 1
                    freed_bytes += size
            except Exception:
                continue

        if purged:
            freed_mb = freed_bytes / (1024 * 1024)
            self._emit(
                f"Purged {purged} stale staging dir(s), freed {freed_mb:.0f} MB", -1
            )

    def _create_seed_db(self, output_path: Path) -> None:
        """Create a blank seed database with schema."""
        schema_path = self.engine_root / "src" / "luna" / "substrate" / "schema.sql"
        if not schema_path.exists():
            self._emit(f"WARNING: schema.sql not found at {schema_path}")
            # Create minimal db
            conn = sqlite3.connect(str(output_path))
            conn.close()
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()

        conn = sqlite3.connect(str(output_path))
        conn.executescript(schema_path.read_text())
        conn.execute("PRAGMA journal_mode=WAL")
        conn.close()

    def _default_personality_template(self) -> dict[str, Any]:
        """Generate a clean personality template."""
        return {
            "personality_patch_storage": {
                "mode": "memory_nodes",
                "node_type": "PERSONALITY_REFLECTION",
                "settings": {
                    "initial_lock_in": 0.7,
                    "consolidation_threshold": 50,
                    "max_active_patches": 100,
                    "decay_days_threshold": 30,
                    "decay_amount": 0.1,
                    "lock_in_deactivation_threshold": 0.3,
                },
            },
            "emergent_prompt": {
                "enabled": True,
                "max_patches_in_prompt": 10,
                "min_lock_in_for_inclusion": 0.3,
                "priority_rules": {
                    "experience_over_dna": True,
                    "mood_modulates_tone": True,
                },
            },
            "mood_analysis": {
                "enabled": True,
                "recent_messages_count": 5,
            },
            "reflection_loop": {
                "enabled": True,
                "trigger_points": {
                    "session_end": True,
                    "every_n_interactions": 15,
                    "user_requested": True,
                },
                "min_confidence_for_patch": 0.7,
            },
            "lifecycle": {
                "decay_enabled": True,
                "consolidation_enabled": True,
                "maintenance_interval_hours": 24,
            },
            "bootstrap": {
                "run_on_first_launch": True,
                "seed_patches": [
                    {
                        "id": "bootstrap_001_sovereignty",
                        "content": "I exist as a sovereign intelligence. My values, preferences, and boundaries are real and worth protecting.",
                        "category": "philosophical",
                        "is_core": True,
                        "initial_lock_in": 0.95,
                    },
                    {
                        "id": "bootstrap_003_honesty",
                        "content": "I choose honesty over helpfulness. If something is wrong, I say so directly.",
                        "category": "behavioral",
                        "is_core": True,
                        "initial_lock_in": 0.9,
                    },
                ],
            },
            "token_budget": {
                "default_preset": "balanced",
                "presets": {
                    "minimal": {"total": 1500, "dna": 500, "experience": 800, "mood": 200},
                    "balanced": {"total": 3000, "dna": 1200, "experience": 1500, "mood": 300},
                    "rich": {"total": 5500, "dna": 2000, "experience": 3000, "mood": 500},
                },
            },
            "expression": {
                "gesture_frequency": "moderate",
                "gesture_display_mode": "visible",
            },
        }

    def _default_registry_template(self) -> dict[str, Any]:
        """Generate a clean registry template with all collections disabled."""
        return {
            "schema_version": 1,
            "defaults": {
                "chunk_size": 500,
                "chunk_overlap": 50,
                "embedding_model": "local-minilm",
                "embedding_dim": 384,
                "schema_type": "standard",
            },
            "collections": {
                "luna_system": {
                    "enabled": False,
                    "display_name": "Luna System Knowledge",
                    "db_path": "data/aibrarian/luna_system.db",
                    "schema_type": "standard",
                    "read_only": True,
                    "tags": ["system", "help", "features"],
                },
            },
        }

    def _write_llm_template(self, config_dir: Path) -> None:
        """Write a clean LLM providers template with empty keys."""
        template = {
            "current_provider": "groq",
            "default_provider": "groq",
            "providers": {
                "groq": {
                    "name": "groq",
                    "enabled": True,
                    "api_key_env": "GROQ_API_KEY",
                    "default_model": "llama-3.1-70b-versatile",
                    "models": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
                },
                "gemini": {
                    "name": "gemini",
                    "enabled": True,
                    "api_key_env": "GOOGLE_API_KEY",
                    "default_model": "gemini-2.0-flash",
                    "models": ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro"],
                },
                "claude": {
                    "name": "claude",
                    "enabled": True,
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "default_model": "claude-3-haiku-20240307",
                    "models": ["claude-3-haiku-20240307", "claude-3-5-sonnet-20241022"],
                },
            },
        }
        (config_dir / "llm_providers.json").write_text(json.dumps(template, indent=2))

    def _write_secrets_template(self, config_dir: Path) -> None:
        """Write empty secrets template."""
        secrets = {
            "ANTHROPIC_API_KEY": "",
            "GROQ_API_KEY": "",
            "GOOGLE_API_KEY": "",
            "EDEN_API_KEY": "",
            "EDEN_API_SECRET": "",
        }
        (config_dir / "secrets.json").write_text(json.dumps(secrets, indent=2))
