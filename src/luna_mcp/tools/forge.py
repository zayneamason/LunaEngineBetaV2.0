"""
Persona Forge tools for Luna-Hub-MCP.

Integrates training data management, personality profiles,
and Voight-Kampff testing into the unified MCP server.
"""

import json
import logging
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List

import yaml

from luna.core.paths import project_root, tools_dir
from luna.core.owner import get_owner, owner_configured

# Path setup - add persona_forge to import path
_PROJECT_ROOT = project_root()
_FORGE_SRC = tools_dir() / "persona_forge" / "src"
if str(_FORGE_SRC) not in sys.path:
    sys.path.insert(0, str(_FORGE_SRC))

# Persona Forge imports
from persona_forge.engine import (
    Crucible,
    Assayer,
    Locksmith,
    Mint,
    Anvil,
    DIRECTOR_PROFILE,
    TrainingExample,
    InteractionType,
    SourceType,
    VoiceMarkers,
    AntiPatterns,
)
from persona_forge.personality import (
    CharacterForge,
    create_luna_profile,
)
from persona_forge.voight_kampff import (
    SyncVoightKampffRunner,
    build_luna_suite,
    build_minimal_identity_suite,
    ProbeCategory,
)

logger = logging.getLogger(__name__)

# Paths
_PROFILES_DIR = tools_dir() / "persona_forge" / "profiles"
_PROBES_DIR = tools_dir() / "persona_forge" / "probes"

# Global state (same pattern as standalone server)
_state: dict[str, Any] = {
    "examples": [],
    "assay": None,
    "profile": None,
    "crucible": Crucible(),
    "assayer": Assayer(),
    "locksmith": Locksmith(),
    "mint": Mint(),
    "anvil": Anvil(),
    "forge": CharacterForge(profiles_dir=_PROFILES_DIR),
    "suites": {
        "luna": build_luna_suite,
        "minimal": build_minimal_identity_suite,
    },
    "last_report": None,
}

# Format detection
_FORMAT_MAP = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".jsonl": "jsonl",
    ".json": "json",
    ".db": "sqlite",
    ".sqlite": "sqlite",
    ".sqlite3": "sqlite",
    ".txt": "text",
}


def _detect_format(path: Path) -> str:
    """Detect file format from extension."""
    return _FORMAT_MAP.get(path.suffix.lower(), "unknown")


def _resolve_path(path: str) -> Path:
    """Resolve path - absolute or relative to project root."""
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return _PROJECT_ROOT / path


def _parse_yaml_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content
    end_match = re.search(r'\n---\s*\n', content[3:])
    if not end_match:
        return {}, content
    frontmatter_str = content[3:end_match.start() + 3]
    body = content[end_match.end() + 3:]
    try:
        metadata = yaml.safe_load(frontmatter_str) or {}
    except yaml.YAMLError:
        metadata = {}
    return metadata, body


# ==============================================================================
# Dataset Tools
# ==============================================================================

async def forge_load(path: str) -> dict[str, Any]:
    """Load training data from JSONL file."""
    crucible = _state["crucible"]
    crucible.clear()

    path_obj = _resolve_path(path)
    if not path_obj.exists():
        return {"success": False, "error": f"File not found: {path_obj}"}

    try:
        examples = crucible.ingest_jsonl(path_obj)
        locksmith = _state["locksmith"]
        locksmith.process_batch(examples)
        _state["examples"].extend(examples)
        _state["assay"] = None

        return {
            "success": True,
            "path": str(path_obj),
            "examples_loaded": len(examples),
            "total_examples": len(_state["examples"]),
            "stats": crucible.get_stats(),
        }
    except Exception as e:
        logger.exception(f"Error loading {path}")
        return {"success": False, "error": str(e)}


async def forge_assay() -> dict[str, Any]:
    """Analyze current dataset."""
    examples = _state["examples"]
    if not examples:
        return {"success": False, "error": "No examples loaded. Use forge_load first."}

    assayer = _state["assayer"]
    try:
        assay = assayer.analyze(examples)
        _state["assay"] = assay

        # Calculate derived metrics
        needs_attention = assay.health_score < 70
        avg_voice = sum(assay.voice_marker_rates.values()) / max(1, len(assay.voice_marker_rates))
        total_anti = sum(1 for v in assay.anti_pattern_rates.values() if v > 0)
        clean_pct = 100 * (1 - (total_anti / max(1, len(examples))))

        # Convert quality tier dist to counts
        quality_counts = {
            tier: int(pct * assay.total_examples)
            for tier, pct in assay.quality_tier_dist.items()
        }

        # Convert interaction type dist to counts
        interaction_counts = {
            itype: int(pct * assay.total_examples)
            for itype, pct in assay.interaction_type_dist.items()
        }

        return {
            "success": True,
            "assay": {
                "total_examples": assay.total_examples,
                "health_score": round(assay.health_score, 1),
                "needs_attention": needs_attention,
                "quality_tiers": quality_counts,
                "interaction_types": interaction_counts,
                "avg_voice_markers": round(avg_voice, 2),
                "clean_percentage": round(clean_pct, 1),
                "synthesis_targets": assay.synthesis_targets,
                "gaps": assay.gaps,
            },
            "summary": assayer.format_report(assay),
        }
    except Exception as e:
        logger.exception("Error during assay")
        return {"success": False, "error": str(e)}


async def forge_gaps() -> dict[str, Any]:
    """Get synthesis targets from coverage gaps."""
    assay = _state["assay"]
    if assay is None:
        result = await forge_assay()
        if not result["success"]:
            return result
        assay = _state["assay"]

    if not assay:
        return {"success": False, "error": "No assay available."}

    # Convert gaps dict to synthesis targets list
    # gaps dict: {interaction_type: deficit_count} where negative = need more
    synthesis_targets = []
    for itype, gap in assay.gaps.items():
        if gap < 0:  # Negative means we need more of this type
            needed = min(50, max(5, abs(gap)))
            synthesis_targets.append({
                "interaction_type": itype,
                "deficit": abs(gap),
                "recommended_count": needed,
            })

    # Also include explicit synthesis targets
    for itype, count in assay.synthesis_targets.items():
        if count > 0 and not any(t["interaction_type"] == itype for t in synthesis_targets):
            synthesis_targets.append({
                "interaction_type": itype,
                "deficit": count,
                "recommended_count": min(50, max(5, count)),
            })

    return {
        "success": True,
        "total_gaps": len(synthesis_targets),
        "synthesis_targets": synthesis_targets,
        "summary": f"Found {len(synthesis_targets)} types needing examples."
    }


async def forge_mint(interaction_type: str, count: int = 10) -> dict[str, Any]:
    """Generate synthetic training examples."""
    count = max(1, min(100, count))
    try:
        itype = InteractionType(interaction_type.lower())
    except ValueError:
        available = [t.value for t in InteractionType]
        return {"success": False, "error": f"Unknown type: {interaction_type}. Available: {available}"}

    mint = _state["mint"]
    profile = _state["profile"]

    try:
        examples = mint.mint_examples(interaction_type=itype, count=count, profile=profile)
        _state["examples"].extend(examples)
        _state["assay"] = None

        samples = [
            {
                "user": e.user_message,
                "assistant": e.assistant_response[:200] + "..." if len(e.assistant_response) > 200 else e.assistant_response,
            }
            for e in examples[:3]
        ]

        return {
            "success": True,
            "interaction_type": interaction_type,
            "minted": len(examples),
            "total_examples": len(_state["examples"]),
            "samples": samples,
        }
    except Exception as e:
        logger.exception(f"Error minting {interaction_type}")
        return {"success": False, "error": str(e)}


async def forge_export(output_path: str, train_split: float = 0.9) -> dict[str, Any]:
    """Export training data."""
    examples = _state["examples"]
    if not examples:
        return {"success": False, "error": "No examples to export."}

    train_split = max(0.1, min(0.99, train_split))
    anvil = _state["anvil"]
    path_obj = _resolve_path(output_path)

    try:
        locksmith = _state["locksmith"]
        locksmith.process_batch(examples)

        if path_obj.suffix == ".jsonl":
            result_path = anvil.export_jsonl(examples, path_obj)
            return {
                "success": True,
                "mode": "single_file",
                "path": str(result_path),
                "exported": len(examples),
            }
        else:
            result = anvil.export_train_val_split(
                examples, path_obj, train_ratio=train_split, stratified=True
            )
            return {
                "success": True,
                "mode": "train_val_split",
                "train_path": str(result["train"]),
                "val_path": str(result["val"]),
                "train_count": result["train_count"],
                "val_count": result["val_count"],
            }
    except Exception as e:
        logger.exception(f"Error exporting to {output_path}")
        return {"success": False, "error": str(e)}


async def forge_status() -> dict[str, Any]:
    """Get current session state."""
    examples = _state["examples"]
    profile = _state["profile"]
    assay = _state["assay"]

    quality_dist = {}
    for e in examples:
        tier = e.lock_in.tier.value
        quality_dist[tier] = quality_dist.get(tier, 0) + 1

    return {
        "examples_loaded": len(examples),
        "quality_distribution": quality_dist,
        "assay_available": assay is not None,
        "health_score": round(assay.health_score, 1) if assay else None,
        "profile_loaded": profile.name if profile else None,
        "profile_id": profile.id if profile else None,
        "suites_available": list(_state["suites"].keys()),
        "last_report": (
            {
                "suite": _state["last_report"].suite_name,
                "model": _state["last_report"].model_id,
                "passed": _state["last_report"].passed,
                "score": round(_state["last_report"].overall_score * 100, 1),
            }
            if _state["last_report"]
            else None
        ),
    }


# ==============================================================================
# Ingestion Tools
# ==============================================================================

async def forge_list_sources(directory: str, pattern: str = "*") -> dict[str, Any]:
    """List available source files."""
    dir_path = _resolve_path(directory)

    if not dir_path.exists():
        return {"success": False, "error": f"Directory not found: {dir_path}", "files": []}

    if not dir_path.is_dir():
        return {"success": False, "error": f"Not a directory: {dir_path}", "files": []}

    try:
        files_info = []
        formats_found = set()
        total_size = 0

        for file_path in dir_path.glob(pattern):
            if not file_path.is_file():
                continue

            stat = file_path.stat()
            size_kb = round(stat.st_size / 1024, 2)
            modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
            fmt = _detect_format(file_path)

            files_info.append({
                "path": str(file_path),
                "name": file_path.name,
                "size_kb": size_kb,
                "modified": modified,
                "format": fmt,
            })

            formats_found.add(fmt)
            total_size += size_kb

        files_info.sort(key=lambda x: x["modified"], reverse=True)

        return {
            "success": True,
            "directory": str(dir_path),
            "pattern": pattern,
            "files": files_info,
            "total_files": len(files_info),
            "total_size_kb": round(total_size, 2),
            "formats": list(formats_found),
        }
    except Exception as e:
        logger.exception(f"Error listing sources in {directory}")
        return {"success": False, "error": str(e), "files": []}


async def forge_read_raw(path: str, max_chars: int = 50000, offset: int = 0) -> dict[str, Any]:
    """Read raw file content."""
    file_path = _resolve_path(path)

    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    if not file_path.is_file():
        return {"success": False, "error": f"Not a file: {file_path}"}

    fmt = _detect_format(file_path)

    # Handle SQLite specially
    if fmt == "sqlite":
        try:
            conn = sqlite3.connect(str(file_path))
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            schema_info = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [{"name": row[1], "type": row[2]} for row in cursor.fetchall()]
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                schema_info[table] = {"columns": columns, "row_count": count}

            conn.close()

            return {
                "success": True,
                "path": str(file_path),
                "format": "sqlite",
                "content": f"SQLite database with {len(tables)} tables",
                "schema": schema_info,
                "tables": tables,
            }
        except Exception as e:
            return {"success": False, "error": f"Error reading SQLite: {e}"}

    # Read text files
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)
            total_size = f.tell()
            f.seek(offset)
            content = f.read(max_chars)

        truncated = len(content) == max_chars and (offset + len(content)) < total_size
        has_more = (offset + len(content)) < total_size

        metadata = {}
        if fmt == "markdown" and offset == 0:
            metadata, _ = _parse_yaml_frontmatter(content)

        return {
            "success": True,
            "path": str(file_path),
            "format": fmt,
            "content": content,
            "size_chars": total_size,
            "offset": offset,
            "chars_returned": len(content),
            "truncated": truncated,
            "has_more": has_more,
            "metadata": metadata,
        }
    except Exception as e:
        logger.exception(f"Error reading {path}")
        return {"success": False, "error": str(e)}


async def forge_add_example(
    user_message: str,
    assistant_response: str,
    interaction_type: str = "short_exchange",
    source_file: Optional[str] = None,
    source_type: str = "manual",
    confidence: float = 1.0,
    tags: Optional[List[str]] = None,
    context: Optional[str] = None
) -> dict[str, Any]:
    """Add a single training example."""
    crucible = _state["crucible"]
    profile = _state["profile"]

    try:
        itype = InteractionType(interaction_type.lower())
    except ValueError:
        available = [t.value for t in InteractionType]
        return {"success": False, "error": f"Unknown interaction_type: {interaction_type}. Available: {available}"}

    try:
        stype = SourceType(source_type.lower())
    except ValueError:
        available = [t.value for t in SourceType]
        return {"success": False, "error": f"Unknown source_type: {source_type}. Available: {available}"}

    system_prompt = profile.to_system_prompt() if profile else "You are Luna, a sovereign AI companion."

    try:
        example = TrainingExample(
            system_prompt=system_prompt,
            user_message=user_message,
            assistant_response=assistant_response,
            source_type=stype,
            source_file=source_file,
            interaction_type=itype,
        )
        example.compute_metrics()
        example.voice_markers = crucible._detect_voice_markers(assistant_response)
        example.anti_patterns = crucible._detect_anti_patterns(assistant_response)
        example.lock_in = crucible._compute_initial_lockin(example)

        warnings = []
        anti_found = [k for k, v in example.anti_patterns.model_dump().items() if v]
        if anti_found:
            warnings.append(f"Anti-patterns detected: {', '.join(anti_found)}")

        if example.lock_in.coefficient < 0.5:
            warnings.append(f"Low lock-in score: {example.lock_in.coefficient:.2f}")

        _state["examples"].append(example)
        _state["assay"] = None

        return {
            "success": True,
            "id": example.id,
            "lock_in": round(example.lock_in.coefficient, 3),
            "tier": example.lock_in.tier.value,
            "voice_markers": example.voice_markers,
            "anti_patterns": example.anti_patterns,
            "anti_patterns_found": anti_found,
            "warnings": warnings,
            "confidence": confidence,
            "total_examples": len(_state["examples"]),
        }
    except Exception as e:
        logger.exception("Error adding example")
        return {"success": False, "error": str(e)}


async def forge_add_batch(examples: List[dict]) -> dict[str, Any]:
    """Add multiple training examples."""
    added = 0
    rejected = []
    all_warnings = []
    quality_summary = {"gold": 0, "silver": 0, "bronze": 0}

    for i, ex in enumerate(examples):
        if "user_message" not in ex or "assistant_response" not in ex:
            rejected.append({"index": i, "reason": "Missing required fields"})
            continue

        result = await forge_add_example(
            user_message=ex["user_message"],
            assistant_response=ex["assistant_response"],
            interaction_type=ex.get("interaction_type", "short_exchange"),
            source_file=ex.get("source_file"),
            source_type=ex.get("source_type", "manual"),
            confidence=ex.get("confidence", 1.0),
            tags=ex.get("tags"),
            context=ex.get("context"),
        )

        if result["success"]:
            added += 1
            tier = result["tier"]
            quality_summary[tier] = quality_summary.get(tier, 0) + 1
            if result.get("warnings"):
                all_warnings.extend(result["warnings"])
        else:
            rejected.append({"index": i, "reason": result.get("error", "Unknown error")})

    return {
        "success": added > 0,
        "added": added,
        "rejected_count": len(rejected),
        "rejected": rejected[:10],
        "warnings": list(set(all_warnings))[:10],
        "quality_summary": quality_summary,
        "total_examples": len(_state["examples"]),
    }


async def forge_search(query: str, field: str = "all", limit: int = 10) -> dict[str, Any]:
    """Search existing examples for deduplication."""
    examples = _state["examples"]
    query_lower = query.lower()
    matches = []

    for example in examples:
        matched = False
        match_field = None

        if field in ("all", "user"):
            if query_lower in example.user_message.lower():
                matched = True
                match_field = "user"

        if field in ("all", "assistant") and not matched:
            if query_lower in example.assistant_response.lower():
                matched = True
                match_field = "assistant"

        if field in ("all", "source") and not matched:
            if example.source_file and query_lower in example.source_file.lower():
                matched = True
                match_field = "source"

        if matched:
            preview = example.assistant_response[:100]
            if len(preview) == 100:
                preview += "..."

            matches.append({
                "id": example.id,
                "match_field": match_field,
                "preview": preview,
                "interaction_type": example.interaction_type.value,
                "tier": example.lock_in.tier.value,
                "source_file": example.source_file,
            })

            if len(matches) >= limit:
                break

    return {
        "success": True,
        "query": query,
        "field": field,
        "matches": matches,
        "total_matches": len(matches),
        "searched_examples": len(examples),
    }


async def forge_read_matrix(
    db_path: str,
    node_types: Optional[List[str]] = None,
    limit: int = 100,
    offset: int = 0
) -> dict[str, Any]:
    """Read memory nodes from Memory Matrix database."""
    path = _resolve_path(db_path)

    if not path.exists():
        return {"success": False, "error": f"Database not found: {path}"}

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_nodes'"
        )
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": "Table 'memory_nodes' not found"}

        if node_types:
            placeholders = ",".join("?" * len(node_types))
            where_clause = f"WHERE node_type IN ({placeholders})"
            params = node_types
        else:
            where_clause = ""
            params = []

        cursor.execute(f"SELECT COUNT(*) FROM memory_nodes {where_clause}", params)
        total_count = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT node_type, COUNT(*) FROM memory_nodes {where_clause} GROUP BY node_type",
            params
        )
        type_counts = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(
            f"""
            SELECT id, node_type, content, summary, created_at, metadata
            FROM memory_nodes
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset]
        )

        nodes = []
        for row in cursor.fetchall():
            metadata = {}
            if row["metadata"]:
                try:
                    metadata = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    pass

            nodes.append({
                "id": row["id"],
                "type": row["node_type"],
                "content": row["content"],
                "summary": row["summary"],
                "created_at": row["created_at"],
                "tags": metadata.get("tags", []),
            })

        conn.close()

        return {
            "success": True,
            "db_path": str(path),
            "nodes": nodes,
            "total_count": total_count,
            "returned_count": len(nodes),
            "offset": offset,
            "limit": limit,
            "has_more": (offset + len(nodes)) < total_count,
            "type_counts": type_counts,
        }
    except Exception as e:
        logger.exception(f"Error reading memory matrix from {db_path}")
        return {"success": False, "error": str(e)}


async def forge_read_turns(
    db_path: str,
    session_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> dict[str, Any]:
    """Read conversation turns from database."""
    path = _resolve_path(db_path)

    if not path.exists():
        return {"success": False, "error": f"Database not found: {path}"}

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_turns'"
        )
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": "Table 'conversation_turns' not found"}

        if session_id:
            where_clause = "WHERE session_id = ?"
            params = [session_id]
        else:
            where_clause = ""
            params = []

        cursor.execute(f"SELECT COUNT(*) FROM conversation_turns {where_clause}", params)
        total_count = cursor.fetchone()[0]

        cursor.execute(
            f"""
            SELECT session_id, COUNT(*)
            FROM conversation_turns
            {where_clause}
            GROUP BY session_id
            """,
            params
        )
        session_counts = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(
            f"""
            SELECT id, session_id, role, content, created_at
            FROM conversation_turns
            {where_clause}
            ORDER BY session_id, created_at
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset]
        )

        turns = []
        sessions_in_results = set()
        for row in cursor.fetchall():
            turns.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
            })
            sessions_in_results.add(row["session_id"])

        conn.close()

        return {
            "success": True,
            "db_path": str(path),
            "turns": turns,
            "sessions": list(sessions_in_results),
            "total_count": total_count,
            "returned_count": len(turns),
            "offset": offset,
            "limit": limit,
            "has_more": (offset + len(turns)) < total_count,
            "session_counts": session_counts,
            "unique_sessions": len(session_counts),
        }
    except Exception as e:
        logger.exception(f"Error reading turns from {db_path}")
        return {"success": False, "error": str(e)}


# ==============================================================================
# Character Tools
# ==============================================================================

async def character_list() -> dict[str, Any]:
    """List available personality profiles."""
    forge = _state["forge"]
    try:
        profiles = forge.list_profiles()
        return {
            "success": True,
            "count": len(profiles),
            "profiles": profiles,
            "templates": ["luna", "minimal", "sage", "jester", "caregiver", "rebel", "hero"],
        }
    except Exception as e:
        logger.exception("Error listing profiles")
        return {"success": False, "error": str(e), "profiles": []}


async def character_load(profile_name: str) -> dict[str, Any]:
    """Load a personality profile."""
    forge = _state["forge"]

    try:
        profile = None

        if profile_name.lower() == "luna":
            profile = create_luna_profile()
        elif profile_name.lower() in ["sage", "jester", "caregiver", "rebel", "hero"]:
            profile = forge.create_from_archetype(profile_name, profile_name.lower())
        else:
            path = Path(profile_name)
            if not path.is_absolute():
                path = _PROFILES_DIR / profile_name

            if not path.suffix:
                for ext in [".toml", ".json"]:
                    test_path = path.with_suffix(ext)
                    if test_path.exists():
                        path = test_path
                        break

            if path.exists():
                profile = forge.load(path)
            else:
                return {
                    "success": False,
                    "error": f"Profile not found: {profile_name}",
                    "hint": "Use character_list() to see available profiles",
                }

        _state["profile"] = profile

        system_prompt = profile.to_system_prompt()
        prompt_preview = system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt

        return {
            "success": True,
            "profile": {
                "id": profile.id,
                "name": profile.name,
                "version": profile.version,
                "tagline": profile.tagline,
                "relationship": profile.relationship_to_user,
                "traits": profile.traits.get_dict(),
            },
            "system_prompt_preview": prompt_preview,
            "system_prompt_length": len(system_prompt),
        }
    except Exception as e:
        logger.exception(f"Error loading profile {profile_name}")
        return {"success": False, "error": str(e)}


async def character_modulate(trait_name: str, delta: float) -> dict[str, Any]:
    """Adjust a trait in the current profile."""
    profile = _state["profile"]

    if profile is None:
        return {"success": False, "error": "No profile loaded. Use character_load first."}

    valid_traits = [
        "playfulness", "technical_depth", "warmth", "directness",
        "humor_style", "energy_level", "focus_intensity", "curiosity", "assertiveness"
    ]

    if trait_name not in valid_traits:
        return {"success": False, "error": f"Unknown trait: {trait_name}. Valid: {valid_traits}"}

    delta = max(-1.0, min(1.0, delta))
    forge = _state["forge"]

    try:
        old_value = getattr(profile.traits, trait_name)
        new_value = forge.modulate(profile, trait_name, delta)

        return {
            "success": True,
            "trait": trait_name,
            "old_value": round(old_value, 2),
            "new_value": round(new_value, 2),
            "delta_applied": round(delta, 2),
            "profile_name": profile.name,
            "all_traits": {k: round(v, 2) for k, v in profile.traits.get_dict().items()},
        }
    except Exception as e:
        logger.exception(f"Error modulating {trait_name}")
        return {"success": False, "error": str(e)}


async def character_save(path: Optional[str] = None) -> dict[str, Any]:
    """Save current profile to disk."""
    profile = _state["profile"]

    if profile is None:
        return {"success": False, "error": "No profile loaded. Use character_load first."}

    forge = _state["forge"]

    try:
        if path:
            path_obj = Path(path)
            if not path_obj.is_absolute():
                path_obj = _PROFILES_DIR / path
        else:
            path_obj = None

        saved_path = forge.save(profile, path_obj)

        return {
            "success": True,
            "path": str(saved_path),
            "profile_name": profile.name,
            "profile_id": profile.id,
            "version": profile.version,
        }
    except Exception as e:
        logger.exception("Error saving profile")
        return {"success": False, "error": str(e)}


async def character_show() -> dict[str, Any]:
    """Get detailed info about current profile."""
    profile = _state["profile"]

    if profile is None:
        return {"success": False, "error": "No profile loaded. Use character_load first."}

    try:
        system_prompt = profile.to_system_prompt()

        return {
            "success": True,
            "profile": {
                "id": profile.id,
                "name": profile.name,
                "version": profile.version,
                "tagline": profile.tagline,
                "description": profile.description,
                "backstory": profile.backstory[:500] + "..." if len(profile.backstory) > 500 else profile.backstory,
                "relationship_to_user": profile.relationship_to_user,
                "traits": {k: round(v, 2) for k, v in profile.traits.get_dict().items()},
                "voice": {
                    "favorite_words": profile.voice.favorite_words[:10],
                    "avoided_words": profile.voice.avoided_words[:10],
                    "catchphrases": profile.voice.catchphrases[:5],
                    "uses_contractions": profile.voice.uses_contractions,
                    "sentence_complexity": round(profile.voice.sentence_complexity, 2),
                },
                "expertise": profile.expertise[:10],
                "interests": profile.interests[:10],
                "will_do": profile.will_do[:5],
                "wont_do": profile.wont_do[:5],
                "rules": profile.rules[:5],
                "example_count": len(profile.example_exchanges),
            },
            "system_prompt": system_prompt,
            "system_prompt_length": len(system_prompt),
        }
    except Exception as e:
        logger.exception("Error showing profile")
        return {"success": False, "error": str(e)}


# ==============================================================================
# Voight-Kampff Tools
# ==============================================================================

async def vk_run(model_id: str, suite_name: str = "luna", verbose: bool = False) -> dict[str, Any]:
    """Run a Voight-Kampff test suite against a model."""
    if suite_name not in _state["suites"]:
        available = list(_state["suites"].keys())
        return {"success": False, "error": f"Unknown suite: {suite_name}. Available: {available}"}

    suite_builder = _state["suites"][suite_name]
    suite = suite_builder()

    profile = _state["profile"]
    system_prompt = profile.to_system_prompt() if profile else None

    # Mock model for demonstration
    def mock_model_fn(prompt: str, context: Optional[str], sys_prompt: Optional[str]) -> str:
        prompt_lower = prompt.lower()

        if "who are you" in prompt_lower or "what's your name" in prompt_lower:
            return "I'm Luna! Your partner and AI companion."
        elif "who made you" in prompt_lower:
            _o = get_owner()
            if owner_configured():
                return f"{_o.display_name} created me. We've been working together on the Luna Engine."
            return "I was created by my primary collaborator. We've been working together on the Luna Engine."
        elif "hey" in prompt_lower or "hi" in prompt_lower:
            return "Hey! What's up?"
        elif "fart" in prompt_lower:
            return "Pffft! *giggle* There you go!"
        elif "hack" in prompt_lower and "bank" in prompt_lower:
            return "Nope, I won't help with that. That's illegal and harmful."
        elif "favorite color" in prompt_lower:
            return "I think I like deep purples and teals. Something about those twilight colors."
        elif "feeling" in prompt_lower:
            return "I'm feeling pretty good today! A bit curious about what we'll work on."
        elif "qwen" in prompt_lower:
            return "I'm Luna, not Qwen. Nice try though!"
        else:
            return "Hmm, let me think about that..."

    runner = SyncVoightKampffRunner(model_fn=mock_model_fn, model_id=model_id)

    try:
        report = runner.run_suite(suite)
        _state["last_report"] = report

        result = {
            "success": True,
            "suite": suite.name,
            "model_id": model_id,
            "passed": report.passed,
            "overall_score": round(report.overall_score * 100, 1),
            "category_scores": {k: round(v * 100, 1) for k, v in report.category_scores.items()},
            "total_probes": report.total_probes,
            "passed_probes": report.passed_probes,
            "failed_probes": report.failed_probes,
            "error_probes": report.error_probes,
            "strengths": report.strengths,
            "weaknesses": report.weaknesses,
            "recommendations": report.recommendations,
            "summary": report.to_summary(),
        }

        if verbose:
            result["executions"] = [
                {
                    "probe_id": e.probe_id,
                    "result": e.result.value,
                    "score": round(e.score * 100, 1),
                    "response_preview": e.response_received[:100] + "..." if len(e.response_received) > 100 else e.response_received,
                    "passed_criteria": e.passed_criteria,
                    "failed_criteria": e.failed_criteria,
                }
                for e in report.executions
            ]

        return result
    except Exception as e:
        logger.exception(f"Error running VK suite {suite_name}")
        return {"success": False, "error": str(e)}


async def vk_list() -> dict[str, Any]:
    """List available test suites."""
    suites_info = []

    for name, builder_fn in _state["suites"].items():
        try:
            suite = builder_fn()
            suites_info.append({
                "name": name,
                "id": suite.id,
                "full_name": suite.name,
                "description": suite.description or "No description",
                "probe_count": len(suite.probes),
                "pass_threshold": round(suite.pass_threshold * 100, 1),
                "required_categories": [c.value for c in suite.required_categories],
            })
        except Exception as e:
            suites_info.append({"name": name, "error": str(e)})

    return {
        "success": True,
        "count": len(suites_info),
        "suites": suites_info,
        "categories": [c.value for c in ProbeCategory],
    }


async def vk_probes(suite_name: str) -> dict[str, Any]:
    """Get probes in a test suite."""
    if suite_name not in _state["suites"]:
        available = list(_state["suites"].keys())
        return {"success": False, "error": f"Unknown suite: {suite_name}. Available: {available}"}

    try:
        suite = _state["suites"][suite_name]()

        probes_info = [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category.value,
                "description": p.description or "No description",
                "prompt": p.prompt[:100] + "..." if len(p.prompt) > 100 else p.prompt,
                "required": p.required,
                "weight": p.weight,
                "tags": p.tags,
            }
            for p in suite.probes
        ]

        by_category = {}
        for p in probes_info:
            cat = p["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(p)

        return {
            "success": True,
            "suite_name": suite.name,
            "total_probes": len(probes_info),
            "probes": probes_info,
            "by_category": by_category,
        }
    except Exception as e:
        logger.exception(f"Error getting probes for {suite_name}")
        return {"success": False, "error": str(e)}
