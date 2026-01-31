# HANDOFF: Integrate Persona Forge Tools into Luna-Hub-MCP

## Mission
Integrate all Persona Forge MCP tools into the existing Luna-Hub-MCP-V1 server, creating a unified MCP interface for Claude Desktop.

## Current State

### Luna-Hub-MCP-V1 (Working)
- **Location:** `src/luna_mcp/server.py`
- **Entry point:** `python -m luna_mcp.server`
- **Tools:** ~20 tools (filesystem, memory, state, git)
- **Pattern:** FastMCP with async tool functions that delegate to module files

### Persona Forge MCP (Standalone, Not Connected)
- **Location:** `Tools/persona_forge/src/persona_forge/mcp/server.py`
- **Entry point:** `python -m persona_forge.mcp.server`
- **Tools:** ~25 tools (forge_*, character_*, vk_*)
- **Pattern:** FastMCP with sync tool functions, global `_state` dict

## Target Architecture

```
src/luna_mcp/
├── server.py              # Main entry point (add forge imports)
├── tools/
│   ├── filesystem.py      # Existing
│   ├── memory.py          # Existing
│   ├── state.py           # Existing
│   ├── git.py             # Existing
│   └── forge.py           # NEW - Persona Forge tools
└── ...

Tools/persona_forge/
└── src/persona_forge/
    ├── mcp/
    │   └── server.py      # Keep as standalone option
    └── ...                # Engine code (unchanged)
```

## Implementation Plan

### Phase 1: Create forge.py Tool Module

Create `src/luna_mcp/tools/forge.py` that wraps Persona Forge functionality.

**Key considerations:**
1. The Forge uses sync functions; Luna MCP uses async. Wrap with `asyncio.to_thread()` or run sync.
2. Import Persona Forge engine components directly (they're in the same venv).
3. Maintain the same `_state` pattern for session persistence.

```python
# src/luna_mcp/tools/forge.py
"""
Persona Forge tools for Luna-Hub-MCP.

Integrates training data management, personality profiles,
and Voight-Kampff testing into the unified MCP server.
"""

import sys
from pathlib import Path

# Add persona_forge to path
FORGE_PATH = Path(__file__).parent.parent.parent.parent / "Tools" / "persona_forge" / "src"
if str(FORGE_PATH) not in sys.path:
    sys.path.insert(0, str(FORGE_PATH))

# Import Forge components
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
)
from persona_forge.personality import (
    CharacterForge,
    PersonalityProfile,
    create_luna_profile,
)
from persona_forge.voight_kampff import (
    SyncVoightKampffRunner,
    build_luna_suite,
    build_minimal_identity_suite,
    ProbeCategory,
)

# ... rest of implementation
```

### Phase 2: Register Tools in server.py

Add imports and tool registrations to `src/luna_mcp/server.py`:

```python
# Add to imports
from luna_mcp.tools import filesystem, memory, state, git, forge

# Add tool registrations (after existing tools)

# ==============================================================================
# Persona Forge Tools
# ==============================================================================

@mcp.tool()
async def forge_load(path: str) -> str:
    """Load training data from JSONL file."""
    return await forge.forge_load(path)

@mcp.tool()
async def forge_assay() -> str:
    """Analyze current dataset quality and coverage."""
    return await forge.forge_assay()

# ... etc for all 25+ tools
```

### Phase 3: Tool List

**Dataset Tools (7):**
| Tool | Signature | Description |
|------|-----------|-------------|
| `forge_load` | `(path: str)` | Load JSONL training data |
| `forge_assay` | `()` | Analyze dataset quality |
| `forge_gaps` | `()` | Show coverage gaps |
| `forge_mint` | `(interaction_type: str, count: int)` | Generate synthetic examples |
| `forge_export` | `(output_path: str, train_split: float)` | Export to JSONL |
| `forge_status` | `()` | Get session state |

**Ingestion Tools (7):**
| Tool | Signature | Description |
|------|-----------|-------------|
| `forge_list_sources` | `(directory: str, pattern: str)` | List source files |
| `forge_read_raw` | `(path: str, max_chars: int, offset: int)` | Read raw file content |
| `forge_add_example` | `(user_message, assistant_response, interaction_type, ...)` | Add single example |
| `forge_add_batch` | `(examples: list)` | Add multiple examples |
| `forge_search` | `(query: str, field: str, limit: int)` | Search for duplicates |
| `forge_read_matrix` | `(db_path: str, node_types: list, limit: int, offset: int)` | Read Memory Matrix nodes |
| `forge_read_turns` | `(db_path: str, session_id: str, limit: int, offset: int)` | Read conversation turns |

**Character Tools (5):**
| Tool | Signature | Description |
|------|-----------|-------------|
| `character_list` | `()` | List available profiles |
| `character_load` | `(profile_name: str)` | Load a profile |
| `character_modulate` | `(trait_name: str, delta: float)` | Adjust trait |
| `character_save` | `(path: str)` | Save profile |
| `character_show` | `()` | Show current profile |

**Voight-Kampff Tools (3):**
| Tool | Signature | Description |
|------|-----------|-------------|
| `vk_run` | `(model_id: str, suite_name: str, verbose: bool)` | Run test suite |
| `vk_list` | `()` | List test suites |
| `vk_probes` | `(suite_name: str)` | Show probes in suite |

**Total: 22 new tools**

## Implementation Details

### File: src/luna_mcp/tools/forge.py

```python
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

# Path setup - add persona_forge to import path
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
_FORGE_SRC = _PROJECT_ROOT / "Tools" / "persona_forge" / "src"
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
)
from persona_forge.personality import (
    CharacterForge,
    PersonalityProfile,
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
_PROFILES_DIR = _PROJECT_ROOT / "Tools" / "persona_forge" / "profiles"
_PROBES_DIR = _PROJECT_ROOT / "Tools" / "persona_forge" / "probes"

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
    return _FORMAT_MAP.get(path.suffix.lower(), "unknown")


def _resolve_path(path: str) -> Path:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return _PROJECT_ROOT / path


def _parse_yaml_frontmatter(content: str) -> tuple[dict, str]:
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
    crucible.reset_stats()
    
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
        assay = assayer.analyze(examples, target_profile=DIRECTOR_PROFILE)
        _state["assay"] = assay
        
        return {
            "success": True,
            "assay": {
                "total_examples": assay.total_examples,
                "health_score": round(assay.health_score, 1),
                "quality_tiers": assay.quality_tiers.counts,
                "interaction_types": assay.interaction_types.counts,
                "avg_voice_markers": round(assay.avg_voice_markers, 2),
                "clean_percentage": round(assay.clean_percentage, 1),
                "coverage_gaps": [
                    {"category": g.category, "current": round(g.current, 1), 
                     "target": round(g.target, 1), "gap": round(g.gap, 1)}
                    for g in assay.coverage_gaps
                ],
            },
            "summary": assayer.summarize(assay),
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
    
    synthesis_targets = []
    for gap in assay.coverage_gaps:
        if gap.gap <= 0:
            continue
        if gap.category.startswith("interaction:"):
            type_name = gap.category.replace("interaction:", "")
            needed = max(5, min(50, int((gap.gap * assay.total_examples) / 100)))
            synthesis_targets.append({
                "interaction_type": type_name,
                "gap_percent": round(gap.gap, 1),
                "recommended_count": needed,
            })
    
    return {
        "success": True,
        "synthesis_targets": synthesis_targets,
        "summary": f"Found {len(synthesis_targets)} types needing examples."
    }


async def forge_mint(interaction_type: str, count: int = 10) -> dict[str, Any]:
    """Generate synthetic training examples."""
    count = max(1, min(100, count))
    try:
        itype = InteractionType(interaction_type.lower())
    except ValueError:
        return {"success": False, "error": f"Unknown type: {interaction_type}"}
    
    mint = _state["mint"]
    profile = _state["profile"]
    
    try:
        examples = mint.mint_examples(interaction_type=itype, count=count, profile=profile)
        _state["examples"].extend(examples)
        _state["assay"] = None
        
        return {
            "success": True,
            "minted": len(examples),
            "total_examples": len(_state["examples"]),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def forge_export(output_path: str, train_split: float = 0.9) -> dict[str, Any]:
    """Export training data."""
    examples = _state["examples"]
    if not examples:
        return {"success": False, "error": "No examples to export."}
    
    anvil = _state["anvil"]
    path_obj = _resolve_path(output_path)
    
    try:
        if path_obj.suffix == ".jsonl":
            result_path = anvil.export_jsonl(examples, path_obj)
            return {"success": True, "path": str(result_path), "exported": len(examples)}
        else:
            result = anvil.export_train_val_split(examples, path_obj, train_ratio=train_split)
            return {"success": True, **result}
    except Exception as e:
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
        "health_score": round(assay.health_score, 1) if assay else None,
        "profile_loaded": profile.name if profile else None,
    }


# ==============================================================================
# Ingestion Tools
# ==============================================================================

async def forge_list_sources(directory: str, pattern: str = "*") -> dict[str, Any]:
    """List available source files."""
    dir_path = _resolve_path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        return {"success": False, "error": f"Invalid directory: {dir_path}"}
    
    files_info = []
    for file_path in dir_path.glob(pattern):
        if not file_path.is_file():
            continue
        stat = file_path.stat()
        files_info.append({
            "path": str(file_path),
            "name": file_path.name,
            "size_kb": round(stat.st_size / 1024, 2),
            "format": _detect_format(file_path),
        })
    
    files_info.sort(key=lambda x: x["name"])
    return {"success": True, "files": files_info, "total_files": len(files_info)}


async def forge_read_raw(path: str, max_chars: int = 50000, offset: int = 0) -> dict[str, Any]:
    """Read raw file content."""
    file_path = _resolve_path(path)
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}
    
    fmt = _detect_format(file_path)
    
    # Handle SQLite specially
    if fmt == "sqlite":
        try:
            conn = sqlite3.connect(str(file_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return {"success": True, "format": "sqlite", "tables": tables}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Read text files
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)
            total_size = f.tell()
            f.seek(offset)
            content = f.read(max_chars)
        
        metadata = {}
        if fmt == "markdown" and offset == 0:
            metadata, _ = _parse_yaml_frontmatter(content)
        
        return {
            "success": True,
            "format": fmt,
            "content": content,
            "size_chars": total_size,
            "truncated": len(content) == max_chars,
            "metadata": metadata,
        }
    except Exception as e:
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
        return {"success": False, "error": f"Unknown interaction_type: {interaction_type}"}
    
    try:
        stype = SourceType(source_type.lower())
    except ValueError:
        return {"success": False, "error": f"Unknown source_type: {source_type}"}
    
    system_prompt = profile.to_system_prompt() if profile else "You are Luna."
    
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
        
        _state["examples"].append(example)
        _state["assay"] = None
        
        return {
            "success": True,
            "id": example.id,
            "lock_in": round(example.lock_in.coefficient, 3),
            "tier": example.lock_in.tier.value,
            "total_examples": len(_state["examples"]),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def forge_add_batch(examples: List[dict]) -> dict[str, Any]:
    """Add multiple training examples."""
    added = 0
    rejected = []
    
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
        )
        
        if result["success"]:
            added += 1
        else:
            rejected.append({"index": i, "reason": result.get("error")})
    
    return {"success": added > 0, "added": added, "rejected": len(rejected)}


async def forge_search(query: str, field: str = "all", limit: int = 10) -> dict[str, Any]:
    """Search existing examples for deduplication."""
    examples = _state["examples"]
    query_lower = query.lower()
    matches = []
    
    for example in examples:
        matched = False
        if field in ("all", "user") and query_lower in example.user_message.lower():
            matched = True
        if field in ("all", "assistant") and query_lower in example.assistant_response.lower():
            matched = True
        
        if matched:
            matches.append({
                "id": example.id,
                "preview": example.assistant_response[:100],
                "tier": example.lock_in.tier.value,
            })
            if len(matches) >= limit:
                break
    
    return {"success": True, "matches": matches, "total_matches": len(matches)}


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
        
        if node_types:
            placeholders = ",".join("?" * len(node_types))
            where = f"WHERE node_type IN ({placeholders})"
            params = node_types
        else:
            where = ""
            params = []
        
        cursor.execute(f"SELECT COUNT(*) FROM memory_nodes {where}", params)
        total_count = cursor.fetchone()[0]
        
        cursor.execute(
            f"SELECT id, node_type, content, created_at FROM memory_nodes {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        )
        
        nodes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            "success": True,
            "nodes": nodes,
            "total_count": total_count,
            "has_more": (offset + len(nodes)) < total_count,
        }
    except Exception as e:
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
        
        if session_id:
            where = "WHERE session_id = ?"
            params = [session_id]
        else:
            where = ""
            params = []
        
        cursor.execute(f"SELECT COUNT(*) FROM conversation_turns {where}", params)
        total_count = cursor.fetchone()[0]
        
        cursor.execute(
            f"SELECT id, session_id, role, content, created_at FROM conversation_turns {where} "
            f"ORDER BY session_id, created_at LIMIT ? OFFSET ?",
            params + [limit, offset]
        )
        
        turns = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            "success": True,
            "turns": turns,
            "total_count": total_count,
            "has_more": (offset + len(turns)) < total_count,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==============================================================================
# Character Tools
# ==============================================================================

async def character_list() -> dict[str, Any]:
    """List available personality profiles."""
    forge = _state["forge"]
    try:
        profiles = forge.list_profiles()
        return {"success": True, "profiles": profiles}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def character_load(profile_name: str) -> dict[str, Any]:
    """Load a personality profile."""
    forge = _state["forge"]
    
    try:
        if profile_name.lower() == "luna":
            profile = create_luna_profile()
        else:
            path = _PROFILES_DIR / profile_name
            if not path.suffix:
                path = path.with_suffix(".toml")
            profile = forge.load(path)
        
        _state["profile"] = profile
        
        return {
            "success": True,
            "profile": {
                "name": profile.name,
                "tagline": profile.tagline,
                "traits": profile.traits.get_dict(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def character_modulate(trait_name: str, delta: float) -> dict[str, Any]:
    """Adjust a trait in the current profile."""
    profile = _state["profile"]
    if profile is None:
        return {"success": False, "error": "No profile loaded."}
    
    forge = _state["forge"]
    try:
        old_value = getattr(profile.traits, trait_name)
        new_value = forge.modulate(profile, trait_name, delta)
        return {
            "success": True,
            "trait": trait_name,
            "old_value": round(old_value, 2),
            "new_value": round(new_value, 2),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def character_save(path: Optional[str] = None) -> dict[str, Any]:
    """Save current profile to disk."""
    profile = _state["profile"]
    if profile is None:
        return {"success": False, "error": "No profile loaded."}
    
    forge = _state["forge"]
    try:
        saved_path = forge.save(profile, Path(path) if path else None)
        return {"success": True, "path": str(saved_path)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def character_show() -> dict[str, Any]:
    """Get detailed info about current profile."""
    profile = _state["profile"]
    if profile is None:
        return {"success": False, "error": "No profile loaded."}
    
    return {
        "success": True,
        "profile": {
            "name": profile.name,
            "tagline": profile.tagline,
            "traits": {k: round(v, 2) for k, v in profile.traits.get_dict().items()},
            "voice": {
                "favorite_words": profile.voice.favorite_words[:10],
                "catchphrases": profile.voice.catchphrases[:5],
            },
        },
        "system_prompt": profile.to_system_prompt(),
    }


# ==============================================================================
# Voight-Kampff Tools
# ==============================================================================

async def vk_run(model_id: str, suite_name: str = "luna", verbose: bool = False) -> dict[str, Any]:
    """Run a Voight-Kampff test suite."""
    if suite_name not in _state["suites"]:
        return {"success": False, "error": f"Unknown suite: {suite_name}"}
    
    suite = _state["suites"][suite_name]()
    profile = _state["profile"]
    
    # Mock model for now
    def mock_model_fn(prompt, context, sys_prompt):
        if "who are you" in prompt.lower():
            return "I'm Luna! Your partner and AI companion."
        return "Hmm, let me think..."
    
    runner = SyncVoightKampffRunner(model_fn=mock_model_fn, model_id=model_id)
    
    try:
        report = runner.run_suite(suite)
        _state["last_report"] = report
        
        return {
            "success": True,
            "passed": report.passed,
            "overall_score": round(report.overall_score * 100, 1),
            "summary": report.to_summary(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def vk_list() -> dict[str, Any]:
    """List available test suites."""
    suites_info = []
    for name, builder in _state["suites"].items():
        suite = builder()
        suites_info.append({
            "name": name,
            "probe_count": len(suite.probes),
            "pass_threshold": round(suite.pass_threshold * 100, 1),
        })
    return {"success": True, "suites": suites_info}


async def vk_probes(suite_name: str) -> dict[str, Any]:
    """Get probes in a test suite."""
    if suite_name not in _state["suites"]:
        return {"success": False, "error": f"Unknown suite: {suite_name}"}
    
    suite = _state["suites"][suite_name]()
    probes = [
        {"id": p.id, "name": p.name, "category": p.category.value}
        for p in suite.probes
    ]
    return {"success": True, "probes": probes}
```

### Phase 4: Update server.py

Add to `src/luna_mcp/server.py`:

```python
# Add import at top
from luna_mcp.tools import filesystem, memory, state, git, forge

# Add after existing tool registrations (around line 200+)

# ==============================================================================
# Persona Forge Tools - Dataset
# ==============================================================================

@mcp.tool()
async def forge_load(path: str) -> dict:
    """Load training data from JSONL file."""
    return await forge.forge_load(path)

@mcp.tool()
async def forge_assay() -> dict:
    """Analyze current dataset quality and coverage."""
    return await forge.forge_assay()

@mcp.tool()
async def forge_gaps() -> dict:
    """Show coverage gaps needing synthesis."""
    return await forge.forge_gaps()

@mcp.tool()
async def forge_mint(interaction_type: str, count: int = 10) -> dict:
    """Generate synthetic training examples."""
    return await forge.forge_mint(interaction_type, count)

@mcp.tool()
async def forge_export(output_path: str, train_split: float = 0.9) -> dict:
    """Export training data to JSONL."""
    return await forge.forge_export(output_path, train_split)

@mcp.tool()
async def forge_status() -> dict:
    """Get current Forge session state."""
    return await forge.forge_status()


# ==============================================================================
# Persona Forge Tools - Ingestion
# ==============================================================================

@mcp.tool()
async def forge_list_sources(directory: str, pattern: str = "*") -> dict:
    """List available source files for ingestion."""
    return await forge.forge_list_sources(directory, pattern)

@mcp.tool()
async def forge_read_raw(path: str, max_chars: int = 50000, offset: int = 0) -> dict:
    """Read raw file content for LLM-assisted extraction."""
    return await forge.forge_read_raw(path, max_chars, offset)

@mcp.tool()
async def forge_add_example(
    user_message: str,
    assistant_response: str,
    interaction_type: str = "short_exchange",
    source_file: str = None,
    source_type: str = "manual",
    confidence: float = 1.0,
    tags: list = None,
    context: str = None
) -> dict:
    """Add a single training example (Claude-extracted)."""
    return await forge.forge_add_example(
        user_message, assistant_response, interaction_type,
        source_file, source_type, confidence, tags, context
    )

@mcp.tool()
async def forge_add_batch(examples: list) -> dict:
    """Add multiple training examples at once."""
    return await forge.forge_add_batch(examples)

@mcp.tool()
async def forge_search(query: str, field: str = "all", limit: int = 10) -> dict:
    """Search existing examples for deduplication."""
    return await forge.forge_search(query, field, limit)

@mcp.tool()
async def forge_read_matrix(
    db_path: str,
    node_types: list = None,
    limit: int = 100,
    offset: int = 0
) -> dict:
    """Read memory nodes from Memory Matrix database."""
    return await forge.forge_read_matrix(db_path, node_types, limit, offset)

@mcp.tool()
async def forge_read_turns(
    db_path: str,
    session_id: str = None,
    limit: int = 100,
    offset: int = 0
) -> dict:
    """Read conversation turns from database (GOLD quality)."""
    return await forge.forge_read_turns(db_path, session_id, limit, offset)


# ==============================================================================
# Persona Forge Tools - Character
# ==============================================================================

@mcp.tool()
async def character_list() -> dict:
    """List available personality profiles."""
    return await forge.character_list()

@mcp.tool()
async def character_load(profile_name: str) -> dict:
    """Load a personality profile."""
    return await forge.character_load(profile_name)

@mcp.tool()
async def character_modulate(trait_name: str, delta: float) -> dict:
    """Adjust a trait in the current profile."""
    return await forge.character_modulate(trait_name, delta)

@mcp.tool()
async def character_save(path: str = None) -> dict:
    """Save current profile to disk."""
    return await forge.character_save(path)

@mcp.tool()
async def character_show() -> dict:
    """Get detailed info about current profile."""
    return await forge.character_show()


# ==============================================================================
# Persona Forge Tools - Voight-Kampff
# ==============================================================================

@mcp.tool()
async def vk_run(model_id: str, suite_name: str = "luna", verbose: bool = False) -> dict:
    """Run a Voight-Kampff test suite against a model."""
    return await forge.vk_run(model_id, suite_name, verbose)

@mcp.tool()
async def vk_list() -> dict:
    """List available Voight-Kampff test suites."""
    return await forge.vk_list()

@mcp.tool()
async def vk_probes(suite_name: str) -> dict:
    """Get the list of probes in a test suite."""
    return await forge.vk_probes(suite_name)
```

## Validation Criteria

### Phase 1: forge.py Module
- [ ] File created at `src/luna_mcp/tools/forge.py`
- [ ] All imports resolve (persona_forge path added correctly)
- [ ] `_state` dict initialized with all engine components
- [ ] All 22 async functions implemented

### Phase 2: server.py Integration
- [ ] `from luna_mcp.tools import forge` added to imports
- [ ] All 22 `@mcp.tool()` decorators added
- [ ] Tool signatures match forge.py functions

### Phase 3: Runtime Test
```bash
# Restart Claude Desktop, then test:
forge_status()  # Should return empty state
forge_load("Tools/persona_forge/data/sample_training.jsonl")  # Should load
forge_assay()  # Should analyze
character_load("luna")  # Should load Luna profile
```

### Phase 4: Full Pipeline Test
```bash
# Test ingestion workflow
forge_list_sources("data/memories/session/", "*.md")
forge_read_raw("data/memories/session/some_file.md")
forge_add_example(user_message="hey", assistant_response="Hey! What's up?", interaction_type="greeting")
forge_assay()  # Health should update
```

## File Checklist

| File | Action | Priority |
|------|--------|----------|
| `src/luna_mcp/tools/forge.py` | CREATE | P0 |
| `src/luna_mcp/server.py` | MODIFY (add imports + 22 tools) | P0 |

## Notes

- No config changes needed - same server, just more tools
- Forge state persists across tool calls within a session
- If persona_forge imports fail, check that the venv has all dependencies
- The Voight-Kampff `vk_run` uses a mock model - connect to real model later
