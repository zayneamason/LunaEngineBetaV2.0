"""
Persona Forge Engine - Anvil (Export Module)

The Anvil shapes raw training examples into the final format
for fine-tuning. It exports to JSONL with optional weighting
and train/validation splits.

Named after the blacksmith's anvil - where shaped metal is
hammered into its final form.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .models import (
    QualityTier,
    TrainingExample,
)

logger = logging.getLogger(__name__)


class AnvilError(Exception):
    """Base exception for Anvil operations."""
    pass


class ExportError(AnvilError):
    """Error during export operation."""
    pass


class Anvil:
    """
    Export module for training data.

    The Anvil transforms TrainingExample objects into training-ready
    formats (JSONL) with support for:
    - Quality-based weighting (gold/silver/bronze)
    - Train/validation splitting
    - Metadata preservation

    Usage:
        anvil = Anvil()
        output_path = anvil.export_jsonl(examples, "training_data.jsonl")

        # Or with train/val split
        paths = anvil.export_train_val_split(examples, "data/", train_ratio=0.9)
    """

    # Weight multipliers by quality tier
    TIER_WEIGHTS: dict[QualityTier, float] = {
        QualityTier.GOLD: 3.0,    # Gold examples get 3x weight
        QualityTier.SILVER: 2.0,  # Silver examples get 2x weight
        QualityTier.BRONZE: 1.0,  # Bronze examples get 1x weight
    }

    def __init__(
        self,
        tier_weights: Optional[dict[QualityTier, float]] = None,
        include_metadata: bool = True,
        format_version: str = "1.0",
    ):
        """
        Initialize the Anvil.

        Args:
            tier_weights: Custom weight multipliers by quality tier.
            include_metadata: Whether to include metadata comments in output.
            format_version: Output format version for compatibility tracking.
        """
        self.tier_weights = tier_weights or self.TIER_WEIGHTS.copy()
        self.include_metadata = include_metadata
        self.format_version = format_version

        # Statistics
        self.stats = {
            "total_exported": 0,
            "by_tier": {},
            "output_files": [],
        }

    def export_jsonl(
        self,
        examples: list[TrainingExample],
        output_path: str | Path,
        weighted: bool = True,
        min_quality_tier: Optional[QualityTier] = None,
    ) -> Path:
        """
        Export training examples to a JSONL file.

        Args:
            examples: List of TrainingExample objects.
            output_path: Path for the output JSONL file.
            weighted: If True, apply tier-based weight multipliers.
            min_quality_tier: Minimum tier to include (None = all).

        Returns:
            Path to the exported file.

        Raises:
            ExportError: If export fails.
        """
        output_path = Path(output_path)

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Filter by quality tier if specified
        filtered_examples = examples
        if min_quality_tier is not None:
            tier_order = [QualityTier.BRONZE, QualityTier.SILVER, QualityTier.GOLD]
            min_index = tier_order.index(min_quality_tier)
            allowed_tiers = set(tier_order[min_index:])
            filtered_examples = [
                e for e in examples
                if e.lock_in.tier in allowed_tiers
            ]

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # Write header comment if including metadata
                if self.include_metadata:
                    header = {
                        "_comment": "Persona Forge Training Data Export",
                        "_format_version": self.format_version,
                        "_exported_at": datetime.utcnow().isoformat(),
                        "_total_examples": len(filtered_examples),
                        "_weighted": weighted,
                    }
                    f.write(f"# {json.dumps(header)}\n")

                # Export each example
                tier_counts = {}
                for example in filtered_examples:
                    record = self._example_to_record(example, weighted)
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

                    # Track tier counts
                    tier = example.lock_in.tier.value
                    tier_counts[tier] = tier_counts.get(tier, 0) + 1

                # Update stats
                self.stats["total_exported"] += len(filtered_examples)
                self.stats["by_tier"] = tier_counts
                self.stats["output_files"].append(str(output_path))

            logger.info(
                f"Exported {len(filtered_examples)} examples to {output_path} "
                f"(weighted={weighted})"
            )

            return output_path

        except Exception as e:
            raise ExportError(f"Failed to export to {output_path}: {e}") from e

    def export_train_val_split(
        self,
        examples: list[TrainingExample],
        output_dir: str | Path,
        train_ratio: float = 0.9,
        weighted: bool = True,
        min_quality_tier: Optional[QualityTier] = None,
        stratified: bool = True,
    ) -> dict[str, Path]:
        """
        Export examples with train/validation split.

        Args:
            examples: List of TrainingExample objects.
            output_dir: Directory for output files.
            train_ratio: Fraction for training (rest goes to validation).
            weighted: If True, apply tier-based weight multipliers.
            min_quality_tier: Minimum tier to include.
            stratified: If True, maintain interaction type distribution.

        Returns:
            Dictionary with 'train' and 'val' paths.

        Raises:
            ExportError: If export fails.
        """
        import random

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Filter by quality tier
        filtered_examples = examples
        if min_quality_tier is not None:
            tier_order = [QualityTier.BRONZE, QualityTier.SILVER, QualityTier.GOLD]
            min_index = tier_order.index(min_quality_tier)
            allowed_tiers = set(tier_order[min_index:])
            filtered_examples = [
                e for e in examples
                if e.lock_in.tier in allowed_tiers
            ]

        if not filtered_examples:
            raise ExportError("No examples to export after filtering")

        if stratified:
            # Split by interaction type to maintain distribution
            train_examples = []
            val_examples = []

            # Group by interaction type
            by_type: dict[str, list[TrainingExample]] = {}
            for example in filtered_examples:
                type_key = (
                    example.metadata.interaction_type.value
                    if example.metadata.interaction_type
                    else "unknown"
                )
                if type_key not in by_type:
                    by_type[type_key] = []
                by_type[type_key].append(example)

            # Split each group
            for type_key, type_examples in by_type.items():
                random.shuffle(type_examples)
                split_idx = int(len(type_examples) * train_ratio)
                train_examples.extend(type_examples[:split_idx])
                val_examples.extend(type_examples[split_idx:])

            # Shuffle the final lists
            random.shuffle(train_examples)
            random.shuffle(val_examples)
        else:
            # Simple random split
            shuffled = list(filtered_examples)
            random.shuffle(shuffled)
            split_idx = int(len(shuffled) * train_ratio)
            train_examples = shuffled[:split_idx]
            val_examples = shuffled[split_idx:]

        # Export train and val files
        train_path = self.export_jsonl(
            train_examples,
            output_dir / "train.jsonl",
            weighted=weighted,
        )

        val_path = self.export_jsonl(
            val_examples,
            output_dir / "val.jsonl",
            weighted=weighted,
        )

        logger.info(
            f"Exported train/val split: "
            f"train={len(train_examples)}, val={len(val_examples)}"
        )

        return {
            "train": train_path,
            "val": val_path,
            "train_count": len(train_examples),
            "val_count": len(val_examples),
            "train_ratio": train_ratio,
        }

    def export_by_tier(
        self,
        examples: list[TrainingExample],
        output_dir: str | Path,
        weighted: bool = True,
    ) -> dict[str, Path]:
        """
        Export examples to separate files by quality tier.

        Args:
            examples: List of TrainingExample objects.
            output_dir: Directory for output files.
            weighted: If True, apply tier-based weight multipliers.

        Returns:
            Dictionary mapping tier names to file paths.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Group by tier
        by_tier: dict[QualityTier, list[TrainingExample]] = {}
        for example in examples:
            tier = example.lock_in.tier
            if tier not in by_tier:
                by_tier[tier] = []
            by_tier[tier].append(example)

        # Export each tier
        paths = {}
        for tier, tier_examples in by_tier.items():
            path = self.export_jsonl(
                tier_examples,
                output_dir / f"{tier.value}.jsonl",
                weighted=weighted,
            )
            paths[tier.value] = path

        return paths

    def _example_to_record(
        self,
        example: TrainingExample,
        weighted: bool = True,
    ) -> dict[str, Any]:
        """
        Convert a TrainingExample to a JSONL record.

        Args:
            example: The training example.
            weighted: Whether to apply tier weights.

        Returns:
            Dictionary ready for JSON serialization.
        """
        # Get base training format
        base_format = example.to_training_dict()

        # Apply tier weighting if requested
        if weighted:
            tier_multiplier = self.tier_weights.get(example.lock_in.tier, 1.0)
            base_format["weight"] = example.lock_in.coefficient * tier_multiplier
        else:
            base_format["weight"] = example.lock_in.coefficient

        # Add metadata if configured
        if self.include_metadata:
            base_format["_metadata"] = {
                "source_type": example.metadata.source_type.value,
                "interaction_type": (
                    example.metadata.interaction_type.value
                    if example.metadata.interaction_type
                    else None
                ),
                "response_length": (
                    example.metadata.response_length.value
                    if example.metadata.response_length
                    else None
                ),
                "quality_tier": example.lock_in.tier.value,
                "word_count": example.metadata.word_count,
                "has_authentic_voice": example.voice_markers.has_authentic_voice,
                "anti_patterns_clean": example.anti_patterns.is_clean,
            }

        return base_format

    def export_unweighted(
        self,
        examples: list[TrainingExample],
        output_path: str | Path,
    ) -> Path:
        """
        Export examples without weight adjustments.

        Args:
            examples: List of TrainingExample objects.
            output_path: Path for the output file.

        Returns:
            Path to the exported file.
        """
        return self.export_jsonl(examples, output_path, weighted=False)

    def export_gold_only(
        self,
        examples: list[TrainingExample],
        output_path: str | Path,
        weighted: bool = True,
    ) -> Path:
        """
        Export only gold-tier examples.

        Args:
            examples: List of TrainingExample objects.
            output_path: Path for the output file.
            weighted: If True, apply tier-based weights.

        Returns:
            Path to the exported file.
        """
        return self.export_jsonl(
            examples,
            output_path,
            weighted=weighted,
            min_quality_tier=QualityTier.GOLD,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get export statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset export statistics."""
        self.stats = {
            "total_exported": 0,
            "by_tier": {},
            "output_files": [],
        }

    def get_recommended_split(
        self,
        example_count: int,
    ) -> dict[str, float]:
        """
        Get recommended train/validation split ratio.

        Args:
            example_count: Total number of examples.

        Returns:
            Dictionary with recommended ratios.
        """
        # Small datasets need more validation data for meaningful evaluation
        if example_count < 100:
            return {"train": 0.8, "val": 0.2}
        elif example_count < 500:
            return {"train": 0.85, "val": 0.15}
        elif example_count < 1000:
            return {"train": 0.9, "val": 0.1}
        else:
            return {"train": 0.95, "val": 0.05}

    def preview_export(
        self,
        examples: list[TrainingExample],
        count: int = 5,
        weighted: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Preview export format without writing to file.

        Args:
            examples: Examples to preview.
            count: Number of examples to show.
            weighted: Whether to apply tier weights.

        Returns:
            List of formatted records.
        """
        preview = []
        for example in examples[:count]:
            record = self._example_to_record(example, weighted)
            preview.append(record)
        return preview

    def __repr__(self) -> str:
        return f"Anvil(format_version={self.format_version})"
