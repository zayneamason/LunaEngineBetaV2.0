"""
Persona Forge Engine - Locksmith (Lock-In Weighting Module)

The Locksmith computes lock-in coefficients for training examples,
determining how strongly each example should influence fine-tuning.

This mirrors the Memory Matrix lock-in system from Luna Engine,
ensuring consistency between runtime memory weighting and training data.
"""

from __future__ import annotations

import logging
from typing import Optional

from .models import (
    AntiPatternPatterns,
    AntiPatterns,
    LockIn,
    QualityTier,
    SourceType,
    TrainingExample,
    VoiceMarkerPatterns,
    VoiceMarkers,
)

logger = logging.getLogger(__name__)


class Locksmith:
    """
    Lock-in coefficient calculator for training examples.

    The Locksmith evaluates training examples and computes their
    lock-in coefficients based on:
    - Source quality (journal > session > synthetic)
    - Voice marker presence (authenticity)
    - Anti-pattern absence (purity)

    Formula: coefficient = clamp(base + retrieval + reinforcement, 0.15, 0.95)

    Usage:
        locksmith = Locksmith()
        for example in examples:
            locksmith.compute_lock_in(example)  # Mutates example.lock_in
    """

    # Base quality scores by source type
    SOURCE_BASE_QUALITY: dict[SourceType, float] = {
        SourceType.JOURNAL: 0.70,     # Luna's own voice
        SourceType.SESSION: 0.55,     # Real conversations
        SourceType.MATRIX: 0.50,      # Extracted memories
        SourceType.INSIGHT: 0.45,     # Generated insights
        SourceType.MANUAL: 0.60,      # Hand-crafted
        SourceType.SYNTHETIC: 0.35,   # LLM-generated
    }

    # Voice marker bonuses
    VOICE_MARKER_BONUS: float = 0.05      # Per marker category present
    MAX_VOICE_BONUS: float = 0.20         # Cap on voice bonuses
    AUTHENTIC_VOICE_BONUS: float = 0.10   # Bonus for has_authentic_voice

    # Anti-pattern penalties
    ANTI_PATTERN_PENALTY: float = 0.15    # Per anti-pattern category present
    MAX_ANTI_PENALTY: float = 0.40        # Cap on penalties

    # Coefficient bounds (matching Memory Matrix)
    MIN_COEFFICIENT: float = 0.15
    MAX_COEFFICIENT: float = 0.95

    def __init__(
        self,
        source_weights: Optional[dict[SourceType, float]] = None,
        voice_bonus: float = 0.05,
        anti_penalty: float = 0.15,
    ):
        """
        Initialize the Locksmith.

        Args:
            source_weights: Custom base quality weights by source type.
            voice_bonus: Bonus per voice marker category (default 0.05).
            anti_penalty: Penalty per anti-pattern category (default 0.15).
        """
        self.source_weights = source_weights or self.SOURCE_BASE_QUALITY.copy()
        self.voice_bonus = voice_bonus
        self.anti_penalty = anti_penalty

        # Statistics
        self.stats = {
            "processed": 0,
            "gold": 0,
            "silver": 0,
            "bronze": 0,
            "avg_coefficient": 0.0,
        }

    def compute_lock_in(self, example: TrainingExample) -> float:
        """
        Compute and set the lock-in coefficient for an example.

        This method mutates the example's lock_in and also ensures
        voice_markers and anti_patterns are computed.

        Args:
            example: The training example to process.

        Returns:
            The computed lock-in coefficient.
        """
        # Ensure voice markers are detected
        if example.voice_markers.total == 0:
            example.voice_markers = self.detect_voice_markers(example.assistant_response)

        # Ensure anti-patterns are detected
        if example.anti_patterns.total == 0:
            example.anti_patterns = self.detect_anti_patterns(example.assistant_response)

        # Compute base quality from source type
        base_quality = self.source_weights.get(
            example.metadata.source_type,
            0.50  # default
        )

        # Compute voice marker bonus
        voice_bonus = self._compute_voice_bonus(example.voice_markers)

        # Compute anti-pattern penalty (applied as negative retrieval bonus)
        anti_penalty = self._compute_anti_penalty(example.anti_patterns)

        # Compute reinforcement bonus (from existing lock_in data if present)
        reinforcement_bonus = example.lock_in.reinforcement_bonus

        # The retrieval_bonus field stores our computed quality adjustment
        # (voice bonus minus anti-pattern penalty)
        quality_adjustment = voice_bonus - anti_penalty

        # Create new lock-in with computed values
        example.lock_in = LockIn(
            base_quality=base_quality,
            retrieval_bonus=max(0.0, quality_adjustment),  # Must be non-negative
            reinforcement_bonus=reinforcement_bonus,
        )

        # If quality adjustment is negative, reduce base quality instead
        if quality_adjustment < 0:
            adjusted_base = base_quality + quality_adjustment
            example.lock_in = LockIn(
                base_quality=max(0.0, adjusted_base),
                retrieval_bonus=0.0,
                reinforcement_bonus=reinforcement_bonus,
            )

        # Update statistics
        self._update_stats(example.lock_in)

        return example.lock_in.coefficient

    def detect_voice_markers(self, text: str) -> VoiceMarkers:
        """
        Detect Luna's voice markers in text.

        Args:
            text: The text to analyze.

        Returns:
            VoiceMarkers with detected counts.
        """
        return VoiceMarkers(
            first_person=len(VoiceMarkerPatterns.FIRST_PERSON.findall(text)),
            warmth_words=len(VoiceMarkerPatterns.WARMTH_WORDS.findall(text)),
            uncertainty=len(VoiceMarkerPatterns.UNCERTAINTY.findall(text)),
            relationship=len(VoiceMarkerPatterns.RELATIONSHIP.findall(text)),
        )

    def detect_anti_patterns(self, text: str) -> AntiPatterns:
        """
        Detect anti-patterns in text.

        Args:
            text: The text to analyze.

        Returns:
            AntiPatterns with detected counts.
        """
        return AntiPatterns(
            generic_ai=len(AntiPatternPatterns.GENERIC_AI.findall(text)),
            corporate=len(AntiPatternPatterns.CORPORATE.findall(text)),
            hedging=len(AntiPatternPatterns.HEDGING.findall(text)),
        )

    def _compute_voice_bonus(self, markers: VoiceMarkers) -> float:
        """
        Compute voice marker bonus.

        Each marker category present adds to the bonus.

        Args:
            markers: Detected voice markers.

        Returns:
            Voice bonus value (0.0 to MAX_VOICE_BONUS).
        """
        bonus = 0.0

        # Each category with at least one match gets the bonus
        if markers.first_person > 0:
            bonus += self.voice_bonus
        if markers.warmth_words > 0:
            bonus += self.voice_bonus
        if markers.uncertainty > 0:
            bonus += self.voice_bonus
        if markers.relationship > 0:
            bonus += self.voice_bonus

        # Extra bonus for authentic voice
        if markers.has_authentic_voice:
            bonus += self.AUTHENTIC_VOICE_BONUS

        return min(bonus, self.MAX_VOICE_BONUS)

    def _compute_anti_penalty(self, patterns: AntiPatterns) -> float:
        """
        Compute anti-pattern penalty.

        Each anti-pattern category present adds to the penalty.

        Args:
            patterns: Detected anti-patterns.

        Returns:
            Penalty value (0.0 to MAX_ANTI_PENALTY).
        """
        penalty = 0.0

        # Each category with at least one match gets penalized
        if patterns.generic_ai > 0:
            penalty += self.anti_penalty
        if patterns.corporate > 0:
            penalty += self.anti_penalty
        if patterns.hedging > 0:
            penalty += self.anti_penalty

        return min(penalty, self.MAX_ANTI_PENALTY)

    def _update_stats(self, lock_in: LockIn) -> None:
        """Update running statistics."""
        self.stats["processed"] += 1

        # Update tier counts
        if lock_in.tier == QualityTier.GOLD:
            self.stats["gold"] += 1
        elif lock_in.tier == QualityTier.SILVER:
            self.stats["silver"] += 1
        else:
            self.stats["bronze"] += 1

        # Update running average
        n = self.stats["processed"]
        old_avg = self.stats["avg_coefficient"]
        self.stats["avg_coefficient"] = old_avg + (lock_in.coefficient - old_avg) / n

    def process_batch(self, examples: list[TrainingExample]) -> dict[str, any]:
        """
        Process a batch of examples and compute their lock-in coefficients.

        Args:
            examples: List of examples to process.

        Returns:
            Statistics dictionary.
        """
        # Reset stats for batch
        self.stats = {
            "processed": 0,
            "gold": 0,
            "silver": 0,
            "bronze": 0,
            "avg_coefficient": 0.0,
        }

        for example in examples:
            self.compute_lock_in(example)

        logger.info(
            f"Processed {self.stats['processed']} examples. "
            f"Gold: {self.stats['gold']}, "
            f"Silver: {self.stats['silver']}, "
            f"Bronze: {self.stats['bronze']}. "
            f"Avg coefficient: {self.stats['avg_coefficient']:.3f}"
        )

        return self.stats.copy()

    def get_stats(self) -> dict[str, any]:
        """Get current processing statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self.stats = {
            "processed": 0,
            "gold": 0,
            "silver": 0,
            "bronze": 0,
            "avg_coefficient": 0.0,
        }

    def calibrate_from_examples(
        self,
        gold_examples: list[TrainingExample],
        bronze_examples: list[TrainingExample],
    ) -> None:
        """
        Calibrate weights based on known good and bad examples.

        Analyzes the differences between gold and bronze examples
        to optimize detection thresholds.

        Args:
            gold_examples: Examples known to be high quality.
            bronze_examples: Examples known to be low quality.
        """
        if not gold_examples or not bronze_examples:
            logger.warning("Need both gold and bronze examples for calibration")
            return

        # Analyze gold examples
        gold_voice_avg = sum(
            self.detect_voice_markers(e.assistant_response).total
            for e in gold_examples
        ) / len(gold_examples)

        gold_anti_avg = sum(
            self.detect_anti_patterns(e.assistant_response).total
            for e in gold_examples
        ) / len(gold_examples)

        # Analyze bronze examples
        bronze_voice_avg = sum(
            self.detect_voice_markers(e.assistant_response).total
            for e in bronze_examples
        ) / len(bronze_examples)

        bronze_anti_avg = sum(
            self.detect_anti_patterns(e.assistant_response).total
            for e in bronze_examples
        ) / len(bronze_examples)

        logger.info(
            f"Calibration analysis:\n"
            f"  Gold avg voice markers: {gold_voice_avg:.2f}\n"
            f"  Gold avg anti-patterns: {gold_anti_avg:.2f}\n"
            f"  Bronze avg voice markers: {bronze_voice_avg:.2f}\n"
            f"  Bronze avg anti-patterns: {bronze_anti_avg:.2f}"
        )

        # Adjust bonuses based on differentiation power
        voice_diff = gold_voice_avg - bronze_voice_avg
        if voice_diff > 0:
            # Voice markers differentiate well, increase bonus
            self.voice_bonus = min(0.08, 0.05 + (voice_diff * 0.01))

        anti_diff = bronze_anti_avg - gold_anti_avg
        if anti_diff > 0:
            # Anti-patterns differentiate well, increase penalty
            self.anti_penalty = min(0.20, 0.15 + (anti_diff * 0.02))

        logger.info(
            f"Calibrated weights: voice_bonus={self.voice_bonus:.3f}, "
            f"anti_penalty={self.anti_penalty:.3f}"
        )

    def __repr__(self) -> str:
        return f"Locksmith(voice_bonus={self.voice_bonus}, anti_penalty={self.anti_penalty})"
