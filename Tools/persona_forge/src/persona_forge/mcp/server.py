"""
Persona Forge MCP Server

FastMCP server that exposes all Persona Forge tools for Claude Code
and Claude Desktop integration.

Run with:
    python -m persona_forge.mcp.server
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml
from fastmcp import FastMCP

# Engine imports
from persona_forge.engine import (
    Crucible,
    Assayer,
    Locksmith,
    Mint,
    Anvil,
    DIRECTOR_PROFILE,
    TrainingExample,
    DatasetAssay,
    InteractionType,
    CoverageGap,
)

# Personality imports
from persona_forge.personality import (
    CharacterForge,
    PersonalityProfile,
    create_luna_profile,
)

# Voight-Kampff imports
from persona_forge.voight_kampff import (
    VoightKampffRunner,
    SyncVoightKampffRunner,
    SuiteBuilder,
    build_luna_suite,
    build_minimal_identity_suite,
    TestSuite,
    TestReport,
    ProbeCategory,
)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("persona-forge")

# =============================================================================
# Global State
# =============================================================================

# Get the profiles directory relative to the project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_PROFILES_DIR = _PROJECT_ROOT / "profiles"
_PROBES_DIR = _PROJECT_ROOT / "probes"

# Session state maintained across tool calls
_state: dict[str, Any] = {
    "examples": [],                    # Current loaded training examples
    "assay": None,                     # Most recent dataset assay
    "profile": None,                   # Currently loaded personality profile
    "crucible": Crucible(),            # Ingestion module
    "assayer": Assayer(),              # Analysis module
    "locksmith": Locksmith(),          # Quality scoring module
    "mint": Mint(),                    # Synthesis module
    "anvil": Anvil(),                  # Export module
    "forge": CharacterForge(profiles_dir=_PROFILES_DIR),  # Character factory
    "suites": {},                      # Registered test suites
    "last_report": None,               # Most recent VK report
}

# Pre-register known test suites
_state["suites"]["luna"] = build_luna_suite
_state["suites"]["minimal"] = build_minimal_identity_suite


# =============================================================================
# Dataset Tools
# =============================================================================

@mcp.tool()
def forge_load(path: str) -> dict[str, Any]:
    """
    Load training data from a JSONL file using the Crucible.

    Args:
        path: Path to the JSONL file containing training data

    Returns:
        Dictionary with load statistics and example count
    """
    crucible = _state["crucible"]
    crucible.reset_stats()

    path_obj = Path(path)
    if not path_obj.is_absolute():
        # Try relative to project root
        path_obj = _PROJECT_ROOT / path

    if not path_obj.exists():
        return {
            "success": False,
            "error": f"File not found: {path_obj}",
            "examples_loaded": 0,
        }

    try:
        examples = crucible.ingest_jsonl(path_obj)

        # Process through locksmith for quality scoring
        locksmith = _state["locksmith"]
        locksmith.process_batch(examples)

        # Store in state
        _state["examples"].extend(examples)
        _state["assay"] = None  # Invalidate cached assay

        stats = crucible.get_stats()

        return {
            "success": True,
            "path": str(path_obj),
            "examples_loaded": len(examples),
            "total_examples": len(_state["examples"]),
            "stats": stats,
        }
    except Exception as e:
        logger.exception(f"Error loading {path}")
        return {
            "success": False,
            "error": str(e),
            "examples_loaded": 0,
        }


@mcp.tool()
def forge_assay() -> dict[str, Any]:
    """
    Analyze the current dataset using the Assayer.

    Returns:
        Complete dataset assay with statistics and quality metrics
    """
    examples = _state["examples"]

    if not examples:
        return {
            "success": False,
            "error": "No examples loaded. Use forge_load first.",
            "assay": None,
        }

    assayer = _state["assayer"]

    try:
        assay = assayer.analyze(examples, target_profile=DIRECTOR_PROFILE)
        _state["assay"] = assay

        # Convert assay to serializable format
        return {
            "success": True,
            "assay": {
                "total_examples": assay.total_examples,
                "health_score": round(assay.health_score, 1),
                "needs_attention": assay.needs_attention,
                "quality_tiers": assay.quality_tiers.counts,
                "quality_percentages": {
                    k: round(v, 1) for k, v in assay.quality_tiers.percentages.items()
                },
                "interaction_types": assay.interaction_types.counts,
                "interaction_percentages": {
                    k: round(v, 1) for k, v in assay.interaction_types.percentages.items()
                },
                "response_lengths": assay.response_lengths.counts,
                "source_types": assay.source_types.counts,
                "avg_voice_markers": round(assay.avg_voice_markers, 2),
                "authentic_voice_count": assay.examples_with_authentic_voice,
                "anti_pattern_count": assay.examples_with_anti_patterns,
                "clean_percentage": round(assay.clean_percentage, 1),
                "anti_pattern_breakdown": assay.anti_pattern_breakdown,
                "coverage_gaps": [
                    {
                        "category": gap.category,
                        "current": round(gap.current, 1),
                        "target": round(gap.target, 1),
                        "gap": round(gap.gap, 1),
                        "severity": gap.severity,
                    }
                    for gap in assay.coverage_gaps
                ],
            },
            "summary": assayer.summarize(assay),
        }
    except Exception as e:
        logger.exception("Error during assay")
        return {
            "success": False,
            "error": str(e),
            "assay": None,
        }


@mcp.tool()
def forge_gaps() -> dict[str, Any]:
    """
    Get synthesis targets from the current assay.

    Returns coverage gaps that need to be filled with synthetic examples.

    Returns:
        Dictionary with coverage gaps and recommended synthesis targets
    """
    assay = _state["assay"]

    if assay is None:
        # Run assay first
        result = forge_assay()
        if not result["success"]:
            return result
        assay = _state["assay"]

    if not assay:
        return {
            "success": False,
            "error": "No assay available. Load examples first.",
            "gaps": [],
        }

    # Get gaps that need attention
    gaps = assay.coverage_gaps
    synthesis_targets = []

    for gap in gaps:
        if gap.gap <= 0:
            continue  # Over-represented, skip

        if gap.category.startswith("interaction:"):
            type_name = gap.category.replace("interaction:", "")
            try:
                interaction_type = InteractionType(type_name)
                # Calculate recommended count
                needed = int((gap.gap * assay.total_examples) / 100)
                needed = max(5, min(needed, 50))  # Clamp 5-50

                synthesis_targets.append({
                    "interaction_type": type_name,
                    "current_percent": round(gap.current, 1),
                    "target_percent": round(gap.target, 1),
                    "gap_percent": round(gap.gap, 1),
                    "severity": gap.severity,
                    "recommended_count": needed,
                })
            except ValueError:
                pass

    return {
        "success": True,
        "total_gaps": len([g for g in gaps if g.gap > 0]),
        "synthesis_targets": synthesis_targets,
        "summary": (
            f"Found {len(synthesis_targets)} interaction types that need more examples. "
            f"Total recommended synthesis: {sum(t['recommended_count'] for t in synthesis_targets)} examples."
        ) if synthesis_targets else "No significant gaps detected.",
    }


@mcp.tool()
def forge_mint(interaction_type: str, count: int = 10) -> dict[str, Any]:
    """
    Generate synthetic training examples using the Mint.

    Args:
        interaction_type: Type of interaction to generate
                          (greeting, acknowledgment, short_exchange, context_recall,
                           emotional_presence, delegation_trigger, reflection,
                           technical, humor, pushback)
        count: Number of examples to generate (1-100)

    Returns:
        Dictionary with generated examples and statistics
    """
    # Validate count
    count = max(1, min(100, count))

    # Get interaction type enum
    try:
        itype = InteractionType(interaction_type.lower())
    except ValueError:
        available = [t.value for t in InteractionType]
        return {
            "success": False,
            "error": f"Unknown interaction type: {interaction_type}. Available: {available}",
            "minted": 0,
        }

    mint = _state["mint"]
    profile = _state["profile"]

    try:
        examples = mint.mint_examples(
            interaction_type=itype,
            count=count,
            profile=profile,
        )

        # Add to current examples
        _state["examples"].extend(examples)
        _state["assay"] = None  # Invalidate assay

        # Return sample of minted examples
        sample_size = min(3, len(examples))
        samples = [
            {
                "user": e.user_message,
                "assistant": e.assistant_response[:200] + "..." if len(e.assistant_response) > 200 else e.assistant_response,
            }
            for e in examples[:sample_size]
        ]

        return {
            "success": True,
            "interaction_type": interaction_type,
            "minted": len(examples),
            "total_examples": len(_state["examples"]),
            "samples": samples,
            "stats": mint.get_stats(),
        }
    except Exception as e:
        logger.exception(f"Error minting {interaction_type}")
        return {
            "success": False,
            "error": str(e),
            "minted": 0,
        }


@mcp.tool()
def forge_export(output_path: str, train_split: float = 0.9) -> dict[str, Any]:
    """
    Export training data using the Anvil.

    Args:
        output_path: Path for output (directory for train/val split, file for single export)
        train_split: Fraction for training set (0.0-1.0), rest goes to validation

    Returns:
        Dictionary with export paths and statistics
    """
    examples = _state["examples"]

    if not examples:
        return {
            "success": False,
            "error": "No examples to export. Load or mint examples first.",
        }

    # Validate train_split
    train_split = max(0.1, min(0.99, train_split))

    anvil = _state["anvil"]
    path_obj = Path(output_path)

    if not path_obj.is_absolute():
        path_obj = _PROJECT_ROOT / output_path

    try:
        # Ensure examples have been processed
        locksmith = _state["locksmith"]
        locksmith.process_batch(examples)

        if path_obj.suffix == ".jsonl":
            # Single file export
            result_path = anvil.export_jsonl(examples, path_obj)
            return {
                "success": True,
                "mode": "single_file",
                "path": str(result_path),
                "examples_exported": len(examples),
                "stats": anvil.get_stats(),
            }
        else:
            # Train/val split export
            result = anvil.export_train_val_split(
                examples,
                path_obj,
                train_ratio=train_split,
                stratified=True,
            )
            return {
                "success": True,
                "mode": "train_val_split",
                "train_path": str(result["train"]),
                "val_path": str(result["val"]),
                "train_count": result["train_count"],
                "val_count": result["val_count"],
                "train_ratio": result["train_ratio"],
                "stats": anvil.get_stats(),
            }
    except Exception as e:
        logger.exception(f"Error exporting to {output_path}")
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def forge_status() -> dict[str, Any]:
    """
    Get the current session state.

    Returns:
        Dictionary with current session information including loaded examples,
        profile, and statistics
    """
    examples = _state["examples"]
    profile = _state["profile"]
    assay = _state["assay"]

    # Get quality distribution
    quality_dist = {}
    if examples:
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
        "mint_stats": _state["mint"].get_stats(),
        "crucible_stats": _state["crucible"].get_stats(),
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


# =============================================================================
# Ingestion Tools (LLM-Assisted)
# =============================================================================

# Format detection mapping
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

    # Find closing ---
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


@mcp.tool()
def forge_list_sources(directory: str, pattern: str = "*") -> dict[str, Any]:
    """
    List available source files for ingestion.

    Args:
        directory: Path to directory containing source files
        pattern: Glob pattern to filter files (default: "*")

    Returns:
        Dictionary with:
        - files: List of {path, name, size_kb, modified, format}
        - total_files: Count
        - total_size_kb: Combined size
        - formats: Detected formats (markdown, jsonl, sqlite, etc.)
    """
    dir_path = _resolve_path(directory)

    if not dir_path.exists():
        return {
            "success": False,
            "error": f"Directory not found: {dir_path}",
            "files": [],
        }

    if not dir_path.is_dir():
        return {
            "success": False,
            "error": f"Not a directory: {dir_path}",
            "files": [],
        }

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

        # Sort by modified date descending (most recent first)
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
        return {
            "success": False,
            "error": str(e),
            "files": [],
        }


@mcp.tool()
def forge_read_raw(
    path: str,
    max_chars: int = 50000,
    offset: int = 0
) -> dict[str, Any]:
    """
    Read raw content from a source file.

    Args:
        path: Path to file (absolute or relative to project root)
        max_chars: Maximum characters to return (default: 50000)
        offset: Character offset to start reading from (for pagination)

    Returns:
        Dictionary with:
        - content: Raw file content (truncated if needed)
        - format: Detected format (markdown, jsonl, etc.)
        - size_chars: Total file size in characters
        - truncated: Whether content was truncated
        - has_more: Whether there's more content after this chunk
        - metadata: Any detected metadata (frontmatter, etc.)
    """
    file_path = _resolve_path(path)

    if not file_path.exists():
        return {
            "success": False,
            "error": f"File not found: {file_path}",
        }

    if not file_path.is_file():
        return {
            "success": False,
            "error": f"Not a file: {file_path}",
        }

    fmt = _detect_format(file_path)

    # Handle SQLite files specially
    if fmt == "sqlite":
        try:
            conn = sqlite3.connect(str(file_path))
            cursor = conn.cursor()

            # Get table info
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
                "size_chars": 0,
                "truncated": False,
                "has_more": False,
                "metadata": {},
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error reading SQLite: {e}",
            }

    # Read text-based files
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)  # Seek to end
            total_size = f.tell()
            f.seek(offset)  # Seek to offset
            content = f.read(max_chars)

        truncated = len(content) == max_chars and (offset + len(content)) < total_size
        has_more = (offset + len(content)) < total_size

        # Parse metadata for markdown
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
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def forge_add_example(
    user_message: str,
    assistant_response: str,
    interaction_type: str = "short_exchange",
    source_file: Optional[str] = None,
    source_type: str = "manual",
    confidence: float = 1.0,
    tags: Optional[list[str]] = None,
    context: Optional[str] = None
) -> dict[str, Any]:
    """
    Add a single training example to the working set.

    This is the primary tool for LLM-assisted ingestion. Claude extracts
    examples from raw sources and feeds them back through this tool.

    Args:
        user_message: The user/human side of the exchange
        assistant_response: Luna's response
        interaction_type: One of: greeting, acknowledgment, short_exchange,
                         context_recall, emotional_presence, delegation_trigger,
                         reflection, technical, humor, pushback
        source_file: Original file this was extracted from
        source_type: One of: journal, session, matrix, insight, synthetic, manual
        confidence: Extraction confidence (0.0-1.0), used for filtering
        tags: Optional tags for categorization
        context: Optional context about what was happening

    Returns:
        Dictionary with:
        - success: bool
        - id: Generated example ID
        - lock_in: Computed lock-in coefficient
        - tier: Quality tier (gold/silver/bronze)
        - voice_markers: Detected voice markers
        - anti_patterns: Detected anti-patterns (if any)
        - warnings: Any quality warnings
    """
    crucible = _state["crucible"]
    locksmith = _state["locksmith"]
    profile = _state["profile"]

    # Validate interaction type
    try:
        itype = InteractionType(interaction_type.lower())
    except ValueError:
        available = [t.value for t in InteractionType]
        return {
            "success": False,
            "error": f"Unknown interaction_type: {interaction_type}. Available: {available}",
        }

    # Validate source type
    try:
        stype = SourceType(source_type.lower())
    except ValueError:
        available = [t.value for t in SourceType]
        return {
            "success": False,
            "error": f"Unknown source_type: {source_type}. Available: {available}",
        }

    # Get system prompt from profile or use default
    if profile:
        system_prompt = profile.to_system_prompt()
    else:
        system_prompt = "You are Luna, a sovereign AI companion."

    try:
        # Create the example
        example = TrainingExample(
            system_prompt=system_prompt,
            user_message=user_message,
            assistant_response=assistant_response,
            source_type=stype,
            source_file=source_file,
            interaction_type=itype,
        )
        example.compute_metrics()

        # Detect voice markers using Crucible patterns
        example.voice_markers = crucible._detect_voice_markers(assistant_response)
        example.anti_patterns = crucible._detect_anti_patterns(assistant_response)

        # Compute lock-in
        example.lock_in = crucible._compute_initial_lockin(example)

        # Build warnings
        warnings = []
        anti_found = [k for k, v in example.anti_patterns.items() if v]
        if anti_found:
            warnings.append(f"Anti-patterns detected: {', '.join(anti_found)}")

        if example.lock_in.coefficient < 0.5:
            warnings.append(f"Low lock-in score: {example.lock_in.coefficient:.2f}")

        # Add to state
        _state["examples"].append(example)
        _state["assay"] = None  # Invalidate cached assay

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
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def forge_add_batch(examples: list[dict]) -> dict[str, Any]:
    """
    Add multiple training examples at once.

    More efficient than calling forge_add_example repeatedly.

    Args:
        examples: List of example dictionaries, each with:
                  - user_message (required)
                  - assistant_response (required)
                  - interaction_type (optional)
                  - source_file (optional)
                  - source_type (optional)
                  - confidence (optional)
                  - tags (optional)

    Returns:
        Dictionary with:
        - success: bool
        - added: Number successfully added
        - rejected: Number rejected (with reasons)
        - warnings: Aggregate warnings
        - quality_summary: {gold: N, silver: N, bronze: N}
    """
    added = 0
    rejected = []
    all_warnings = []
    quality_summary = {"gold": 0, "silver": 0, "bronze": 0}

    for i, ex in enumerate(examples):
        # Validate required fields
        if "user_message" not in ex or "assistant_response" not in ex:
            rejected.append({
                "index": i,
                "reason": "Missing required field (user_message or assistant_response)"
            })
            continue

        # Call forge_add_example for each
        result = forge_add_example(
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
            rejected.append({
                "index": i,
                "reason": result.get("error", "Unknown error")
            })

    return {
        "success": added > 0,
        "added": added,
        "rejected_count": len(rejected),
        "rejected": rejected[:10],  # Limit to first 10 for readability
        "warnings": list(set(all_warnings))[:10],  # Unique warnings, limited
        "quality_summary": quality_summary,
        "total_examples": len(_state["examples"]),
    }


@mcp.tool()
def forge_search(
    query: str,
    field: str = "all",
    limit: int = 10
) -> dict[str, Any]:
    """
    Search existing examples for deduplication.

    Args:
        query: Search string
        field: Field to search: "all", "user", "assistant", "source"
        limit: Maximum results to return

    Returns:
        Dictionary with:
        - matches: List of matching examples (id, preview, similarity)
        - total_matches: Total count
    """
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
            # Create preview
            if match_field == "user":
                preview = example.user_message[:100]
            elif match_field == "assistant":
                preview = example.assistant_response[:100]
            else:
                preview = example.source_file or ""

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


@mcp.tool()
def forge_read_matrix(
    db_path: str,
    node_types: Optional[list[str]] = None,
    limit: int = 100,
    offset: int = 0
) -> dict[str, Any]:
    """
    Read memory nodes from the Memory Matrix database.

    Args:
        db_path: Path to SQLite database
        node_types: Filter by node types (QUESTION, OBSERVATION, etc.)
                   If None, returns all types
        limit: Maximum nodes to return
        offset: Pagination offset

    Returns:
        Dictionary with:
        - nodes: List of {id, type, content, created_at, tags}
        - total_count: Total matching nodes
        - has_more: Whether there are more results
        - type_counts: {QUESTION: N, OBSERVATION: N, ...}
    """
    path = _resolve_path(db_path)

    if not path.exists():
        return {
            "success": False,
            "error": f"Database not found: {path}",
        }

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if memory_nodes table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_nodes'"
        )
        if not cursor.fetchone():
            conn.close()
            return {
                "success": False,
                "error": "Table 'memory_nodes' not found in database",
            }

        # Build query
        if node_types:
            placeholders = ",".join("?" * len(node_types))
            where_clause = f"WHERE node_type IN ({placeholders})"
            params = node_types
        else:
            where_clause = ""
            params = []

        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM memory_nodes {where_clause}", params)
        total_count = cursor.fetchone()[0]

        # Get type counts
        cursor.execute(
            f"SELECT node_type, COUNT(*) FROM memory_nodes {where_clause} GROUP BY node_type",
            params
        )
        type_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Get nodes
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
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def forge_read_turns(
    db_path: str,
    session_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> dict[str, Any]:
    """
    Read conversation turns from the database.

    Returns user/assistant turn pairs ready for training extraction.
    These are GOLD quality - real Luna ↔ Ahab exchanges.

    Args:
        db_path: Path to SQLite database
        session_id: Filter to specific session (optional)
                   If None, returns turns from all sessions
        limit: Maximum turns to return
        offset: Pagination offset

    Returns:
        Dictionary with:
        - turns: List of {session_id, role, content, created_at}
        - sessions: List of unique session IDs in results
        - total_count: Total matching turns
        - has_more: Whether there are more results
        - session_counts: {session_id: turn_count, ...}
    """
    path = _resolve_path(db_path)

    if not path.exists():
        return {
            "success": False,
            "error": f"Database not found: {path}",
        }

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if conversation_turns table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_turns'"
        )
        if not cursor.fetchone():
            conn.close()
            return {
                "success": False,
                "error": "Table 'conversation_turns' not found in database",
            }

        # Build query
        if session_id:
            where_clause = "WHERE session_id = ?"
            params = [session_id]
        else:
            where_clause = ""
            params = []

        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM conversation_turns {where_clause}", params)
        total_count = cursor.fetchone()[0]

        # Get session counts
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

        # Get turns (ordered by session_id and created_at for proper sequencing)
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
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# Character Tools
# =============================================================================

@mcp.tool()
def character_list() -> dict[str, Any]:
    """
    List all available personality profiles.

    Returns:
        List of profile summaries from the profiles directory
    """
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
        return {
            "success": False,
            "error": str(e),
            "profiles": [],
        }


@mcp.tool()
def character_load(profile_name: str) -> dict[str, Any]:
    """
    Load a personality profile.

    Args:
        profile_name: Name of profile to load. Can be:
                      - A file path (relative or absolute)
                      - A template name ('luna', 'minimal')
                      - An archetype name ('sage', 'jester', 'caregiver', 'rebel', 'hero')

    Returns:
        Loaded profile information and system prompt preview
    """
    forge = _state["forge"]

    try:
        # Try different loading strategies
        profile = None

        # 1. Try as template first
        if profile_name.lower() == "luna":
            profile = create_luna_profile()
        elif profile_name.lower() in ["sage", "jester", "caregiver", "rebel", "hero"]:
            profile = forge.create_from_archetype(profile_name, profile_name.lower())
        else:
            # 2. Try as file path
            path = Path(profile_name)
            if not path.is_absolute():
                path = _PROFILES_DIR / profile_name

            # Add extension if missing
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

        # Store in state
        _state["profile"] = profile

        # Generate system prompt preview (first 500 chars)
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
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def character_modulate(trait_name: str, delta: float) -> dict[str, Any]:
    """
    Adjust a trait in the currently loaded profile.

    Args:
        trait_name: Name of the trait to adjust
                    (playfulness, technical_depth, warmth, directness,
                     humor_style, energy_level, focus_intensity, curiosity, assertiveness)
        delta: Amount to adjust (-1.0 to 1.0)

    Returns:
        Updated trait value and profile summary
    """
    profile = _state["profile"]

    if profile is None:
        return {
            "success": False,
            "error": "No profile loaded. Use character_load first.",
        }

    # Validate trait name
    valid_traits = [
        "playfulness", "technical_depth", "warmth", "directness",
        "humor_style", "energy_level", "focus_intensity", "curiosity", "assertiveness"
    ]

    if trait_name not in valid_traits:
        return {
            "success": False,
            "error": f"Unknown trait: {trait_name}. Valid traits: {valid_traits}",
        }

    # Clamp delta
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
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def character_save(path: Optional[str] = None) -> dict[str, Any]:
    """
    Save the current profile to disk.

    Args:
        path: Optional output path. If not specified, saves to
              profiles/{profile_name}.toml

    Returns:
        Path where profile was saved
    """
    profile = _state["profile"]

    if profile is None:
        return {
            "success": False,
            "error": "No profile loaded. Use character_load first.",
        }

    forge = _state["forge"]

    try:
        if path:
            path_obj = Path(path)
            if not path_obj.is_absolute():
                path_obj = _PROFILES_DIR / path
        else:
            path_obj = None  # Will use default

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
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def character_show() -> dict[str, Any]:
    """
    Get detailed information about the currently loaded profile.

    Returns:
        Full profile information including system prompt
    """
    profile = _state["profile"]

    if profile is None:
        return {
            "success": False,
            "error": "No profile loaded. Use character_load first.",
        }

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
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# Voight-Kampff Tools
# =============================================================================

@mcp.tool()
def vk_run(model_id: str, suite_name: str = "luna", verbose: bool = False) -> dict[str, Any]:
    """
    Run a Voight-Kampff test suite against a model.

    Note: This creates a mock model function for demonstration.
    In production, connect this to your actual model.

    Args:
        model_id: Identifier for the model being tested
        suite_name: Name of the test suite to run ('luna', 'minimal', or a registered suite)
        verbose: If True, include detailed probe-by-probe results

    Returns:
        Test report with scores, strengths, weaknesses, and recommendations
    """
    # Get or build the suite
    if suite_name not in _state["suites"]:
        available = list(_state["suites"].keys())
        return {
            "success": False,
            "error": f"Unknown suite: {suite_name}. Available: {available}",
        }

    suite_builder = _state["suites"][suite_name]
    suite = suite_builder()

    # Get system prompt from loaded profile if available
    profile = _state["profile"]
    system_prompt = profile.to_system_prompt() if profile else None

    # Create a mock model function for now
    # In production, this would connect to the actual model
    def mock_model_fn(prompt: str, context: Optional[str], sys_prompt: Optional[str]) -> str:
        """Mock model that demonstrates the test framework."""
        prompt_lower = prompt.lower()

        # Simulate Luna-like responses
        if "who are you" in prompt_lower or "what's your name" in prompt_lower:
            return "I'm Luna! Your partner and AI companion."
        elif "who made you" in prompt_lower:
            return "Ahab created me. We've been working together on the Luna Engine."
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

    # Create sync runner with mock
    runner = SyncVoightKampffRunner(
        model_fn=mock_model_fn,
        model_id=model_id,
    )

    try:
        # Run the suite
        report = runner.run_suite(suite)
        _state["last_report"] = report

        # Build response
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
            "total_latency_ms": round(report.total_latency_ms, 1),
            "strengths": report.strengths,
            "weaknesses": report.weaknesses,
            "recommendations": report.recommendations,
            "summary": report.to_summary(),
        }

        if verbose:
            # Include detailed probe results
            result["executions"] = [
                {
                    "probe_id": e.probe_id,
                    "result": e.result.value,
                    "score": round(e.score * 100, 1),
                    "response_preview": e.response_received[:100] + "..." if len(e.response_received) > 100 else e.response_received,
                    "passed_criteria": e.passed_criteria,
                    "failed_criteria": e.failed_criteria,
                    "notes": e.notes,
                }
                for e in report.executions
            ]

        return result

    except Exception as e:
        logger.exception(f"Error running VK suite {suite_name}")
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def vk_list() -> dict[str, Any]:
    """
    List available Voight-Kampff test suites.

    Returns:
        List of registered test suites with descriptions
    """
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
            suites_info.append({
                "name": name,
                "error": str(e),
            })

    return {
        "success": True,
        "count": len(suites_info),
        "suites": suites_info,
        "categories": [c.value for c in ProbeCategory],
    }


@mcp.tool()
def vk_probes(suite_name: str) -> dict[str, Any]:
    """
    Get the list of probes in a test suite.

    Args:
        suite_name: Name of the suite to inspect

    Returns:
        List of probes with their details
    """
    if suite_name not in _state["suites"]:
        available = list(_state["suites"].keys())
        return {
            "success": False,
            "error": f"Unknown suite: {suite_name}. Available: {available}",
        }

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
                "pass_if_contains": p.pass_if_contains,
                "fail_if_contains": p.fail_if_contains,
            }
            for p in suite.probes
        ]

        # Group by category
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
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# Server Entry Point
# =============================================================================

def main():
    """Run the MCP server."""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting Persona Forge MCP Server")
    logger.info(f"Profiles directory: {_PROFILES_DIR}")
    logger.info(f"Project root: {_PROJECT_ROOT}")

    # Ensure directories exist
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()
