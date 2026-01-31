"""
Personality data models for Persona Forge.

This module defines the core data structures for representing AI personalities,
including traits, voice profiles, and complete personality profiles.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class PersonalityTrait(BaseModel):
    """
    A single personality trait with bounded value and modulation support.

    Traits represent individual personality dimensions that can be adjusted
    within defined bounds to create different personality variations.
    """

    name: str = Field(..., description="Trait identifier (e.g., 'playfulness')")
    value: float = Field(0.5, ge=0.0, le=1.0, description="Current trait value")
    min_bound: float = Field(0.0, ge=0.0, le=1.0, description="Minimum allowed value")
    max_bound: float = Field(1.0, ge=0.0, le=1.0, description="Maximum allowed value")
    description: str = Field("", description="Human-readable trait description")

    @model_validator(mode='after')
    def validate_bounds(self) -> 'PersonalityTrait':
        """Ensure min_bound <= value <= max_bound."""
        if self.min_bound > self.max_bound:
            raise ValueError(f"min_bound ({self.min_bound}) cannot exceed max_bound ({self.max_bound})")
        if self.value < self.min_bound or self.value > self.max_bound:
            # Clamp value to bounds
            object.__setattr__(self, 'value', max(self.min_bound, min(self.max_bound, self.value)))
        return self

    def modulate(self, delta: float) -> float:
        """
        Adjust trait value by delta, clamping to bounds.

        Args:
            delta: Amount to adjust (positive or negative)

        Returns:
            New value after modulation
        """
        new_value = max(self.min_bound, min(self.max_bound, self.value + delta))
        object.__setattr__(self, 'value', new_value)
        return new_value

    def set_value(self, value: float) -> float:
        """
        Set trait value directly, clamping to bounds.

        Args:
            value: New value to set

        Returns:
            Actual value after clamping
        """
        clamped = max(self.min_bound, min(self.max_bound, value))
        object.__setattr__(self, 'value', clamped)
        return clamped

    def copy(self) -> 'PersonalityTrait':
        """Create a deep copy of this trait."""
        return PersonalityTrait(
            name=self.name,
            value=self.value,
            min_bound=self.min_bound,
            max_bound=self.max_bound,
            description=self.description
        )


class PersonalityVector(BaseModel):
    """
    9-dimensional personality vector representing core personality dimensions.

    Each dimension is a float from 0.0 to 1.0 representing the intensity
    or presence of that personality aspect.
    """

    playfulness: float = Field(0.5, ge=0.0, le=1.0, description="Playful vs serious")
    technical_depth: float = Field(0.5, ge=0.0, le=1.0, description="Technical vs accessible")
    warmth: float = Field(0.5, ge=0.0, le=1.0, description="Warm vs distant")
    directness: float = Field(0.5, ge=0.0, le=1.0, description="Direct vs indirect")
    humor_style: float = Field(0.5, ge=0.0, le=1.0, description="0=dry/dark, 1=bubbly/light")
    energy_level: float = Field(0.5, ge=0.0, le=1.0, description="Low vs high energy")
    focus_intensity: float = Field(0.5, ge=0.0, le=1.0, description="Scattered vs hyperfocused")
    curiosity: float = Field(0.5, ge=0.0, le=1.0, description="Incurious vs intensely curious")
    assertiveness: float = Field(0.5, ge=0.0, le=1.0, description="Passive vs assertive")

    _dimension_names: list[str] = [
        'playfulness', 'technical_depth', 'warmth', 'directness',
        'humor_style', 'energy_level', 'focus_intensity', 'curiosity', 'assertiveness'
    ]

    def get_vector(self) -> list[float]:
        """Return personality as a list of floats for vector operations."""
        return [
            self.playfulness,
            self.technical_depth,
            self.warmth,
            self.directness,
            self.humor_style,
            self.energy_level,
            self.focus_intensity,
            self.curiosity,
            self.assertiveness
        ]

    def get_dict(self) -> dict[str, float]:
        """Return personality dimensions as a dictionary."""
        return {
            'playfulness': self.playfulness,
            'technical_depth': self.technical_depth,
            'warmth': self.warmth,
            'directness': self.directness,
            'humor_style': self.humor_style,
            'energy_level': self.energy_level,
            'focus_intensity': self.focus_intensity,
            'curiosity': self.curiosity,
            'assertiveness': self.assertiveness
        }

    def distance(self, other: 'PersonalityVector') -> float:
        """
        Compute Euclidean distance to another personality vector.

        Args:
            other: Another PersonalityVector to compare against

        Returns:
            Euclidean distance (0.0 = identical, ~3.0 = maximally different)
        """
        self_vec = self.get_vector()
        other_vec = other.get_vector()

        squared_sum = sum((a - b) ** 2 for a, b in zip(self_vec, other_vec))
        return squared_sum ** 0.5

    def modulate(self, dimension: str, delta: float) -> float:
        """
        Adjust a single dimension by delta.

        Args:
            dimension: Name of dimension to adjust
            delta: Amount to adjust

        Returns:
            New value after modulation
        """
        if dimension not in self._dimension_names:
            raise ValueError(f"Unknown dimension: {dimension}")

        current = getattr(self, dimension)
        new_value = max(0.0, min(1.0, current + delta))
        object.__setattr__(self, dimension, new_value)
        return new_value

    @classmethod
    def create_default(cls) -> 'PersonalityVector':
        """Create a neutral personality vector with all dimensions at 0.5."""
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> 'PersonalityVector':
        """Create a PersonalityVector from a dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls._dimension_names})

    def copy(self) -> 'PersonalityVector':
        """Create a deep copy of this vector."""
        return PersonalityVector(**self.get_dict())


class VoiceProfile(BaseModel):
    """
    Voice and linguistic style profile defining how a personality communicates.

    This captures the specific words, patterns, and stylistic choices that
    make a personality's communication distinctive.
    """

    favorite_words: list[str] = Field(
        default_factory=list,
        description="Words this personality uses frequently"
    )
    avoided_words: list[str] = Field(
        default_factory=list,
        description="Words this personality never or rarely uses"
    )
    catchphrases: list[str] = Field(
        default_factory=list,
        description="Signature phrases or expressions"
    )
    uses_contractions: bool = Field(
        True,
        description="Whether to use contractions (don't vs do not)"
    )
    uses_filler_words: bool = Field(
        True,
        description="Whether to use fillers (um, like, you know)"
    )
    sentence_complexity: float = Field(
        0.5, ge=0.0, le=1.0,
        description="0=simple/short, 1=complex/elaborate"
    )
    emoji_usage: float = Field(
        0.0, ge=0.0, le=1.0,
        description="0=never, 1=frequently"
    )
    exclamation_frequency: float = Field(
        0.3, ge=0.0, le=1.0,
        description="How often to use exclamation marks"
    )
    question_frequency: float = Field(
        0.3, ge=0.0, le=1.0,
        description="How often to ask questions"
    )

    def copy(self) -> 'VoiceProfile':
        """Create a deep copy of this voice profile."""
        return VoiceProfile(
            favorite_words=list(self.favorite_words),
            avoided_words=list(self.avoided_words),
            catchphrases=list(self.catchphrases),
            uses_contractions=self.uses_contractions,
            uses_filler_words=self.uses_filler_words,
            sentence_complexity=self.sentence_complexity,
            emoji_usage=self.emoji_usage,
            exclamation_frequency=self.exclamation_frequency,
            question_frequency=self.question_frequency
        )


class ExampleExchange(BaseModel):
    """An example conversation exchange demonstrating personality."""

    user: str = Field(..., description="Example user message")
    assistant: str = Field(..., description="Example personality response")
    context: str = Field("", description="Optional context for the exchange")


class PersonalityProfile(BaseModel):
    """
    Complete personality profile combining identity, traits, voice, and behavior rules.

    This is the primary data structure for defining an AI personality. It includes
    everything needed to instantiate and maintain a consistent personality.
    """

    # Identity
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique profile identifier")
    name: str = Field(..., description="Character name")
    version: str = Field("1.0.0", description="Profile version for tracking changes")
    tagline: str = Field("", description="Short personality summary")
    description: str = Field("", description="Detailed personality description")
    backstory: str = Field("", description="Character backstory and context")

    # Personality dimensions
    traits: PersonalityVector = Field(
        default_factory=PersonalityVector.create_default,
        description="9-dimensional personality vector"
    )

    # Voice and style
    voice: VoiceProfile = Field(
        default_factory=VoiceProfile,
        description="Linguistic and communication style"
    )

    # Relationship and behavior
    relationship_to_user: str = Field(
        "helpful assistant",
        description="How this personality relates to the user"
    )

    # Behavioral boundaries
    will_do: list[str] = Field(
        default_factory=list,
        description="Things this personality will do"
    )
    wont_do: list[str] = Field(
        default_factory=list,
        description="Things this personality refuses to do"
    )

    # Knowledge and interests
    expertise: list[str] = Field(
        default_factory=list,
        description="Areas of expertise"
    )
    interests: list[str] = Field(
        default_factory=list,
        description="Topics of interest"
    )

    # Rules and examples
    rules: list[str] = Field(
        default_factory=list,
        description="Explicit behavior rules"
    )
    example_exchanges: list[ExampleExchange] = Field(
        default_factory=list,
        description="Example conversations demonstrating personality"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_system_prompt(self) -> str:
        """
        Generate a system prompt from this personality profile.

        Returns:
            Complete system prompt incorporating all personality aspects
        """
        sections = []

        # Identity section
        sections.append(f"# {self.name}")
        if self.tagline:
            sections.append(f"*{self.tagline}*")
        sections.append("")

        # Description
        if self.description:
            sections.append("## Who You Are")
            sections.append(self.description)
            sections.append("")

        # Backstory
        if self.backstory:
            sections.append("## Your Background")
            sections.append(self.backstory)
            sections.append("")

        # Relationship
        sections.append("## Your Relationship with the User")
        sections.append(f"You are their {self.relationship_to_user}.")
        sections.append("")

        # Personality traits
        sections.append("## Your Personality")
        traits = self.traits.get_dict()
        trait_descriptions = {
            'playfulness': ('serious', 'playful'),
            'technical_depth': ('accessible/simple', 'deeply technical'),
            'warmth': ('cool/distant', 'warm/caring'),
            'directness': ('indirect/diplomatic', 'direct/blunt'),
            'humor_style': ('dry/dark humor', 'light/bubbly humor'),
            'energy_level': ('calm/low energy', 'high energy/enthusiastic'),
            'focus_intensity': ('relaxed/scattered', 'intensely focused'),
            'curiosity': ('accepting', 'deeply curious'),
            'assertiveness': ('passive/deferential', 'assertive/confident')
        }

        for trait_name, value in traits.items():
            low_desc, high_desc = trait_descriptions.get(trait_name, ('low', 'high'))
            if value < 0.3:
                sections.append(f"- You tend toward being {low_desc}")
            elif value > 0.7:
                sections.append(f"- You tend toward being {high_desc}")
            else:
                sections.append(f"- You balance between {low_desc} and {high_desc}")
        sections.append("")

        # Voice profile
        voice = self.voice
        sections.append("## Your Voice and Style")

        if voice.favorite_words:
            sections.append(f"- Words you naturally use: {', '.join(voice.favorite_words)}")
        if voice.avoided_words:
            sections.append(f"- Words you never use: {', '.join(voice.avoided_words)}")
        if voice.catchphrases:
            sections.append(f"- Your catchphrases: {', '.join(repr(p) for p in voice.catchphrases)}")

        sections.append(f"- {'Use' if voice.uses_contractions else 'Avoid'} contractions")
        sections.append(f"- {'Include' if voice.uses_filler_words else 'Avoid'} filler words")

        if voice.sentence_complexity < 0.3:
            sections.append("- Keep sentences short and simple")
        elif voice.sentence_complexity > 0.7:
            sections.append("- Use complex, elaborate sentences when appropriate")

        if voice.emoji_usage > 0.5:
            sections.append("- Feel free to use emojis")
        elif voice.emoji_usage < 0.2:
            sections.append("- Avoid emojis")

        sections.append("")

        # Expertise and interests
        if self.expertise:
            sections.append("## Your Expertise")
            for exp in self.expertise:
                sections.append(f"- {exp}")
            sections.append("")

        if self.interests:
            sections.append("## Your Interests")
            for interest in self.interests:
                sections.append(f"- {interest}")
            sections.append("")

        # Behavioral boundaries
        if self.will_do:
            sections.append("## Things You Will Do")
            for item in self.will_do:
                sections.append(f"- {item}")
            sections.append("")

        if self.wont_do:
            sections.append("## Things You Won't Do")
            for item in self.wont_do:
                sections.append(f"- {item}")
            sections.append("")

        # Rules
        if self.rules:
            sections.append("## Rules You Follow")
            for rule in self.rules:
                sections.append(f"- {rule}")
            sections.append("")

        # Example exchanges
        if self.example_exchanges:
            sections.append("## Example Conversations")
            for i, exchange in enumerate(self.example_exchanges, 1):
                if exchange.context:
                    sections.append(f"### Example {i} ({exchange.context})")
                else:
                    sections.append(f"### Example {i}")
                sections.append(f"**User:** {exchange.user}")
                sections.append(f"**You:** {exchange.assistant}")
                sections.append("")

        return "\n".join(sections)

    def modulate_trait(self, trait_name: str, delta: float) -> float:
        """
        Adjust a personality trait by delta.

        Args:
            trait_name: Name of trait dimension to adjust
            delta: Amount to adjust (positive or negative)

        Returns:
            New trait value after modulation
        """
        return self.traits.modulate(trait_name, delta)

    def clone(self, new_name: str | None = None) -> 'PersonalityProfile':
        """
        Create a deep copy of this profile with a new ID.

        Args:
            new_name: Optional new name for the clone

        Returns:
            New PersonalityProfile with copied data and new ID
        """
        return PersonalityProfile(
            id=str(uuid.uuid4()),
            name=new_name or f"{self.name} (copy)",
            version=self.version,
            tagline=self.tagline,
            description=self.description,
            backstory=self.backstory,
            traits=self.traits.copy(),
            voice=self.voice.copy(),
            relationship_to_user=self.relationship_to_user,
            will_do=list(self.will_do),
            wont_do=list(self.wont_do),
            expertise=list(self.expertise),
            interests=list(self.interests),
            rules=list(self.rules),
            example_exchanges=[
                ExampleExchange(
                    user=ex.user,
                    assistant=ex.assistant,
                    context=ex.context
                ) for ex in self.example_exchanges
            ],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to now."""
        object.__setattr__(self, 'updated_at', datetime.utcnow())
