"""
Character factory for Persona Forge.

This module provides the CharacterForge class for creating, managing,
and persisting personality profiles.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import tomli
except ImportError:
    import tomllib as tomli  # Python 3.11+

try:
    import tomli_w
except ImportError:
    tomli_w = None  # Will use JSON fallback if not available

from .models import (
    ExampleExchange,
    PersonalityProfile,
    PersonalityTrait,
    PersonalityVector,
    VoiceProfile,
)
from .templates import ARCHETYPES, TEMPLATES
from .trait_engine import TraitEngine


class CharacterForge:
    """
    Factory class for creating and managing personality profiles.

    Provides methods for creating profiles from scratch, templates, or
    archetypes, as well as loading, saving, and listing profiles.
    """

    def __init__(self, profiles_dir: str | Path | None = None):
        """
        Initialize the CharacterForge.

        Args:
            profiles_dir: Directory for storing profiles. Defaults to
                         ./profiles relative to this file.
        """
        if profiles_dir is None:
            # Default to sibling profiles directory
            module_dir = Path(__file__).parent.parent.parent.parent
            profiles_dir = module_dir / "profiles"

        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        self.trait_engine = TraitEngine()

    def create_blank(self, name: str) -> PersonalityProfile:
        """
        Create a blank personality profile with default values.

        Args:
            name: Name for the new personality

        Returns:
            New PersonalityProfile with neutral defaults
        """
        return PersonalityProfile(
            name=name,
            version="1.0.0",
            tagline="",
            description="",
            backstory="",
            traits=PersonalityVector.create_default(),
            voice=VoiceProfile(),
            relationship_to_user="assistant",
            will_do=[],
            wont_do=[],
            expertise=[],
            interests=[],
            rules=[],
            example_exchanges=[]
        )

    def create_from_template(self, template_name: str) -> PersonalityProfile:
        """
        Create a personality profile from a registered template.

        Args:
            template_name: Name of the template (e.g., 'luna', 'assistant')

        Returns:
            New PersonalityProfile based on the template

        Raises:
            ValueError: If template_name is not found
        """
        if template_name not in TEMPLATES:
            available = ", ".join(TEMPLATES.keys())
            raise ValueError(
                f"Unknown template: {template_name}. Available: {available}"
            )

        template_func = TEMPLATES[template_name]
        return template_func()

    def create_from_archetype(self, name: str, archetype: str) -> PersonalityProfile:
        """
        Create a personality profile based on a Jungian archetype.

        Archetypes provide preset trait configurations representing
        common personality patterns.

        Args:
            name: Name for the new personality
            archetype: Archetype name (sage, jester, caregiver, rebel, hero)

        Returns:
            New PersonalityProfile with archetype-based traits

        Raises:
            ValueError: If archetype is not found
        """
        if archetype not in ARCHETYPES:
            available = ", ".join(ARCHETYPES.keys())
            raise ValueError(
                f"Unknown archetype: {archetype}. Available: {available}"
            )

        archetype_config = ARCHETYPES[archetype]

        return PersonalityProfile(
            name=name,
            version="1.0.0",
            tagline=archetype_config.get('tagline', f"A {archetype} personality"),
            description=archetype_config.get('description', ''),
            backstory="",
            traits=PersonalityVector(**archetype_config['traits']),
            voice=VoiceProfile(**archetype_config.get('voice', {})),
            relationship_to_user=archetype_config.get('relationship', 'guide'),
            will_do=archetype_config.get('will_do', []),
            wont_do=archetype_config.get('wont_do', []),
            expertise=archetype_config.get('expertise', []),
            interests=archetype_config.get('interests', []),
            rules=archetype_config.get('rules', []),
            example_exchanges=[]
        )

    def create_custom(
        self,
        name: str,
        traits: dict[str, float] | PersonalityVector,
        voice: dict[str, Any] | VoiceProfile,
        **kwargs: Any
    ) -> PersonalityProfile:
        """
        Create a fully customized personality profile.

        Args:
            name: Name for the personality
            traits: Trait values as dict or PersonalityVector
            voice: Voice profile as dict or VoiceProfile
            **kwargs: Additional profile fields (tagline, description, etc.)

        Returns:
            New PersonalityProfile with specified configuration
        """
        # Convert traits if needed
        if isinstance(traits, dict):
            traits = PersonalityVector(**traits)

        # Convert voice if needed
        if isinstance(voice, dict):
            voice = VoiceProfile(**voice)

        return PersonalityProfile(
            name=name,
            traits=traits,
            voice=voice,
            version=kwargs.get('version', '1.0.0'),
            tagline=kwargs.get('tagline', ''),
            description=kwargs.get('description', ''),
            backstory=kwargs.get('backstory', ''),
            relationship_to_user=kwargs.get('relationship_to_user', 'assistant'),
            will_do=kwargs.get('will_do', []),
            wont_do=kwargs.get('wont_do', []),
            expertise=kwargs.get('expertise', []),
            interests=kwargs.get('interests', []),
            rules=kwargs.get('rules', []),
            example_exchanges=kwargs.get('example_exchanges', [])
        )

    def modulate(
        self,
        profile: PersonalityProfile,
        trait_name: str,
        delta: float
    ) -> float:
        """
        Adjust a trait in a profile by delta.

        Args:
            profile: Profile to modify
            trait_name: Name of trait to adjust
            delta: Amount to adjust (positive or negative)

        Returns:
            New trait value after modulation
        """
        new_value = profile.modulate_trait(trait_name, delta)
        profile.update_timestamp()
        return new_value

    def compare(
        self,
        profile_a: PersonalityProfile,
        profile_b: PersonalityProfile
    ) -> dict[str, Any]:
        """
        Compare two personality profiles.

        Args:
            profile_a: First profile
            profile_b: Second profile

        Returns:
            Dictionary containing comparison metrics
        """
        distance = self.trait_engine.compute_distance(profile_a, profile_b)
        similarity = self.trait_engine.compute_similarity(profile_a, profile_b)

        traits_a = profile_a.traits.get_dict()
        traits_b = profile_b.traits.get_dict()

        # Compute per-trait differences
        trait_diffs = {}
        for key in traits_a:
            diff = traits_b[key] - traits_a[key]
            trait_diffs[key] = {
                'a': traits_a[key],
                'b': traits_b[key],
                'diff': diff,
                'abs_diff': abs(diff)
            }

        # Find most and least similar traits
        sorted_by_diff = sorted(trait_diffs.items(), key=lambda x: x[1]['abs_diff'])
        most_similar = sorted_by_diff[:3]
        most_different = sorted_by_diff[-3:][::-1]

        return {
            'profile_a': profile_a.name,
            'profile_b': profile_b.name,
            'distance': distance,
            'similarity': similarity,
            'similarity_percent': f"{similarity * 100:.1f}%",
            'trait_differences': trait_diffs,
            'most_similar_traits': [t[0] for t in most_similar],
            'most_different_traits': [t[0] for t in most_different]
        }

    def save(
        self,
        profile: PersonalityProfile,
        path: str | Path | None = None,
        format: str = 'toml'
    ) -> Path:
        """
        Save a personality profile to disk.

        Args:
            profile: Profile to save
            path: Optional path. Defaults to profiles_dir/{profile.name}.toml
            format: Output format ('toml' or 'json')

        Returns:
            Path where profile was saved
        """
        if path is None:
            # Sanitize name for filename
            safe_name = "".join(
                c if c.isalnum() or c in '-_' else '_'
                for c in profile.name.lower()
            )
            extension = 'toml' if format == 'toml' else 'json'
            path = self.profiles_dir / f"{safe_name}.{extension}"
        else:
            path = Path(path)

        # Convert profile to dict
        profile_dict = self._profile_to_dict(profile)

        # Save based on format
        if format == 'toml' and tomli_w is not None:
            with open(path, 'wb') as f:
                tomli_w.dump(profile_dict, f)
        else:
            # JSON fallback
            if not str(path).endswith('.json'):
                path = path.with_suffix('.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(profile_dict, f, indent=2, default=str)

        return path

    def load(self, path: str | Path) -> PersonalityProfile:
        """
        Load a personality profile from disk.

        Args:
            path: Path to profile file (TOML or JSON)

        Returns:
            Loaded PersonalityProfile
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Profile not found: {path}")

        # Load based on extension
        if path.suffix == '.toml':
            with open(path, 'rb') as f:
                data = tomli.load(f)
        else:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

        return self._dict_to_profile(data)

    def list_profiles(self) -> list[dict[str, Any]]:
        """
        List all saved profiles in the profiles directory.

        Returns:
            List of profile summaries with name, path, and metadata
        """
        profiles = []

        # Look for both TOML and JSON files
        for pattern in ['*.toml', '*.json']:
            for path in self.profiles_dir.glob(pattern):
                try:
                    profile = self.load(path)
                    profiles.append({
                        'name': profile.name,
                        'id': profile.id,
                        'path': str(path),
                        'version': profile.version,
                        'tagline': profile.tagline,
                        'created_at': profile.created_at.isoformat(),
                        'updated_at': profile.updated_at.isoformat()
                    })
                except Exception as e:
                    # Skip invalid files
                    profiles.append({
                        'name': path.stem,
                        'path': str(path),
                        'error': str(e)
                    })

        return sorted(profiles, key=lambda x: x.get('name', ''))

    def delete_profile(self, path: str | Path) -> bool:
        """
        Delete a profile file.

        Args:
            path: Path to profile to delete

        Returns:
            True if deleted, False if not found
        """
        path = Path(path)
        if path.exists():
            path.unlink()
            return True
        return False

    def _profile_to_dict(self, profile: PersonalityProfile) -> dict[str, Any]:
        """Convert a PersonalityProfile to a serializable dictionary."""
        return {
            'identity': {
                'id': profile.id,
                'name': profile.name,
                'version': profile.version,
                'tagline': profile.tagline,
                'description': profile.description,
                'backstory': profile.backstory
            },
            'traits': profile.traits.get_dict(),
            'voice': {
                'favorite_words': profile.voice.favorite_words,
                'avoided_words': profile.voice.avoided_words,
                'catchphrases': profile.voice.catchphrases,
                'uses_contractions': profile.voice.uses_contractions,
                'uses_filler_words': profile.voice.uses_filler_words,
                'sentence_complexity': profile.voice.sentence_complexity,
                'emoji_usage': profile.voice.emoji_usage,
                'exclamation_frequency': profile.voice.exclamation_frequency,
                'question_frequency': profile.voice.question_frequency
            },
            'behavior': {
                'relationship_to_user': profile.relationship_to_user,
                'will_do': profile.will_do,
                'wont_do': profile.wont_do,
                'rules': profile.rules
            },
            'knowledge': {
                'expertise': profile.expertise,
                'interests': profile.interests
            },
            'examples': [
                {
                    'user': ex.user,
                    'assistant': ex.assistant,
                    'context': ex.context
                }
                for ex in profile.example_exchanges
            ],
            'metadata': {
                'created_at': profile.created_at.isoformat(),
                'updated_at': profile.updated_at.isoformat()
            }
        }

    def _dict_to_profile(self, data: dict[str, Any]) -> PersonalityProfile:
        """Convert a dictionary to a PersonalityProfile."""
        identity = data.get('identity', data)

        # Handle flat vs nested format
        if 'traits' in data and isinstance(data['traits'], dict):
            traits_data = data['traits']
        else:
            traits_data = {}

        if 'voice' in data and isinstance(data['voice'], dict):
            voice_data = data['voice']
        else:
            voice_data = {}

        behavior = data.get('behavior', {})
        knowledge = data.get('knowledge', {})
        metadata = data.get('metadata', {})

        # Parse example exchanges
        examples = []
        for ex_data in data.get('examples', []):
            examples.append(ExampleExchange(
                user=ex_data.get('user', ''),
                assistant=ex_data.get('assistant', ''),
                context=ex_data.get('context', '')
            ))

        # Parse timestamps
        created_at = metadata.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.utcnow()

        updated_at = metadata.get('updated_at')
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        else:
            updated_at = datetime.utcnow()

        return PersonalityProfile(
            id=identity.get('id', ''),
            name=identity.get('name', 'Unknown'),
            version=identity.get('version', '1.0.0'),
            tagline=identity.get('tagline', ''),
            description=identity.get('description', ''),
            backstory=identity.get('backstory', ''),
            traits=PersonalityVector(**traits_data) if traits_data else PersonalityVector.create_default(),
            voice=VoiceProfile(**voice_data) if voice_data else VoiceProfile(),
            relationship_to_user=behavior.get('relationship_to_user', 'assistant'),
            will_do=behavior.get('will_do', []),
            wont_do=behavior.get('wont_do', []),
            expertise=knowledge.get('expertise', []),
            interests=knowledge.get('interests', []),
            rules=behavior.get('rules', []),
            example_exchanges=examples,
            created_at=created_at,
            updated_at=updated_at
        )
