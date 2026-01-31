"""
Trait computation engine for Persona Forge.

This module provides operations for comparing, interpolating, and
manipulating personality profiles and their trait vectors.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .models import PersonalityProfile, PersonalityVector, VoiceProfile

if TYPE_CHECKING:
    pass


class TraitEngine:
    """
    Engine for computing and manipulating personality traits.

    Provides mathematical operations on personality vectors including
    distance calculations, similarity metrics, interpolation, and
    random variation generation.
    """

    # Maximum possible Euclidean distance in 9D unit hypercube
    # sqrt(9 * 1^2) = 3.0
    MAX_DISTANCE: float = 3.0

    @staticmethod
    def compute_distance(profile_a: PersonalityProfile, profile_b: PersonalityProfile) -> float:
        """
        Compute Euclidean distance between two personality profiles.

        The distance is computed in the 9-dimensional personality vector space.
        A distance of 0 means identical personalities, while the maximum
        theoretical distance is 3.0 (sqrt(9)).

        Args:
            profile_a: First personality profile
            profile_b: Second personality profile

        Returns:
            Euclidean distance between the two profiles' trait vectors
        """
        return profile_a.traits.distance(profile_b.traits)

    @staticmethod
    def compute_similarity(profile_a: PersonalityProfile, profile_b: PersonalityProfile) -> float:
        """
        Compute similarity score between two personality profiles.

        Returns a value from 0.0 (maximally different) to 1.0 (identical).
        This is computed as 1 - (distance / max_distance).

        Args:
            profile_a: First personality profile
            profile_b: Second personality profile

        Returns:
            Similarity score between 0.0 and 1.0
        """
        distance = TraitEngine.compute_distance(profile_a, profile_b)
        normalized_distance = distance / TraitEngine.MAX_DISTANCE
        return 1.0 - normalized_distance

    @staticmethod
    def interpolate(
        profile_a: PersonalityProfile,
        profile_b: PersonalityProfile,
        t: float
    ) -> PersonalityProfile:
        """
        Create a new profile by interpolating between two profiles.

        Linear interpolation is applied to all numeric trait values.
        At t=0, the result matches profile_a; at t=1, it matches profile_b.

        Args:
            profile_a: Starting profile (t=0)
            profile_b: Ending profile (t=1)
            t: Interpolation factor (0.0 to 1.0)

        Returns:
            New PersonalityProfile with interpolated values
        """
        if not 0.0 <= t <= 1.0:
            raise ValueError(f"Interpolation factor t must be between 0 and 1, got {t}")

        # Interpolate trait vectors
        vec_a = profile_a.traits.get_dict()
        vec_b = profile_b.traits.get_dict()

        interpolated_traits = {}
        for key in vec_a:
            interpolated_traits[key] = vec_a[key] + t * (vec_b[key] - vec_a[key])

        # Interpolate voice profile numeric values
        voice_a = profile_a.voice
        voice_b = profile_b.voice

        interpolated_voice = VoiceProfile(
            # For lists, merge based on t threshold
            favorite_words=(
                voice_a.favorite_words if t < 0.5 else voice_b.favorite_words
            ),
            avoided_words=(
                voice_a.avoided_words if t < 0.5 else voice_b.avoided_words
            ),
            catchphrases=(
                voice_a.catchphrases if t < 0.5 else voice_b.catchphrases
            ),
            # For booleans, choose based on t threshold
            uses_contractions=(
                voice_a.uses_contractions if t < 0.5 else voice_b.uses_contractions
            ),
            uses_filler_words=(
                voice_a.uses_filler_words if t < 0.5 else voice_b.uses_filler_words
            ),
            # Interpolate numeric values
            sentence_complexity=(
                voice_a.sentence_complexity + t * (voice_b.sentence_complexity - voice_a.sentence_complexity)
            ),
            emoji_usage=(
                voice_a.emoji_usage + t * (voice_b.emoji_usage - voice_a.emoji_usage)
            ),
            exclamation_frequency=(
                voice_a.exclamation_frequency + t * (voice_b.exclamation_frequency - voice_a.exclamation_frequency)
            ),
            question_frequency=(
                voice_a.question_frequency + t * (voice_b.question_frequency - voice_a.question_frequency)
            )
        )

        # Create new profile name
        if t < 0.5:
            new_name = f"{profile_a.name} → {profile_b.name} ({t:.0%})"
        else:
            new_name = f"{profile_a.name} → {profile_b.name} ({t:.0%})"

        # Create interpolated profile
        return PersonalityProfile(
            name=new_name,
            version="1.0.0",
            tagline=profile_a.tagline if t < 0.5 else profile_b.tagline,
            description=profile_a.description if t < 0.5 else profile_b.description,
            backstory=profile_a.backstory if t < 0.5 else profile_b.backstory,
            traits=PersonalityVector(**interpolated_traits),
            voice=interpolated_voice,
            relationship_to_user=(
                profile_a.relationship_to_user if t < 0.5 else profile_b.relationship_to_user
            ),
            will_do=profile_a.will_do if t < 0.5 else profile_b.will_do,
            wont_do=profile_a.wont_do if t < 0.5 else profile_b.wont_do,
            expertise=profile_a.expertise if t < 0.5 else profile_b.expertise,
            interests=profile_a.interests if t < 0.5 else profile_b.interests,
            rules=profile_a.rules if t < 0.5 else profile_b.rules,
            example_exchanges=(
                profile_a.example_exchanges if t < 0.5 else profile_b.example_exchanges
            )
        )

    @staticmethod
    def random_variation(
        profile: PersonalityProfile,
        max_delta: float = 0.1,
        seed: int | None = None
    ) -> PersonalityProfile:
        """
        Create a variation of a profile with random trait adjustments.

        Each trait dimension is randomly adjusted by up to max_delta
        (positive or negative), creating a personality that is similar
        but slightly different from the original.

        Args:
            profile: Base profile to create variation from
            max_delta: Maximum adjustment per trait (default 0.1)
            seed: Optional random seed for reproducibility

        Returns:
            New PersonalityProfile with randomly varied traits
        """
        if seed is not None:
            random.seed(seed)

        # Clone the profile
        varied = profile.clone(new_name=f"{profile.name} (variation)")

        # Apply random variations to each trait
        traits_dict = varied.traits.get_dict()
        for trait_name in traits_dict:
            delta = random.uniform(-max_delta, max_delta)
            varied.traits.modulate(trait_name, delta)

        # Optionally vary voice profile numeric values
        voice = varied.voice
        object.__setattr__(
            voice,
            'sentence_complexity',
            max(0.0, min(1.0, voice.sentence_complexity + random.uniform(-max_delta, max_delta)))
        )
        object.__setattr__(
            voice,
            'emoji_usage',
            max(0.0, min(1.0, voice.emoji_usage + random.uniform(-max_delta, max_delta)))
        )
        object.__setattr__(
            voice,
            'exclamation_frequency',
            max(0.0, min(1.0, voice.exclamation_frequency + random.uniform(-max_delta, max_delta)))
        )
        object.__setattr__(
            voice,
            'question_frequency',
            max(0.0, min(1.0, voice.question_frequency + random.uniform(-max_delta, max_delta)))
        )

        return varied

    @staticmethod
    def blend_profiles(
        profiles: list[PersonalityProfile],
        weights: list[float] | None = None
    ) -> PersonalityProfile:
        """
        Create a new profile by blending multiple profiles with weights.

        Args:
            profiles: List of profiles to blend
            weights: Optional weights (must sum to 1.0, defaults to equal weights)

        Returns:
            New PersonalityProfile representing the weighted blend
        """
        if not profiles:
            raise ValueError("At least one profile required for blending")

        if len(profiles) == 1:
            return profiles[0].clone()

        # Default to equal weights
        if weights is None:
            weights = [1.0 / len(profiles)] * len(profiles)

        if len(weights) != len(profiles):
            raise ValueError("Number of weights must match number of profiles")

        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # Blend trait vectors
        blended_traits = {}
        trait_names = profiles[0].traits.get_dict().keys()

        for trait_name in trait_names:
            weighted_sum = sum(
                w * p.traits.get_dict()[trait_name]
                for w, p in zip(weights, profiles)
            )
            blended_traits[trait_name] = weighted_sum

        # Blend voice numeric values
        blended_voice = VoiceProfile(
            # Use first profile's lists (could be enhanced to merge)
            favorite_words=profiles[0].voice.favorite_words.copy(),
            avoided_words=profiles[0].voice.avoided_words.copy(),
            catchphrases=profiles[0].voice.catchphrases.copy(),
            uses_contractions=profiles[0].voice.uses_contractions,
            uses_filler_words=profiles[0].voice.uses_filler_words,
            sentence_complexity=sum(
                w * p.voice.sentence_complexity for w, p in zip(weights, profiles)
            ),
            emoji_usage=sum(
                w * p.voice.emoji_usage for w, p in zip(weights, profiles)
            ),
            exclamation_frequency=sum(
                w * p.voice.exclamation_frequency for w, p in zip(weights, profiles)
            ),
            question_frequency=sum(
                w * p.voice.question_frequency for w, p in zip(weights, profiles)
            )
        )

        # Create blended profile
        profile_names = [p.name for p in profiles]
        return PersonalityProfile(
            name=f"Blend({', '.join(profile_names)})",
            version="1.0.0",
            tagline=f"Blended from {len(profiles)} profiles",
            description=profiles[0].description,
            backstory=profiles[0].backstory,
            traits=PersonalityVector(**blended_traits),
            voice=blended_voice,
            relationship_to_user=profiles[0].relationship_to_user,
            will_do=profiles[0].will_do.copy(),
            wont_do=profiles[0].wont_do.copy(),
            expertise=profiles[0].expertise.copy(),
            interests=profiles[0].interests.copy(),
            rules=profiles[0].rules.copy(),
            example_exchanges=profiles[0].example_exchanges.copy()
        )

    @staticmethod
    def trait_report(profile: PersonalityProfile) -> dict:
        """
        Generate a detailed report of a profile's traits.

        Args:
            profile: Profile to analyze

        Returns:
            Dictionary with trait analysis
        """
        traits = profile.traits.get_dict()

        # Categorize traits
        high_traits = {k: v for k, v in traits.items() if v > 0.7}
        low_traits = {k: v for k, v in traits.items() if v < 0.3}
        moderate_traits = {k: v for k, v in traits.items() if 0.3 <= v <= 0.7}

        # Compute statistics
        values = list(traits.values())
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = variance ** 0.5

        return {
            'profile_name': profile.name,
            'all_traits': traits,
            'high_traits': high_traits,
            'low_traits': low_traits,
            'moderate_traits': moderate_traits,
            'statistics': {
                'mean': mean,
                'std_dev': std_dev,
                'min': min(values),
                'max': max(values),
                'range': max(values) - min(values)
            },
            'dominant_trait': max(traits.items(), key=lambda x: x[1]),
            'weakest_trait': min(traits.items(), key=lambda x: x[1])
        }
