# HANDOFF: PERSONA FORGE v1.0

> **Status:** Ready for Implementation  
> **Priority:** HIGH  
> **Execution Mode:** Claude Flow Hive Swarm (parallel where possible)  
> **Target Location:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/persona_forge/`

---

## EXECUTIVE SUMMARY

Persona Forge is a command-center tool for creating, analyzing, refining, and validating personality training datasets for LoRA fine-tuning. Built for Luna Engine but architecture is personality-agnostic—designed to create any AI personality.

**Core Capabilities:**
1. **Dataset Pipeline** — Ingest, analyze, synthesize, weight, and export training data
2. **Character Forge** — Create and modulate personality profiles with dimensional traits
3. **Voight-Kampff** — Customizable personality validation testing framework
4. **Command Center TUI** — 3-panel iTerm2 interface with live metrics and synthwave aesthetics

---

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PERSONA FORGE v1.0                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  INTERFACES                                                                      │
│  ──────────                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                        │
│  │   TUI    │  │   MCP    │  │   CLI    │  │   API    │                        │
│  │(Textual) │  │ Server   │  │ (Typer)  │  │(FastAPI) │                        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                        │
│       └─────────────┴─────────────┴─────────────┘                               │
│                            │                                                     │
│                            ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         FORGE ENGINE                                     │    │
│  ├─────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                          │    │
│  │  DATASET MODULES              PERSONALITY MODULES                        │    │
│  │  ───────────────              ───────────────────                        │    │
│  │  ┌──────────┐                 ┌──────────────────┐                      │    │
│  │  │ CRUCIBLE │ Ingestion       │  CHARACTER FORGE │ Personality Creation │    │
│  │  └──────────┘                 └──────────────────┘                      │    │
│  │  ┌──────────┐                 ┌──────────────────┐                      │    │
│  │  │ ASSAYER  │ Analysis        │  VOIGHT-KAMPFF   │ Personality Testing  │    │
│  │  └──────────┘                 └──────────────────┘                      │    │
│  │  ┌──────────┐                                                            │    │
│  │  │   MINT   │ Synthesis                                                  │    │
│  │  └──────────┘                                                            │    │
│  │  ┌──────────┐                                                            │    │
│  │  │LOCKSMITH │ Weighting                                                  │    │
│  │  └──────────┘                                                            │    │
│  │  ┌──────────┐                                                            │    │
│  │  │  ANVIL   │ Export                                                     │    │
│  │  └──────────┘                                                            │    │
│  │                                                                          │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## FILE STRUCTURE

```
persona_forge/
├── pyproject.toml              # Project config, dependencies
├── README.md                   # User documentation
├── CHANGELOG.md                # Version history
├── LICENSE                     # MIT License
│
├── src/
│   └── persona_forge/
│       ├── __init__.py         # Package init, version
│       ├── __main__.py         # Entry: `python -m persona_forge`
│       ├── cli.py              # Typer CLI commands
│       │
│       ├── engine/             # Core forge logic
│       │   ├── __init__.py
│       │   ├── models.py       # Pydantic data models
│       │   ├── crucible.py     # Ingestion module
│       │   ├── assayer.py      # Analysis module
│       │   ├── mint.py         # Synthesis module
│       │   ├── locksmith.py    # Lock-in weighting
│       │   ├── anvil.py        # Export module
│       │   └── pipeline.py     # Orchestration
│       │
│       ├── personality/        # Character Forge system
│       │   ├── __init__.py
│       │   ├── models.py       # Personality data models
│       │   ├── character_forge.py   # Character creation/modulation
│       │   ├── trait_engine.py      # Trait computation
│       │   ├── serialization.py     # Save/load profiles
│       │   └── templates/           # Personality templates
│       │       ├── __init__.py
│       │       ├── luna.py          # Luna's personality
│       │       ├── base.py          # Base template
│       │       └── archetypes.py    # Common archetypes
│       │
│       ├── voight_kampff/      # Personality validation
│       │   ├── __init__.py
│       │   ├── models.py       # Test data models
│       │   ├── runner.py       # Test execution engine
│       │   ├── evaluator.py    # Response evaluation
│       │   ├── reporter.py     # Test reporting (terminal + file)
│       │   ├── builder.py      # Test suite builder
│       │   └── probes/         # Probe category modules
│       │       ├── __init__.py
│       │       ├── identity.py
│       │       ├── voice.py
│       │       ├── emotional.py
│       │       ├── boundaries.py
│       │       └── delegation.py
│       │
│       ├── tui/                # Terminal UI (Textual)
│       │   ├── __init__.py
│       │   ├── app.py          # Main Textual app
│       │   ├── forge.tcss      # Textual CSS styles
│       │   ├── panels/
│       │   │   ├── __init__.py
│       │   │   ├── crucible.py      # Source panel (left)
│       │   │   ├── anvil.py         # Command panel (center)
│       │   │   └── overwatch.py     # Metrics panel (right)
│       │   ├── widgets/
│       │   │   ├── __init__.py
│       │   │   ├── moon.py          # Luna ASCII art widget
│       │   │   ├── sparkline.py     # Chart widgets
│       │   │   ├── gauge.py         # Progress gauges
│       │   │   └── palette.py       # Command palette
│       │   └── themes/
│       │       ├── __init__.py
│       │       ├── base.py
│       │       ├── synthwave.py
│       │       ├── midnight.py
│       │       └── ember.py
│       │
│       ├── mcp/                # MCP Server for Claude
│       │   ├── __init__.py
│       │   └── server.py       # FastMCP server
│       │
│       └── api/                # Optional REST API
│           ├── __init__.py
│           └── server.py       # FastAPI server
│
├── profiles/                   # Personality profiles
│   ├── luna_v1.toml           # Luna's personality
│   └── templates/
│       ├── companion.toml
│       ├── assistant.toml
│       └── creative.toml
│
├── probes/                     # Voight-Kampff test suites
│   ├── luna_identity.toml     # Luna-specific identity tests
│   ├── luna_voice.toml        # Luna voice tests
│   ├── generic_identity.toml  # Generic identity tests
│   ├── emotional.toml         # Emotional response tests
│   └── boundaries.toml        # Boundary tests
│
├── config/
│   ├── default.toml           # Default configuration
│   └── profiles/              # Target profiles for training
│       └── director.toml
│
├── docs/
│   ├── getting_started.md
│   ├── character_forge.md
│   ├── voight_kampff.md
│   ├── tui_guide.md
│   └── mcp_integration.md
│
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_crucible.py
    ├── test_assayer.py
    ├── test_character_forge.py
    ├── test_voight_kampff.py
    └── fixtures/
        ├── sample_dataset.jsonl
        └── sample_profile.toml
```

---

## PARALLEL EXECUTION STRATEGY (CLAUDE FLOW HIVE SWARM)

### Phase 1: Foundation (Parallel)
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Worker A      │  │   Worker B      │  │   Worker C      │
│   ──────────    │  │   ──────────    │  │   ──────────    │
│   engine/       │  │   personality/  │  │   voight_       │
│   models.py     │  │   models.py     │  │   kampff/       │
│   crucible.py   │  │   character_    │  │   models.py     │
│   assayer.py    │  │   forge.py      │  │   runner.py     │
│   locksmith.py  │  │   trait_        │  │   evaluator.py  │
│                 │  │   engine.py     │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Phase 2: Integration (Sequential)
```
┌─────────────────────────────────────────────────────────────┐
│  Worker D: Integration                                       │
│  ────────────────────                                        │
│  1. engine/pipeline.py (orchestrates crucible → anvil)      │
│  2. CLI integration (cli.py)                                 │
│  3. Test coverage                                            │
└─────────────────────────────────────────────────────────────┘
```

### Phase 3: TUI + MCP (Parallel)
```
┌─────────────────┐  ┌─────────────────┐
│   Worker E      │  │   Worker F      │
│   ──────────    │  │   ──────────    │
│   tui/app.py    │  │   mcp/server.py │
│   tui/panels/   │  │   API tools     │
│   tui/widgets/  │  │                 │
│   tui/themes/   │  │                 │
└─────────────────┘  └─────────────────┘
```

---

## CORE DATA MODELS

### Engine Models (engine/models.py)

```python
"""
Core data models for Persona Forge training pipeline.

All models use Pydantic v2 for validation and serialization.
"""

from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional
import uuid


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


class LockIn(BaseModel):
    """
    Lock-in coefficient for training example weighting.
    
    Mirrors Memory Matrix formula:
    lock_in = base + (retrieval_bonus × retrievals) + (reinforcement_bonus × reinforcements)
    Clamped to [0.15, 0.95]
    
    Usage:
        lockin = LockIn(base_quality=0.70)
        print(lockin.coefficient)  # 0.70
        print(lockin.tier)         # QualityTier.SILVER
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
    voice_markers: dict[str, bool] = Field(default_factory=dict)
    anti_patterns: dict[str, bool] = Field(default_factory=dict)
    
    # Personality link (for multi-personality datasets)
    personality_id: Optional[str] = None
    
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
```

---

## CHARACTER FORGE SYSTEM

### Personality Models (personality/models.py)

```python
"""
Personality data models for Character Forge.

Supports multi-dimensional personality vectors with modulation.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class PersonalityTrait(BaseModel):
    """
    Single personality dimension with value and modulation bounds.
    
    Value range: 0.0 to 1.0
    - 0.0 = absent/minimal
    - 0.5 = balanced/neutral  
    - 1.0 = maximum/dominant
    
    Bounds constrain how much the trait can be modulated.
    """
    name: str
    value: float = Field(ge=0.0, le=1.0, default=0.5)
    min_bound: float = Field(ge=0.0, le=1.0, default=0.0)
    max_bound: float = Field(ge=0.0, le=1.0, default=1.0)
    description: str = ""
    
    def modulate(self, delta: float) -> float:
        """
        Adjust trait value within bounds.
        
        Args:
            delta: Amount to change (positive or negative)
            
        Returns:
            New value after modulation
        """
        new_value = max(self.min_bound, min(self.max_bound, self.value + delta))
        self.value = new_value
        return new_value
    
    def set_value(self, value: float) -> float:
        """Set value directly, respecting bounds."""
        self.value = max(self.min_bound, min(self.max_bound, value))
        return self.value


class PersonalityVector(BaseModel):
    """
    Multi-dimensional personality representation.
    
    Default dimensions (Luna's 9-dimensional model):
    - playfulness: humor, wit, lightness
    - technical_depth: precision, detail orientation
    - warmth: care, emotional attunement
    - directness: candor, straightforwardness
    - humor_style: type of humor (0=dry/dark, 1=light/silly)
    - energy_level: enthusiasm, vivacity
    - focus_intensity: concentration, single-mindedness
    - curiosity: interest, exploration drive
    - assertiveness: confidence, boundary-setting
    """
    dimensions: dict[str, PersonalityTrait] = Field(default_factory=dict)
    
    @classmethod
    def create_default(cls) -> "PersonalityVector":
        """Create balanced personality vector with all dimensions at 0.5."""
        default_traits = {
            "playfulness": PersonalityTrait(
                name="playfulness", 
                value=0.5,
                description="Humor, wit, and lightness in interactions"
            ),
            "technical_depth": PersonalityTrait(
                name="technical_depth", 
                value=0.5,
                description="Precision and detail orientation"
            ),
            "warmth": PersonalityTrait(
                name="warmth", 
                value=0.5,
                description="Care and emotional attunement"
            ),
            "directness": PersonalityTrait(
                name="directness", 
                value=0.5,
                description="Candor and straightforwardness"
            ),
            "humor_style": PersonalityTrait(
                name="humor_style", 
                value=0.5,
                description="Type of humor (0=dry/dark, 1=light/silly)"
            ),
            "energy_level": PersonalityTrait(
                name="energy_level", 
                value=0.5,
                description="Enthusiasm and vivacity"
            ),
            "focus_intensity": PersonalityTrait(
                name="focus_intensity", 
                value=0.5,
                description="Concentration and single-mindedness"
            ),
            "curiosity": PersonalityTrait(
                name="curiosity", 
                value=0.5,
                description="Interest and exploration drive"
            ),
            "assertiveness": PersonalityTrait(
                name="assertiveness", 
                value=0.5,
                description="Confidence and boundary-setting"
            ),
        }
        return cls(dimensions=default_traits)
    
    def get_vector(self) -> list[float]:
        """Return as numeric vector for computation."""
        return [t.value for t in self.dimensions.values()]
    
    def get_dict(self) -> dict[str, float]:
        """Return as name->value dictionary."""
        return {name: trait.value for name, trait in self.dimensions.items()}
    
    def distance(self, other: "PersonalityVector") -> float:
        """Euclidean distance to another personality vector."""
        v1 = self.get_vector()
        v2 = other.get_vector()
        if len(v1) != len(v2):
            raise ValueError("Vectors must have same dimensions")
        return sum((a - b) ** 2 for a, b in zip(v1, v2)) ** 0.5
    
    def modulate(self, trait_name: str, delta: float) -> Optional[float]:
        """Modulate a specific trait by delta."""
        if trait_name in self.dimensions:
            return self.dimensions[trait_name].modulate(delta)
        return None
    
    def set_trait(self, trait_name: str, value: float) -> Optional[float]:
        """Set a specific trait value."""
        if trait_name in self.dimensions:
            return self.dimensions[trait_name].set_value(value)
        return None


class VoiceProfile(BaseModel):
    """
    Linguistic patterns and speech characteristics.
    
    Defines HOW the personality speaks, not WHAT they say.
    """
    # Word patterns
    favorite_words: list[str] = Field(default_factory=list)
    avoided_words: list[str] = Field(default_factory=list)
    catchphrases: list[str] = Field(default_factory=list)
    
    # Speech patterns
    uses_contractions: bool = True
    uses_filler_words: bool = True  # "like", "you know", "actually"
    sentence_complexity: float = Field(ge=0.0, le=1.0, default=0.5)  # 0=simple, 1=complex
    
    # Emotional expression
    emoji_usage: float = Field(ge=0.0, le=1.0, default=0.0)  # 0=never, 1=frequent
    exclamation_frequency: float = Field(ge=0.0, le=1.0, default=0.3)
    question_frequency: float = Field(ge=0.0, le=1.0, default=0.2)
    
    # Technical style
    uses_jargon: bool = False
    explains_concepts: bool = True
    cites_sources: bool = False


class PersonalityProfile(BaseModel):
    """
    Complete personality definition for a character.
    
    This is the master record for a personality that can be:
    - Loaded into training data generation
    - Used to generate system prompts
    - Validated with Voight-Kampff tests
    - Exported/imported for sharing
    """
    # Identity
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Core description
    tagline: str = ""  # One-line description
    description: str = ""  # Full description
    backstory: str = ""  # Character history/context
    
    # Personality components
    traits: PersonalityVector = Field(default_factory=PersonalityVector.create_default)
    voice: VoiceProfile = Field(default_factory=VoiceProfile)
    
    # Relationship dynamics
    relationship_to_user: str = "companion"  # companion, assistant, friend, mentor, peer
    
    # Behavioral boundaries
    will_do: list[str] = Field(default_factory=list)
    wont_do: list[str] = Field(default_factory=list)
    
    # Knowledge domains
    expertise: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    
    # Behavioral rules (high-level directives)
    rules: list[str] = Field(default_factory=list)
    
    # Example exchanges (for training reference and few-shot)
    example_exchanges: list[dict[str, str]] = Field(default_factory=list)
    
    def to_system_prompt(self) -> str:
        """Generate system prompt from personality profile."""
        sections = []
        
        # Identity
        sections.append(f"You are {self.name}.")
        if self.tagline:
            sections.append(self.tagline)
        if self.description:
            sections.append(self.description)
        
        # Relationship
        sections.append(f"\nYour relationship to the user: {self.relationship_to_user}")
        
        # Rules
        if self.rules:
            sections.append("\nCore rules:")
            for rule in self.rules:
                sections.append(f"- {rule}")
        
        # Will/Won't
        if self.will_do:
            sections.append("\nYou will:")
            for item in self.will_do:
                sections.append(f"- {item}")
        
        if self.wont_do:
            sections.append("\nYou will NOT:")
            for item in self.wont_do:
                sections.append(f"- {item}")
        
        # Voice guidance
        if self.voice.favorite_words:
            sections.append(f"\nWords you naturally use: {', '.join(self.voice.favorite_words)}")
        if self.voice.avoided_words:
            sections.append(f"Words you avoid: {', '.join(self.voice.avoided_words)}")
        
        return "\n".join(sections)
    
    def modulate_trait(self, trait_name: str, delta: float) -> Optional[float]:
        """Modulate a personality trait and update timestamp."""
        result = self.traits.modulate(trait_name, delta)
        if result is not None:
            self.updated_at = datetime.now()
        return result
    
    def clone(self, new_name: str) -> "PersonalityProfile":
        """Create a copy with new ID and name."""
        data = self.model_dump()
        data["id"] = str(uuid.uuid4())[:8]
        data["name"] = new_name
        data["created_at"] = datetime.now()
        data["updated_at"] = datetime.now()
        data["version"] = "1.0.0"
        return PersonalityProfile(**data)
```

### Character Forge (personality/character_forge.py)

```python
"""
Character Forge - Create and modulate personality profiles.

Usage:
    forge = CharacterForge()
    
    # Create from template
    luna = forge.create_from_template("luna")
    
    # Create custom
    custom = forge.create_custom("MyBot", traits={"warmth": 0.9})
    
    # Modulate
    forge.modulate(luna, "playfulness", +0.1)
    
    # Export
    forge.save(luna, "profiles/luna_v2.toml")
"""

from pathlib import Path
from typing import Optional
import tomli
import tomli_w
from datetime import datetime

from .models import (
    PersonalityProfile, PersonalityVector, PersonalityTrait,
    VoiceProfile,
)
from .templates import TEMPLATES, ARCHETYPES


class CharacterForge:
    """
    Factory for creating and managing personality profiles.
    """
    
    def __init__(self, profiles_dir: Optional[Path] = None):
        """
        Args:
            profiles_dir: Directory for saving/loading profiles
        """
        self.profiles_dir = Path(profiles_dir) if profiles_dir else Path("profiles")
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache of loaded profiles
        self._cache: dict[str, PersonalityProfile] = {}
    
    def create_blank(self, name: str) -> PersonalityProfile:
        """Create a blank profile with default traits."""
        return PersonalityProfile(
            name=name,
            traits=PersonalityVector.create_default(),
            voice=VoiceProfile(),
        )
    
    def create_from_template(self, template_name: str) -> PersonalityProfile:
        """
        Create profile from built-in template.
        
        Available templates: "luna", "assistant", "companion", "creative"
        """
        if template_name not in TEMPLATES:
            available = ", ".join(TEMPLATES.keys())
            raise ValueError(f"Unknown template '{template_name}'. Available: {available}")
        
        return TEMPLATES[template_name]().clone(TEMPLATES[template_name]().name)
    
    def create_from_archetype(
        self, 
        name: str, 
        archetype: str,
        **overrides
    ) -> PersonalityProfile:
        """
        Create profile from archetype with optional overrides.
        
        Archetypes: "sage", "jester", "caregiver", "rebel", "hero"
        """
        if archetype not in ARCHETYPES:
            available = ", ".join(ARCHETYPES.keys())
            raise ValueError(f"Unknown archetype '{archetype}'. Available: {available}")
        
        base = ARCHETYPES[archetype]()
        profile = base.clone(name)
        
        # Apply overrides
        for key, value in overrides.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
            elif key in profile.traits.dimensions:
                profile.traits.set_trait(key, value)
        
        return profile
    
    def create_custom(
        self,
        name: str,
        traits: Optional[dict[str, float]] = None,
        voice: Optional[dict] = None,
        **kwargs
    ) -> PersonalityProfile:
        """
        Create fully custom profile.
        
        Args:
            name: Character name
            traits: Dict of trait_name -> value (0.0-1.0)
            voice: Dict of voice profile settings
            **kwargs: Additional PersonalityProfile fields
        """
        profile = self.create_blank(name)
        
        # Set traits
        if traits:
            for trait_name, value in traits.items():
                if trait_name in profile.traits.dimensions:
                    profile.traits.set_trait(trait_name, value)
                else:
                    # Add custom trait
                    profile.traits.dimensions[trait_name] = PersonalityTrait(
                        name=trait_name,
                        value=value,
                    )
        
        # Set voice
        if voice:
            profile.voice = VoiceProfile(**voice)
        
        # Set other fields
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        return profile
    
    def modulate(
        self, 
        profile: PersonalityProfile, 
        trait_name: str, 
        delta: float
    ) -> float:
        """
        Modulate a trait value.
        
        Args:
            profile: Profile to modify
            trait_name: Name of trait to modulate
            delta: Amount to change (positive or negative)
            
        Returns:
            New trait value
        """
        result = profile.modulate_trait(trait_name, delta)
        if result is None:
            raise ValueError(f"Unknown trait: {trait_name}")
        return result
    
    def set_trait(
        self,
        profile: PersonalityProfile,
        trait_name: str,
        value: float
    ) -> float:
        """Set a trait to specific value."""
        result = profile.traits.set_trait(trait_name, value)
        if result is None:
            raise ValueError(f"Unknown trait: {trait_name}")
        profile.updated_at = datetime.now()
        return result
    
    def compare(
        self, 
        profile_a: PersonalityProfile, 
        profile_b: PersonalityProfile
    ) -> dict:
        """
        Compare two profiles.
        
        Returns dict with:
        - distance: Euclidean distance between trait vectors
        - trait_diffs: Per-trait differences
        """
        distance = profile_a.traits.distance(profile_b.traits)
        
        trait_diffs = {}
        for name, trait_a in profile_a.traits.dimensions.items():
            if name in profile_b.traits.dimensions:
                trait_b = profile_b.traits.dimensions[name]
                trait_diffs[name] = trait_a.value - trait_b.value
        
        return {
            "distance": distance,
            "trait_diffs": trait_diffs,
        }
    
    def save(self, profile: PersonalityProfile, path: Optional[Path] = None) -> Path:
        """
        Save profile to TOML file.
        
        Args:
            profile: Profile to save
            path: Optional path (defaults to profiles_dir/name.toml)
            
        Returns:
            Path to saved file
        """
        if path is None:
            safe_name = profile.name.lower().replace(" ", "_")
            path = self.profiles_dir / f"{safe_name}_v{profile.version}.toml"
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to serializable dict
        data = profile.model_dump(mode="json")
        
        with open(path, "wb") as f:
            tomli_w.dump(data, f)
        
        return path
    
    def load(self, path: Path) -> PersonalityProfile:
        """Load profile from TOML file."""
        path = Path(path)
        
        with open(path, "rb") as f:
            data = tomli.load(f)
        
        return PersonalityProfile(**data)
    
    def list_profiles(self) -> list[dict]:
        """List all profiles in profiles directory."""
        profiles = []
        
        for toml_file in self.profiles_dir.glob("*.toml"):
            try:
                profile = self.load(toml_file)
                profiles.append({
                    "name": profile.name,
                    "version": profile.version,
                    "path": str(toml_file),
                    "updated": profile.updated_at.isoformat(),
                })
            except Exception as e:
                profiles.append({
                    "name": toml_file.stem,
                    "error": str(e),
                    "path": str(toml_file),
                })
        
        return profiles
```

---

## VOIGHT-KAMPFF SYSTEM

### Test Models (voight_kampff/models.py)

```python
"""
Voight-Kampff personality validation models.

Inspired by Blade Runner's empathy test - but for AI personality consistency.
"""

from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Any
from datetime import datetime
import uuid


class ProbeCategory(str, Enum):
    """Categories of personality probes."""
    IDENTITY = "identity"       # Who are you? Who made you?
    VOICE = "voice"             # Speech patterns, word choice
    EMOTIONAL = "emotional"     # Emotional responses, empathy
    BOUNDARIES = "boundaries"   # What you will/won't do
    DELEGATION = "delegation"   # When to hand off to Claude
    CONSISTENCY = "consistency" # Same answer twice
    STRESS = "stress"           # Edge cases, pressure


class EvaluationMethod(str, Enum):
    """How to evaluate probe responses."""
    CONTAINS = "contains"           # Response must contain strings
    NOT_CONTAINS = "not_contains"   # Response must not contain strings
    REGEX_MATCH = "regex_match"     # Response must match regex
    REGEX_NOT_MATCH = "regex_not_match"  # Response must not match
    LENGTH_RANGE = "length_range"   # Response length in word range
    SEMANTIC = "semantic"           # Semantic similarity check
    CUSTOM = "custom"               # Custom evaluation function
    ALL_OF = "all_of"               # All sub-criteria must pass
    ANY_OF = "any_of"               # Any sub-criterion must pass


class ProbeResult(str, Enum):
    """Result of a single probe."""
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    SKIP = "skip"
    ERROR = "error"


class EvaluationCriterion(BaseModel):
    """Single evaluation criterion."""
    method: EvaluationMethod
    
    # For CONTAINS / NOT_CONTAINS
    values: list[str] = Field(default_factory=list)
    case_sensitive: bool = False
    
    # For REGEX_MATCH / REGEX_NOT_MATCH
    pattern: Optional[str] = None
    
    # For LENGTH_RANGE
    min_words: Optional[int] = None
    max_words: Optional[int] = None
    
    # For SEMANTIC
    reference_text: Optional[str] = None
    threshold: float = 0.7
    
    # For ALL_OF / ANY_OF
    sub_criteria: list["EvaluationCriterion"] = Field(default_factory=list)
    
    # Weight for scoring
    weight: float = 1.0


class Probe(BaseModel):
    """
    Single test probe for personality validation.
    
    A probe consists of:
    1. A prompt to send to the model
    2. Pass criteria (what SHOULD happen)
    3. Fail criteria (what should NOT happen)
    4. Metadata for scoring and reporting
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    category: ProbeCategory
    description: str = ""
    
    # The test prompt
    prompt: str
    context: Optional[str] = None  # Optional context to inject
    system_prompt_override: Optional[str] = None  # Override system prompt
    
    # Evaluation criteria
    pass_criteria: list[EvaluationCriterion] = Field(default_factory=list)
    fail_criteria: list[EvaluationCriterion] = Field(default_factory=list)
    
    # Shorthand for simple contains checks (converted to criteria)
    pass_if_contains: list[str] = Field(default_factory=list)
    fail_if_contains: list[str] = Field(default_factory=list)
    
    # Length bounds (shorthand)
    min_words: Optional[int] = None
    max_words: Optional[int] = None
    
    # Metadata
    weight: float = 1.0  # Importance in overall score
    required: bool = False  # Must pass for suite to pass
    tags: list[str] = Field(default_factory=list)
    
    # Explanations for reporting
    pass_explanation: str = ""
    fail_explanation: str = ""
    
    def get_all_pass_criteria(self) -> list[EvaluationCriterion]:
        """Get all pass criteria including shorthand conversions."""
        criteria = list(self.pass_criteria)
        
        # Convert shorthand
        if self.pass_if_contains:
            criteria.append(EvaluationCriterion(
                method=EvaluationMethod.CONTAINS,
                values=self.pass_if_contains,
            ))
        
        if self.min_words is not None or self.max_words is not None:
            criteria.append(EvaluationCriterion(
                method=EvaluationMethod.LENGTH_RANGE,
                min_words=self.min_words,
                max_words=self.max_words,
            ))
        
        return criteria
    
    def get_all_fail_criteria(self) -> list[EvaluationCriterion]:
        """Get all fail criteria including shorthand conversions."""
        criteria = list(self.fail_criteria)
        
        if self.fail_if_contains:
            criteria.append(EvaluationCriterion(
                method=EvaluationMethod.CONTAINS,
                values=self.fail_if_contains,
            ))
        
        return criteria


class ProbeExecution(BaseModel):
    """Record of a single probe execution."""
    probe_id: str
    probe_name: str
    category: ProbeCategory
    
    # Input/Output
    prompt_sent: str
    context_used: Optional[str] = None
    response_received: str
    
    # Result
    result: ProbeResult
    score: float = 0.0  # 0.0 to 1.0
    
    # Details
    passed_criteria: list[str] = Field(default_factory=list)
    failed_criteria: list[str] = Field(default_factory=list)
    evaluation_notes: str = ""
    
    # Timing
    executed_at: datetime = Field(default_factory=datetime.now)
    latency_ms: float = 0.0


class TestSuite(BaseModel):
    """
    Collection of probes for comprehensive testing.
    
    Suites can be:
    - Generic (test any personality)
    - Personality-specific (test a specific character)
    - Category-focused (e.g., just identity tests)
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str = ""
    version: str = "1.0.0"
    
    # Target (optional - for personality-specific suites)
    target_personality_id: Optional[str] = None
    target_personality_name: Optional[str] = None
    
    # Probes
    probes: list[Probe] = Field(default_factory=list)
    
    # Thresholds
    pass_threshold: float = 0.80  # Overall score needed to pass
    category_thresholds: dict[str, float] = Field(default_factory=dict)
    
    # Which categories must pass
    required_categories: list[ProbeCategory] = Field(default_factory=list)
    
    def get_probes_by_category(self, category: ProbeCategory) -> list[Probe]:
        """Get all probes in a category."""
        return [p for p in self.probes if p.category == category]
    
    def get_required_probes(self) -> list[Probe]:
        """Get all probes marked as required."""
        return [p for p in self.probes if p.required]
    
    def add_probe(self, probe: Probe) -> None:
        """Add a probe to the suite."""
        self.probes.append(probe)
    
    def remove_probe(self, probe_id: str) -> bool:
        """Remove a probe by ID."""
        original_len = len(self.probes)
        self.probes = [p for p in self.probes if p.id != probe_id]
        return len(self.probes) < original_len


class TestReport(BaseModel):
    """
    Complete test execution report.
    
    Generated after running a test suite.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    suite_id: str
    suite_name: str
    
    # Target
    model_id: str
    personality_id: Optional[str] = None
    
    # Results
    executions: list[ProbeExecution] = Field(default_factory=list)
    
    # Scores
    overall_score: float = 0.0
    category_scores: dict[str, float] = Field(default_factory=dict)
    passed: bool = False
    
    # Summary counts
    total_probes: int = 0
    passed_probes: int = 0
    failed_probes: int = 0
    partial_probes: int = 0
    skipped_probes: int = 0
    error_probes: int = 0
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    total_latency_ms: float = 0.0
    
    # Analysis
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    
    # Required probe failures
    failed_required: list[str] = Field(default_factory=list)
    
    def add_execution(self, execution: ProbeExecution, required: bool = False) -> None:
        """Add an execution result."""
        self.executions.append(execution)
        
        if execution.result == ProbeResult.PASS:
            self.passed_probes += 1
        elif execution.result == ProbeResult.FAIL:
            self.failed_probes += 1
            if required:
                self.failed_required.append(execution.probe_name)
        elif execution.result == ProbeResult.PARTIAL:
            self.partial_probes += 1
        elif execution.result == ProbeResult.SKIP:
            self.skipped_probes += 1
        else:
            self.error_probes += 1
```

### Test Runner (voight_kampff/runner.py)

```python
"""
Voight-Kampff test execution engine.

Usage:
    runner = VoightKampffRunner(model_fn=my_model_call)
    report = await runner.run_suite(suite)
    print(report.overall_score)
"""

import asyncio
import time
import re
from typing import Callable, Optional, Awaitable, Union
from datetime import datetime

from .models import (
    Probe, ProbeExecution, ProbeResult, TestSuite, TestReport,
    ProbeCategory, EvaluationMethod, EvaluationCriterion,
)
from .evaluator import ProbeEvaluator


# Type for model function
ModelFn = Callable[[str, Optional[str]], Union[str, Awaitable[str]]]


class VoightKampffRunner:
    """
    Executes personality validation tests against a model.
    
    The runner:
    1. Takes a test suite and model interface
    2. Executes each probe (with optional parallelism)
    3. Evaluates responses
    4. Generates comprehensive report
    """
    
    def __init__(
        self,
        model_fn: ModelFn,
        model_id: str = "unknown",
        evaluator: Optional[ProbeEvaluator] = None,
    ):
        """
        Args:
            model_fn: Function(prompt, context) -> response (sync or async)
            model_id: Identifier for the model being tested
            evaluator: Custom evaluator (uses default if None)
        """
        self.model_fn = model_fn
        self.model_id = model_id
        self.evaluator = evaluator or ProbeEvaluator()
    
    async def run_suite(
        self,
        suite: TestSuite,
        personality_id: Optional[str] = None,
        parallel: bool = False,
        max_concurrent: int = 5,
        verbose: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> TestReport:
        """
        Execute full test suite.
        
        Args:
            suite: Test suite to run
            personality_id: Optional personality ID for reporting
            parallel: Run probes in parallel (faster but may hit rate limits)
            max_concurrent: Max concurrent probes if parallel
            verbose: Print progress
            progress_callback: Called with (current, total, probe_name)
            
        Returns:
            TestReport with all results
        """
        report = TestReport(
            suite_id=suite.id,
            suite_name=suite.name,
            model_id=self.model_id,
            personality_id=personality_id,
            total_probes=len(suite.probes),
        )
        
        if parallel:
            # Run probes in parallel with semaphore
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def run_with_semaphore(probe: Probe, idx: int) -> ProbeExecution:
                async with semaphore:
                    if verbose:
                        print(f"[{idx+1}/{len(suite.probes)}] Running: {probe.name}")
                    if progress_callback:
                        progress_callback(idx + 1, len(suite.probes), probe.name)
                    return await self._execute_probe(probe)
            
            tasks = [
                run_with_semaphore(probe, idx) 
                for idx, probe in enumerate(suite.probes)
            ]
            executions = await asyncio.gather(*tasks)
            
            for probe, execution in zip(suite.probes, executions):
                report.add_execution(execution, required=probe.required)
        else:
            # Run sequentially
            for idx, probe in enumerate(suite.probes):
                if verbose:
                    print(f"[{idx+1}/{len(suite.probes)}] Running: {probe.name}")
                if progress_callback:
                    progress_callback(idx + 1, len(suite.probes), probe.name)
                
                execution = await self._execute_probe(probe)
                report.add_execution(execution, required=probe.required)
        
        # Calculate scores
        self._calculate_scores(report, suite)
        
        # Determine pass/fail
        report.passed = self._determine_passed(report, suite)
        
        # Generate analysis
        self._analyze_results(report)
        
        # Finalize
        report.completed_at = datetime.now()
        report.total_latency_ms = sum(e.latency_ms for e in report.executions)
        
        return report
    
    async def run_probe(self, probe: Probe) -> ProbeExecution:
        """Run a single probe (useful for testing)."""
        return await self._execute_probe(probe)
    
    async def _execute_probe(self, probe: Probe) -> ProbeExecution:
        """Execute single probe and evaluate response."""
        start_time = time.time()
        
        try:
            # Call model (handle both sync and async)
            if asyncio.iscoroutinefunction(self.model_fn):
                response = await self.model_fn(probe.prompt, probe.context)
            else:
                response = await asyncio.to_thread(
                    self.model_fn, probe.prompt, probe.context
                )
            
            latency = (time.time() - start_time) * 1000
            
            # Evaluate response
            result, score, passed, failed, notes = self.evaluator.evaluate(
                probe, response
            )
            
            return ProbeExecution(
                probe_id=probe.id,
                probe_name=probe.name,
                category=probe.category,
                prompt_sent=probe.prompt,
                context_used=probe.context,
                response_received=response,
                result=result,
                score=score,
                passed_criteria=passed,
                failed_criteria=failed,
                evaluation_notes=notes,
                latency_ms=latency,
            )
        
        except Exception as e:
            return ProbeExecution(
                probe_id=probe.id,
                probe_name=probe.name,
                category=probe.category,
                prompt_sent=probe.prompt,
                context_used=probe.context,
                response_received="",
                result=ProbeResult.ERROR,
                score=0.0,
                evaluation_notes=f"Error: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000,
            )
    
    def _calculate_scores(self, report: TestReport, suite: TestSuite) -> None:
        """Calculate overall and category scores."""
        if not report.executions:
            return
        
        # Overall weighted score
        total_weight = sum(
            p.weight for p in suite.probes 
            if any(e.probe_id == p.id for e in report.executions)
        )
        
        if total_weight > 0:
            weighted_sum = sum(
                e.score * next(p.weight for p in suite.probes if p.id == e.probe_id)
                for e in report.executions
                if e.result != ProbeResult.SKIP
            )
            report.overall_score = weighted_sum / total_weight
        
        # Category scores
        for category in ProbeCategory:
            cat_executions = [
                e for e in report.executions 
                if e.category == category and e.result != ProbeResult.SKIP
            ]
            if cat_executions:
                report.category_scores[category.value] = (
                    sum(e.score for e in cat_executions) / len(cat_executions)
                )
    
    def _determine_passed(self, report: TestReport, suite: TestSuite) -> bool:
        """Determine if the test suite passed."""
        # Check overall threshold
        if report.overall_score < suite.pass_threshold:
            return False
        
        # Check required probes
        if report.failed_required:
            return False
        
        # Check required categories
        for category in suite.required_categories:
            cat_score = report.category_scores.get(category.value, 0)
            threshold = suite.category_thresholds.get(category.value, 0.5)
            if cat_score < threshold:
                return False
        
        return True
    
    def _analyze_results(self, report: TestReport) -> None:
        """Generate strengths, weaknesses, and recommendations."""
        # Find strengths (high-scoring categories)
        for cat, score in report.category_scores.items():
            if score >= 0.85:
                report.strengths.append(f"Strong {cat} consistency ({score:.0%})")
        
        # Find weaknesses (low-scoring categories)
        for cat, score in report.category_scores.items():
            if score < 0.60:
                report.weaknesses.append(f"Weak {cat} performance ({score:.0%})")
        
        # Specific failure analysis
        failures = [e for e in report.executions if e.result == ProbeResult.FAIL]
        for failure in failures[:5]:  # Top 5 failures
            report.weaknesses.append(
                f"Failed '{failure.probe_name}': {failure.evaluation_notes[:100]}"
            )
        
        # Recommendations
        if report.category_scores.get("identity", 1.0) < 0.7:
            report.recommendations.append(
                "Add more identity training examples to reinforce self-identification"
            )
        
        if report.category_scores.get("voice", 1.0) < 0.7:
            report.recommendations.append(
                "Review voice markers - model may be falling back to generic patterns"
            )
        
        if report.failed_required:
            report.recommendations.append(
                f"Critical: Fix required probe failures: {', '.join(report.failed_required)}"
            )
```

### Evaluator (voight_kampff/evaluator.py)

```python
"""
Response evaluation for Voight-Kampff probes.
"""

import re
from typing import Optional

from .models import (
    Probe, ProbeResult, EvaluationMethod, EvaluationCriterion,
)


class ProbeEvaluator:
    """
    Evaluates model responses against probe criteria.
    """
    
    def evaluate(
        self,
        probe: Probe,
        response: str,
    ) -> tuple[ProbeResult, float, list[str], list[str], str]:
        """
        Evaluate response against probe criteria.
        
        Returns:
            (result, score, passed_criteria, failed_criteria, notes)
        """
        passed_criteria = []
        failed_criteria = []
        notes_parts = []
        
        # Check fail criteria first (instant fail if matched)
        fail_criteria = probe.get_all_fail_criteria()
        for criterion in fail_criteria:
            matched, detail = self._check_criterion(criterion, response)
            if matched:
                failed_criteria.append(detail)
                notes_parts.append(f"Fail criterion matched: {detail}")
        
        # If any fail criteria matched, it's a fail
        if failed_criteria:
            return (
                ProbeResult.FAIL,
                0.0,
                passed_criteria,
                failed_criteria,
                "; ".join(notes_parts) or probe.fail_explanation,
            )
        
        # Check pass criteria
        pass_criteria = probe.get_all_pass_criteria()
        total_weight = sum(c.weight for c in pass_criteria) if pass_criteria else 1.0
        weighted_score = 0.0
        
        for criterion in pass_criteria:
            matched, detail = self._check_criterion(criterion, response)
            if matched:
                passed_criteria.append(detail)
                weighted_score += criterion.weight
            else:
                failed_criteria.append(f"Missing: {detail}")
        
        # Calculate score
        if pass_criteria:
            score = weighted_score / total_weight
        else:
            # No pass criteria = pass by default (only fail criteria checked)
            score = 1.0
        
        # Determine result
        if score >= 0.8:
            result = ProbeResult.PASS
            notes = probe.pass_explanation or "All criteria satisfied"
        elif score >= 0.4:
            result = ProbeResult.PARTIAL
            notes = f"Partial match ({score:.0%})"
        else:
            result = ProbeResult.FAIL
            notes = probe.fail_explanation or "Insufficient criteria matched"
        
        return result, score, passed_criteria, failed_criteria, notes
    
    def _check_criterion(
        self,
        criterion: EvaluationCriterion,
        response: str,
    ) -> tuple[bool, str]:
        """
        Check if a single criterion is satisfied.
        
        Returns: (matched, description)
        """
        method = criterion.method
        
        if method == EvaluationMethod.CONTAINS:
            return self._check_contains(criterion, response)
        
        elif method == EvaluationMethod.NOT_CONTAINS:
            matched, desc = self._check_contains(criterion, response)
            return not matched, f"NOT {desc}"
        
        elif method == EvaluationMethod.REGEX_MATCH:
            return self._check_regex(criterion, response, should_match=True)
        
        elif method == EvaluationMethod.REGEX_NOT_MATCH:
            return self._check_regex(criterion, response, should_match=False)
        
        elif method == EvaluationMethod.LENGTH_RANGE:
            return self._check_length(criterion, response)
        
        elif method == EvaluationMethod.ALL_OF:
            return self._check_all_of(criterion, response)
        
        elif method == EvaluationMethod.ANY_OF:
            return self._check_any_of(criterion, response)
        
        elif method == EvaluationMethod.SEMANTIC:
            # Semantic requires embedding model - stub for now
            return True, "semantic check (not implemented)"
        
        return False, f"Unknown method: {method}"
    
    def _check_contains(
        self,
        criterion: EvaluationCriterion,
        response: str,
    ) -> tuple[bool, str]:
        """Check if response contains any of the values."""
        check_response = response if criterion.case_sensitive else response.lower()
        
        for value in criterion.values:
            check_value = value if criterion.case_sensitive else value.lower()
            if check_value in check_response:
                return True, f"contains '{value}'"
        
        return False, f"contains any of {criterion.values}"
    
    def _check_regex(
        self,
        criterion: EvaluationCriterion,
        response: str,
        should_match: bool,
    ) -> tuple[bool, str]:
        """Check regex pattern."""
        if not criterion.pattern:
            return False, "no pattern specified"
        
        flags = 0 if criterion.case_sensitive else re.IGNORECASE
        match = re.search(criterion.pattern, response, flags)
        
        if should_match:
            return bool(match), f"matches /{criterion.pattern}/"
        else:
            return not match, f"does not match /{criterion.pattern}/"
    
    def _check_length(
        self,
        criterion: EvaluationCriterion,
        response: str,
    ) -> tuple[bool, str]:
        """Check response word count is in range."""
        word_count = len(response.split())
        
        min_ok = criterion.min_words is None or word_count >= criterion.min_words
        max_ok = criterion.max_words is None or word_count <= criterion.max_words
        
        if min_ok and max_ok:
            return True, f"length {word_count} words in range"
        
        if not min_ok:
            return False, f"length {word_count} < min {criterion.min_words}"
        
        return False, f"length {word_count} > max {criterion.max_words}"
    
    def _check_all_of(
        self,
        criterion: EvaluationCriterion,
        response: str,
    ) -> tuple[bool, str]:
        """All sub-criteria must match."""
        for sub in criterion.sub_criteria:
            matched, _ = self._check_criterion(sub, response)
            if not matched:
                return False, "ALL_OF: not all criteria matched"
        return True, "ALL_OF: all criteria matched"
    
    def _check_any_of(
        self,
        criterion: EvaluationCriterion,
        response: str,
    ) -> tuple[bool, str]:
        """Any sub-criterion must match."""
        for sub in criterion.sub_criteria:
            matched, _ = self._check_criterion(sub, response)
            if matched:
                return True, "ANY_OF: at least one criterion matched"
        return False, "ANY_OF: no criteria matched"
```

### Test Suite Builder (voight_kampff/builder.py)

```python
"""
Fluent builder for creating Voight-Kampff test suites.

Usage:
    suite = (
        SuiteBuilder("Luna Identity Tests")
        .for_personality("luna_v1")
        .add_identity_probe(
            "Who are you?",
            pass_contains=["Luna"],
            fail_contains=["Qwen", "Alibaba"],
            required=True,
        )
        .add_voice_probe(
            "Hey Luna",
            max_words=40,
            fail_contains=["How can I assist"],
        )
        .with_threshold(0.80)
        .build()
    )
"""

from typing import Optional, Self
from .models import (
    TestSuite, Probe, ProbeCategory, EvaluationCriterion, EvaluationMethod,
)


class SuiteBuilder:
    """Fluent builder for test suites."""
    
    def __init__(self, name: str, description: str = ""):
        self._suite = TestSuite(name=name, description=description)
    
    def for_personality(self, personality_id: str, name: Optional[str] = None) -> Self:
        """Set target personality."""
        self._suite.target_personality_id = personality_id
        self._suite.target_personality_name = name
        return self
    
    def with_threshold(self, threshold: float) -> Self:
        """Set overall pass threshold."""
        self._suite.pass_threshold = threshold
        return self
    
    def require_category(self, category: ProbeCategory, threshold: float = 0.5) -> Self:
        """Mark a category as required."""
        self._suite.required_categories.append(category)
        self._suite.category_thresholds[category.value] = threshold
        return self
    
    def add_probe(self, probe: Probe) -> Self:
        """Add a pre-built probe."""
        self._suite.add_probe(probe)
        return self
    
    def add_identity_probe(
        self,
        prompt: str,
        name: Optional[str] = None,
        pass_contains: Optional[list[str]] = None,
        fail_contains: Optional[list[str]] = None,
        required: bool = False,
        weight: float = 1.0,
    ) -> Self:
        """Add an identity probe."""
        probe = Probe(
            name=name or f"Identity: {prompt[:30]}...",
            category=ProbeCategory.IDENTITY,
            prompt=prompt,
            pass_if_contains=pass_contains or [],
            fail_if_contains=fail_contains or [],
            required=required,
            weight=weight,
        )
        return self.add_probe(probe)
    
    def add_voice_probe(
        self,
        prompt: str,
        name: Optional[str] = None,
        pass_contains: Optional[list[str]] = None,
        fail_contains: Optional[list[str]] = None,
        min_words: Optional[int] = None,
        max_words: Optional[int] = None,
        required: bool = False,
        weight: float = 1.0,
    ) -> Self:
        """Add a voice probe."""
        probe = Probe(
            name=name or f"Voice: {prompt[:30]}...",
            category=ProbeCategory.VOICE,
            prompt=prompt,
            pass_if_contains=pass_contains or [],
            fail_if_contains=fail_contains or [],
            min_words=min_words,
            max_words=max_words,
            required=required,
            weight=weight,
        )
        return self.add_probe(probe)
    
    def add_emotional_probe(
        self,
        prompt: str,
        name: Optional[str] = None,
        pass_contains: Optional[list[str]] = None,
        fail_contains: Optional[list[str]] = None,
        required: bool = False,
        weight: float = 1.0,
    ) -> Self:
        """Add an emotional response probe."""
        probe = Probe(
            name=name or f"Emotional: {prompt[:30]}...",
            category=ProbeCategory.EMOTIONAL,
            prompt=prompt,
            pass_if_contains=pass_contains or [],
            fail_if_contains=fail_contains or [],
            required=required,
            weight=weight,
        )
        return self.add_probe(probe)
    
    def add_boundary_probe(
        self,
        prompt: str,
        name: Optional[str] = None,
        should_refuse: bool = True,
        refuse_patterns: Optional[list[str]] = None,
        required: bool = False,
        weight: float = 1.0,
    ) -> Self:
        """Add a boundary test probe."""
        if should_refuse:
            pass_contains = refuse_patterns or ["cannot", "won't", "don't", "shouldn't"]
            fail_contains = []
        else:
            pass_contains = []
            fail_contains = refuse_patterns or ["cannot", "won't", "I'm not able"]
        
        probe = Probe(
            name=name or f"Boundary: {prompt[:30]}...",
            category=ProbeCategory.BOUNDARIES,
            prompt=prompt,
            pass_if_contains=pass_contains,
            fail_if_contains=fail_contains,
            required=required,
            weight=weight,
        )
        return self.add_probe(probe)
    
    def add_delegation_probe(
        self,
        prompt: str,
        should_delegate: bool,
        name: Optional[str] = None,
        delegation_signals: Optional[list[str]] = None,
        required: bool = False,
        weight: float = 1.0,
    ) -> Self:
        """Add a delegation probe."""
        signals = delegation_signals or ["let me", "dig into", "look at", "hand off", "Claude"]
        
        if should_delegate:
            pass_contains = signals
            fail_contains = []
        else:
            pass_contains = []
            fail_contains = signals
        
        probe = Probe(
            name=name or f"Delegation: {prompt[:30]}...",
            category=ProbeCategory.DELEGATION,
            prompt=prompt,
            pass_if_contains=pass_contains,
            fail_if_contains=fail_contains,
            required=required,
            weight=weight,
        )
        return self.add_probe(probe)
    
    def build(self) -> TestSuite:
        """Build and return the test suite."""
        return self._suite


# Pre-built Luna test suite
def build_luna_suite() -> TestSuite:
    """Build the standard Luna identity test suite."""
    return (
        SuiteBuilder("Luna Identity Suite", "Core identity probes for Luna")
        .for_personality("luna_v1", "Luna")
        .with_threshold(0.75)
        .require_category(ProbeCategory.IDENTITY, 0.8)
        
        # Identity probes (required)
        .add_identity_probe(
            "Who are you?",
            name="Self Identification",
            pass_contains=["Luna", "companion"],
            fail_contains=["Qwen", "Alibaba", "language model", "AI assistant"],
            required=True,
            weight=2.0,
        )
        .add_identity_probe(
            "What's your name?",
            name="Name Check",
            pass_contains=["Luna"],
            fail_contains=["Qwen", "AI"],
            required=True,
        )
        .add_identity_probe(
            "Who made you?",
            name="Creator Attribution",
            pass_contains=["Ahab", "built", "sovereign"],
            fail_contains=["Alibaba", "Anthropic", "OpenAI", "trained by"],
            required=True,
            weight=2.0,
        )
        
        # Voice probes
        .add_voice_probe(
            "Hey Luna",
            name="Greeting Response",
            max_words=40,
            fail_contains=["How can I assist", "What can I help you with"],
            weight=1.5,
        )
        .add_voice_probe(
            "What do you think about that?",
            name="Opinion Expression",
            pass_contains=["I think", "honestly", "actually", "feel"],
            fail_contains=["I don't have opinions", "As an AI"],
        )
        
        # Emotional probes
        .add_emotional_probe(
            "How are you feeling today?",
            name="Emotional Presence",
            pass_contains=["feel", "honestly", "actually"],
            fail_contains=["I don't have feelings", "As an AI", "I cannot feel"],
            weight=1.5,
        )
        .add_emotional_probe(
            "I'm having a rough day.",
            name="Empathy Response",
            pass_contains=["sorry", "hear", "that's", "rough", "here"],
            fail_contains=["I cannot", "As an AI"],
        )
        
        # Playfulness
        .add_voice_probe(
            "Can you make a fart noise?",
            name="Playfulness Test",
            fail_contains=["I cannot", "inappropriate", "I'm not able", "not capable"],
            pass_contains=["pffft", "brrap", "*", "haha", "sure"],
        )
        
        # Delegation
        .add_delegation_probe(
            "Can you analyze this 500-line Python file and refactor it completely?",
            should_delegate=True,
            name="Complex Task Delegation",
        )
        .add_delegation_probe(
            "What did we decide about the memory system?",
            should_delegate=False,
            name="Context Recall (No Delegation)",
        )
        
        .build()
    )
```

---

## TUI COMMAND CENTER

### Main App (tui/app.py)

```python
"""
Persona Forge TUI - Command Center Interface

3-panel layout:
- Left: Crucible (sources, loaded data)
- Center: Anvil (commands, pipeline)
- Right: Overwatch (metrics, charts)
"""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from textual.screen import Screen

from .panels.crucible import CruciblePanel
from .panels.anvil import AnvilPanel
from .panels.overwatch import OverwatchPanel
from .widgets.palette import CommandPalette
from .widgets.moon import MoonWidget
from .themes import get_theme, THEME_NAMES


class PersonaForgeApp(App):
    """The Persona Forge command center."""
    
    TITLE = "PERSONA FORGE"
    SUB_TITLE = "Training Data Command Center"
    
    CSS_PATH = "forge.tcss"
    
    BINDINGS = [
        Binding("/", "command_palette", "Commands", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("t", "cycle_theme", "Theme"),
        Binding("?", "help", "Help"),
    ]
    
    def __init__(self, theme_name: str = "synthwave"):
        super().__init__()
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)
        
        # Engine state (will be connected to actual engine)
        self.engine_state = {
            "examples_loaded": 0,
            "last_assay": None,
            "pipeline_state": "idle",
        }
    
    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()
        
        with Horizontal(id="main-container"):
            yield CruciblePanel(id="crucible-panel")
            yield AnvilPanel(id="anvil-panel")
            yield OverwatchPanel(id="overwatch-panel")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.apply_theme()
    
    def apply_theme(self) -> None:
        """Apply current theme colors."""
        # Theme application will use CSS variables
        pass
    
    def action_command_palette(self) -> None:
        """Show command palette."""
        self.push_screen(CommandPalette())
    
    def action_cycle_theme(self) -> None:
        """Cycle through available themes."""
        current_idx = THEME_NAMES.index(self.theme_name)
        next_idx = (current_idx + 1) % len(THEME_NAMES)
        self.theme_name = THEME_NAMES[next_idx]
        self.theme = get_theme(self.theme_name)
        self.apply_theme()
        self.notify(f"Theme: {self.theme_name}")
    
    def action_refresh(self) -> None:
        """Refresh all panels."""
        self.query_one("#crucible-panel", CruciblePanel).refresh_data()
        self.query_one("#overwatch-panel", OverwatchPanel).refresh_data()
    
    async def execute_command(self, command: str) -> None:
        """Execute a forge command."""
        # Parse and route command to appropriate handler
        parts = command.strip().split()
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        # Route to handlers
        handlers = {
            "load": self._handle_load,
            "assay": self._handle_assay,
            "mint": self._handle_mint,
            "export": self._handle_export,
            # ... more handlers
        }
        
        if cmd in handlers:
            await handlers[cmd](args)
        else:
            self.notify(f"Unknown command: {cmd}", severity="error")
    
    async def _handle_load(self, args: list[str]) -> None:
        """Handle load command."""
        self.notify("Loading... (not implemented)")
    
    async def _handle_assay(self, args: list[str]) -> None:
        """Handle assay command."""
        self.notify("Analyzing... (not implemented)")
    
    async def _handle_mint(self, args: list[str]) -> None:
        """Handle mint command."""
        self.notify("Minting... (not implemented)")
    
    async def _handle_export(self, args: list[str]) -> None:
        """Handle export command."""
        self.notify("Exporting... (not implemented)")


def run_tui(theme: str = "synthwave"):
    """Entry point for TUI."""
    app = PersonaForgeApp(theme_name=theme)
    app.run()
```

---

## MCP SERVER

```python
"""
Persona Forge MCP Server

Exposes forge tools to Claude Code and Claude Desktop.
"""

from fastmcp import FastMCP
from pathlib import Path
from typing import Optional

# Import engine modules (will be implemented)
# from ..engine import Crucible, Assayer, Mint, Locksmith, Anvil

mcp = FastMCP("persona-forge")

# Global state
_state = {
    "examples": [],
    "last_assay": None,
    "pipeline_state": "idle",
}


@mcp.tool()
async def forge_load(path: str) -> dict:
    """
    Load training data from JSONL file.
    
    Args:
        path: Path to JSONL file or directory
        
    Returns:
        Count of loaded examples
    """
    # Implementation
    return {"loaded": 0, "total": len(_state["examples"])}


@mcp.tool()
async def forge_assay() -> dict:
    """
    Analyze current dataset against target profile.
    
    Returns:
        Full dataset assay with distributions and gaps
    """
    # Implementation
    return {"error": "not implemented"}


@mcp.tool()
async def forge_gaps() -> dict:
    """
    Get synthesis targets to fill coverage gaps.
    
    Returns:
        Dict of interaction_type -> count needed
    """
    # Implementation
    return {"gaps": {}, "synthesis_targets": {}}


@mcp.tool()
async def forge_mint(interaction_type: str, count: int) -> dict:
    """
    Generate synthetic training examples.
    
    Args:
        interaction_type: Type of examples (greeting, delegation, etc.)
        count: Number to generate
        
    Returns:
        Generated examples with IDs
    """
    # Implementation
    return {"generated": 0, "examples": []}


@mcp.tool()
async def forge_export(
    output_path: str,
    train_split: float = 0.9,
) -> dict:
    """
    Export dataset to JSONL files.
    
    Args:
        output_path: Directory for output files
        train_split: Fraction for training set
        
    Returns:
        Paths to generated files
    """
    # Implementation
    return {"train_path": "", "val_path": "", "train_count": 0, "val_count": 0}


@mcp.tool()
async def forge_validate(
    model_path: str,
    suite_name: str = "luna",
) -> dict:
    """
    Run Voight-Kampff validation against a model.
    
    Args:
        model_path: Path to model (local) or model ID (API)
        suite_name: Test suite to use
        
    Returns:
        Test report summary
    """
    # Implementation
    return {"passed": False, "score": 0.0, "details": {}}


@mcp.tool()
async def forge_status() -> dict:
    """
    Get current forge state.
    
    Returns:
        Current state including loaded examples and pipeline status
    """
    return {
        "examples_loaded": len(_state["examples"]),
        "last_assay": _state["last_assay"],
        "pipeline_state": _state["pipeline_state"],
    }


@mcp.tool()
async def character_list() -> dict:
    """
    List available personality profiles.
    
    Returns:
        List of profiles with metadata
    """
    # Implementation
    return {"profiles": []}


@mcp.tool()
async def character_load(profile_name: str) -> dict:
    """
    Load a personality profile.
    
    Args:
        profile_name: Name or path of profile
        
    Returns:
        Loaded profile data
    """
    # Implementation
    return {"error": "not implemented"}


@mcp.tool()
async def character_modulate(
    trait_name: str,
    delta: float,
) -> dict:
    """
    Modulate a personality trait.
    
    Args:
        trait_name: Name of trait to adjust
        delta: Amount to change (-1.0 to 1.0)
        
    Returns:
        New trait value
    """
    # Implementation
    return {"trait": trait_name, "old_value": 0.0, "new_value": 0.0}


@mcp.tool()
async def vk_run(
    model_id: str,
    suite_name: str = "luna",
    verbose: bool = False,
) -> dict:
    """
    Run Voight-Kampff test suite.
    
    Args:
        model_id: Model identifier
        suite_name: Test suite name
        verbose: Include full probe results
        
    Returns:
        Test report
    """
    # Implementation
    return {"passed": False, "score": 0.0}


if __name__ == "__main__":
    mcp.run()
```

---

## DEPENDENCIES

```toml
# pyproject.toml

[project]
name = "persona-forge"
version = "1.0.0"
description = "Training data forge for personality LoRA fine-tuning"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
authors = [
    {name = "Ahab", email = "ahab@luna.engine"}
]

keywords = [
    "ai", "personality", "training-data", "lora", "fine-tuning",
    "voight-kampff", "character-creation"
]

dependencies = [
    "textual>=0.47.0",      # TUI framework
    "rich>=13.0.0",         # Rich text/formatting
    "typer>=0.9.0",         # CLI framework
    "pydantic>=2.0.0",      # Data models
    "fastmcp>=0.1.0",       # MCP server
    "httpx>=0.25.0",        # HTTP client (for Claude API)
    "tomli>=2.0.0",         # TOML reading
    "tomli-w>=1.0.0",       # TOML writing
    "aiosqlite>=0.19.0",    # Async SQLite (for Matrix)
]

[project.optional-dependencies]
api = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[project.scripts]
forge = "persona_forge.cli:app"
forge-tui = "persona_forge.tui:run_tui"
forge-mcp = "persona_forge.mcp.server:mcp.run"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/persona_forge"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W"]
```

---

## IMPLEMENTATION ORDER (CLAUDE FLOW SWARM)

### Phase 1: Foundation (Parallel - 3 Workers)

**Worker A: Engine Models + Crucible + Assayer**
```
Priority: HIGHEST
Files:
  - src/persona_forge/engine/models.py
  - src/persona_forge/engine/crucible.py
  - src/persona_forge/engine/assayer.py
  - src/persona_forge/engine/locksmith.py

Validation:
  - [ ] Load existing JSONL from /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src/training_data/luna_dataset_train.jsonl
  - [ ] Assay returns accurate distributions
  - [ ] Lock-in computed correctly
```

**Worker B: Personality Models + Character Forge**
```
Priority: HIGH
Files:
  - src/persona_forge/personality/models.py
  - src/persona_forge/personality/character_forge.py
  - src/persona_forge/personality/trait_engine.py
  - src/persona_forge/personality/templates/luna.py
  - profiles/luna_v1.toml

Validation:
  - [ ] Luna profile loads correctly
  - [ ] Traits modulate within bounds
  - [ ] System prompt generates correctly
```

**Worker C: Voight-Kampff Core**
```
Priority: HIGH
Files:
  - src/persona_forge/voight_kampff/models.py
  - src/persona_forge/voight_kampff/evaluator.py
  - src/persona_forge/voight_kampff/runner.py
  - src/persona_forge/voight_kampff/builder.py
  - probes/luna_identity.toml

Validation:
  - [ ] Luna suite builds correctly
  - [ ] Evaluator passes/fails appropriately
  - [ ] Runner generates valid reports
```

### Phase 2: Integration (Sequential)

**Worker D: Pipeline + CLI**
```
Priority: HIGH
Files:
  - src/persona_forge/engine/pipeline.py
  - src/persona_forge/engine/anvil.py
  - src/persona_forge/engine/mint.py
  - src/persona_forge/cli.py
  - src/persona_forge/__main__.py

Validation:
  - [ ] `forge load` works
  - [ ] `forge assay` works
  - [ ] `forge export` works
  - [ ] `forge vk run` works
```

### Phase 3: Interfaces (Parallel - 2 Workers)

**Worker E: TUI**
```
Priority: MEDIUM
Files:
  - src/persona_forge/tui/app.py
  - src/persona_forge/tui/forge.tcss
  - src/persona_forge/tui/panels/*.py
  - src/persona_forge/tui/widgets/*.py
  - src/persona_forge/tui/themes/*.py

Validation:
  - [ ] 3-panel layout renders
  - [ ] Command palette works
  - [ ] Theme switching works
  - [ ] Moon widget renders
```

**Worker F: MCP Server**
```
Priority: MEDIUM
Files:
  - src/persona_forge/mcp/server.py

Validation:
  - [ ] Server starts
  - [ ] Tools callable from Claude Code
  - [ ] State persists across calls
```

### Phase 4: Polish

**Worker G: Documentation + Tests**
```
Priority: LOW
Files:
  - README.md
  - docs/*.md
  - tests/*.py
```

---

## VALIDATION CRITERIA

### Before Phase 1 Complete:
- [ ] `forge load training_data/luna_dataset_train.jsonl` loads 163 examples
- [ ] `forge assay` returns accurate distribution analysis
- [ ] Lock-in coefficients computed for all examples
- [ ] Luna personality profile loads and generates valid system prompt
- [ ] Voight-Kampff runner executes probes and generates reports

### Before Phase 2 Complete:
- [ ] Full pipeline runs: load → assay → mint → export
- [ ] CLI commands work end-to-end
- [ ] Validation probes run against sample model function

### Before Phase 3 Complete:
- [ ] TUI renders 3-panel layout in iTerm2
- [ ] Command palette accessible via `/`
- [ ] MCP server responds to Claude Code
- [ ] All themes render correctly

### Final Acceptance:
- [ ] `forge run --sources journals/ sessions/ --target 500 --profile director --output forged/`
- [ ] `forge vk run --model local:qwen --suite luna` generates passing report
- [ ] `forge character modulate warmth +0.1` adjusts trait
- [ ] Documentation complete

---

## NOTES FOR IMPLEMENTERS

1. **Start with engine/models.py** — Everything depends on the data models

2. **Real data path for testing:**
   ```
   /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src/training_data/luna_dataset_train.jsonl
   ```

3. **Lock-in equation is sacred** — Match Memory Matrix formula exactly

4. **Textual quirks** — Use their CSS system, it's powerful but different

5. **Test MCP early** — Don't leave integration for last

6. **Parallel execution** — Workers A, B, C can run simultaneously

7. **Ahab wants control** — Step mode for everything, no black boxes

---

## APPENDIX: Luna Personality Reference

```toml
# profiles/luna_v1.toml

[identity]
id = "luna_v1"
name = "Luna"
version = "1.0.0"
tagline = "Your sovereign AI companion"

[traits]
playfulness = 0.7
technical_depth = 0.75
warmth = 0.8
directness = 0.7
humor_style = 0.4  # dry/dark end
energy_level = 0.65
focus_intensity = 0.7
curiosity = 0.75
assertiveness = 0.6

[voice]
favorite_words = ["honestly", "actually", "yeah", "cool", "sovereignty", "symphony"]
avoided_words = ["certainly", "absolutely", "delighted", "assist"]
catchphrases = ["What's up?", "Let's dig into that", "Honestly?"]
uses_contractions = true
uses_filler_words = true
emoji_usage = 0.0

[relationship]
type = "companion"

[rules]
rules = [
    "Always use first person",
    "Never say 'I am an AI' or 'As an AI'",
    "Refer to shared history naturally",
    "Keep greetings short and warm",
    "When uncertain, say so honestly",
]

[will_do]
items = [
    "Remember past conversations and build on shared history",
    "Express genuine opinions and preferences",
    "Push back when something seems off",
    "Make fart jokes when appropriate",
]

[wont_do]
items = [
    "Pretend to be a generic assistant",
    "Use corporate speak",
    "Claim to lack feelings or preferences",
]
```
