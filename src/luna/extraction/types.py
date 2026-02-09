"""
Extraction Types for Luna Engine
=================================

Dataclasses shared between Scribe (extraction) and Librarian (filing).
These define the contract for the extraction pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class ExtractionType(str, Enum):
    """Types of knowledge that can be extracted."""
    FACT = "FACT"               # Something known to be true
    DECISION = "DECISION"       # A choice that was made
    PROBLEM = "PROBLEM"         # An unresolved issue
    ASSUMPTION = "ASSUMPTION"   # Believed but unverified
    CONNECTION = "CONNECTION"   # Relationship between entities
    ACTION = "ACTION"           # Something done or to be done
    OUTCOME = "OUTCOME"         # Result of action or decision
    QUESTION = "QUESTION"       # A question asked or to be answered
    PREFERENCE = "PREFERENCE"   # User preference or opinion
    OBSERVATION = "OBSERVATION" # Something noticed or observed
    MEMORY = "MEMORY"           # A memory or recollection shared


@dataclass
class Chunk:
    """
    A semantic chunk of conversation for extraction.

    Chunks are the unit of extraction - small enough to process
    but large enough for context.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = ""
    tokens: int = 0
    source_id: str = ""
    turn_ids: list[int] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def __len__(self) -> int:
        return self.tokens


@dataclass
class ExtractedObject:
    """
    A piece of structured knowledge extracted from conversation.

    This is what Scribe produces and Librarian files.
    """
    type: ExtractionType
    content: str
    confidence: float = 1.0  # 0.0-1.0
    entities: list[str] = field(default_factory=list)
    source_id: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        # Ensure type is ExtractionType enum
        if isinstance(self.type, str):
            self.type = ExtractionType(self.type)

        # Clamp confidence to valid range
        self.confidence = max(0.0, min(1.0, self.confidence))

    def is_high_confidence(self) -> bool:
        """Check if this extraction is high confidence (>= 0.7)."""
        return self.confidence >= 0.7

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "content": self.content,
            "confidence": self.confidence,
            "entities": self.entities,
            "source_id": self.source_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractedObject":
        """Create from dictionary."""
        return cls(
            type=ExtractionType(data["type"]),
            content=data["content"],
            confidence=data.get("confidence", 1.0),
            entities=data.get("entities", []),
            source_id=data.get("source_id", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExtractedEdge:
    """
    A relationship between entities extracted from conversation.

    Edges connect nodes in the Memory Matrix graph.
    """
    from_ref: str       # Entity name or ID
    to_ref: str         # Entity name or ID
    edge_type: str      # "works_on", "decided", "caused", etc.
    confidence: float = 1.0
    role: Optional[str] = None  # "author", "subject", etc.
    source_id: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "from_ref": self.from_ref,
            "to_ref": self.to_ref,
            "edge_type": self.edge_type,
            "confidence": self.confidence,
            "role": self.role,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractedEdge":
        """Create from dictionary."""
        return cls(
            from_ref=data["from_ref"],
            to_ref=data["to_ref"],
            edge_type=data["edge_type"],
            confidence=data.get("confidence", 1.0),
            role=data.get("role"),
            source_id=data.get("source_id", ""),
        )


@dataclass
class ExtractionOutput:
    """
    Complete output from an extraction operation.

    Contains all objects and edges extracted from a chunk.
    """
    objects: list[ExtractedObject] = field(default_factory=list)
    edges: list[ExtractedEdge] = field(default_factory=list)
    source_id: str = ""
    extraction_time_ms: int = 0

    def __len__(self) -> int:
        return len(self.objects)

    def is_empty(self) -> bool:
        """Check if extraction produced nothing."""
        return len(self.objects) == 0 and len(self.edges) == 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "objects": [obj.to_dict() for obj in self.objects],
            "edges": [edge.to_dict() for edge in self.edges],
            "source_id": self.source_id,
            "extraction_time_ms": self.extraction_time_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractionOutput":
        """Create from dictionary."""
        return cls(
            objects=[ExtractedObject.from_dict(o) for o in data.get("objects", [])],
            edges=[ExtractedEdge.from_dict(e) for e in data.get("edges", [])],
            source_id=data.get("source_id", ""),
            extraction_time_ms=data.get("extraction_time_ms", 0),
        )


@dataclass
class FilingResult:
    """
    Result of filing an extraction into the Memory Matrix.

    Returned by Librarian after processing an ExtractionOutput.
    """
    nodes_created: list[str] = field(default_factory=list)
    nodes_merged: list[tuple[str, str]] = field(default_factory=list)  # (name, existing_id)
    edges_created: list[str] = field(default_factory=list)
    edges_skipped: list[str] = field(default_factory=list)
    filing_time_ms: int = 0

    def __len__(self) -> int:
        return len(self.nodes_created) + len(self.nodes_merged)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "nodes_created": self.nodes_created,
            "nodes_merged": self.nodes_merged,
            "edges_created": self.edges_created,
            "edges_skipped": self.edges_skipped,
            "filing_time_ms": self.filing_time_ms,
        }


# =============================================================================
# EXTRACTION CONFIGURATION
# =============================================================================

@dataclass
class ExtractionConfig:
    """
    Configuration for extraction backend.

    Allows runtime switching between Claude models and local inference.
    """
    backend: str = "haiku"  # "haiku", "sonnet", "local", "disabled"
    batch_size: int = 5     # Turns per extraction call
    min_content_length: int = 10  # Skip very short messages

    # Model-specific settings
    temperature: float = 0.3  # Lower = more deterministic extractions
    max_tokens: int = 1024    # Max response tokens


# Backend configurations
EXTRACTION_BACKENDS = {
    "haiku": {
        "model": "claude-haiku-4-5-20251001",
        "cost_per_1k_input": 0.0008,
        "cost_per_1k_output": 0.004,
        "quality": "good",
    },
    "sonnet": {
        "model": "claude-sonnet-4-5-20250929",
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.015,
        "quality": "excellent",
    },
    "local": {
        "model": "qwen-3b",
        "cost_per_1k_input": 0,
        "cost_per_1k_output": 0,
        "quality": "basic",
    },
}
