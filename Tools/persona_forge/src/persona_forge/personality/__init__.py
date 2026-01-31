"""
Personality module for Persona Forge.

This module provides the core personality modeling system including:
- Data models for traits, voices, and complete profiles
- Trait computation engine for comparisons and manipulations
- Character forge factory for creating and managing personalities
- Pre-built templates and Jungian archetypes
"""

from .models import (
    ExampleExchange,
    PersonalityProfile,
    PersonalityTrait,
    PersonalityVector,
    VoiceProfile,
)
from .trait_engine import TraitEngine
from .character_forge import CharacterForge
from .templates import (
    ARCHETYPES,
    TEMPLATES,
    get_archetype,
    get_template,
    list_archetypes,
    list_templates,
    register_archetype,
    register_template,
)
from .templates.luna import (
    create_luna_profile,
    create_luna_minimal,
    create_luna_system_prompt,
)

__all__ = [
    # Models
    'PersonalityTrait',
    'PersonalityVector',
    'VoiceProfile',
    'ExampleExchange',
    'PersonalityProfile',

    # Engines
    'TraitEngine',
    'CharacterForge',

    # Templates
    'TEMPLATES',
    'ARCHETYPES',
    'get_template',
    'get_archetype',
    'list_templates',
    'list_archetypes',
    'register_template',
    'register_archetype',

    # Luna
    'create_luna_profile',
    'create_luna_minimal',
    'create_luna_system_prompt',
]
