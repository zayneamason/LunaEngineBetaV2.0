"""
Pydantic models for MCP tools.
==============================

All input models for MCP tool functions.
Organized by domain: filesystem, memory, state, git.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum


# ==============================================================================
# Filesystem Models
# ==============================================================================

class ReadFileInput(BaseModel):
    """Input for luna_read tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    path: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Relative path to file within project"
    )


class WriteFileInput(BaseModel):
    """Input for luna_write tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    path: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Relative path to file within project"
    )
    content: str = Field(
        ...,
        description="Content to write to file"
    )
    create_dirs: bool = Field(
        default=True,
        description="Create parent directories if they don't exist"
    )


class ListDirInput(BaseModel):
    """Input for luna_list tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    path: str = Field(
        default="",
        max_length=500,
        description="Relative path to directory (empty for project root)"
    )
    recursive: bool = Field(
        default=False,
        description="Recursively list subdirectories"
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum depth for recursive listing"
    )


# ==============================================================================
# Memory Models
# ==============================================================================

class SmartFetchInput(BaseModel):
    """Input for luna_smart_fetch tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Query to search for relevant context"
    )
    budget_preset: str = Field(
        default="balanced",
        description="Token budget: minimal (1800), balanced (3800), rich (7200)"
    )


class MemorySearchInput(BaseModel):
    """Input for memory_matrix_search tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results"
    )


class NodeType(str, Enum):
    """Valid memory node types."""
    FACT = "FACT"
    DECISION = "DECISION"
    PROBLEM = "PROBLEM"
    ACTION = "ACTION"
    INSIGHT = "INSIGHT"
    QUESTION = "QUESTION"
    CONTEXT = "CONTEXT"
    ENTITY = "ENTITY"
    EVENT = "EVENT"
    PREFERENCE = "PREFERENCE"


class AddNodeInput(BaseModel):
    """Input for memory_matrix_add_node tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    node_type: str = Field(
        ...,
        description="Node type: FACT, DECISION, PROBLEM, ACTION, INSIGHT, etc."
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Content of the memory node"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Optional tags for categorization"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )


class RelationshipType(str, Enum):
    """Valid relationship types between nodes."""
    DEPENDS_ON = "depends_on"
    ENABLES = "enables"
    CONTRADICTS = "contradicts"
    CLARIFIES = "clarifies"
    RELATED_TO = "related_to"
    CAUSED_BY = "caused_by"
    CAUSES = "causes"
    PART_OF = "part_of"
    REFERENCES = "references"


class AddEdgeInput(BaseModel):
    """Input for memory_matrix_add_edge tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    from_node: str = Field(
        ...,
        description="Source node ID"
    )
    to_node: str = Field(
        ...,
        description="Target node ID"
    )
    relationship: str = Field(
        ...,
        description="Relationship type: depends_on, enables, contradicts, etc."
    )
    strength: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relationship strength (0.0-1.0)"
    )


class GetContextInput(BaseModel):
    """Input for memory_matrix_get_context tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    node_id: str = Field(
        ...,
        description="Node ID to get context for"
    )
    depth: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Depth of context graph traversal"
    )


class TraceDependenciesInput(BaseModel):
    """Input for memory_matrix_trace tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    node_id: str = Field(
        ...,
        description="Node ID to trace dependencies for"
    )
    max_depth: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum depth for dependency trace"
    )


class MemoryType(str, Enum):
    """Memory types for structured storage."""
    SESSION = "session"
    INSIGHT = "insight"
    CONTEXT = "context"
    ARTIFACT = "artifact"


class SaveMemoryInput(BaseModel):
    """Input for luna_save_memory tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    memory_type: MemoryType = Field(
        ...,
        description="Type of memory to save"
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Memory title"
    )
    content: str = Field(
        ...,
        description="Memory content"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Optional tags"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata"
    )


# ==============================================================================
# Session & Conversation Recording Models
# ==============================================================================

class StartSessionInput(BaseModel):
    """Input for luna_start_session tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    app_context: str = Field(
        default="mcp",
        max_length=100,
        description="Application context identifier (e.g., 'mcp', 'voice', 'api')"
    )


class RecordTurnInput(BaseModel):
    """Input for luna_record_turn tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    role: str = Field(
        ...,
        description="Message role: 'user' or 'assistant'"
    )
    content: str = Field(
        ...,
        min_length=1,
        description="The message content to record"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID (uses current session if not provided)"
    )


class EndSessionInput(BaseModel):
    """Input for luna_end_session tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    session_id: Optional[str] = Field(
        default=None,
        description="Session ID to end (uses current session if not provided)"
    )


# ==============================================================================
# State Models
# ==============================================================================

class DetectContextInput(BaseModel):
    """Input for luna_detect_context tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Message to process through Luna's pipeline"
    )
    auto_fetch: bool = Field(
        default=True,
        description="Automatically fetch relevant memories"
    )
    budget_preset: str = Field(
        default="balanced",
        description="Token budget preset"
    )


class SetAppContextInput(BaseModel):
    """Input for luna_set_app_context tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    app: str = Field(
        ...,
        description="Application name"
    )
    app_state: str = Field(
        ...,
        description="Application state"
    )


# ==============================================================================
# Git Models
# ==============================================================================

class GitSyncInput(BaseModel):
    """Input for luna_git_sync tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Commit message (optional)"
    )
    push: bool = Field(
        default=True,
        description="Push to remote after commit"
    )
