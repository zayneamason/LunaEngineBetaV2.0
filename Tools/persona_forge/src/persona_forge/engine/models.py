"""
Core data models for Persona Forge training pipeline.

All models use Pydantic v2 for validation and serialization.
"""

from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional
import uuid
import re


# =============================================================================
# Voice Markers and Anti-Patterns (used by Locksmith)
# =============================================================================

class VoiceMarkerPatterns:
    """Regex patterns for detecting Luna's authentic voice markers."""
    FIRST_PERSON = re.compile(r"\b(I|I'm|I've|I'd|my|me)\b", re.IGNORECASE)
    WARMTH_WORDS = re.compile(r"\b(honestly|actually|you know|yeah|cool|nice|hey)\b", re.IGNORECASE)
    UNCERTAINTY = re.compile(r"\b(maybe|probably|I think|not sure|might|could be)\b", re.IGNORECASE)
    RELATIONSHIP = re.compile(r"\b(we|we've|we're|our|together|Ahab)\b", re.IGNORECASE)


class VoiceMarkers(BaseModel):
    """Detected voice markers with counts."""
    first_person: int = 0
    warmth_words: int = 0
    uncertainty: int = 0
    relationship: int = 0

    @property
    def total(self) -> int:
        """Total marker count across all categories."""
        return self.first_person + self.warmth_words + self.uncertainty + self.relationship

    @property
    def has_authentic_voice(self) -> bool:
        """True if at least 2 different marker categories are present."""
        present = sum([
            self.first_person > 0,
            self.warmth_words > 0,
            self.uncertainty > 0,
            self.relationship > 0,
        ])
        return present >= 2


class AntiPatternPatterns:
    """Regex patterns for detecting unwanted AI speech patterns."""
    GENERIC_AI = re.compile(r"\b(I am an AI|as an AI|language model|Alibaba|Qwen|created by)\b", re.IGNORECASE)
    CORPORATE = re.compile(r"\b(I'd be happy to|certainly|absolutely|assist you|help you with)\b", re.IGNORECASE)
    HEDGING = re.compile(r"\b(I cannot|I'm not able|I don't have the ability|I'm unable)\b", re.IGNORECASE)


class AntiPatterns(BaseModel):
    """Detected anti-patterns with counts."""
    generic_ai: int = 0
    corporate: int = 0
    hedging: int = 0

    @property
    def total(self) -> int:
        """Total anti-pattern count across all categories."""
        return self.generic_ai + self.corporate + self.hedging

    @property
    def is_clean(self) -> bool:
        """True if no anti-patterns detected."""
        return self.total == 0


class InteractionType(str, Enum):
    """Categories of conversational interactions."""
    GREETING = "greeting"
    ACKNOWLEDGMENT = "acknowledgment"
    SHORT_EXCHANGE = "short_exchange"
    CONTEXT_RECALL = "context_recall"
    EMOTIONAL_PRESENCE = "emotional_presence"
    DELEGATION_TRIGGER = "delegation_trigger"
    REFLECTION = "reflection"
    TECHNICAL = "technical"
    HUMOR = "humor"
    PUSHBACK = "pushback"


class QualityTier(str, Enum):
    """Quality tiers for training examples."""
    GOLD = "gold"      # >= 0.75 lock-in
    SILVER = "silver"  # >= 0.50 lock-in
    BRONZE = "bronze"  # < 0.50 lock-in


class SourceType(str, Enum):
    """Source types for training data."""
    JOURNAL = "journal"
    SESSION = "session"
    MATRIX = "matrix"
    INSIGHT = "insight"
    SYNTHETIC = "synthetic"
    MANUAL = "manual"


class ResponseLength(str, Enum):
    """Response length categories."""
    SHORT = "short"    # < 50 words
    MEDIUM = "medium"  # 50-150 words
    LONG = "long"      # > 150 words


class ExampleMetadata(BaseModel):
    """
    Metadata container for training examples.

    Provides a unified interface for source tracking, interaction typing,
    and timing information.
    """
    source_type: SourceType = SourceType.MANUAL
    source_file: Optional[str] = None
    interaction_type: InteractionType = InteractionType.SHORT_EXCHANGE
    response_length: ResponseLength = ResponseLength.MEDIUM
    session_id: Optional[str] = None
    timestamp: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    word_count: int = 0


class CoverageGap(BaseModel):
    """
    Represents a gap in dataset coverage.

    Used by the Assayer to identify areas needing synthesis.
    """
    category: str  # e.g., "interaction:greeting", "length:short"
    current_count: int = 0
    target_count: int = 0
    deficit: int = 0  # target - current (negative = surplus)
    priority: float = 1.0  # Higher = more important to fill


class LockIn(BaseModel):
    """
    Lock-in coefficient for training example weighting.

    Mirrors Memory Matrix formula:
    lock_in = base + (retrieval_bonus × retrievals) + (reinforcement_bonus × reinforcements)
    Clamped to [0.15, 0.95]
    """
    base_quality: float = Field(ge=0.0, le=1.0, default=0.5)
    retrieval_bonus: float = Field(default=0.0, ge=0.0, le=0.20)
    reinforcement_bonus: float = Field(default=0.0, ge=0.0, le=0.25)
    
    @property
    def coefficient(self) -> float:
        """Compute clamped lock-in coefficient."""
        raw = self.base_quality + self.retrieval_bonus + self.reinforcement_bonus
        return max(0.15, min(0.95, raw))
    
    @property
    def tier(self) -> QualityTier:
        """Get quality tier based on coefficient."""
        if self.coefficient >= 0.75:
            return QualityTier.GOLD
        elif self.coefficient >= 0.50:
            return QualityTier.SILVER
        return QualityTier.BRONZE
    
    def add_retrieval(self, bonus: float = 0.02) -> None:
        """Add retrieval bonus (capped at 0.20)."""
        self.retrieval_bonus = min(0.20, self.retrieval_bonus + bonus)
    
    def add_reinforcement(self, bonus: float = 0.05) -> None:
        """Add reinforcement bonus (capped at 0.25)."""
        self.reinforcement_bonus = min(0.25, self.reinforcement_bonus + bonus)


class TrainingExample(BaseModel):
    """
    Single training example with full metadata.
    
    This is the atomic unit of the training dataset.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    # Core training data (required for export)
    system_prompt: str
    user_message: str
    assistant_response: str
    
    # Metadata
    source_type: SourceType = SourceType.MANUAL
    source_file: Optional[str] = None
    interaction_type: InteractionType = InteractionType.SHORT_EXCHANGE
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Computed metrics
    response_word_count: int = 0
    user_word_count: int = 0
    
    # Quality assessment
    lock_in: LockIn = Field(default_factory=LockIn)
    voice_markers: VoiceMarkers = Field(default_factory=VoiceMarkers)
    anti_patterns: AntiPatterns = Field(default_factory=AntiPatterns)
    
    # Personality link (for multi-personality datasets)
    personality_id: Optional[str] = None

    # Personality scores (8-dimensional)
    personality_scores: Optional[dict[str, float]] = None
    """
    Personality scores across 8 dimensions (0-1).

    Keys:
    - warmth: Emotional engagement and care
    - technical: Domain expertise and jargon usage
    - humor: Levity and entertainment value
    - directness: Conciseness and clarity
    - creativity: Imagination and originality
    - reflection: Philosophical depth and introspection
    - relationship: Personal connection and history awareness
    - assertiveness: Boundary-setting and confidence
    """
    
    def compute_metrics(self) -> None:
        """Compute word counts and other metrics."""
        self.response_word_count = len(self.assistant_response.split())
        self.user_word_count = len(self.user_message.split())
    
    @property
    def response_length_category(self) -> ResponseLength:
        """Categorize response by length."""
        if self.response_word_count < 50:
            return ResponseLength.SHORT
        elif self.response_word_count < 150:
            return ResponseLength.MEDIUM
        return ResponseLength.LONG
    
    @property
    def metadata(self) -> ExampleMetadata:
        """
        Backward-compatible metadata accessor.

        Returns an ExampleMetadata object built from direct fields.
        """
        return ExampleMetadata(
            source_type=self.source_type,
            source_file=self.source_file,
            interaction_type=self.interaction_type,
            response_length=self.response_length_category,
            timestamp=self.created_at.isoformat() if self.created_at else None,
            word_count=self.response_word_count,
        )

    def to_training_dict(self) -> dict:
        """Export in OpenAI-compatible format."""
        return {
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.user_message},
                {"role": "assistant", "content": self.assistant_response},
            ]
        }


class DatasetAssay(BaseModel):
    """
    Complete analysis of a training dataset.
    
    Generated by the Assayer module.
    """
    timestamp: datetime = Field(default_factory=datetime.now)
    total_examples: int
    
    # Distributions (as percentages 0.0-1.0)
    interaction_type_dist: dict[str, float]
    response_length_dist: dict[str, float]
    source_type_dist: dict[str, float]
    quality_tier_dist: dict[str, float]
    
    # Voice analysis
    voice_marker_rates: dict[str, float]
    anti_pattern_rates: dict[str, float]
    
    # Lock-in statistics
    avg_lock_in: float
    lock_in_std: float
    lock_in_min: float
    lock_in_max: float
    
    # Coverage analysis
    gaps: dict[str, int]  # negative = deficit
    synthesis_targets: dict[str, int]
    
    # Health score (0-100)
    health_score: float
    health_breakdown: dict[str, float]

    # Personality analysis (optional, computed when --with-personality)
    personality_profile: Optional[dict[str, float]] = None
    """Average personality across dataset (8 dimensions, 0-1 scores)."""

    personality_variance: Optional[dict[str, float]] = None
    """Standard deviation of personality scores per dimension."""

    personality_alignment: Optional[float] = None
    """Alignment with target personality (0-1). 1.0 = perfect alignment."""


class TargetProfile(BaseModel):
    """
    Target distribution profile for dataset shaping.
    
    Defines what the ideal dataset looks like.
    """
    name: str
    description: str = ""
    
    # Target distributions (should sum to ~1.0)
    interaction_types: dict[str, float]
    response_lengths: dict[str, float]
    
    # Voice requirements (minimum rates)
    voice_markers: dict[str, float]
    
    # Anti-pattern limits (maximum rates)
    anti_patterns: dict[str, float]
    
    # Dataset size targets
    min_examples: int = 300
    target_examples: int = 500
    max_examples: int = 1000


# Default profile optimized for Director LLM
DIRECTOR_PROFILE = TargetProfile(
    name="director",
    description="Profile for Luna's Director LLM - optimized for short exchanges and voice consistency",
    interaction_types={
        "greeting": 0.15,
        "acknowledgment": 0.10,
        "short_exchange": 0.25,
        "context_recall": 0.15,
        "emotional_presence": 0.15,
        "delegation_trigger": 0.10,
        "reflection": 0.10,
    },
    response_lengths={
        "short": 0.40,
        "medium": 0.35,
        "long": 0.25,
    },
    voice_markers={
        "first_person": 0.90,
        "warmth_words": 0.60,
        "uncertainty": 0.30,
        "relationship": 0.40,
    },
    anti_patterns={
        "generic_ai": 0.00,
        "corporate": 0.05,
        "hedging": 0.10,
    },
)
