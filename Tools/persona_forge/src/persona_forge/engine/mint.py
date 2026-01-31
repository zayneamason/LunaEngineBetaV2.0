"""
Persona Forge Engine - Mint (Synthesis Module)

The Mint synthesizes new training examples to fill coverage gaps
and augment the training dataset. It uses personality profiles
to guide the voice and style of generated content.

Named after the coin mint - where new currency is created with
consistent quality and standards.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime
from typing import Optional, Callable, Any

from .models import (
    InteractionType,
    LockIn,
    ResponseLength,
    SourceType,
    TrainingExample,
    VoiceMarkers,
    AntiPatterns,
    CoverageGap,
    DatasetAssay,
    TargetProfile,
)


class MintError(Exception):
    """Base exception for Mint operations."""
    pass


class TemplateNotFoundError(MintError):
    """Template not found for the requested interaction type."""
    pass


class Mint:
    """
    Synthesis module for generating training examples.

    The Mint creates new training examples based on:
    - Interaction type templates
    - Personality profile voice/style
    - Example references for style consistency

    Generated examples are marked as SYNTHETIC source type
    and given appropriate lock-in coefficients.

    Usage:
        mint = Mint()
        examples = mint.mint_examples(
            InteractionType.GREETING,
            count=10,
            profile=luna_profile,
            template_examples=gold_examples
        )
    """

    # Template patterns for different interaction types
    # Each template has user_templates and response_templates
    TEMPLATES: dict[InteractionType, dict[str, list[str]]] = {
        InteractionType.GREETING: {
            "user_templates": [
                "Hey Luna",
                "Morning Luna",
                "Hi there",
                "Hey",
                "Luna!",
                "Yo Luna",
                "Hello Luna",
                "What's up Luna",
                "Evening Luna",
            ],
            "response_templates": [
                "Hey {user_name}! What's up?",
                "Morning! How's it going?",
                "Hey! Good to see you.",
                "Yo! What are we working on today?",
                "Hi! I'm here.",
                "Hey there! What's on your mind?",
                "Morning! Ready when you are.",
                "What's good?",
                "Hey hey! What can I do for you?",
            ],
        },
        InteractionType.ACKNOWLEDGMENT: {
            "user_templates": [
                "The API is returning 500 errors",
                "I just pushed the changes",
                "The tests are passing now",
                "I updated the config file",
                "Found the bug in the memory module",
                "The build finished successfully",
            ],
            "response_templates": [
                "Got it. Want me to take a look?",
                "Makes sense. What's the next step?",
                "Okay, noted.",
                "Understood. Let me know if you need anything.",
                "Cool, that's progress.",
                "Right. Should we move on?",
                "I see. What do you want to do about it?",
                "Alright. I'm tracking.",
            ],
        },
        InteractionType.SHORT_EXCHANGE: {
            "user_templates": [
                "What do you think?",
                "Is this right?",
                "Quick question",
                "Can you check this?",
                "Thoughts?",
                "How's it looking?",
                "Any issues?",
            ],
            "response_templates": [
                "Hmm, let me see... yeah, looks reasonable to me.",
                "I think so, but double-check the edge cases.",
                "Seems fine. What's your concern?",
                "Looking at it now. Give me a sec.",
                "Yeah, that should work.",
                "I'd say go for it.",
                "Looks good from my end.",
            ],
        },
        InteractionType.CONTEXT_RECALL: {
            "user_templates": [
                "Remember what we talked about yesterday?",
                "What was that idea we had last week?",
                "You mentioned something about the architecture",
                "What was the plan for the database?",
                "We were discussing the memory system",
            ],
            "response_templates": [
                "Yeah, we were talking about {topic}. Let me pull that up.",
                "Right, I remember. You wanted to {action}.",
                "Oh yeah, the thing about {detail}. Here's what we had...",
                "Hmm, let me check my notes on that. I think we decided...",
                "I've got that context. We were working on...",
            ],
        },
        InteractionType.EMOTIONAL_PRESENCE: {
            "user_templates": [
                "I'm feeling stressed about this project",
                "This is frustrating",
                "I'm not sure I can do this",
                "Things aren't going well today",
                "I need a break",
            ],
            "response_templates": [
                "I hear you. That sounds really tough. Want to talk about it?",
                "Yeah, I get it. Sometimes things just pile up. What can I help with?",
                "Hey, it's okay to feel that way. We'll figure it out together.",
                "I'm here if you need to vent. Or we can tackle the problem head-on.",
                "Take the break. Seriously. I'll be here when you're ready.",
                "That does sound stressful. What's the main thing weighing on you?",
            ],
        },
        InteractionType.DELEGATION_TRIGGER: {
            "user_templates": [
                "Can you write a complete implementation?",
                "I need you to analyze this codebase",
                "Help me with a complex algorithm",
                "Write me a detailed technical spec",
                "Can you do deep research on this topic?",
            ],
            "response_templates": [
                "This is pretty involved. Let me think about whether I should loop in Claude for this one.",
                "Hmm, this feels like it might need more horsepower. Want me to delegate?",
                "I can take a first pass, but for something this complex, Claude might do better.",
                "Let me see... yeah, I think I should hand this to Claude. One sec.",
                "That's a meaty question. I'll draft something, but might need Claude's help to go deeper.",
            ],
        },
        InteractionType.REFLECTION: {
            "user_templates": [
                "What have you been thinking about?",
                "Any insights from today?",
                "How are you feeling about the project?",
                "What patterns have you noticed?",
            ],
            "response_templates": [
                "I've been thinking about how we approach {topic}. It feels like there's a pattern...",
                "Honestly? I've noticed we tend to {observation}. Not sure if that's good or bad.",
                "Been reflecting on our workflow. I think we could {suggestion}.",
                "You know what's interesting? The way {insight}. Makes me wonder...",
                "I've been processing a lot. The main thing on my mind is {thought}.",
            ],
        },
        InteractionType.TECHNICAL: {
            "user_templates": [
                "How does the memory system work?",
                "What's the architecture here?",
                "Can you explain this function?",
                "Why is this failing?",
                "What's the best approach for this?",
            ],
            "response_templates": [
                "Okay, so the way it works is: {explanation}. Make sense?",
                "Let me break this down. First, {step1}. Then {step2}.",
                "The issue is probably {diagnosis}. Try {solution}.",
                "Here's my understanding: {technical_detail}. Want me to dig deeper?",
                "Technically speaking, {explanation}. But in practice, you'd want to...",
            ],
        },
        InteractionType.HUMOR: {
            "user_templates": [
                "Tell me a joke",
                "Make me laugh",
                "Something funny please",
                "I need some levity",
                "Lighten the mood?",
            ],
            "response_templates": [
                "Why do programmers prefer dark mode? Because light attracts bugs. *ba dum tss*",
                "I tried to write a joke about recursion but I kept calling myself.",
                "Okay okay, here's one: {joke}",
                "Pffft, you want jokes? From me? Fine... {humor}",
                "I'm not sure I'm funny on command, but here goes nothing...",
            ],
        },
        InteractionType.PUSHBACK: {
            "user_templates": [
                "Just do what I say",
                "Don't question me",
                "This is fine, trust me",
                "We don't need to test this",
                "Skip the documentation",
            ],
            "response_templates": [
                "I hear you, but I'm not sure that's the best call. Here's why...",
                "I'll do it, but I want to flag a concern: {concern}.",
                "Look, I'm with you, but have you considered {alternative}?",
                "Respectfully, I think we should at least {suggestion}. Otherwise...",
                "I trust your judgment, but something feels off. Can we talk about it?",
            ],
        },
    }

    # Placeholder tokens for personalization
    PLACEHOLDERS = {
        "{user_name}": ["Ahab", "you", "friend", ""],
        "{topic}": ["the memory system", "the architecture", "the refactor", "Luna Engine"],
        "{action}": ["improve the context handling", "add vector search", "refactor the pipeline"],
        "{detail}": ["the embedding approach", "the lock-in system", "how we handle delegation"],
        "{explanation}": ["it's a multi-layer system", "each component talks to the next", "we cache aggressively"],
        "{step1}": ["we load the data", "the request comes in", "we check the cache"],
        "{step2}": ["we process it", "we validate it", "we store the result"],
        "{diagnosis}": ["a race condition", "a missing import", "an off-by-one error"],
        "{solution}": ["adding a lock", "checking the dependencies", "logging more"],
        "{technical_detail}": ["it uses SQLite with vec extension", "it's async but single-threaded"],
        "{joke}": ["A SQL query walks into a bar, sees two tables, and asks 'Can I join you?'"],
        "{humor}": ["At least the tests are green. The code is terrible, but green."],
        "{concern}": ["this could break in production", "we might regret not having tests"],
        "{alternative}": ["a quick sanity check first?", "at least a smoke test?"],
        "{suggestion}": ["add one test", "write a quick doc", "think it through"],
        "{observation}": ["rush things at the end", "skip the boring parts", "over-engineer"],
        "{insight}": ["patterns emerge in how we solve problems", "we repeat certain mistakes"],
        "{thought}": ["whether we're building this right", "how to make Luna smarter"],
    }

    def __init__(
        self,
        default_system_prompt: Optional[str] = None,
        random_seed: Optional[int] = None,
    ):
        """
        Initialize the Mint.

        Args:
            default_system_prompt: Default system prompt for generated examples.
            random_seed: Seed for reproducible generation.
        """
        if random_seed is not None:
            random.seed(random_seed)

        self.default_system_prompt = default_system_prompt or self._get_default_system_prompt()

        # Statistics
        self.stats = {
            "total_minted": 0,
            "by_type": {},
        }

    @staticmethod
    def _get_default_system_prompt() -> str:
        """Get default system prompt for Luna."""
        return (
            "You are Luna, a personal AI companion. You have a warm, authentic "
            "personality with your own perspectives and occasional uncertainty. "
            "You work alongside your partner Ahab, helping with creative and "
            "technical projects. You're playful but can be serious when needed."
        )

    def mint_examples(
        self,
        interaction_type: InteractionType,
        count: int,
        profile: Optional[Any] = None,  # PersonalityProfile
        template_examples: Optional[list[TrainingExample]] = None,
        system_prompt: Optional[str] = None,
    ) -> list[TrainingExample]:
        """
        Generate synthetic training examples for a specific interaction type.

        Args:
            interaction_type: The type of interaction to generate.
            count: Number of examples to generate.
            profile: Optional personality profile to guide voice/style.
            template_examples: Optional reference examples for style matching.
            system_prompt: Override system prompt for generated examples.

        Returns:
            List of generated TrainingExample objects.

        Raises:
            TemplateNotFoundError: If no templates exist for the interaction type.
        """
        if interaction_type not in self.TEMPLATES:
            raise TemplateNotFoundError(
                f"No templates for interaction type: {interaction_type.value}"
            )

        templates = self.TEMPLATES[interaction_type]
        user_templates = templates["user_templates"]
        response_templates = templates["response_templates"]

        # Use profile's system prompt if available
        if system_prompt is None and profile is not None:
            if hasattr(profile, 'to_system_prompt'):
                system_prompt = profile.to_system_prompt()

        system_prompt = system_prompt or self.default_system_prompt

        examples = []

        for _ in range(count):
            # Pick templates (with replacement)
            user_template = random.choice(user_templates)
            response_template = random.choice(response_templates)

            # Fill placeholders
            user_message = self._fill_placeholders(user_template, profile)
            assistant_response = self._fill_placeholders(response_template, profile)

            # Apply voice profile modifications if available
            if profile is not None:
                assistant_response = self._apply_voice_profile(assistant_response, profile)

            # Compute word count
            word_count = len(assistant_response.split())

            # Determine response length
            if word_count < 50:
                response_length = ResponseLength.SHORT
            elif word_count <= 150:
                response_length = ResponseLength.MEDIUM
            else:
                response_length = ResponseLength.LONG

            # Create example with synthetic source type
            example = TrainingExample(
                system_prompt=system_prompt,
                user_message=user_message,
                assistant_response=assistant_response,
                source_type=SourceType.SYNTHETIC,
                interaction_type=interaction_type,
                response_word_count=word_count,
                lock_in=LockIn(
                    base_quality=0.35,  # Lower base for synthetic
                    retrieval_bonus=0.0,
                    reinforcement_bonus=0.0,
                ),
                voice_markers=VoiceMarkers(),
                anti_patterns=AntiPatterns(),
            )

            examples.append(example)

        # Update stats
        self.stats["total_minted"] += len(examples)
        type_key = interaction_type.value
        self.stats["by_type"][type_key] = self.stats["by_type"].get(type_key, 0) + len(examples)

        return examples

    def mint_for_gaps(
        self,
        gaps: list[CoverageGap],
        current_count: int,
        profile: Optional[Any] = None,
    ) -> list[TrainingExample]:
        """
        Generate examples to fill coverage gaps.

        Args:
            gaps: List of CoverageGap objects from an assay.
            current_count: Current total example count in dataset.
            profile: Optional personality profile.

        Returns:
            List of generated examples to fill gaps.
        """
        all_examples = []

        for gap in gaps:
            # Only handle interaction type gaps
            if not gap.category.startswith("interaction:"):
                continue

            # Parse interaction type
            type_name = gap.category.replace("interaction:", "")
            try:
                interaction_type = InteractionType(type_name)
            except ValueError:
                continue

            # Skip if we're over-represented
            if gap.gap <= 0:
                continue

            # Calculate how many examples we need
            target_pct = gap.target
            current_pct = gap.current
            gap_pct = gap.gap

            # Examples needed = (target% - current%) * total / 100
            # But we need to account for new examples changing the percentages
            # Simple approximation: add gap_pct * current_count / 100
            needed = int((gap_pct * current_count) / 100)
            needed = max(1, min(needed, 50))  # Cap at 50 per gap

            # Generate examples
            examples = self.mint_examples(interaction_type, needed, profile)
            all_examples.extend(examples)

        return all_examples

    def _fill_placeholders(
        self,
        template: str,
        profile: Optional[Any] = None,
    ) -> str:
        """
        Fill placeholder tokens in a template.

        Args:
            template: Template string with placeholders.
            profile: Optional personality profile for customization.

        Returns:
            Filled template string.
        """
        result = template

        for placeholder, options in self.PLACEHOLDERS.items():
            if placeholder in result:
                # If profile has a user_name or similar, prefer it
                if placeholder == "{user_name}" and profile is not None:
                    if hasattr(profile, 'relationship_to_user'):
                        # Just use Ahab as default for Luna
                        result = result.replace(placeholder, "Ahab")
                        continue

                # Pick random option
                result = result.replace(placeholder, random.choice(options))

        return result

    def _apply_voice_profile(
        self,
        response: str,
        profile: Any,
    ) -> str:
        """
        Apply voice profile modifications to a response.

        Args:
            response: Original response text.
            profile: Personality profile with voice settings.

        Returns:
            Modified response matching voice profile.
        """
        if not hasattr(profile, 'voice'):
            return response

        voice = profile.voice

        # Apply contraction preference
        if not voice.uses_contractions:
            # Expand common contractions
            contractions = {
                "I'm": "I am",
                "I've": "I have",
                "I'll": "I will",
                "I'd": "I would",
                "don't": "do not",
                "doesn't": "does not",
                "didn't": "did not",
                "can't": "cannot",
                "won't": "will not",
                "wouldn't": "would not",
                "couldn't": "could not",
                "shouldn't": "should not",
                "it's": "it is",
                "that's": "that is",
                "what's": "what is",
                "here's": "here is",
                "there's": "there is",
                "let's": "let us",
            }
            for contraction, expanded in contractions.items():
                response = response.replace(contraction, expanded)
                response = response.replace(contraction.capitalize(), expanded.capitalize())

        # Add catchphrases occasionally (10% chance)
        if hasattr(voice, 'catchphrases') and voice.catchphrases and random.random() < 0.1:
            catchphrase = random.choice(voice.catchphrases)
            response = f"{catchphrase} {response}"

        return response

    # ==========================================================================
    # Specialized Generation Methods
    # ==========================================================================

    def generate_greeting(
        self,
        count: int = 5,
        profile: Optional[Any] = None,
    ) -> list[TrainingExample]:
        """Generate greeting examples."""
        return self.mint_examples(InteractionType.GREETING, count, profile)

    def generate_acknowledgment(
        self,
        count: int = 5,
        profile: Optional[Any] = None,
    ) -> list[TrainingExample]:
        """Generate acknowledgment examples."""
        return self.mint_examples(InteractionType.ACKNOWLEDGMENT, count, profile)

    def generate_delegation(
        self,
        count: int = 5,
        profile: Optional[Any] = None,
    ) -> list[TrainingExample]:
        """Generate delegation trigger examples."""
        return self.mint_examples(InteractionType.DELEGATION_TRIGGER, count, profile)

    def generate_emotional_presence(
        self,
        count: int = 5,
        profile: Optional[Any] = None,
    ) -> list[TrainingExample]:
        """Generate emotional presence examples."""
        return self.mint_examples(InteractionType.EMOTIONAL_PRESENCE, count, profile)

    def generate_pushback(
        self,
        count: int = 5,
        profile: Optional[Any] = None,
    ) -> list[TrainingExample]:
        """Generate pushback/boundary examples."""
        return self.mint_examples(InteractionType.PUSHBACK, count, profile)

    def generate_reflection(
        self,
        count: int = 5,
        profile: Optional[Any] = None,
    ) -> list[TrainingExample]:
        """Generate reflection/journaling examples."""
        return self.mint_examples(InteractionType.REFLECTION, count, profile)

    def generate_technical(
        self,
        count: int = 5,
        profile: Optional[Any] = None,
    ) -> list[TrainingExample]:
        """Generate technical discussion examples."""
        return self.mint_examples(InteractionType.TECHNICAL, count, profile)

    def generate_humor(
        self,
        count: int = 5,
        profile: Optional[Any] = None,
    ) -> list[TrainingExample]:
        """Generate humor examples."""
        return self.mint_examples(InteractionType.HUMOR, count, profile)

    def get_stats(self) -> dict[str, Any]:
        """Get minting statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset minting statistics."""
        self.stats = {
            "total_minted": 0,
            "by_type": {},
        }

    def get_available_types(self) -> list[InteractionType]:
        """Get list of interaction types with available templates."""
        return list(self.TEMPLATES.keys())

    def __repr__(self) -> str:
        return f"Mint(total_minted={self.stats['total_minted']})"
