"""
Lunar Forge — Web UI Backend.

FastAPI server wrapping core.py for browser-based build management.
Serves React frontend from frontend/dist/ in production.

Usage:
    python serve.py                     # start on :8200
    uvicorn serve:app --port 8200       # alternative
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import shutil
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("forge")

# ── Forge imports (relative package) ──

FORGE_ROOT = Path(__file__).parent
ENGINE_ROOT = Path(
    os.environ.get(
        "LUNA_ENGINE_ROOT",
        str(FORGE_ROOT.parent.parent / "_LunaEngine_BetaProject_V2.0_Root"),
    )
)
PROFILES_DIR = FORGE_ROOT / "profiles"
OUTPUT_DIR = FORGE_ROOT / "output"

# Lazy import core — add FORGE_ROOT to sys.path so core.py can be imported directly
_core = None


def _get_core():
    global _core
    if _core is None:
        import sys

        forge_str = str(FORGE_ROOT)
        if forge_str not in sys.path:
            sys.path.insert(0, forge_str)
        import core as _core_mod

        _core = _core_mod
    return _core


# ── Stage matching (from tui/app.py) ──

STAGE_KEYWORDS = {
    "staging": "staging",
    "frontend assets": "frontend",
    "config": "config",
    "data": "data",
    "secrets": "secrets",
    "frontend_config": "frontend_cfg",
    "nuitka": "nuitka",
    "post-process": "post_process",
    "qa validation": "qa",
    "qa engine": "qa",
    "sending test": "qa",
    "output": "output",
    "moving": "output",
}


def _match_stage(message: str) -> Optional[str]:
    lower = message.lower()
    for keyword, stage in STAGE_KEYWORDS.items():
        if keyword in lower:
            return stage
    return None


# ── In-memory build state ──

_builds: dict[str, dict[str, Any]] = {}
_build_lock = threading.Lock()

# ── App ──

app = FastAPI(title="Lunar Forge", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://127.0.0.1:5175"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request models ──


class CollectionOverride(BaseModel):
    model_config = {"strict": True}
    enabled: bool
    mode: Literal["compiled", "plugin"] = "compiled"


class SkillBuildOverride(BaseModel):
    mode: Literal["compiled", "plugin", "exclude"]


class FrontendOverride(BaseModel):
    pages: Optional[dict[str, bool]] = None
    widgets: Optional[dict[str, bool]] = None
    remap: Optional[dict] = None


class ConfigOverrides(BaseModel):
    personality_patches: Optional[list[str]] = None
    fallback_chain: Optional[list[str]] = None
    skills: Optional[dict[str, bool]] = None
    personality: Optional[dict] = None
    directives: Optional[dict] = None


class NuitkaOverride(BaseModel):
    exclude_packages: Optional[list[str]] = None


class BuildOverrides(BaseModel):
    frontend: Optional[FrontendOverride] = None
    collections: Optional[dict[str, CollectionOverride]] = None
    skills: Optional[dict[str, SkillBuildOverride]] = None
    config: Optional[ConfigOverrides] = None
    nuitka: Optional[NuitkaOverride] = None
    settings_overrides: Optional[dict] = None


class BuildRequest(BaseModel):
    profile: str
    platform: str = "auto"
    overrides: Optional[BuildOverrides] = None


# ── Profile endpoints ──


@app.get("/api/profiles")
async def list_profiles_endpoint():
    core = _get_core()
    profiles = core.list_profiles(PROFILES_DIR)
    return profiles


@app.get("/api/profiles/{name}")
async def preview_profile(name: str):
    core = _get_core()
    profile_path = PROFILES_DIR / f"{name}.yaml"
    if not profile_path.exists():
        raise HTTPException(404, f"Profile not found: {name}")
    try:
        pipeline = core.BuildPipeline(profile_path, forge_root=FORGE_ROOT)
        manifest = pipeline.preview()
        return json.loads(json.dumps(manifest, default=str))
    except Exception as exc:
        logger.error("Preview failed for %s: %s", name, traceback.format_exc())
        raise HTTPException(500, detail=f"Failed to generate preview: {exc}")


# ── Build endpoints ──


def _validate_merged_profile(profile: dict) -> list[str]:
    """Validate merged profile YAML structurally. Returns list of errors (empty = valid)."""
    errors = []
    # Collections: enabled=bool, mode=enum
    for name, cfg in profile.get("collections", {}).items():
        if not isinstance(cfg, dict):
            errors.append(f"collections.{name}: expected dict, got {type(cfg).__name__}")
            continue
        e = cfg.get("enabled")
        if e is not None and not isinstance(e, bool):
            errors.append(f"collections.{name}.enabled: expected bool, got {type(e).__name__}: {e!r}")
        m = cfg.get("mode")
        if m is not None and m not in ("compiled", "plugin"):
            errors.append(f"collections.{name}.mode: expected compiled|plugin, got {m!r}")
    # Skills: mode=enum
    for name, cfg in profile.get("skills", {}).items():
        if not isinstance(cfg, dict):
            errors.append(f"skills.{name}: expected dict, got {type(cfg).__name__}")
            continue
        m = cfg.get("mode")
        if m is not None and m not in ("compiled", "plugin", "exclude"):
            errors.append(f"skills.{name}.mode: expected compiled|plugin|exclude, got {m!r}")
    # Frontend: pages/widgets must be bool
    for section in ("pages", "widgets"):
        for key, val in profile.get("frontend", {}).get(section, {}).items():
            if not isinstance(val, bool):
                errors.append(f"frontend.{section}.{key}: expected bool, got {type(val).__name__}: {val!r}")
    # Fallback chain must be list
    chain = profile.get("config", {}).get("fallback_chain", {}).get("chain")
    if chain is not None and not isinstance(chain, list):
        errors.append(f"config.fallback_chain.chain: expected list, got {type(chain).__name__}")
    # Database mode
    db_mode = profile.get("database", {}).get("mode")
    if db_mode is not None and db_mode not in ("seed", "clone", "empty"):
        errors.append(f"database.mode: expected seed|clone|empty, got {db_mode!r}")
    return errors


def _run_preflight(profile: dict) -> dict:
    """Run preflight checks. Returns {passed: bool, checks: [{name, status, detail}]}."""
    checks = []

    # 1. Profile structure valid
    val_errors = _validate_merged_profile(profile)
    if val_errors:
        for ve in val_errors:
            checks.append({"name": "type_safety", "status": "fail", "detail": ve})
    else:
        checks.append({"name": "type_safety", "status": "pass", "detail": "All fields correctly typed"})

    # 2. Collection source DBs exist
    for name, cfg in profile.get("collections", {}).items():
        if not isinstance(cfg, dict) or not cfg.get("enabled"):
            continue
        source = cfg.get("source", "")
        db_path = ENGINE_ROOT / source if source else None
        if db_path and not db_path.exists():
            checks.append({"name": f"collection_{name}_exists", "status": "fail",
                           "detail": f"Collection DB not found: {db_path}"})
        else:
            checks.append({"name": f"collection_{name}_exists", "status": "pass",
                           "detail": f"Found: {db_path}"})

    # 3. Engine source directory exists
    src_dir = ENGINE_ROOT / "src"
    checks.append({"name": "engine_source", "status": "pass" if src_dir.exists() else "fail",
                    "detail": str(src_dir)})

    # 4. Frontend buildable
    fe_dir = ENGINE_ROOT / "frontend"
    node_mods = fe_dir / "node_modules"
    if profile.get("frontend", {}).get("build"):
        checks.append({"name": "frontend_deps",
                        "status": "pass" if node_mods.exists() else "warn",
                        "detail": "node_modules present" if node_mods.exists() else "node_modules missing — npm install needed"})

    # 5. Output directory writable
    output_dir = FORGE_ROOT / "output"
    try:
        output_dir.mkdir(exist_ok=True)
        test_file = output_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        checks.append({"name": "output_writable", "status": "pass", "detail": str(output_dir)})
    except Exception as e:
        checks.append({"name": "output_writable", "status": "fail", "detail": str(e)})

    # 6. Staging directory writable
    staging_dir = FORGE_ROOT / "staging"
    try:
        staging_dir.mkdir(exist_ok=True)
        checks.append({"name": "staging_writable", "status": "pass", "detail": str(staging_dir)})
    except Exception as e:
        checks.append({"name": "staging_writable", "status": "fail", "detail": str(e)})

    # 7. Nuitka available
    if profile.get("nuitka", {}).get("standalone"):
        nuitka_path = shutil.which("nuitka")
        checks.append({"name": "nuitka_available",
                        "status": "pass" if nuitka_path else "fail",
                        "detail": nuitka_path or "nuitka not found in PATH"})

    # 8. Disk space (warn if < 2GB free)
    total, used, free = shutil.disk_usage(str(FORGE_ROOT))
    free_gb = free / (1024**3)
    checks.append({"name": "disk_space",
                    "status": "pass" if free_gb > 2 else "warn",
                    "detail": f"{free_gb:.1f} GB free"})

    passed = all(c["status"] != "fail" for c in checks)
    return {"passed": passed, "checks": checks}


def _merge_overrides(profile_path: Path, overrides: BuildOverrides) -> Path:
    """Merge typed overrides into a temp copy of the profile YAML."""
    import tempfile
    import yaml

    with open(profile_path) as f:
        profile = yaml.safe_load(f) or {}

    ov = overrides.model_dump(exclude_none=True)
    logger.debug("MERGE input: %s", json.dumps(ov, default=str))

    # Frontend overrides
    fe_ov = ov.get("frontend")
    if fe_ov:
        fe = profile.setdefault("frontend", {})
        if "pages" in fe_ov:
            fe["pages"] = fe_ov["pages"]
            logger.debug("MERGE frontend.pages: %s", fe_ov["pages"])
        if "widgets" in fe_ov:
            fe["widgets"] = fe_ov["widgets"]
            logger.debug("MERGE frontend.widgets: %s", fe_ov["widgets"])
        if "remap" in fe_ov:
            fe["remap"] = fe_ov["remap"]

    # Collection overrides — Pydantic guarantees enabled=bool, mode=enum
    coll_ov = ov.get("collections")
    if coll_ov:
        cols = profile.setdefault("collections", {})
        for cname, val in coll_ov.items():
            if cname in cols and isinstance(cols[cname], dict):
                cols[cname]["enabled"] = val["enabled"]
                cols[cname]["mode"] = val["mode"]
            else:
                cols[cname] = {"enabled": val["enabled"], "mode": val["mode"]}
            logger.debug("MERGE collection %s: enabled=%s mode=%s", cname, val["enabled"], val["mode"])

    # Config overrides — patches and fallback chain
    cfg_ov = ov.get("config")
    if cfg_ov:
        cfg = profile.setdefault("config", {})
        if "personality_patches" in cfg_ov:
            cfg.setdefault("personality", {})["bootstrap_patches"] = cfg_ov["personality_patches"]
            logger.debug("MERGE personality_patches: %d items", len(cfg_ov["personality_patches"]))
        if "fallback_chain" in cfg_ov:
            cfg.setdefault("fallback_chain", {})["chain"] = cfg_ov["fallback_chain"]
            logger.debug("MERGE fallback_chain: %s", cfg_ov["fallback_chain"])

    # Nuitka overrides — key matches profile YAML: exclude_packages
    nk_ov = ov.get("nuitka")
    if nk_ov:
        nk = profile.setdefault("nuitka", {})
        if "exclude_packages" in nk_ov:
            nk["exclude_packages"] = nk_ov["exclude_packages"]
            logger.debug("MERGE nuitka.exclude_packages: %d items", len(nk_ov["exclude_packages"]))

    # Skills runtime overrides — toggle individual skills on/off
    skills_runtime_ov = (cfg_ov or {}).get("skills")
    if skills_runtime_ov:
        skills_cfg = profile.setdefault("config", {}).setdefault("skills", {})
        for skill_name, enabled in skills_runtime_ov.items():
            if skill_name in skills_cfg and isinstance(skills_cfg[skill_name], dict):
                skills_cfg[skill_name]["enabled"] = enabled
            logger.debug("MERGE config.skills.%s: enabled=%s", skill_name, enabled)

    # Skills build mode overrides — compiled/plugin/exclude
    skills_build_ov = ov.get("skills")
    if skills_build_ov:
        skills_section = profile.setdefault("skills", {})
        for sname, sval in skills_build_ov.items():
            if sname in skills_section and isinstance(skills_section[sname], dict):
                skills_section[sname]["mode"] = sval["mode"]
            else:
                skills_section[sname] = {"mode": sval["mode"]}
            logger.debug("MERGE skills.%s.mode: %s", sname, sval["mode"])

    # Personality overrides — token budget, expression, bootstrap
    pers_ov = (cfg_ov or {}).get("personality")
    if pers_ov:
        pers = profile.setdefault("config", {}).setdefault("personality", {})
        if "token_budget_preset" in pers_ov:
            pers.setdefault("token_budget", {})["default_preset"] = pers_ov["token_budget_preset"]
        if "gesture_frequency" in pers_ov:
            pers.setdefault("expression", {})["gesture_frequency"] = pers_ov["gesture_frequency"]
        if "run_on_first_launch" in pers_ov:
            pers.setdefault("bootstrap", {})["run_on_first_launch"] = pers_ov["run_on_first_launch"]

    # Settings pre-configuration overrides
    settings_ov = ov.get("settings_overrides")
    if settings_ov:
        cfg = profile.setdefault("config", {})
        if "llm" in settings_ov:
            llm = settings_ov["llm"]
            if "default_provider" in llm:
                fc = cfg.setdefault("fallback_chain", {})
                chain = fc.get("chain", [])
                provider = llm["default_provider"]
                if provider in chain:
                    chain.remove(provider)
                chain.insert(0, provider)
                fc["chain"] = chain
        if "voice" in settings_ov:
            voice_cfg = cfg.setdefault("voice", {})
            voice_cfg.update(settings_ov["voice"])
        if "memory" in settings_ov:
            pers = cfg.setdefault("personality", {})
            pps = pers.setdefault("personality_patch_storage", {})
            pps.update(settings_ov["memory"])

    # Directive overrides — disable specific seed directives
    dir_ov = (cfg_ov or {}).get("directives")
    if dir_ov:
        disabled = set(dir_ov.get("disabled_ids", []))
        dirs = profile.setdefault("config", {}).setdefault("directives_seed", {})
        existing = dirs.get("seed_directives", [])
        dirs["seed_directives"] = [d for d in existing if d.get("id") not in disabled]

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", prefix="forge_override_",
        dir=FORGE_ROOT / "staging", delete=False,
    )
    yaml.dump(profile, tmp, default_flow_style=False, sort_keys=False)
    tmp.close()
    logger.info("MERGE complete — wrote merged profile to %s", tmp.name)
    return Path(tmp.name)


@app.post("/api/build/preflight")
async def preflight_check(req: BuildRequest):
    """Run preflight checks without starting a build."""
    import yaml

    profile_path = PROFILES_DIR / f"{req.profile}.yaml"
    if not profile_path.exists():
        raise HTTPException(404, f"Profile not found: {req.profile}")

    effective_profile = profile_path
    if req.overrides:
        try:
            (FORGE_ROOT / "staging").mkdir(exist_ok=True)
            effective_profile = _merge_overrides(profile_path, req.overrides)
        except Exception as exc:
            logger.error("Preflight merge failed: %s", traceback.format_exc())
            raise HTTPException(500, detail=f"Failed to merge overrides: {exc}")

    with open(effective_profile) as f:
        merged = yaml.safe_load(f) or {}

    # Clean up temp file if we created one
    if effective_profile != profile_path:
        effective_profile.unlink(missing_ok=True)

    return _run_preflight(merged)


@app.post("/api/build", status_code=202)
async def start_build(req: BuildRequest):
    import yaml

    core = _get_core()
    profile_path = PROFILES_DIR / f"{req.profile}.yaml"
    if not profile_path.exists():
        raise HTTPException(404, f"Profile not found: {req.profile}")

    if not _build_lock.acquire(blocking=False):
        raise HTTPException(409, "A build is already in progress")

    # If overrides provided, merge into a temp profile
    effective_profile = profile_path
    if req.overrides:
        try:
            (FORGE_ROOT / "staging").mkdir(exist_ok=True)
            effective_profile = _merge_overrides(profile_path, req.overrides)
        except Exception as exc:
            _build_lock.release()
            logger.error("Override merge failed: %s", traceback.format_exc())
            raise HTTPException(500, detail=f"Failed to apply overrides: {exc}")

    # ── Validation gate — reject structurally invalid profiles ──
    with open(effective_profile) as f:
        merged = yaml.safe_load(f) or {}

    val_errors = _validate_merged_profile(merged)
    if val_errors:
        logger.error("BUILD REJECTED — %d validation errors:", len(val_errors))
        for ve in val_errors:
            logger.error("  VALIDATION: %s", ve)
        _build_lock.release()
        raise HTTPException(422, detail={"errors": val_errors, "message": "Merged profile failed validation"})

    # ── Preflight checks — reject if critical checks fail ──
    preflight = _run_preflight(merged)
    if not preflight["passed"]:
        failed = [c for c in preflight["checks"] if c["status"] == "fail"]
        logger.error("PREFLIGHT FAILED — %d checks failed:", len(failed))
        for f in failed:
            logger.error("  FAIL: %s — %s", f["name"], f["detail"])
        _build_lock.release()
        raise HTTPException(422, detail={
            "message": "Preflight checks failed",
            "preflight": preflight,
        })

    build_id = uuid.uuid4().hex[:12]
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    _builds[build_id] = {
        "status": "running",
        "profile": req.profile,
        "queue": queue,
        "history": [],
        "report": None,
        "started": datetime.now().isoformat(),
    }

    def _run_build():
        try:
            pipeline = core.BuildPipeline(
                effective_profile, req.platform, forge_root=FORGE_ROOT
            )

            def on_progress(message: str, pct: int) -> None:
                stage = _match_stage(message)
                event = {"message": message, "pct": pct, "stage": stage}
                _builds[build_id]["history"].append(event)
                loop.call_soon_threadsafe(queue.put_nowait, event)

            report = pipeline.build(on_progress=on_progress)
            report_dict = dataclasses.asdict(report)
            for k, v in report_dict.items():
                if isinstance(v, Path):
                    report_dict[k] = str(v)

            _builds[build_id]["status"] = report.status.lower()
            _builds[build_id]["report"] = report_dict

            done_event = {"event": "done", "status": report.status, "report": report_dict}
            loop.call_soon_threadsafe(queue.put_nowait, done_event)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Build thread crashed:\n%s", tb)
            error_event = {"event": "done", "status": "FAILED", "error": str(exc), "traceback": tb}
            _builds[build_id]["status"] = "failed"
            _builds[build_id]["report"] = {"status": "FAILED", "errors": [str(exc)], "traceback": tb}
            loop.call_soon_threadsafe(queue.put_nowait, error_event)
        finally:
            _build_lock.release()

    thread = threading.Thread(target=_run_build, daemon=True)
    thread.start()

    return {"build_id": build_id}


@app.get("/api/build/active")
async def active_build():
    """Return the currently running build, if any."""
    for bid, info in _builds.items():
        if info["status"] == "running":
            return {"build_id": bid, "profile": info["profile"], "started": info["started"]}
    return {"build_id": None}


@app.get("/api/build/{build_id}/progress")
async def build_progress(build_id: str):
    if build_id not in _builds:
        raise HTTPException(404, f"Build not found: {build_id}")

    build = _builds[build_id]

    # If build already finished, send the done event immediately
    if build["status"] in ("success", "failed"):
        async def done_stream():
            # Replay history
            for event in build["history"]:
                yield f"data: {json.dumps(event, default=str)}\n\n"
            done_event = {"event": "done", "status": build["report"].get("status", "FAILED"), "report": build["report"]}
            yield f"data: {json.dumps(done_event, default=str)}\n\n"
        return StreamingResponse(done_stream(), media_type="text/event-stream")

    # Create a per-listener queue so multiple clients can connect
    listener_queue: asyncio.Queue = asyncio.Queue()
    # Snapshot current history length, then subscribe
    history_snapshot = list(build["history"])
    # Replace the main queue with a broadcaster if not already
    main_queue = build["queue"]

    async def event_stream():
        # Replay past events
        for event in history_snapshot:
            yield f"data: {json.dumps(event, default=str)}\n\n"

        # Stream new events from main queue
        while True:
            try:
                event = await asyncio.wait_for(main_queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue

            yield f"data: {json.dumps(event, default=str)}\n\n"

            if event.get("event") == "done":
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/build/{build_id}/report")
async def build_report(build_id: str):
    if build_id not in _builds:
        raise HTTPException(404, f"Build not found: {build_id}")
    report = _builds[build_id].get("report")
    if report is None:
        raise HTTPException(202, "Build still in progress")
    return report


# ── Output endpoints ──


@app.get("/api/outputs")
async def list_outputs():
    if not OUTPUT_DIR.exists():
        return []

    results = []
    for d in sorted(OUTPUT_DIR.iterdir()):
        if not d.is_dir():
            continue
        size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        has_report = (d / "BUILD_REPORT.md").exists()
        qa_path = d / "QA_REPORT.json"
        qa_summary = None
        if qa_path.exists():
            try:
                qa_data = json.loads(qa_path.read_text())
                qa_summary = {
                    "passed": qa_data.get("passed", False),
                    "total": qa_data.get("total", 0),
                    "failed_count": qa_data.get("failed_count", 0),
                }
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("QA report parse failed for %s: %s", qa_path, exc)
        mtime = datetime.fromtimestamp(d.stat().st_mtime).isoformat()
        results.append(
            {
                "name": d.name,
                "size_mb": round(size / (1024 * 1024), 1),
                "has_report": has_report,
                "qa": qa_summary,
                "modified": mtime,
            }
        )
    return results


@app.delete("/api/outputs/{name}")
async def delete_output(name: str):
    # Path traversal protection
    if ".." in name or "/" in name or "\x00" in name:
        raise HTTPException(400, "Invalid output name")

    target = (OUTPUT_DIR / name).resolve()
    if not str(target).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(400, "Invalid output name")

    if not target.exists():
        raise HTTPException(404, f"Output not found: {name}")

    shutil.rmtree(target)
    return {"deleted": name}


# ── Config file endpoints (read-only) ──

SAFE_CONFIG_FILES = {
    "personality": "personality.json",
    "bootstrap-patches": "personality.json",
    "registry": "aibrarian_registry.yaml",
    "owner": "owner.yaml",
    "directives": "directives_seed.yaml",
    "fallback-chain": "fallback_chain.yaml",
}


@app.get("/api/files/{file_key}")
async def read_config_file(file_key: str):
    if file_key not in SAFE_CONFIG_FILES:
        raise HTTPException(404, "Unknown config file")

    filename = SAFE_CONFIG_FILES[file_key]
    target = (ENGINE_ROOT / "config" / filename).resolve()

    # Path traversal protection
    if not str(target).startswith(str(ENGINE_ROOT.resolve())):
        raise HTTPException(403, "Access denied")
    if not target.exists():
        raise HTTPException(404, f"Config file not found: {filename}")

    try:
        raw = target.read_text()
        if filename.endswith(".json"):
            return json.loads(raw)
        elif filename.endswith(".yaml") or filename.endswith(".yml"):
            import yaml
            return yaml.safe_load(raw) or {}
        else:
            return {"content": raw}
    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Config file parse failed for %s: %s", filename, exc)
        raise HTTPException(500, detail=f"Failed to parse {filename}: {exc}")


# ── Luna context endpoints ──


@app.get("/api/system-knowledge")
async def system_knowledge():
    """Read Luna-System-Knowledge docs from engine data dir."""
    sk_dir = ENGINE_ROOT / "data" / "system" / "Luna-System-Knowledge"
    if not sk_dir.exists():
        return []
    docs = []
    for f in sorted(sk_dir.glob("*.md")):
        if f.name == "README.md":
            continue
        title = f.stem.replace("_", " ")
        if len(title) > 2 and title[:2].isdigit():
            title = title[3:]
        docs.append({"filename": f.name, "title": title, "content": f.read_text()})
    return docs


@app.get("/api/directives")
async def directives():
    """Read directives_seed.yaml."""
    import yaml

    seed_path = ENGINE_ROOT / "config" / "directives_seed.yaml"
    if not seed_path.exists():
        return {"seed_directives": [], "seed_skills": []}
    with open(seed_path) as f:
        data = yaml.safe_load(f) or {}
    return {
        "seed_directives": data.get("seed_directives", []),
        "seed_skills": data.get("seed_skills", []),
    }


# ── Database Sanitizer ──


@app.get("/api/sanitizer/stats")
async def sanitizer_stats():
    """Show row counts and size for the source engine DB."""
    from sanitizer import DatabaseSanitizer, SanitizeConfig

    source_db = ENGINE_ROOT / "data" / "user" / "luna_engine.db"
    if not source_db.exists():
        raise HTTPException(404, "Engine database not found")

    config = SanitizeConfig(source_db=source_db, output_db=Path("/dev/null"))
    s = DatabaseSanitizer(config)
    return s.get_source_stats()


@app.get("/api/sanitizer/entities")
async def sanitizer_entities():
    """List all entities with type, origin, and mention count."""
    from sanitizer import DatabaseSanitizer, SanitizeConfig

    source_db = ENGINE_ROOT / "data" / "user" / "luna_engine.db"
    if not source_db.exists():
        raise HTTPException(404, "Engine database not found")

    config = SanitizeConfig(source_db=source_db, output_db=Path("/dev/null"))
    s = DatabaseSanitizer(config)
    return s.list_entities()


@app.get("/api/sanitizer/node-types")
async def sanitizer_node_types():
    """Return node type breakdown."""
    from sanitizer import DatabaseSanitizer, SanitizeConfig

    source_db = ENGINE_ROOT / "data" / "user" / "luna_engine.db"
    if not source_db.exists():
        raise HTTPException(404, "Engine database not found")

    config = SanitizeConfig(source_db=source_db, output_db=Path("/dev/null"))
    s = DatabaseSanitizer(config)
    return s.list_node_type_counts()


class SanitizeRequest(BaseModel):
    include_entities: Optional[list[str]] = None
    exclude_entities: Optional[list[str]] = None
    include_node_types: Optional[list[str]] = None
    min_confidence: float = 0.0
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    include_conversations: bool = False
    output_name: str = "filtered"


@app.post("/api/sanitizer/preview")
async def sanitizer_preview(req: SanitizeRequest):
    """Dry run — show what would be included/excluded."""
    from sanitizer import DatabaseSanitizer, SanitizeConfig
    import dataclasses

    source_db = ENGINE_ROOT / "data" / "user" / "luna_engine.db"
    if not source_db.exists():
        raise HTTPException(404, "Engine database not found")

    config = SanitizeConfig(
        source_db=source_db,
        output_db=Path("/dev/null"),
        include_entities=req.include_entities,
        exclude_entities=req.exclude_entities,
        include_node_types=req.include_node_types,
        min_confidence=req.min_confidence,
        date_from=req.date_from,
        date_to=req.date_to,
        include_conversations=req.include_conversations,
    )
    try:
        s = DatabaseSanitizer(config)
        report = s.preview()
        return dataclasses.asdict(report)
    except Exception as exc:
        logger.error("Sanitizer preview failed: %s", traceback.format_exc())
        raise HTTPException(500, detail=f"Preview failed: {exc}")


@app.post("/api/sanitizer/execute")
async def sanitizer_execute(req: SanitizeRequest):
    """Create a filtered database."""
    from sanitizer import DatabaseSanitizer, SanitizeConfig
    import dataclasses

    source_db = ENGINE_ROOT / "data" / "user" / "luna_engine.db"
    if not source_db.exists():
        raise HTTPException(404, "Engine database not found")

    staging = FORGE_ROOT / "staging"
    staging.mkdir(exist_ok=True)
    output_db = staging / f"{req.output_name}.db"

    config = SanitizeConfig(
        source_db=source_db,
        output_db=output_db,
        include_entities=req.include_entities,
        exclude_entities=req.exclude_entities,
        include_node_types=req.include_node_types,
        min_confidence=req.min_confidence,
        date_from=req.date_from,
        date_to=req.date_to,
        include_conversations=req.include_conversations,
    )
    try:
        s = DatabaseSanitizer(config)
        report = s.execute()
        result = dataclasses.asdict(report)
        result["output_path"] = str(output_db)
        return result
    except Exception as exc:
        logger.error("Sanitizer execute failed: %s", traceback.format_exc())
        raise HTTPException(500, detail=f"Sanitization failed: {exc}")


# ── Sanitizer Templates ──

SANITIZER_TEMPLATES_DIR = FORGE_ROOT / "sanitizer_templates"


class SanitizerTemplateRequest(BaseModel):
    name: str
    config: dict


@app.get("/api/sanitizer/templates")
async def list_sanitizer_templates():
    """List all saved sanitizer filter templates."""
    SANITIZER_TEMPLATES_DIR.mkdir(exist_ok=True)
    templates = []
    for f in sorted(SANITIZER_TEMPLATES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            templates.append({
                "name": f.stem,
                "created_at": data.get("created_at"),
                "entity_count": len(data.get("config", {}).get("include_entities", [])),
                "node_type_count": len(data.get("config", {}).get("include_node_types", [])),
                "min_confidence": data.get("config", {}).get("min_confidence", 0),
            })
        except Exception:
            continue
    return templates


@app.post("/api/sanitizer/templates")
async def save_sanitizer_template(req: SanitizerTemplateRequest):
    """Save a sanitizer filter configuration as a reusable template."""
    import re
    if not re.match(r"^[a-zA-Z0-9_-]+$", req.name):
        raise HTTPException(400, "Template name must be alphanumeric (dashes/underscores allowed)")
    SANITIZER_TEMPLATES_DIR.mkdir(exist_ok=True)
    path = SANITIZER_TEMPLATES_DIR / f"{req.name}.json"
    data = {
        "name": req.name,
        "config": req.config,
        "created_at": datetime.now().isoformat(),
    }
    path.write_text(json.dumps(data, indent=2))
    return {"status": "saved", "name": req.name}


@app.get("/api/sanitizer/templates/{name}")
async def get_sanitizer_template(name: str):
    """Load a single sanitizer template."""
    path = SANITIZER_TEMPLATES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(404, f"Template not found: {name}")
    return json.loads(path.read_text())


@app.delete("/api/sanitizer/templates/{name}")
async def delete_sanitizer_template(name: str):
    """Delete a saved sanitizer template."""
    path = SANITIZER_TEMPLATES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(404, f"Template not found: {name}")
    path.unlink()
    return {"status": "deleted", "name": name}


# ── Plugin / Collection Management ──


@app.get("/api/collections")
async def list_collections():
    """List all Nexus collections (registry + plugin)."""
    import yaml
    import sqlite3

    collections = []

    # Registry collections
    registry_path = ENGINE_ROOT / "config" / "aibrarian_registry.yaml"
    if registry_path.exists():
        with open(registry_path) as f:
            data = yaml.safe_load(f) or {}
        for key, cfg in data.get("collections", {}).items():
            db_path_str = cfg.get("db_path", "")
            db_path = Path(db_path_str) if Path(db_path_str).is_absolute() else ENGINE_ROOT / db_path_str
            stats = _get_collection_stats(db_path)
            collections.append({
                "key": key,
                "name": cfg.get("name", key),
                "description": cfg.get("description", ""),
                "source": "registry",
                "enabled": cfg.get("enabled", True),
                "read_only": cfg.get("read_only", False),
                "db_exists": db_path.exists(),
                "db_path": str(db_path),
                "tags": cfg.get("tags", []),
                **stats,
            })

    # Plugin collections
    collections_dir = ENGINE_ROOT / "collections"
    if collections_dir.exists():
        for entry in sorted(collections_dir.iterdir()):
            manifest_path = entry / "manifest.yaml"
            if not entry.is_dir() or not manifest_path.exists():
                continue
            with open(manifest_path) as f:
                manifest = yaml.safe_load(f) or {}
            coll = manifest.get("collection", {})
            key = coll.get("key", entry.name)
            # Skip if already in registry
            if any(c["key"] == key for c in collections):
                continue
            db_file = coll.get("db_file", f"{key}.db")
            db_path = entry / db_file
            stats = _get_collection_stats(db_path)
            collections.append({
                "key": key,
                "name": manifest.get("name", key),
                "description": manifest.get("description", ""),
                "source": "plugin",
                "enabled": True,
                "read_only": coll.get("read_only", False),
                "db_exists": db_path.exists(),
                "db_path": str(db_path),
                "tags": coll.get("tags", []),
                "plugin_dir": str(entry),
                **stats,
            })

    return collections


def _get_collection_stats(db_path: Path) -> dict:
    """Get chunk/document counts from a collection DB."""
    import sqlite3
    if not db_path.exists():
        return {"chunks": 0, "documents": 0, "size_mb": 0}
    try:
        conn = sqlite3.connect(str(db_path))
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        documents = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        conn.close()
        size_mb = round(db_path.stat().st_size / (1024 * 1024), 2)
        return {"chunks": chunks, "documents": documents, "size_mb": size_mb}
    except Exception:
        size_mb = round(db_path.stat().st_size / (1024 * 1024), 2) if db_path.exists() else 0
        return {"chunks": 0, "documents": 0, "size_mb": size_mb}


class CollectionCreateRequest(BaseModel):
    key: str
    name: str
    description: str = ""
    tags: list[str] = []


@app.post("/api/collections/create")
async def create_collection(req: CollectionCreateRequest):
    """Create a new plugin collection with empty DB and manifest."""
    import yaml

    collections_dir = ENGINE_ROOT / "collections"
    plugin_dir = collections_dir / req.key
    if plugin_dir.exists():
        raise HTTPException(400, f"Collection '{req.key}' already exists")

    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Generate manifest
    manifest = {
        "name": req.name,
        "description": req.description,
        "version": "1.0.0",
        "collection": {
            "key": req.key,
            "db_file": f"{req.key}.db",
            "schema_type": "standard",
            "read_only": False,
            "tags": req.tags,
        },
    }
    with open(plugin_dir / "manifest.yaml", "w") as f:
        yaml.safe_dump(manifest, f, sort_keys=False)

    # Create empty DB with standard schema
    import sqlite3
    db_path = plugin_dir / f"{req.key}.db"
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            import sys
            engine_src = str(ENGINE_ROOT / "src")
            if engine_src not in sys.path:
                sys.path.insert(0, engine_src)
            from luna.substrate.aibrarian_schema import STANDARD_SCHEMA
            conn.executescript(STANDARD_SCHEMA)
        except ImportError:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, title TEXT, content TEXT, source TEXT,
                    metadata TEXT, created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT REFERENCES documents(id),
                    content TEXT NOT NULL, chunk_index INTEGER, metadata TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(content, content='chunks', content_rowid='rowid');
            """)
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.error("Collection DB creation failed for %s: %s", req.key, traceback.format_exc())
        # Clean up partial directory
        shutil.rmtree(plugin_dir, ignore_errors=True)
        raise HTTPException(500, detail=f"Failed to create collection database: {exc}")

    return {"status": "created", "key": req.key, "path": str(plugin_dir)}


class CollectionIngestRequest(BaseModel):
    file_path: str
    title: str = ""
    metadata: dict = {}


@app.post("/api/collections/{key}/ingest")
async def ingest_document(key: str, req: CollectionIngestRequest):
    """Ingest a document into a collection using the AiBrarian engine."""
    import sys
    engine_src = str(ENGINE_ROOT / "src")
    if engine_src not in sys.path:
        sys.path.insert(0, engine_src)

    file_path = Path(req.file_path)
    if not file_path.exists():
        raise HTTPException(404, f"File not found: {file_path}")

    # Find collection DB path
    db_path = None
    # Check plugin collections first
    plugin_manifest = ENGINE_ROOT / "collections" / key / "manifest.yaml"
    if plugin_manifest.exists():
        import yaml
        with open(plugin_manifest) as f:
            manifest = yaml.safe_load(f) or {}
        coll = manifest.get("collection", {})
        db_file = coll.get("db_file", f"{key}.db")
        db_path = ENGINE_ROOT / "collections" / key / db_file

    # Check registry collections
    if db_path is None:
        registry_path = ENGINE_ROOT / "config" / "aibrarian_registry.yaml"
        if registry_path.exists():
            import yaml
            with open(registry_path) as f:
                data = yaml.safe_load(f) or {}
            coll_cfg = data.get("collections", {}).get(key, {})
            if coll_cfg:
                p = Path(coll_cfg.get("db_path", ""))
                db_path = p if p.is_absolute() else ENGINE_ROOT / p

    if db_path is None or not db_path.exists():
        raise HTTPException(404, f"Collection '{key}' not found or DB missing")

    # Use AiBrarianEngine for ingestion
    try:
        from luna.substrate.aibrarian_engine import AiBrarianConfig, AiBrarianConnection
        config = AiBrarianConfig(key=key, name=key, db_path=str(db_path), create_if_missing=False)
        conn = AiBrarianConnection(config, db_path)
        await conn.connect()

        # Read file content
        content = file_path.read_text(errors="replace")
        title = req.title or file_path.stem

        # Chunk and insert
        from luna.substrate.aibrarian_engine import chunk_text
        chunks = chunk_text(content, config.chunk_size, config.chunk_overlap)
        import uuid as _uuid
        doc_id = str(_uuid.uuid4())[:12]

        conn._conn.execute(
            "INSERT INTO documents (id, title, content, source, metadata) VALUES (?, ?, ?, ?, ?)",
            (doc_id, title, content[:5000], str(file_path), json.dumps(req.metadata))
        )
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_c{i}"
            conn._conn.execute(
                "INSERT INTO chunks (id, document_id, content, chunk_index) VALUES (?, ?, ?, ?)",
                (chunk_id, doc_id, chunk.text, i)
            )
        conn._conn.commit()
        await conn.close()

        return {"status": "ingested", "document_id": doc_id, "chunks": len(chunks)}
    except Exception as e:
        raise HTTPException(500, f"Ingestion failed: {e}")


@app.post("/api/collections/{key}/package")
async def package_collection(key: str):
    """Package a plugin collection as a downloadable zip."""
    plugin_dir = ENGINE_ROOT / "collections" / key
    if not plugin_dir.exists():
        raise HTTPException(404, f"Plugin collection '{key}' not found")

    import tempfile
    import zipfile

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in plugin_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f"{key}/{f.relative_to(plugin_dir)}")

    from starlette.responses import FileResponse
    return FileResponse(
        tmp_path,
        media_type="application/zip",
        filename=f"{key}.zip",
        background=None,  # cleanup handled by OS temp
    )


@app.get("/api/plugins")
async def list_plugins():
    """List all skills (built-in + plugins) and plugin collections."""
    plugins = {"skills": [], "collections": []}

    # Built-in engine skills — read from skills config
    import yaml
    skills_yaml = ENGINE_ROOT / "config" / "skills.yaml"
    builtin_skill_names = set()
    if skills_yaml.exists():
        with open(skills_yaml) as f:
            skills_config = yaml.safe_load(f) or {}
        for name, info in skills_config.get("skills", skills_config).items():
            if isinstance(info, dict):
                builtin_skill_names.add(name)
                plugins["skills"].append({
                    "name": name,
                    "source": "builtin",
                    "has_init": True,
                    "enabled": info.get("enabled", True),
                    "requirements": [],
                })
    else:
        # Fallback — list known defaults
        for name in ("math", "logic", "diagnostic", "reading", "analytics"):
            builtin_skill_names.add(name)
            plugins["skills"].append({
                "name": name,
                "source": "builtin",
                "has_init": True,
                "enabled": True,
                "requirements": [],
            })

    # Skill plugins from plugins/ directory
    plugins_dir = ENGINE_ROOT / "plugins"
    if plugins_dir.exists():
        for entry in sorted(plugins_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith(("_", ".")):
                continue
            init_path = entry / "__init__.py"
            reqs_path = entry / "requirements.txt"
            if entry.name not in builtin_skill_names:
                plugins["skills"].append({
                    "name": entry.name,
                    "source": "plugin",
                    "has_init": init_path.exists(),
                    "has_requirements": reqs_path.exists(),
                    "requirements": reqs_path.read_text().strip().splitlines() if reqs_path.exists() else [],
                    "path": str(entry),
                })

    # Collection plugins (reuse list_collections logic)
    collections_dir = ENGINE_ROOT / "collections"
    if collections_dir.exists():
        import yaml
        for entry in sorted(collections_dir.iterdir()):
            manifest_path = entry / "manifest.yaml"
            if not entry.is_dir() or not manifest_path.exists():
                continue
            with open(manifest_path) as f:
                manifest = yaml.safe_load(f) or {}
            coll = manifest.get("collection", {})
            db_file = coll.get("db_file", f"{entry.name}.db")
            db_path = entry / db_file
            plugins["collections"].append({
                "key": coll.get("key", entry.name),
                "name": manifest.get("name", entry.name),
                "db_exists": db_path.exists(),
                "size_mb": round(db_path.stat().st_size / (1024 * 1024), 2) if db_path.exists() else 0,
                "path": str(entry),
            })

    return plugins


# ── Build Drafts ──

DRAFTS_DIR = FORGE_ROOT / "builds"


class DraftCreateRequest(BaseModel):
    template_profile: Optional[str] = None
    name: Optional[str] = None


class DraftUpdateRequest(BaseModel):
    config: Optional[dict] = None
    name: Optional[str] = None
    platform: Optional[str] = None


@app.post("/api/builds/drafts")
async def create_draft(req: DraftCreateRequest):
    """Create a new build draft, optionally from a profile template."""
    import yaml

    DRAFTS_DIR.mkdir(exist_ok=True)
    draft_id = uuid.uuid4().hex[:10]
    now = datetime.now().isoformat()

    # Start from profile template or defaults
    core = _get_core()
    if req.template_profile:
        profile_path = PROFILES_DIR / f"{req.template_profile}.yaml"
        if not profile_path.exists():
            raise HTTPException(404, f"Template profile not found: {req.template_profile}")
        config = core.load_profile(profile_path)
    else:
        import copy
        config = copy.deepcopy(core.PROFILE_DEFAULTS)

    draft = {
        "id": draft_id,
        "name": req.name or config.get("name") or f"Build {draft_id[:6]}",
        "status": "draft",
        "template": req.template_profile,
        "platform": config.pop("platform", "auto"),
        "created_at": now,
        "updated_at": now,
        "config": config,
    }

    path = DRAFTS_DIR / f"{draft_id}.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(draft, f, default_flow_style=False, sort_keys=False)

    return draft


@app.get("/api/builds/drafts")
async def list_drafts():
    """List all build drafts, sorted by most recently updated."""
    import yaml

    DRAFTS_DIR.mkdir(exist_ok=True)
    drafts = []
    for f in DRAFTS_DIR.glob("*.yaml"):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh) or {}
            drafts.append({
                "id": data.get("id", f.stem),
                "name": data.get("name", f.stem),
                "status": data.get("status", "draft"),
                "template": data.get("template"),
                "platform": data.get("platform", "auto"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
            })
        except Exception:
            continue
    drafts.sort(key=lambda d: d.get("updated_at") or "", reverse=True)
    return drafts


@app.get("/api/builds/drafts/{draft_id}")
async def get_draft(draft_id: str):
    """Load a full build draft."""
    import yaml

    path = DRAFTS_DIR / f"{draft_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"Draft not found: {draft_id}")
    with open(path) as f:
        return yaml.safe_load(f) or {}


@app.put("/api/builds/drafts/{draft_id}")
async def update_draft(draft_id: str, req: DraftUpdateRequest):
    """Update a build draft's config, name, or platform."""
    import yaml

    path = DRAFTS_DIR / f"{draft_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"Draft not found: {draft_id}")

    with open(path) as f:
        draft = yaml.safe_load(f) or {}

    if req.config is not None:
        draft["config"] = req.config
    if req.name is not None:
        draft["name"] = req.name
    if req.platform is not None:
        draft["platform"] = req.platform
    draft["updated_at"] = datetime.now().isoformat()
    if draft.get("status") == "draft":
        draft["status"] = "configured"

    with open(path, "w") as f:
        yaml.safe_dump(draft, f, default_flow_style=False, sort_keys=False)

    return draft


@app.delete("/api/builds/drafts/{draft_id}")
async def delete_draft(draft_id: str):
    """Delete a build draft."""
    path = DRAFTS_DIR / f"{draft_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"Draft not found: {draft_id}")
    path.unlink()
    return {"status": "deleted", "id": draft_id}


@app.post("/api/builds/drafts/{draft_id}/build", status_code=202)
async def start_draft_build(draft_id: str):
    """Start a build from a saved draft."""
    import yaml

    path = DRAFTS_DIR / f"{draft_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"Draft not found: {draft_id}")

    with open(path) as f:
        draft = yaml.safe_load(f) or {}

    config = draft.get("config", {})
    platform = draft.get("platform", "auto")

    if not _build_lock.acquire(blocking=False):
        raise HTTPException(409, "A build is already in progress")

    # Write temp profile for BuildPipeline
    core = _get_core()
    staging_dir = FORGE_ROOT / "staging"
    staging_dir.mkdir(exist_ok=True)
    temp_profile = staging_dir / f"draft_{draft_id}.yaml"
    profile_data = {**config, "platform": platform}
    with open(temp_profile, "w") as f:
        yaml.safe_dump(profile_data, f, default_flow_style=False, sort_keys=False)

    # Validate
    val_errors = _validate_merged_profile(profile_data)
    if val_errors:
        _build_lock.release()
        raise HTTPException(422, detail={"errors": val_errors, "message": "Draft config failed validation"})

    preflight = _run_preflight(profile_data)
    if not preflight["passed"]:
        _build_lock.release()
        raise HTTPException(422, detail={"message": "Preflight checks failed", "preflight": preflight})

    # Update draft status
    draft["status"] = "building"
    draft["updated_at"] = datetime.now().isoformat()
    with open(path, "w") as f:
        yaml.safe_dump(draft, f, default_flow_style=False, sort_keys=False)

    build_id = uuid.uuid4().hex[:12]
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    _builds[build_id] = {
        "status": "running",
        "profile": draft.get("name", draft_id),
        "draft_id": draft_id,
        "queue": queue,
        "history": [],
        "report": None,
        "started": datetime.now().isoformat(),
    }

    def _run_build():
        try:
            pipeline = core.BuildPipeline(
                temp_profile, platform, forge_root=FORGE_ROOT
            )

            def on_progress(message: str, pct: int) -> None:
                stage = _match_stage(message)
                event = {"message": message, "pct": pct, "stage": stage}
                _builds[build_id]["history"].append(event)
                loop.call_soon_threadsafe(queue.put_nowait, event)

            report = pipeline.build(on_progress=on_progress)
            report_dict = dataclasses.asdict(report)
            for k, v in report_dict.items():
                if isinstance(v, Path):
                    report_dict[k] = str(v)

            _builds[build_id]["status"] = report.status.lower()
            _builds[build_id]["report"] = report_dict

            # Update draft status
            try:
                with open(path) as fh:
                    d = yaml.safe_load(fh) or {}
                d["status"] = "complete" if report.status == "SUCCESS" else "failed"
                d["updated_at"] = datetime.now().isoformat()
                with open(path, "w") as fh:
                    yaml.safe_dump(d, fh, default_flow_style=False, sort_keys=False)
            except Exception:
                pass

            done_event = {"event": "done", "status": report.status, "report": report_dict}
            loop.call_soon_threadsafe(queue.put_nowait, done_event)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Build thread crashed:\n%s", tb)
            error_event = {"event": "done", "status": "FAILED", "error": str(exc), "traceback": tb}
            _builds[build_id]["status"] = "failed"
            _builds[build_id]["report"] = {"status": "FAILED", "errors": [str(exc)], "traceback": tb}

            try:
                with open(path) as fh:
                    d = yaml.safe_load(fh) or {}
                d["status"] = "failed"
                d["updated_at"] = datetime.now().isoformat()
                with open(path, "w") as fh:
                    yaml.safe_dump(d, fh, default_flow_style=False, sort_keys=False)
            except Exception:
                pass

            loop.call_soon_threadsafe(queue.put_nowait, error_event)
        finally:
            _build_lock.release()

    thread = threading.Thread(target=_run_build, daemon=True)
    thread.start()

    return {"build_id": build_id, "draft_id": draft_id}


# ── Static file serving (production) ──

_frontend_dist = FORGE_ROOT / "frontend" / "dist"
if _frontend_dist.exists():
    from starlette.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


# ── Singleton guard ──

_PID_FILE = FORGE_ROOT / ".forge.pid"


def _check_singleton(port: int) -> bool:
    """Return True if no other Forge instance is running. Kill stale PIDs."""
    import urllib.request
    import urllib.error

    # Check PID file
    if _PID_FILE.exists():
        try:
            old_pid = int(_PID_FILE.read_text().strip())
            # Check if process is alive
            os.kill(old_pid, 0)
            # Process exists — check if it's actually serving Forge
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{port}/api/profiles")
                with urllib.request.urlopen(req, timeout=2):
                    # Another instance is running and responding
                    return False
            except (urllib.error.URLError, OSError):
                # Process alive but not serving — stale, kill it
                os.kill(old_pid, 9)
        except (ProcessLookupError, ValueError, PermissionError):
            pass  # Process dead or PID file corrupt
        _PID_FILE.unlink(missing_ok=True)

    # Also check if port is in use by something else
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.close()
        return True
    except OSError:
        # Port in use — try to reach Forge API
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/profiles")
            with urllib.request.urlopen(req, timeout=2):
                return False  # Another Forge instance
        except (urllib.error.URLError, OSError):
            pass
        sock.close()
        return True  # Port used by something else, uvicorn will error clearly


def _write_pid():
    _PID_FILE.write_text(str(os.getpid()))


def _cleanup_pid(*_args):
    _PID_FILE.unlink(missing_ok=True)


# ── Entry point ──

if __name__ == "__main__":
    import signal
    import sys
    import webbrowser

    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8200

    if not _check_singleton(port):
        print(f"\n  Lunar Forge is already running on :{port}")
        print(f"  Opening browser...\n")
        webbrowser.open(f"http://localhost:{port}")
        sys.exit(0)

    _write_pid()
    signal.signal(signal.SIGTERM, _cleanup_pid)
    signal.signal(signal.SIGINT, _cleanup_pid)

    import atexit
    atexit.register(_cleanup_pid)

    # Open browser after a short delay (server needs to start first)
    import threading
    def _open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=_open_browser, daemon=True).start()

    print(f"\n  Lunar Forge starting on http://localhost:{port}")
    print(f"  PID: {os.getpid()}\n")

    uvicorn.run(app, host="0.0.0.0", port=port)
