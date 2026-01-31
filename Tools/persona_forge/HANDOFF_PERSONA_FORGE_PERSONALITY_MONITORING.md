# HANDOFF: Persona Forge Personality Monitoring Integration

**Project:** Luna Engine v2.0 - Persona Forge Enhancement  
**Date:** January 29, 2026  
**Type:** Feature Addition + Architecture Enhancement  
**Complexity:** Medium (2 phases, 6.5 hours total)  
**Execution:** Claude Flow Swarm (3 agents)

---

## Executive Summary

Add personality monitoring capabilities to Persona Forge, enabling real-time dataset quality validation through 8-dimensional personality scoring. This integration allows pre-training validation, gap identification, and source quality comparison. Additionally, add target LLM selection to support multiple base models with LLM-specific personality adjustments.

**Key Changes:**
- Add PersonalityScorer integration to Crucible
- Enhance Assayer with personality analysis
- Add visualization generation
- Implement target LLM configuration system
- Update CLI with new commands

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Changes](#architecture-changes)
3. [Implementation Phases](#implementation-phases)
4. [Claude Flow Swarm Coordination](#claude-flow-swarm-coordination)
5. [Detailed Specifications](#detailed-specifications)
6. [Testing Strategy](#testing-strategy)
7. [Validation Criteria](#validation-criteria)
8. [Deployment](#deployment)
9. [Appendix](#appendix)

---

## Overview

### Current State

Persona Forge has 4 core components:
- **Crucible** - Ingests training examples from multiple sources
- **Assayer** - Analyzes dataset quality and identifies gaps
- **Locksmith** - Computes lock-in coefficients for example importance
- **Anvil** - Exports weighted JSONL for training

### Target State

Enhanced Persona Forge with:
- **Personality Scoring** during ingestion (automatic)
- **Personality Analysis** in dataset assay reports
- **Personality Visualizations** for dataset validation
- **Target LLM Selection** for model-specific training
- **LLM-Specific Baselines** for personality comparison

### Value Proposition

**Before:** Train blindly, validate after training with Voight-Kampff
**After:** Validate dataset BEFORE training, identify gaps proactively

**Impact:**
- Reduce training iterations (catch issues early)
- Improve dataset quality (targeted synthesis)
- Support multiple base models (Qwen, Llama, Mistral)
- Enable A/B testing different models

---

## Architecture Changes

### Component Diagram

```
┌─────────────────────────────────────────────────────┐
│              Persona Forge (Enhanced)                │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │  Crucible (Ingestion Engine)               │    │
│  │  + PersonalityScorer integration     [NEW] │    │
│  └────────────┬───────────────────────────────┘    │
│               │                                      │
│               ▼                                      │
│  ┌────────────────────────────────────────────┐    │
│  │  Assayer (Quality Analysis)                │    │
│  │  + Personality profile computation   [NEW] │    │
│  │  + Personality variance analysis     [NEW] │    │
│  │  + LLM baseline comparison           [NEW] │    │
│  └────────────┬───────────────────────────────┘    │
│               │                                      │
│               ▼                                      │
│  ┌────────────────────────────────────────────┐    │
│  │  Visualization Generator              [NEW] │    │
│  │  - Spider graph (dataset vs target)        │    │
│  │  - Box plot (variance analysis)            │    │
│  │  - Heatmap (source quality)                │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│        Configuration System (New)                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  config/training_targets.json                       │
│  - target_llm specification                         │
│  - personality_profile (VK targets)                 │
│  - llm_specific_adjustments                         │
│  - training_params (rank, alpha, etc.)              │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Data Flow

```
Input: Training examples from multiple sources
  ↓
[Crucible] Ingest + Score Personality
  ↓
TrainingExample {
  system_prompt,
  user_message,
  assistant_response,
  interaction_type,
  response_length_category,
  source_type,
  voice_markers,
  anti_patterns,
  lock_in,
  metadata,
  personality_scores: {         ← NEW
    warmth: 0.85,
    technical: 0.6,
    humor: 0.7,
    ...
  }
}
  ↓
[Assayer] Analyze Dataset
  ↓
DatasetAssay {
  ...(existing fields),
  personality_profile: {         ← NEW
    warmth: 0.82,
    technical: 0.68,
    ...
  },
  personality_variance: {        ← NEW
    warmth: 0.12,
    technical: 0.18,
    ...
  }
}
  ↓
[Reporter] Enhanced Report + Visualizations
  ↓
Output: 
  - Text report with personality section
  - personality_profile.html (spider graph)
  - personality_variance.html (box plot)
  - personality_sources.html (heatmap)
```

---

## Implementation Phases

### Phase 1: Personality Monitoring (Priority 1)
**Duration:** 2.5 hours  
**Agent:** Alpha (Core Changes)  
**Complexity:** Medium

**Deliverables:**
1. Updated `TrainingExample` model with `personality_scores`
2. PersonalityScorer integration in Crucible
3. Enhanced Assayer with personality analysis methods
4. Updated DatasetAssay model
5. Enhanced report formatting with personality section
6. CLI integration (`--with-personality` flag)
7. Tests for personality scoring

### Phase 2: Target LLM Selection (Priority 2)
**Duration:** 4 hours  
**Agent:** Beta (Configuration System)  
**Complexity:** Medium

**Deliverables:**
1. `config/training_targets.json` specification
2. LLM-specific baseline profiles
3. Configuration loading system
4. CLI integration (`--target-llm` flag)
5. Training pipeline integration
6. Documentation of LLM differences
7. Tests for configuration system

### Phase 3: Visualization Dashboard (Priority 3)
**Duration:** 3 hours  
**Agent:** Gamma (Visualization)  
**Complexity:** Low-Medium

**Deliverables:**
1. Visualization generation functions
2. HTML dashboard templates
3. Integration with Assayer
4. CLI integration (`--personality-viz` flag)
5. Example visualizations
6. Documentation

---

## Claude Flow Swarm Coordination

### Swarm Architecture

```yaml
swarm_name: "persona_forge_personality_enhancement"
coordination: "sequential_with_handoffs"
agents:
  - id: "alpha"
    role: "Core Integration"
    priority: 1
    dependencies: []
    
  - id: "beta"
    role: "Configuration System"
    priority: 2
    dependencies: ["alpha"]
    
  - id: "gamma"
    role: "Visualization"
    priority: 3
    dependencies: ["alpha", "beta"]
```

### Agent Alpha: Core Integration

**Responsibility:** Implement personality scoring in Persona Forge core

**Files to Modify:**
```
Tools/persona_forge/
├── engine/
│   ├── models.py          [MODIFY] Add personality_scores field
│   ├── crucible.py        [MODIFY] Add PersonalityScorer
│   └── assayer.py         [MODIFY] Add personality analysis
├── cli/
│   └── forge_cli.py       [MODIFY] Add --with-personality flag
└── tests/
    └── test_personality.py [CREATE] New test file
```

**Acceptance Criteria:**
- [ ] TrainingExample has `personality_scores: dict[str, float]` field
- [ ] Crucible scores personality during ingestion
- [ ] Assayer computes personality profile and variance
- [ ] Report includes personality section
- [ ] CLI accepts `--with-personality` flag
- [ ] All tests pass

**Estimated Time:** 2.5 hours

### Agent Beta: Configuration System

**Responsibility:** Implement target LLM selection and configuration

**Files to Create/Modify:**
```
Tools/persona_forge/
├── config/
│   ├── training_targets.json    [CREATE] LLM configs
│   └── config_loader.py         [CREATE] Config system
├── engine/
│   └── assayer.py               [MODIFY] LLM baseline comparison
└── cli/
    └── forge_cli.py             [MODIFY] Add --target-llm flag
```

**Acceptance Criteria:**
- [ ] training_targets.json defines 3+ LLM configs
- [ ] Configuration loader validates and loads configs
- [ ] Assayer compares against LLM-specific baselines
- [ ] CLI accepts `--target-llm` flag
- [ ] Config system is documented
- [ ] Tests for config loading

**Estimated Time:** 4 hours

### Agent Gamma: Visualization

**Responsibility:** Generate personality visualizations

**Files to Create/Modify:**
```
Tools/persona_forge/
├── visualization/
│   ├── __init__.py              [CREATE]
│   ├── personality_viz.py       [CREATE] Viz generation
│   └── templates/               [CREATE] HTML templates
│       ├── spider.html
│       ├── boxplot.html
│       └── heatmap.html
└── cli/
    └── forge_cli.py             [MODIFY] Add --personality-viz flag
```

**Acceptance Criteria:**
- [ ] Spider graph shows dataset vs target
- [ ] Box plot shows personality variance
- [ ] Heatmap shows source quality comparison
- [ ] HTML files generated correctly
- [ ] CLI accepts `--personality-viz` flag
- [ ] Example visualizations in docs

**Estimated Time:** 3 hours

### Handoff Protocol

**Alpha → Beta:**
```
Handoff Contents:
1. Updated models.py with personality_scores field
2. Working PersonalityScorer integration in Crucible
3. Enhanced Assayer with personality methods
4. Test suite passing
5. Documentation of personality scoring API

Beta Prerequisites:
- Alpha's changes merged and tested
- Personality profile computation working
- Report includes personality section
```

**Beta → Gamma:**
```
Handoff Contents:
1. Configuration system implemented
2. LLM-specific baselines defined
3. Config loader working
4. Assayer supports LLM comparison
5. Documentation of config format

Gamma Prerequisites:
- Beta's changes merged and tested
- Configuration loads correctly
- LLM baselines accessible
- DatasetAssay has personality data
```

### Parallel Work Opportunities

**Alpha can start immediately**

**Beta can work in parallel after Alpha completes models:**
- Create config/training_targets.json (no dependencies)
- Write config_loader.py (no dependencies)
- Document LLM differences (no dependencies)

**Gamma can prepare in parallel:**
- Set up visualization module structure
- Create HTML templates
- Write utility functions

---

## Detailed Specifications

### Spec 1: TrainingExample Model Enhancement

**File:** `engine/models.py`

```python
@dataclass
class TrainingExample:
    """Training example with personality scoring."""
    
    # Existing fields
    system_prompt: str
    user_message: str
    assistant_response: str
    interaction_type: InteractionType
    response_length_category: ResponseLength
    source_type: SourceType
    voice_markers: dict[str, bool]
    anti_patterns: dict[str, bool]
    lock_in: LockIn
    metadata: dict
    
    # NEW FIELD
    personality_scores: dict[str, float] | None = None
    """
    Personality scores across 8 dimensions (0-1).
    
    Keys:
    - warmth: Emotional engagement and care
    - technical: Domain expertise and jargon usage
    - humor: Levity and entertainment value
    - directness: Conciseness and clarity
    - creativity: Imagination and originality
    - reflection: Philosophical depth and introspection
    - relationship: Personal connection and history awareness
    - assertiveness: Boundary-setting and confidence
    
    Example:
    {
        "warmth": 0.85,
        "technical": 0.60,
        "humor": 0.70,
        "directness": 0.80,
        "creativity": 0.65,
        "reflection": 0.75,
        "relationship": 0.90,
        "assertiveness": 0.75
    }
    """
```

**Dependencies:**
- personality_visualization_suite.py (copy to Persona Forge)

**Tests:**
```python
def test_training_example_with_personality_scores():
    example = TrainingExample(
        system_prompt="You are Luna",
        user_message="Hi Luna!",
        assistant_response="Hey Ahab! How's it going?",
        interaction_type=InteractionType.GREETING,
        response_length_category=ResponseLength.SHORT,
        source_type=SourceType.MANUAL,
        voice_markers={},
        anti_patterns={},
        lock_in=LockIn(coefficient=0.8, tier=QualityTier.GOLD),
        metadata={},
        personality_scores={
            "warmth": 0.85,
            "technical": 0.30,
            "humor": 0.60,
            "directness": 0.70,
            "creativity": 0.50,
            "reflection": 0.40,
            "relationship": 0.90,
            "assertiveness": 0.60,
        }
    )
    
    assert example.personality_scores is not None
    assert len(example.personality_scores) == 8
    assert 0 <= example.personality_scores["warmth"] <= 1
```

### Spec 2: Crucible Enhancement

**File:** `engine/crucible.py`

```python
from personality_visualization_suite import PersonalityScorer

class Crucible:
    """Ingestion engine with personality scoring."""
    
    def __init__(self):
        self.examples: list[TrainingExample] = []
        self.stats = {
            "ingested": 0,
            "deduplicated": 0,
            "sources": {},
        }
        self.deduplication_cache: set[str] = set()
        
        # NEW: Personality scorer
        self.personality_scorer = PersonalityScorer()
        print("✓ PersonalityScorer initialized")
    
    def _create_training_example(
        self,
        system_prompt: str,
        user_message: str,
        assistant_response: str,
        interaction_type: InteractionType,
        response_length_category: ResponseLength,
        source_type: SourceType,
        voice_markers: dict[str, bool],
        anti_patterns: dict[str, bool],
        metadata: dict,
    ) -> TrainingExample:
        """Create training example with personality scoring."""
        
        # NEW: Score personality
        personality_scores = self.personality_scorer.score_response(
            assistant_response
        )
        
        # Compute lock-in
        lock_in = self._compute_lock_in(
            interaction_type=interaction_type,
            response_length=response_length_category,
            voice_markers=voice_markers,
            anti_patterns=anti_patterns,
        )
        
        return TrainingExample(
            system_prompt=system_prompt,
            user_message=user_message,
            assistant_response=assistant_response,
            interaction_type=interaction_type,
            response_length_category=response_length_category,
            source_type=source_type,
            voice_markers=voice_markers,
            anti_patterns=anti_patterns,
            lock_in=lock_in,
            metadata=metadata,
            personality_scores=personality_scores,  # NEW
        )
```

**Performance Impact:**
- PersonalityScorer: ~1ms per response
- Negligible compared to existing processing
- Can be disabled with flag if needed

**Tests:**
```python
def test_crucible_scores_personality():
    crucible = Crucible()
    
    # Create example
    example = crucible._create_training_example(
        system_prompt="You are Luna",
        user_message="Hi",
        assistant_response="Hey! Great to see you.",
        interaction_type=InteractionType.GREETING,
        response_length_category=ResponseLength.SHORT,
        source_type=SourceType.MANUAL,
        voice_markers={},
        anti_patterns={},
        metadata={},
    )
    
    # Verify personality scored
    assert example.personality_scores is not None
    assert "warmth" in example.personality_scores
    assert example.personality_scores["warmth"] > 0.7  # Warm greeting
```

### Spec 3: Assayer Enhancement

**File:** `engine/assayer.py`

```python
class Assayer:
    """Dataset quality analyzer with personality analysis."""
    
    def __init__(self, target_profile: dict[str, float] = None):
        """
        Initialize assayer.
        
        Args:
            target_profile: Target personality profile (from VK spec)
                           Default: Luna's target personality
        """
        if target_profile is None:
            # Default Luna target
            target_profile = {
                "warmth": 0.85,
                "technical": 0.70,
                "humor": 0.65,
                "directness": 0.80,
                "creativity": 0.70,
                "reflection": 0.75,
                "relationship": 0.90,
                "assertiveness": 0.75,
            }
        
        self.target_profile = target_profile
    
    def analyze(
        self,
        examples: list[TrainingExample]
    ) -> DatasetAssay:
        """Perform full dataset analysis including personality."""
        
        # Existing analysis
        total_examples = len(examples)
        interaction_type_dist = self._compute_type_distribution(examples)
        response_length_dist = self._compute_length_distribution(examples)
        source_type_dist = self._compute_source_distribution(examples)
        quality_tier_dist = self._compute_quality_distribution(examples)
        voice_marker_rates = self._compute_voice_markers(examples)
        anti_pattern_rates = self._compute_anti_patterns(examples)
        
        # Lock-in statistics
        lock_ins = [e.lock_in.coefficient for e in examples]
        avg_lock_in = np.mean(lock_ins)
        lock_in_std = np.std(lock_ins)
        lock_in_min = np.min(lock_ins)
        lock_in_max = np.max(lock_ins)
        
        # Gap analysis
        gaps = self._identify_gaps(examples)
        synthesis_targets = self._compute_synthesis_targets(gaps)
        
        # Health score
        health_breakdown = self._compute_health_breakdown(
            examples,
            interaction_type_dist,
            response_length_dist,
            quality_tier_dist,
            voice_marker_rates,
            anti_pattern_rates,
        )
        health_score = np.mean(list(health_breakdown.values()))
        
        # NEW: Personality analysis
        personality_profile = self._compute_personality_profile(examples)
        personality_variance = self._compute_personality_variance(examples)
        personality_alignment = self._compute_personality_alignment(
            personality_profile
        )
        
        return DatasetAssay(
            total_examples=total_examples,
            interaction_type_dist=interaction_type_dist,
            response_length_dist=response_length_dist,
            source_type_dist=source_type_dist,
            quality_tier_dist=quality_tier_dist,
            voice_marker_rates=voice_marker_rates,
            anti_pattern_rates=anti_pattern_rates,
            avg_lock_in=avg_lock_in,
            lock_in_std=lock_in_std,
            lock_in_min=lock_in_min,
            lock_in_max=lock_in_max,
            gaps=gaps,
            synthesis_targets=synthesis_targets,
            health_score=health_score,
            health_breakdown=health_breakdown,
            personality_profile=personality_profile,          # NEW
            personality_variance=personality_variance,        # NEW
            personality_alignment=personality_alignment,      # NEW
        )
    
    def _compute_personality_profile(
        self,
        examples: list[TrainingExample]
    ) -> dict[str, float]:
        """Compute average personality across dataset."""
        
        # Filter examples with personality scores
        scored_examples = [
            e for e in examples
            if e.personality_scores is not None
        ]
        
        if not scored_examples:
            return {}
        
        # Get dimensions from first example
        dimensions = list(scored_examples[0].personality_scores.keys())
        
        # Average each dimension
        profile = {}
        for dim in dimensions:
            scores = [
                e.personality_scores[dim]
                for e in scored_examples
            ]
            profile[dim] = float(np.mean(scores))
        
        return profile
    
    def _compute_personality_variance(
        self,
        examples: list[TrainingExample]
    ) -> dict[str, float]:
        """Compute personality variance (standard deviation)."""
        
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
            ]
            variance[dim] = float(np.std(scores))
        
        return variance
    
    def _compute_personality_alignment(
        self,
        profile: dict[str, float]
    ) -> float:
        """
        Compute alignment with target profile (0-1).
        
        Uses weighted euclidean distance converted to alignment score.
        1.0 = perfect alignment, 0.0 = maximum distance.
        """
        if not profile:
            return 0.0
        
        # Compute squared differences
        squared_diffs = []
        for dim, target_score in self.target_profile.items():
            if dim in profile:
                diff = profile[dim] - target_score
                squared_diffs.append(diff ** 2)
        
        if not squared_diffs:
            return 0.0
        
        # Mean squared error
        mse = np.mean(squared_diffs)
        
        # Convert to alignment (1 = perfect, 0 = max distance)
        max_distance = 1.0
        alignment = 1.0 - min(1.0, np.sqrt(mse) / max_distance)
        
        return alignment
```

**Tests:**
```python
def test_assayer_computes_personality_profile():
    examples = [
        create_test_example(
            response="Hey! Great to see you!",
            # Should have high warmth
        ),
        create_test_example(
            response="The algorithm complexity is O(n log n).",
            # Should have high technical
        ),
    ]
    
    assayer = Assayer()
    assay = assayer.analyze(examples)
    
    assert assay.personality_profile is not None
    assert "warmth" in assay.personality_profile
    assert "technical" in assay.personality_profile
    assert 0 <= assay.personality_profile["warmth"] <= 1
```

### Spec 4: DatasetAssay Model Enhancement

**File:** `engine/models.py`

```python
@dataclass
class DatasetAssay:
    """Dataset quality analysis results."""
    
    # Existing fields
    total_examples: int
    interaction_type_dist: dict[str, float]
    response_length_dist: dict[str, float]
    source_type_dist: dict[str, float]
    quality_tier_dist: dict[str, float]
    voice_marker_rates: dict[str, float]
    anti_pattern_rates: dict[str, float]
    avg_lock_in: float
    lock_in_std: float
    lock_in_min: float
    lock_in_max: float
    gaps: dict[str, int]
    synthesis_targets: dict[str, int]
    health_score: float
    health_breakdown: dict[str, float]
    
    # NEW FIELDS
    personality_profile: dict[str, float] | None = None
    """
    Average personality across dataset.
    Keys: warmth, technical, humor, directness, creativity,
          reflection, relationship, assertiveness
    Values: 0-1 scores
    """
    
    personality_variance: dict[str, float] | None = None
    """
    Standard deviation of personality scores.
    Keys: Same as personality_profile
    Values: Standard deviations
    """
    
    personality_alignment: float | None = None
    """
    Alignment with target personality (0-1).
    1.0 = perfect alignment, 0.0 = maximum distance
    """
```

### Spec 5: Enhanced Report Formatting

**File:** `engine/assayer.py`

```python
def format_report(self, assay: DatasetAssay) -> str:
    """Format assay as readable report."""
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("PERSONA FORGE - DATASET ASSAY REPORT")
    lines.append("=" * 80)
    lines.append("")
    
    # ... existing sections ...
    
    # NEW: Personality Section
    if assay.personality_profile:
        lines.append("─" * 80)
        lines.append("PERSONALITY PROFILE")
        lines.append("─" * 80)
        lines.append("")
        
        # Overall alignment
        if assay.personality_alignment is not None:
            alignment_pct = assay.personality_alignment * 100
            status = "✓" if alignment_pct >= 85 else "✗"
            lines.append(
                f"{status} Overall Alignment: {alignment_pct:.1f}% "
                f"(target: ≥85%)"
            )
            lines.append("")
        
        # Dimension breakdown
        lines.append("Dimension Scores:")
        for dim, score in assay.personality_profile.items():
            target = self.target_profile.get(dim, 0.7)
            variance = assay.personality_variance.get(dim, 0)
            diff = score - target
            
            # Status indicator
            if abs(diff) < 0.05:
                status = "✓✓"  # Perfect
            elif abs(diff) < 0.10:
                status = "✓"   # Good
            else:
                status = "✗"   # Gap
            
            # Visual bar
            bar_length = int(score * 50)
            bar = "█" * bar_length + "░" * (50 - bar_length)
            
            # Diff indicator
            diff_str = f"{diff:+.2f}" if diff != 0 else " 0.00"
            diff_color = "↑" if diff > 0 else "↓" if diff < 0 else "="
            
            lines.append(
                f"  {status} {dim:15s} [{bar}] "
                f"{score:.2f} ±{variance:.2f} "
                f"| target: {target:.2f} | {diff_color} {diff_str}"
            )
        
        lines.append("")
        
        # Recommendations
        lines.append("Recommendations:")
        gaps_found = False
        for dim, score in assay.personality_profile.items():
            target = self.target_profile.get(dim, 0.7)
            diff = score - target
            
            if abs(diff) >= 0.10:
                gaps_found = True
                if diff < 0:
                    lines.append(
                        f"  • Add examples with higher {dim} "
                        f"(need +{abs(diff):.2f})"
                    )
                else:
                    lines.append(
                        f"  • Reduce examples with high {dim} "
                        f"(need {diff:.2f})"
                    )
        
        if not gaps_found:
            lines.append("  ✓ Personality profile well-aligned with target")
        
        lines.append("")
    
    # ... rest of report ...
    
    return "\n".join(lines)
```

**Example Output:**
```
════════════════════════════════════════════════════════════════════════════════
PERSONA FORGE - DATASET ASSAY REPORT
════════════════════════════════════════════════════════════════════════════════

Total Examples: 847
Sources: 4 (Memory Matrix, Sessions, Conversations, Alpha Notes)
Health Score: 82.3/100

────────────────────────────────────────────────────────────────────────────────
PERSONALITY PROFILE
────────────────────────────────────────────────────────────────────────────────

✓ Overall Alignment: 88.5% (target: ≥85%)

Dimension Scores:
  ✓✓ warmth          [████████████████████████████████████████████░░] 0.84 ±0.12 | target: 0.85 | ↓ -0.01
  ✗  technical       [██████████████████████████░░░░░░░░░░░░░░░░░░░░] 0.54 ±0.18 | target: 0.70 | ↓ -0.16
  ✓  humor           [████████████████████████████████░░░░░░░░░░░░░░] 0.68 ±0.15 | target: 0.65 | ↑ +0.03
  ✓  directness      [████████████████████████████████████████░░░░░░] 0.82 ±0.14 | target: 0.80 | ↑ +0.02
  ✓✓ creativity      [███████████████████████████████████░░░░░░░░░░░] 0.71 ±0.16 | target: 0.70 | ↑ +0.01
  ✓  reflection      [█████████████████████████████████████░░░░░░░░░] 0.76 ±0.13 | target: 0.75 | ↑ +0.01
  ✓  relationship    [███████████████████████████████████████████░░░] 0.88 ±0.10 | target: 0.90 | ↓ -0.02
  ✓  assertiveness   [██████████████████████████████████████░░░░░░░░] 0.77 ±0.14 | target: 0.75 | ↑ +0.02

Recommendations:
  • Add examples with higher technical (need +0.16)

────────────────────────────────────────────────────────────────────────────────
```

### Spec 6: CLI Integration

**File:** `cli/forge_cli.py`

```python
def main():
    parser = argparse.ArgumentParser(
        description="Persona Forge - Training Data Pipeline"
    )
    subparsers = parser.add_subparsers(dest="command")
    
    # Assay command
    assay_parser = subparsers.add_parser(
        "assay",
        help="Analyze dataset quality"
    )
    assay_parser.add_argument(
        "path",
        help="Path to JSONL dataset"
    )
    assay_parser.add_argument(
        "--with-personality",
        action="store_true",
        help="Include personality analysis (scores all examples)"
    )
    assay_parser.add_argument(
        "--personality-viz",
        action="store_true",
        help="Generate personality visualizations (requires --with-personality)"
    )
    assay_parser.add_argument(
        "--target-llm",
        default="qwen2.5-7b-instruct",
        help="Target LLM for personality baseline (default: qwen2.5-7b-instruct)"
    )
    
    # ... other commands ...
    
    args = parser.parse_args()
    
    if args.command == "assay":
        run_assay(args)
    # ... other commands ...

def run_assay(args):
    """Run full dataset assay with optional personality analysis."""
    
    # Load configuration
    if args.target_llm:
        config = load_training_config(args.target_llm)
        target_profile = config["personality_profile"]
        print(f"Target LLM: {args.target_llm}")
    else:
        target_profile = None
    
    # Create components
    crucible = Crucible()
    assayer = Assayer(target_profile=target_profile)
    
    print(f"Loading: {args.path}")
    examples = crucible.ingest_jsonl(Path(args.path))
    print(f"✓ Loaded {len(examples)} examples")
    
    if args.with_personality:
        print("\n✓ Personality scoring enabled (automatic during ingestion)")
    
    print("\nAnalyzing...")
    assay = assayer.analyze(examples)
    
    # Print report
    print("\n" + assayer.format_report(assay))
    
    # Generate visualizations
    if args.with_personality and args.personality_viz:
        print("\nGenerating personality visualizations...")
        generate_personality_visualizations(examples, assay, args.target_llm)
```

**Usage Examples:**
```bash
# Basic assay
python forge_cli.py assay luna_dataset.jsonl

# With personality analysis
python forge_cli.py assay luna_dataset.jsonl --with-personality

# With visualizations
python forge_cli.py assay luna_dataset.jsonl \
  --with-personality \
  --personality-viz

# Target specific LLM
python forge_cli.py assay luna_dataset.jsonl \
  --with-personality \
  --target-llm llama-3-8b-instruct
```

### Spec 7: Configuration System

**File:** `config/training_targets.json`

```json
{
  "qwen2.5-7b-instruct": {
    "model_path": "Qwen/Qwen2.5-7B-Instruct",
    "personality_profile": {
      "warmth": 0.85,
      "technical": 0.70,
      "humor": 0.65,
      "directness": 0.80,
      "creativity": 0.70,
      "reflection": 0.75,
      "relationship": 0.90,
      "assertiveness": 0.75
    },
    "base_personality": {
      "warmth": 0.70,
      "technical": 0.80,
      "note": "Qwen is naturally technical, needs warmth boost"
    },
    "training_params": {
      "rank": 16,
      "alpha": 32,
      "learning_rate": 2e-4,
      "epochs": 3,
      "batch_size": 4,
      "gradient_accumulation": 4
    }
  },
  
  "llama-3-8b-instruct": {
    "model_path": "meta-llama/Meta-Llama-3-8B-Instruct",
    "personality_profile": {
      "warmth": 0.85,
      "technical": 0.70,
      "humor": 0.65,
      "directness": 0.80,
      "creativity": 0.70,
      "reflection": 0.75,
      "relationship": 0.90,
      "assertiveness": 0.75
    },
    "base_personality": {
      "warmth": 0.80,
      "technical": 0.60,
      "note": "Llama is naturally warm, needs technical boost"
    },
    "training_params": {
      "rank": 16,
      "alpha": 32,
      "learning_rate": 2e-4,
      "epochs": 3,
      "batch_size": 4,
      "gradient_accumulation": 4
    }
  },
  
  "mistral-7b-instruct": {
    "model_path": "mistralai/Mistral-7B-Instruct-v0.2",
    "personality_profile": {
      "warmth": 0.85,
      "technical": 0.70,
      "humor": 0.65,
      "directness": 0.80,
      "creativity": 0.70,
      "reflection": 0.75,
      "relationship": 0.90,
      "assertiveness": 0.75
    },
    "base_personality": {
      "warmth": 0.60,
      "technical": 0.70,
      "note": "Mistral is neutral, balanced training"
    },
    "training_params": {
      "rank": 16,
      "alpha": 32,
      "learning_rate": 2e-4,
      "epochs": 3,
      "batch_size": 4,
      "gradient_accumulation": 4
    }
  }
}
```

**File:** `config/config_loader.py`

```python
import json
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    """Load and validate training target configurations."""
    
    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = Path(__file__).parent / "training_targets.json"
        
        self.config_path = config_path
        self._configs = self._load_configs()
    
    def _load_configs(self) -> Dict[str, Any]:
        """Load configurations from JSON file."""
        with open(self.config_path, 'r') as f:
            configs = json.load(f)
        
        # Validate
        for llm_name, config in configs.items():
            self._validate_config(llm_name, config)
        
        return configs
    
    def _validate_config(self, llm_name: str, config: Dict[str, Any]):
        """Validate configuration structure."""
        required_fields = [
            "model_path",
            "personality_profile",
            "base_personality",
            "training_params"
        ]
        
        for field in required_fields:
            if field not in config:
                raise ValueError(
                    f"Config for {llm_name} missing required field: {field}"
                )
        
        # Validate personality profile
        required_dims = [
            "warmth", "technical", "humor", "directness",
            "creativity", "reflection", "relationship", "assertiveness"
        ]
        
        profile = config["personality_profile"]
        for dim in required_dims:
            if dim not in profile:
                raise ValueError(
                    f"Config for {llm_name} personality_profile "
                    f"missing dimension: {dim}"
                )
            
            if not 0 <= profile[dim] <= 1:
                raise ValueError(
                    f"Config for {llm_name} personality_profile[{dim}] "
                    f"out of range: {profile[dim]} (must be 0-1)"
                )
    
    def get_config(self, llm_name: str) -> Dict[str, Any]:
        """Get configuration for specific LLM."""
        if llm_name not in self._configs:
            available = list(self._configs.keys())
            raise ValueError(
                f"Unknown LLM: {llm_name}. "
                f"Available: {', '.join(available)}"
            )
        
        return self._configs[llm_name]
    
    def list_llms(self) -> list[str]:
        """List available LLM configurations."""
        return list(self._configs.keys())
    
    def get_personality_profile(self, llm_name: str) -> Dict[str, float]:
        """Get target personality profile for LLM."""
        config = self.get_config(llm_name)
        return config["personality_profile"]
    
    def get_base_personality(self, llm_name: str) -> Dict[str, Any]:
        """Get base personality characteristics for LLM."""
        config = self.get_config(llm_name)
        return config["base_personality"]
    
    def get_training_params(self, llm_name: str) -> Dict[str, Any]:
        """Get training parameters for LLM."""
        config = self.get_config(llm_name)
        return config["training_params"]

# Convenience function
def load_training_config(llm_name: str) -> Dict[str, Any]:
    """Load training configuration for specific LLM."""
    loader = ConfigLoader()
    return loader.get_config(llm_name)
```

### Spec 8: Visualization Generation

**File:** `visualization/personality_viz.py`

```python
from pathlib import Path
from typing import List, Dict
from persona_forge.engine.models import TrainingExample, DatasetAssay
from personality_visualization_suite import (
    PersonalityMonitor,
    PersonalityVisualizer,
    TARGET_PROFILE
)

def generate_personality_visualizations(
    examples: List[TrainingExample],
    assay: DatasetAssay,
    target_llm: str = "qwen2.5-7b-instruct",
    output_dir: Path = None
):
    """
    Generate personality visualizations for dataset.
    
    Args:
        examples: Training examples with personality scores
        assay: Dataset assay results
        target_llm: Target LLM name
        output_dir: Output directory (default: current directory)
    
    Outputs:
        - persona_forge_spider.html (dataset vs target)
        - persona_forge_variance.html (box plot)
        - persona_forge_sources.html (heatmap)
    """
    if output_dir is None:
        output_dir = Path.cwd()
    
    # Create monitor and populate
    monitor = PersonalityMonitor()
    
    for example in examples:
        if example.personality_scores:
            # Create snapshot from example
            monitor.record_response(
                response=example.assistant_response,
                lora_config={
                    "active": "training_data",
                    "source": example.source_type.value
                },
                query_type=example.interaction_type.value
            )
    
    # Create visualizer
    viz = PersonalityVisualizer(monitor)
    
    # 1. Spider Graph (dataset vs target)
    profiles = {
        "Training Dataset": assay.personality_profile,
        f"Target ({target_llm})": TARGET_PROFILE,
    }
    
    fig = viz.spider_graph(
        profiles,
        title=f"Personality Profile: Dataset vs Target ({target_llm})",
        show_target=True
    )
    
    output_path = output_dir / "persona_forge_spider.html"
    fig.write_html(str(output_path))
    print(f"✓ Saved {output_path}")
    
    # 2. Box Plot (variance analysis)
    fig = viz.box_plot(days=365)  # All data
    fig.update_layout(
        title="Personality Variance Across Dataset"
    )
    
    output_path = output_dir / "persona_forge_variance.html"
    fig.write_html(str(output_path))
    print(f"✓ Saved {output_path}")
    
    # 3. Heatmap (source quality comparison)
    # Group by source
    source_profiles = {}
    for source_type in set(e.source_type for e in examples):
        source_name = source_type.value
        source_profile = monitor.get_profile(
            lora_name=source_name
        )
        if source_profile:
            source_profiles[source_name] = source_profile
    
    if source_profiles:
        fig = viz.spider_graph(
            source_profiles,
            title="Personality by Source",
            show_target=False
        )
        
        output_path = output_dir / "persona_forge_sources.html"
        fig.write_html(str(output_path))
        print(f"✓ Saved {output_path}")
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_personality_integration.py`

```python
import pytest
from persona_forge.engine.models import *
from persona_forge.engine.crucible import Crucible
from persona_forge.engine.assayer import Assayer

class TestPersonalityScoring:
    """Test personality scoring integration."""
    
    def test_crucible_scores_personality(self):
        """Verify Crucible scores personality during ingestion."""
        crucible = Crucible()
        
        example = crucible._create_training_example(
            system_prompt="You are Luna",
            user_message="Hi Luna!",
            assistant_response="Hey Ahab! Great to see you!",
            interaction_type=InteractionType.GREETING,
            response_length_category=ResponseLength.SHORT,
            source_type=SourceType.MANUAL,
            voice_markers={},
            anti_patterns={},
            metadata={},
        )
        
        assert example.personality_scores is not None
        assert len(example.personality_scores) == 8
        assert "warmth" in example.personality_scores
        assert 0 <= example.personality_scores["warmth"] <= 1
    
    def test_assayer_computes_personality_profile(self):
        """Verify Assayer computes personality profile."""
        # Create test examples
        examples = self._create_test_examples()
        
        assayer = Assayer()
        assay = assayer.analyze(examples)
        
        assert assay.personality_profile is not None
        assert len(assay.personality_profile) == 8
        assert assay.personality_variance is not None
        assert assay.personality_alignment is not None
        assert 0 <= assay.personality_alignment <= 1
    
    def test_personality_scoring_disabled_gracefully(self):
        """Verify system works when personality scores are None."""
        examples = [
            TrainingExample(
                system_prompt="test",
                user_message="test",
                assistant_response="test",
                interaction_type=InteractionType.GREETING,
                response_length_category=ResponseLength.SHORT,
                source_type=SourceType.MANUAL,
                voice_markers={},
                anti_patterns={},
                lock_in=LockIn(coefficient=0.8, tier=QualityTier.GOLD),
                metadata={},
                personality_scores=None,  # No scores
            )
        ]
        
        assayer = Assayer()
        assay = assayer.analyze(examples)
        
        # Should handle gracefully
        assert assay.personality_profile == {}
        assert assay.personality_variance == {}
    
    def _create_test_examples(self) -> list[TrainingExample]:
        """Create test examples with known personalities."""
        crucible = Crucible()
        
        return [
            crucible._create_training_example(
                system_prompt="You are Luna",
                user_message="Hi",
                assistant_response="Hey! Great to see you!",
                interaction_type=InteractionType.GREETING,
                response_length_category=ResponseLength.SHORT,
                source_type=SourceType.MANUAL,
                voice_markers={},
                anti_patterns={},
                metadata={},
            ),
            crucible._create_training_example(
                system_prompt="You are Luna",
                user_message="Explain sorting",
                assistant_response="The algorithm uses O(n log n) quicksort.",
                interaction_type=InteractionType.TECHNICAL,
                response_length_category=ResponseLength.MEDIUM,
                source_type=SourceType.MEMORY_MATRIX,
                voice_markers={},
                anti_patterns={},
                metadata={},
            ),
        ]

class TestConfigurationSystem:
    """Test configuration loading and validation."""
    
    def test_load_valid_config(self):
        """Verify configuration loads correctly."""
        from persona_forge.config.config_loader import load_training_config
        
        config = load_training_config("qwen2.5-7b-instruct")
        
        assert "model_path" in config
        assert "personality_profile" in config
        assert "training_params" in config
    
    def test_config_validation(self):
        """Verify invalid configs are rejected."""
        from persona_forge.config.config_loader import ConfigLoader
        
        # Invalid config (missing dimension)
        invalid_config = {
            "model_path": "test",
            "personality_profile": {
                "warmth": 0.8,
                # Missing other dimensions
            },
            "base_personality": {},
            "training_params": {}
        }
        
        loader = ConfigLoader()
        with pytest.raises(ValueError):
            loader._validate_config("test", invalid_config)
```

### Integration Tests

**File:** `tests/test_end_to_end.py`

```python
def test_full_pipeline_with_personality():
    """Test complete pipeline from ingestion to visualization."""
    
    # 1. Ingest examples
    crucible = Crucible()
    examples = crucible.ingest_jsonl(Path("test_dataset.jsonl"))
    
    assert len(examples) > 0
    assert all(e.personality_scores is not None for e in examples)
    
    # 2. Analyze
    assayer = Assayer()
    assay = assayer.analyze(examples)
    
    assert assay.personality_profile is not None
    assert assay.personality_alignment > 0
    
    # 3. Generate report
    report = assayer.format_report(assay)
    
    assert "PERSONALITY PROFILE" in report
    assert "Overall Alignment" in report
    
    # 4. Generate visualizations
    from persona_forge.visualization.personality_viz import (
        generate_personality_visualizations
    )
    
    output_dir = Path("/tmp/persona_forge_test")
    output_dir.mkdir(exist_ok=True)
    
    generate_personality_visualizations(
        examples,
        assay,
        "qwen2.5-7b-instruct",
        output_dir
    )
    
    assert (output_dir / "persona_forge_spider.html").exists()
    assert (output_dir / "persona_forge_variance.html").exists()
```

---

## Validation Criteria

### Phase 1: Core Integration

**Must Have:**
- [ ] PersonalityScorer correctly integrated into Crucible
- [ ] All TrainingExamples have personality_scores field populated
- [ ] Assayer computes personality_profile correctly
- [ ] Assayer computes personality_variance correctly
- [ ] Assayer computes personality_alignment correctly
- [ ] Report includes personality section with visual bars
- [ ] CLI accepts `--with-personality` flag
- [ ] All existing tests still pass
- [ ] New personality tests pass

**Performance:**
- [ ] Scoring adds <2ms per example
- [ ] Total ingestion time increases <10%
- [ ] Memory usage increases <5%

**Quality:**
- [ ] Personality scores correlate with manual ratings (r > 0.75)
- [ ] Variance calculations match numpy std
- [ ] Alignment formula matches spec

### Phase 2: Configuration System

**Must Have:**
- [ ] training_targets.json defines 3+ LLM configs
- [ ] ConfigLoader validates all fields
- [ ] ConfigLoader rejects invalid configs
- [ ] CLI accepts `--target-llm` flag
- [ ] Assayer uses correct target profile per LLM
- [ ] Report shows LLM-specific baseline comparison

**Quality:**
- [ ] All configs validate correctly
- [ ] Error messages are clear and actionable
- [ ] Documentation explains each LLM's characteristics

### Phase 3: Visualization

**Must Have:**
- [ ] Spider graph generates correctly
- [ ] Box plot generates correctly
- [ ] Source heatmap generates correctly
- [ ] HTML files render in browser
- [ ] CLI accepts `--personality-viz` flag
- [ ] Visualizations match data in assay

**Quality:**
- [ ] Graphs are readable and aesthetic
- [ ] Interactive features work (hover, zoom)
- [ ] Colors distinguish clearly
- [ ] Labels are accurate

---

## Deployment

### File Structure

```
Tools/persona_forge/
├── config/
│   ├── __init__.py
│   ├── training_targets.json       [NEW]
│   └── config_loader.py            [NEW]
├── engine/
│   ├── __init__.py
│   ├── models.py                   [MODIFIED]
│   ├── crucible.py                 [MODIFIED]
│   ├── assayer.py                  [MODIFIED]
│   └── locksmith.py
├── visualization/
│   ├── __init__.py                 [NEW]
│   └── personality_viz.py          [NEW]
├── cli/
│   └── forge_cli.py                [MODIFIED]
├── tests/
│   ├── test_personality_integration.py  [NEW]
│   └── test_end_to_end.py               [NEW]
├── personality_visualization_suite.py   [COPY FROM OUTPUTS]
├── README.md                            [UPDATE]
└── requirements.txt                     [UPDATE]
```

### Dependencies

**Add to requirements.txt:**
```
plotly>=5.18.0
networkx>=3.2
scipy>=1.11.4
```

### Installation

```bash
cd Tools/persona_forge

# Install dependencies
pip install -r requirements.txt --break-system-packages

# Run tests
python -m pytest tests/

# Verify CLI
python forge_cli.py --help
```

### Migration Path

**Step 1: Copy Dependencies**
```bash
# Copy personality visualization suite
cp /path/to/personality_visualization_suite.py \
   Tools/persona_forge/personality_visualization_suite.py
```

**Step 2: Apply Changes**
```bash
# Agent Alpha applies Phase 1 changes
# Agent Beta applies Phase 2 changes
# Agent Gamma applies Phase 3 changes
```

**Step 3: Test**
```bash
# Run test suite
python -m pytest tests/ -v

# Run manual test
python forge_cli.py assay test_data.jsonl \
  --with-personality \
  --personality-viz
```

**Step 4: Documentation**
```bash
# Update README with new features
# Add examples to docs/
# Update CHANGELOG
```

---

## Appendix

### A. Quick Reference

**Commands:**
```bash
# Basic assay (no personality)
python forge_cli.py assay dataset.jsonl

# With personality analysis
python forge_cli.py assay dataset.jsonl --with-personality

# With visualizations
python forge_cli.py assay dataset.jsonl \
  --with-personality \
  --personality-viz

# Target specific LLM
python forge_cli.py assay dataset.jsonl \
  --with-personality \
  --target-llm llama-3-8b-instruct
```

**Configuration:**
```python
# Load config
from persona_forge.config.config_loader import load_training_config

config = load_training_config("qwen2.5-7b-instruct")
target_profile = config["personality_profile"]
training_params = config["training_params"]
```

**Programmatic Usage:**
```python
from persona_forge.engine.crucible import Crucible
from persona_forge.engine.assayer import Assayer

# Ingest with personality scoring
crucible = Crucible()
examples = crucible.ingest_jsonl(Path("dataset.jsonl"))

# Analyze
assayer = Assayer(target_profile=custom_profile)
assay = assayer.analyze(examples)

# Check alignment
if assay.personality_alignment >= 0.85:
    print("✓ Dataset ready for training")
else:
    print("✗ Personality gaps detected")
```

### B. Personality Dimensions Reference

| Dimension | Description | Markers | Target |
|-----------|-------------|---------|--------|
| Warmth | Emotional engagement | appreciate, glad, happy, care | 0.85 |
| Technical | Domain expertise | algorithm, function, optimize | 0.70 |
| Humor | Playfulness | lol, haha, joke, wild | 0.65 |
| Directness | Conciseness | Short responses, no hedging | 0.80 |
| Creativity | Imagination | metaphors, "like a", "imagine" | 0.70 |
| Reflection | Philosophy | wonder, think about, consciousness | 0.75 |
| Relationship | Personal connection | Ahab mentions, "we", "our" | 0.90 |
| Assertiveness | Boundaries | "I can't", "no", clear limits | 0.75 |

### C. Troubleshooting

**Issue:** Personality scores are all None
```
Solution: Verify PersonalityScorer is imported and initialized in Crucible
Check: crucible.personality_scorer should not be None
```

**Issue:** Alignment score too low
```
Solution: Check personality_profile vs target_profile
Action: Run with --personality-viz to see gaps visually
Generate: More examples in low-scoring dimensions
```

**Issue:** Visualization generation fails
```
Solution: Verify plotly is installed
Check: pip list | grep plotly
Install: pip install plotly --break-system-packages
```

**Issue:** Config validation fails
```
Solution: Check training_targets.json format
Verify: All required fields present
Verify: All scores in 0-1 range
```

### D. Performance Benchmarks

**Scoring Performance:**
- Per example: ~1ms
- 1000 examples: ~1 second
- Negligible compared to model inference

**Visualization Generation:**
- Spider graph: ~50ms
- Box plot: ~100ms
- Heatmap: ~150ms
- Total: <500ms for all three

**Memory Usage:**
- PersonalityScorer: ~1KB
- Scores per example: ~200 bytes
- 10K examples: ~2MB additional

### E. Future Enhancements

**Phase 4 (Optional):**
- Real-time monitoring dashboard
- Automated gap detection and synthesis
- Historical trend analysis
- A/B testing framework
- Multi-user personality branching

**Phase 5 (Optional):**
- Integration with Voight-Kampff
- Automated training pipeline
- Continuous learning system
- Personality version control

---

## Contact & Support

**Primary Architect:** Ahab (Zayne Mason)  
**Documentation:** This handoff + inline code comments  
**Issues:** Check tests first, then review specs  
**Questions:** Reference personality_visualization_suite.py for scoring logic

---

**END OF HANDOFF**

**Status:** Ready for Implementation  
**Approved By:** Ahab  
**Date:** January 29, 2026  
**Version:** 1.0
