"""
Assayer - Analysis module for Persona Forge

Analyzes training datasets against target profiles.
"""

from collections import Counter
import statistics
from typing import Optional

from .models import (
    TrainingExample, DatasetAssay, TargetProfile,
    InteractionType, ResponseLength, QualityTier, SourceType,
    DIRECTOR_PROFILE,
)
from .personality_scorer import PersonalityScorer, TARGET_PROFILE


class Assayer:
    """
    Analyzes training dataset against target profile.
    
    Computes:
    - Distribution analysis (types, lengths, sources)
    - Voice marker rates
    - Anti-pattern rates
    - Lock-in statistics
    - Coverage gaps
    - Health score
    """
    
    def __init__(
        self,
        target_profile: TargetProfile = DIRECTOR_PROFILE,
        personality_target: dict[str, float] = None,
    ):
        """
        Initialize Assayer.

        Args:
            target_profile: Target distribution profile for dataset shaping
            personality_target: Target personality profile (8 dimensions, 0-1 scores).
                               Defaults to Luna's TARGET_PROFILE if None.
        """
        self.profile = target_profile
        self.personality_target = personality_target or TARGET_PROFILE
        self._personality_scorer = PersonalityScorer()
    
    def analyze(self, examples: list[TrainingExample]) -> DatasetAssay:
        """Perform full dataset analysis."""
        if not examples:
            return self._empty_assay()
        
        # Compute distributions
        type_dist = self._compute_type_distribution(examples)
        length_dist = self._compute_length_distribution(examples)
        source_dist = self._compute_source_distribution(examples)
        tier_dist = self._compute_tier_distribution(examples)
        
        # Voice analysis
        voice_rates = self._compute_voice_marker_rates(examples)
        anti_rates = self._compute_anti_pattern_rates(examples)
        
        # Lock-in statistics
        coefficients = [e.lock_in.coefficient for e in examples]
        avg_lockin = statistics.mean(coefficients)
        std_lockin = statistics.stdev(coefficients) if len(coefficients) > 1 else 0.0
        
        # Coverage gaps
        gaps = self._compute_gaps(type_dist, len(examples))
        synthesis_targets = self._compute_synthesis_targets(gaps)
        
        # Health score
        health_score, health_breakdown = self._compute_health_score(
            type_dist, length_dist, voice_rates, anti_rates, avg_lockin, len(examples)
        )

        # Personality analysis
        personality_profile = self._compute_personality_profile(examples)
        personality_variance = self._compute_personality_variance(examples)
        personality_alignment = self._compute_personality_alignment(personality_profile)

        return DatasetAssay(
            total_examples=len(examples),
            interaction_type_dist=type_dist,
            response_length_dist=length_dist,
            source_type_dist=source_dist,
            quality_tier_dist=tier_dist,
            voice_marker_rates=voice_rates,
            anti_pattern_rates=anti_rates,
            avg_lock_in=avg_lockin,
            lock_in_std=std_lockin,
            lock_in_min=min(coefficients),
            lock_in_max=max(coefficients),
            gaps=gaps,
            synthesis_targets=synthesis_targets,
            health_score=health_score,
            health_breakdown=health_breakdown,
            personality_profile=personality_profile,
            personality_variance=personality_variance,
            personality_alignment=personality_alignment,
        )
    
    def _compute_type_distribution(self, examples: list[TrainingExample]) -> dict[str, float]:
        """Compute interaction type distribution."""
        counter = Counter(e.interaction_type.value for e in examples)
        total = len(examples)
        
        # Include all types, even zero
        result = {}
        for itype in InteractionType:
            result[itype.value] = counter.get(itype.value, 0) / total
        
        return result
    
    def _compute_length_distribution(self, examples: list[TrainingExample]) -> dict[str, float]:
        """Compute response length distribution."""
        counter = Counter(e.response_length_category.value for e in examples)
        total = len(examples)
        
        result = {}
        for length in ResponseLength:
            result[length.value] = counter.get(length.value, 0) / total
        
        return result
    
    def _compute_source_distribution(self, examples: list[TrainingExample]) -> dict[str, float]:
        """Compute source type distribution."""
        counter = Counter(e.source_type.value for e in examples)
        total = len(examples)
        
        result = {}
        for stype in SourceType:
            result[stype.value] = counter.get(stype.value, 0) / total
        
        return result
    
    def _compute_tier_distribution(self, examples: list[TrainingExample]) -> dict[str, float]:
        """Compute quality tier distribution."""
        counter = Counter(e.lock_in.tier.value for e in examples)
        total = len(examples)
        
        result = {}
        for tier in QualityTier:
            result[tier.value] = counter.get(tier.value, 0) / total
        
        return result
    
    def _compute_voice_marker_rates(self, examples: list[TrainingExample]) -> dict[str, float]:
        """Compute voice marker rates across dataset."""
        if not examples:
            return {}
        
        # Note: inside_refs not in VoiceMarkers model
        markers = ["first_person", "warmth_words", "uncertainty", "relationship"]
        rates = {}
        
        for marker in markers:
            # Use getattr() - VoiceMarkers is Pydantic model, not dict
            count = sum(1 for e in examples if getattr(e.voice_markers, marker, 0) > 0)
            rates[marker] = count / len(examples)
        
        return rates
    
    def _compute_anti_pattern_rates(self, examples: list[TrainingExample]) -> dict[str, float]:
        """Compute anti-pattern rates across dataset."""
        if not examples:
            return {}
        
        patterns = ["generic_ai", "corporate", "hedging"]
        rates = {}
        
        for pattern in patterns:
            # Use getattr() - AntiPatterns is Pydantic model, not dict
            count = sum(1 for e in examples if getattr(e.anti_patterns, pattern, 0) > 0)
            rates[pattern] = count / len(examples)
        
        return rates
    
    def _compute_gaps(self, actual_dist: dict[str, float], total: int) -> dict[str, int]:
        """Compute gap between actual and target counts."""
        gaps = {}
        
        for itype in InteractionType:
            target_pct = self.profile.interaction_types.get(itype.value, 0)
            actual_pct = actual_dist.get(itype.value, 0)
            target_count = int(self.profile.target_examples * target_pct)
            actual_count = int(total * actual_pct)
            gaps[itype.value] = actual_count - target_count  # negative = need more
        
        return gaps
    
    def _compute_synthesis_targets(self, gaps: dict[str, int]) -> dict[str, int]:
        """How many of each type to synthesize."""
        return {t: abs(g) for t, g in gaps.items() if g < 0}
    
    def _compute_health_score(
        self,
        type_dist: dict,
        length_dist: dict,
        voice_rates: dict,
        anti_rates: dict,
        avg_lockin: float,
        total_examples: int,
    ) -> tuple[float, dict[str, float]]:
        """Compute overall dataset health score (0-100)."""
        
        breakdown = {}
        
        # Type coverage (25 points)
        type_score = 0
        for itype, target in self.profile.interaction_types.items():
            actual = type_dist.get(itype, 0)
            if target > 0:
                type_score += min(1.0, actual / target) * (target * 100)
        breakdown["type_coverage"] = min(25, type_score * 0.25)
        
        # Length balance (15 points)
        length_score = 0
        for length, target in self.profile.response_lengths.items():
            actual = length_dist.get(length, 0)
            if target > 0:
                length_score += min(1.0, actual / target) * (target * 100)
        breakdown["length_balance"] = min(15, length_score * 0.15)
        
        # Voice markers (30 points)
        voice_score = 0
        voice_count = len(self.profile.voice_markers)
        for marker, min_rate in self.profile.voice_markers.items():
            actual = voice_rates.get(marker, 0)
            if actual >= min_rate:
                voice_score += 1
            else:
                # Partial credit
                voice_score += actual / min_rate if min_rate > 0 else 0
        breakdown["voice_quality"] = (voice_score / voice_count) * 30 if voice_count > 0 else 30
        
        # Anti-pattern absence (20 points)
        anti_score = 20
        for pattern, max_rate in self.profile.anti_patterns.items():
            actual = anti_rates.get(pattern, 0)
            if actual > max_rate:
                penalty = min(10, (actual - max_rate) * 100)
                anti_score -= penalty
        breakdown["anti_pattern_absence"] = max(0, anti_score)
        
        # Lock-in quality (10 points)
        breakdown["lockin_quality"] = avg_lockin * 10
        
        # Dataset size bonus/penalty (10 points)
        if total_examples >= self.profile.target_examples:
            size_score = 10
        elif total_examples >= self.profile.min_examples:
            size_score = 5 + 5 * (total_examples - self.profile.min_examples) / (self.profile.target_examples - self.profile.min_examples)
        else:
            size_score = 5 * total_examples / self.profile.min_examples
        breakdown["dataset_size"] = size_score
        
        total = sum(breakdown.values())
        return total, breakdown

    def _compute_personality_profile(
        self,
        examples: list[TrainingExample]
    ) -> dict[str, float]:
        """
        Compute average personality profile across dataset.

        Args:
            examples: List of training examples

        Returns:
            Dictionary mapping dimension names to average scores (0-1)
        """
        # Filter examples with personality scores
        scored_examples = [
            e for e in examples
            if e.personality_scores is not None
        ]

        if not scored_examples:
            return {}

        # Get dimensions from first scored example
        dimensions = list(scored_examples[0].personality_scores.keys())

        # Compute average for each dimension
        profile = {}
        for dim in dimensions:
            scores = [
                e.personality_scores[dim]
                for e in scored_examples
                if dim in e.personality_scores
            ]
            if scores:
                profile[dim] = sum(scores) / len(scores)

        return profile

    def _compute_personality_variance(
        self,
        examples: list[TrainingExample]
    ) -> dict[str, float]:
        """
        Compute personality variance (standard deviation) per dimension.

        Args:
            examples: List of training examples

        Returns:
            Dictionary mapping dimension names to standard deviations
        """
        scored_examples = [
            e for e in examples
            if e.personality_scores is not None
        ]

        if not scored_examples:
            return {}

        dimensions = list(scored_examples[0].personality_scores.keys())

        variance = {}
        for dim in dimensions:
            scores = [
                e.personality_scores[dim]
                for e in scored_examples
                if dim in e.personality_scores
            ]
            if len(scores) > 1:
                variance[dim] = statistics.stdev(scores)
            elif scores:
                variance[dim] = 0.0

        return variance

    def _compute_personality_alignment(
        self,
        profile: dict[str, float]
    ) -> float:
        """
        Compute alignment between profile and target (0-1).

        1.0 = perfect alignment, 0.0 = maximum distance.

        Args:
            profile: Computed personality profile

        Returns:
            Alignment score (0-1)
        """
        return self._personality_scorer.compute_alignment(
            profile,
            self.personality_target
        )

    def _empty_assay(self) -> DatasetAssay:
        """Return empty assay for empty dataset."""
        return DatasetAssay(
            total_examples=0,
            interaction_type_dist={t.value: 0.0 for t in InteractionType},
            response_length_dist={l.value: 0.0 for l in ResponseLength},
            source_type_dist={s.value: 0.0 for s in SourceType},
            quality_tier_dist={t.value: 0.0 for t in QualityTier},
            voice_marker_rates={},
            anti_pattern_rates={},
            avg_lock_in=0.0,
            lock_in_std=0.0,
            lock_in_min=0.0,
            lock_in_max=0.0,
            gaps={},
            synthesis_targets={},
            health_score=0.0,
            health_breakdown={},
            personality_profile={},
            personality_variance={},
            personality_alignment=0.0,
        )
    
    def format_report(self, assay: DatasetAssay) -> str:
        """Format assay as readable report."""
        lines = []
        
        lines.append("=" * 60)
        lines.append("           PERSONA FORGE - DATASET ASSAY")
        lines.append("=" * 60)
        lines.append("")
        
        # Health score
        health_emoji = "🟢" if assay.health_score >= 70 else "🟡" if assay.health_score >= 50 else "🔴"
        lines.append(f"HEALTH SCORE: {health_emoji} {assay.health_score:.1f}/100")
        lines.append("")
        
        # Health breakdown
        lines.append("Health Breakdown:")
        for component, score in assay.health_breakdown.items():
            bar = "█" * int(score) + "░" * (30 - int(score))
            lines.append(f"  {component:20s} [{bar}] {score:.1f}")
        lines.append("")
        
        # Summary
        lines.append(f"Total Examples: {assay.total_examples}")
        lines.append(f"Avg Lock-in: {assay.avg_lock_in:.3f} (std: {assay.lock_in_std:.3f})")
        lines.append(f"Lock-in Range: [{assay.lock_in_min:.3f}, {assay.lock_in_max:.3f}]")
        lines.append("")
        
        # Quality tiers
        lines.append("Quality Tiers:")
        for tier in ["gold", "silver", "bronze"]:
            pct = assay.quality_tier_dist.get(tier, 0) * 100
            bar = "█" * int(pct / 3) + "░" * (33 - int(pct / 3))
            emoji = "🥇" if tier == "gold" else "🥈" if tier == "silver" else "🥉"
            lines.append(f"  {emoji} {tier:8s} [{bar}] {pct:.1f}%")
        lines.append("")
        
        # Interaction types
        lines.append("Interaction Types:")
        for itype, pct in sorted(assay.interaction_type_dist.items(), key=lambda x: -x[1]):
            if pct > 0:
                bar = "█" * int(pct * 50) + "░" * (50 - int(pct * 50))
                lines.append(f"  {itype:20s} [{bar}] {pct*100:.1f}%")
        lines.append("")
        
        # Response lengths
        lines.append("Response Lengths:")
        for length in ["short", "medium", "long"]:
            pct = assay.response_length_dist.get(length, 0) * 100
            bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
            lines.append(f"  {length:10s} [{bar}] {pct:.1f}%")
        lines.append("")
        
        # Voice markers
        lines.append("Voice Markers:")
        for marker, rate in assay.voice_marker_rates.items():
            target = self.profile.voice_markers.get(marker, 0)
            status = "✓" if rate >= target else "✗"
            lines.append(f"  {status} {marker:15s} {rate*100:5.1f}% (target: {target*100:.0f}%)")
        lines.append("")
        
        # Anti-patterns
        lines.append("Anti-Patterns:")
        for pattern, rate in assay.anti_pattern_rates.items():
            limit = self.profile.anti_patterns.get(pattern, 0)
            status = "✓" if rate <= limit else "✗"
            lines.append(f"  {status} {pattern:15s} {rate*100:5.1f}% (limit: {limit*100:.0f}%)")
        lines.append("")
        
        # Synthesis targets
        if assay.synthesis_targets:
            lines.append("Synthesis Targets (to fill gaps):")
            for itype, count in sorted(assay.synthesis_targets.items(), key=lambda x: -x[1]):
                if count > 0:
                    lines.append(f"  + {count:3d} {itype}")
        lines.append("")

        # Personality Profile Section
        if assay.personality_profile:
            lines.append("-" * 60)
            lines.append("PERSONALITY PROFILE")
            lines.append("-" * 60)
            lines.append("")

            # Overall alignment
            if assay.personality_alignment is not None:
                alignment_pct = assay.personality_alignment * 100
                if alignment_pct >= 85:
                    status = "🟢"
                elif alignment_pct >= 70:
                    status = "🟡"
                else:
                    status = "🔴"
                lines.append(f"{status} Overall Alignment: {alignment_pct:.1f}% (target: ≥85%)")
                lines.append("")

            # Dimension breakdown
            lines.append("Dimension Scores:")
            for dim, score in assay.personality_profile.items():
                target = self.personality_target.get(dim, 0.7)
                variance = assay.personality_variance.get(dim, 0)
                diff = score - target

                # Status indicator
                if abs(diff) < 0.05:
                    status = "✓✓"  # Perfect
                elif abs(diff) < 0.10:
                    status = "✓ "  # Good
                else:
                    status = "✗ "  # Gap

                # Visual bar (50 chars max)
                bar_length = int(score * 40)
                bar = "█" * bar_length + "░" * (40 - bar_length)

                # Diff indicator
                diff_str = f"{diff:+.2f}" if diff != 0 else " 0.00"
                diff_arrow = "↑" if diff > 0 else "↓" if diff < 0 else "="

                lines.append(
                    f"  {status} {dim:15s} [{bar}] {score:.2f} ±{variance:.2f} "
                    f"| target: {target:.2f} | {diff_arrow} {diff_str}"
                )

            lines.append("")

            # Recommendations
            lines.append("Recommendations:")
            gaps_found = False
            for dim, score in assay.personality_profile.items():
                target = self.personality_target.get(dim, 0.7)
                diff = score - target

                if abs(diff) >= 0.10:
                    gaps_found = True
                    if diff < 0:
                        lines.append(
                            f"  • Add examples with higher {dim} (need +{abs(diff):.2f})"
                        )
                    else:
                        lines.append(
                            f"  • Reduce examples with high {dim} (need {diff:.2f})"
                        )

            if not gaps_found:
                lines.append("  ✓ Personality profile well-aligned with target")

            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)
