"""
Persona Forge Engine - Pipeline (Orchestration Module)

The ForgePipeline orchestrates the complete training data pipeline:
Crucible -> Locksmith -> Assayer -> Mint -> Anvil

It provides a high-level interface for the entire workflow with
step-by-step callbacks for progress tracking and TUI integration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Union

from .models import (
    DatasetAssay,
    TargetProfile,
    TrainingExample,
    DIRECTOR_PROFILE,
)
from .crucible import Crucible
from .assayer import Assayer
from .locksmith import Locksmith
from .mint import Mint
from .anvil import Anvil

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """Pipeline execution stages."""
    INIT = "init"
    INGEST = "ingest"
    WEIGHT = "weight"
    ANALYZE = "analyze"
    SYNTHESIZE = "synthesize"
    EXPORT = "export"
    COMPLETE = "complete"


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""

    success: bool = False
    stage_reached: PipelineStage = PipelineStage.INIT

    # Data products
    examples: list[TrainingExample] = field(default_factory=list)
    synthetic_examples: list[TrainingExample] = field(default_factory=list)
    assay: Optional[DatasetAssay] = None

    # Output paths
    output_paths: dict[str, Path] = field(default_factory=dict)

    # Statistics
    total_loaded: int = 0
    total_synthetic: int = 0
    total_exported: int = 0

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stage_timings: dict[str, float] = field(default_factory=dict)

    # Errors
    error_message: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Total duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def total_examples(self) -> int:
        """Total examples including synthetic."""
        return len(self.examples) + len(self.synthetic_examples)


# Callback type for progress reporting
ProgressCallback = Callable[[PipelineStage, str, float], None]


class ForgePipeline:
    """
    Orchestrator for the complete Persona Forge training pipeline.

    The pipeline chains together:
    1. Crucible - Load training data from sources
    2. Locksmith - Compute lock-in coefficients
    3. Assayer - Analyze dataset and find gaps
    4. Mint - Generate synthetic examples for gaps (optional)
    5. Anvil - Export to training format

    Usage:
        pipeline = ForgePipeline()
        result = pipeline.run(
            sources=["data/train.jsonl"],
            target_profile=DIRECTOR_PROFILE,
            output_dir="output/",
        )

        # With callbacks for TUI
        def on_progress(stage, message, progress):
            print(f"[{stage.value}] {message} ({progress:.0%})")

        result = pipeline.run(
            sources=["data/"],
            on_progress=on_progress,
        )
    """

    def __init__(
        self,
        crucible: Optional[Crucible] = None,
        locksmith: Optional[Locksmith] = None,
        assayer: Optional[Assayer] = None,
        mint: Optional[Mint] = None,
        anvil: Optional[Anvil] = None,
    ):
        """
        Initialize the pipeline with optional custom components.

        Args:
            crucible: Custom Crucible instance.
            locksmith: Custom Locksmith instance.
            assayer: Custom Assayer instance.
            mint: Custom Mint instance.
            anvil: Custom Anvil instance.
        """
        self.crucible = crucible or Crucible()
        self.locksmith = locksmith or Locksmith()
        self.assayer = assayer or Assayer()
        self.mint = mint or Mint()
        self.anvil = anvil or Anvil()

        # Pipeline state
        self._current_stage = PipelineStage.INIT
        self._result = PipelineResult()

    def run(
        self,
        sources: list[Union[str, Path]],
        target_profile: Optional[TargetProfile] = None,
        output_dir: Optional[Union[str, Path]] = None,
        synthesize: bool = True,
        max_synthetic: int = 100,
        train_ratio: float = 0.9,
        weighted: bool = True,
        dry_run: bool = False,
        on_progress: Optional[ProgressCallback] = None,
    ) -> PipelineResult:
        """
        Execute the complete pipeline.

        Args:
            sources: List of JSONL files or directories to ingest.
            target_profile: Target distribution profile (default: DIRECTOR_PROFILE).
            output_dir: Directory for output files (required unless dry_run).
            synthesize: If True, generate examples to fill gaps.
            max_synthetic: Maximum synthetic examples to generate.
            train_ratio: Train/validation split ratio.
            weighted: If True, apply quality weighting.
            dry_run: If True, skip export step.
            on_progress: Progress callback for TUI integration.

        Returns:
            PipelineResult with all outputs and statistics.
        """
        import time

        target_profile = target_profile or DIRECTOR_PROFILE

        # Initialize result
        self._result = PipelineResult(started_at=datetime.utcnow())

        try:
            # ================================================================
            # Stage 1: INGEST - Load training data
            # ================================================================
            self._advance_stage(PipelineStage.INGEST, on_progress)
            self._report_progress(on_progress, "Loading training data...", 0.0)

            stage_start = time.perf_counter()
            examples = self._ingest_sources(sources, on_progress)
            self._result.stage_timings["ingest"] = time.perf_counter() - stage_start

            if not examples:
                raise ValueError("No valid training examples found")

            self._result.examples = examples
            self._result.total_loaded = len(examples)
            self._report_progress(on_progress, f"Loaded {len(examples)} examples", 1.0)

            # ================================================================
            # Stage 2: WEIGHT - Compute lock-in coefficients
            # ================================================================
            self._advance_stage(PipelineStage.WEIGHT, on_progress)
            self._report_progress(on_progress, "Computing lock-in coefficients...", 0.0)

            stage_start = time.perf_counter()
            self.locksmith.reset_stats()

            for i, example in enumerate(examples):
                self.locksmith.compute_lock_in(example)
                if i % 100 == 0:
                    progress = (i + 1) / len(examples)
                    self._report_progress(on_progress, f"Processed {i + 1}/{len(examples)}", progress)

            self._result.stage_timings["weight"] = time.perf_counter() - stage_start

            stats = self.locksmith.get_stats()
            self._report_progress(
                on_progress,
                f"Gold: {stats['gold']}, Silver: {stats['silver']}, Bronze: {stats['bronze']}",
                1.0
            )

            # ================================================================
            # Stage 3: ANALYZE - Analyze dataset and find gaps
            # ================================================================
            self._advance_stage(PipelineStage.ANALYZE, on_progress)
            self._report_progress(on_progress, "Analyzing dataset...", 0.0)

            stage_start = time.perf_counter()
            assay = self.assayer.analyze(examples, target_profile)
            self._result.assay = assay
            self._result.stage_timings["analyze"] = time.perf_counter() - stage_start

            self._report_progress(
                on_progress,
                f"Health score: {assay.health_score:.1f}/100, Gaps: {len(assay.coverage_gaps)}",
                1.0
            )

            # ================================================================
            # Stage 4: SYNTHESIZE - Generate synthetic examples (optional)
            # ================================================================
            if synthesize and assay.coverage_gaps:
                self._advance_stage(PipelineStage.SYNTHESIZE, on_progress)
                self._report_progress(on_progress, "Generating synthetic examples...", 0.0)

                stage_start = time.perf_counter()
                synthetic_examples = self.mint.mint_for_gaps(
                    gaps=assay.coverage_gaps,
                    current_count=len(examples),
                )

                # Cap synthetic examples
                if len(synthetic_examples) > max_synthetic:
                    synthetic_examples = synthetic_examples[:max_synthetic]

                # Compute lock-in for synthetic examples
                for example in synthetic_examples:
                    self.locksmith.compute_lock_in(example)

                self._result.synthetic_examples = synthetic_examples
                self._result.total_synthetic = len(synthetic_examples)
                self._result.stage_timings["synthesize"] = time.perf_counter() - stage_start

                self._report_progress(
                    on_progress,
                    f"Generated {len(synthetic_examples)} synthetic examples",
                    1.0
                )

            # ================================================================
            # Stage 5: EXPORT - Export to training format
            # ================================================================
            if not dry_run:
                if output_dir is None:
                    raise ValueError("output_dir required when dry_run=False")

                self._advance_stage(PipelineStage.EXPORT, on_progress)
                self._report_progress(on_progress, "Exporting training data...", 0.0)

                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                stage_start = time.perf_counter()

                # Combine all examples
                all_examples = self._result.examples + self._result.synthetic_examples

                # Export train/val split
                split_result = self.anvil.export_train_val_split(
                    examples=all_examples,
                    output_dir=output_dir,
                    train_ratio=train_ratio,
                    weighted=weighted,
                    stratified=True,
                )

                self._result.output_paths = {
                    "train": split_result["train"],
                    "val": split_result["val"],
                }
                self._result.total_exported = split_result["train_count"] + split_result["val_count"]
                self._result.stage_timings["export"] = time.perf_counter() - stage_start

                self._report_progress(
                    on_progress,
                    f"Exported {self._result.total_exported} examples",
                    1.0
                )

            # ================================================================
            # Complete
            # ================================================================
            self._advance_stage(PipelineStage.COMPLETE, on_progress)
            self._result.success = True
            self._result.completed_at = datetime.utcnow()

            logger.info(
                f"Pipeline completed successfully in {self._result.duration_seconds:.1f}s. "
                f"Total examples: {self._result.total_examples}"
            )

            return self._result

        except Exception as e:
            self._result.error_message = str(e)
            self._result.completed_at = datetime.utcnow()
            logger.error(f"Pipeline failed at stage {self._current_stage.value}: {e}")
            return self._result

    def run_analysis_only(
        self,
        sources: list[Union[str, Path]],
        target_profile: Optional[TargetProfile] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> PipelineResult:
        """
        Run pipeline through analysis stage only (no export).

        Args:
            sources: Sources to analyze.
            target_profile: Target profile for gap analysis.
            on_progress: Progress callback.

        Returns:
            PipelineResult with analysis but no exports.
        """
        return self.run(
            sources=sources,
            target_profile=target_profile,
            synthesize=False,
            dry_run=True,
            on_progress=on_progress,
        )

    def _ingest_sources(
        self,
        sources: list[Union[str, Path]],
        on_progress: Optional[ProgressCallback] = None,
    ) -> list[TrainingExample]:
        """Ingest examples from multiple sources."""
        all_examples = []

        for i, source in enumerate(sources):
            source_path = Path(source)
            progress = i / len(sources)

            if source_path.is_file():
                self._report_progress(on_progress, f"Loading {source_path.name}...", progress)
                examples = self.crucible.ingest_jsonl(source_path)
                all_examples.extend(examples)
            elif source_path.is_dir():
                self._report_progress(on_progress, f"Loading from {source_path.name}/...", progress)
                examples = self.crucible.ingest_directory(source_path)
                all_examples.extend(examples)
            else:
                logger.warning(f"Source not found: {source_path}")

        return all_examples

    def _advance_stage(
        self,
        stage: PipelineStage,
        on_progress: Optional[ProgressCallback] = None,
    ) -> None:
        """Advance to the next pipeline stage."""
        self._current_stage = stage
        self._result.stage_reached = stage

        if on_progress:
            on_progress(stage, f"Starting {stage.value}...", 0.0)

    def _report_progress(
        self,
        callback: Optional[ProgressCallback],
        message: str,
        progress: float,
    ) -> None:
        """Report progress via callback if available."""
        if callback:
            callback(self._current_stage, message, progress)

    def get_summary(self) -> str:
        """Generate a human-readable pipeline summary."""
        r = self._result

        lines = [
            "=" * 60,
            "FORGE PIPELINE SUMMARY",
            "=" * 60,
            f"Status: {'SUCCESS' if r.success else 'FAILED'}",
            f"Stage Reached: {r.stage_reached.value}",
            "",
            "EXAMPLES:",
            f"  Loaded: {r.total_loaded}",
            f"  Synthetic: {r.total_synthetic}",
            f"  Total: {r.total_examples}",
            f"  Exported: {r.total_exported}",
            "",
        ]

        if r.assay:
            lines.extend([
                "DATASET HEALTH:",
                f"  Health Score: {r.assay.health_score:.1f}/100",
                f"  Gold Examples: {r.assay.gold_percentage:.1f}%",
                f"  Clean (no anti-patterns): {r.assay.clean_percentage:.1f}%",
                f"  Coverage Gaps: {len(r.assay.coverage_gaps)}",
                "",
            ])

        if r.stage_timings:
            lines.append("TIMING:")
            for stage, duration in r.stage_timings.items():
                lines.append(f"  {stage}: {duration:.2f}s")
            lines.append(f"  TOTAL: {r.duration_seconds:.2f}s")
            lines.append("")

        if r.output_paths:
            lines.append("OUTPUT FILES:")
            for name, path in r.output_paths.items():
                lines.append(f"  {name}: {path}")
            lines.append("")

        if r.error_message:
            lines.extend([
                "ERROR:",
                f"  {r.error_message}",
                "",
            ])

        lines.append("=" * 60)

        return "\n".join(lines)

    @property
    def current_stage(self) -> PipelineStage:
        """Get current pipeline stage."""
        return self._current_stage

    @property
    def result(self) -> PipelineResult:
        """Get the current/last pipeline result."""
        return self._result

    def __repr__(self) -> str:
        return f"ForgePipeline(stage={self._current_stage.value})"
