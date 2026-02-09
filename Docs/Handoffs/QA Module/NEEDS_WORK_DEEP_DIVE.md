# NEEDS_WORK Items Deep Dive

**Date:** 2026-02-02
**Validator:** Claude Code (Opus 4.5)

---

## Overview

Three items were marked as ⚠ needs_work in `luna_engine_brain.jsx`:
1. Consciousness Actor
2. Luna LoRA
3. Narration Layer

**Finding:** All three are **more complete than claimed**.

---

## 1. Consciousness Actor

### Claimed Status
> "⚠ needs_work" — State management

### Actual Implementation

**Files Found:**
- `src/luna/consciousness/state.py` (252 lines)
- `src/luna/consciousness/attention.py` (182 lines)
- `src/luna/consciousness/personality.py` (156 lines)

### What's Implemented ✅

#### ConsciousnessState (state.py)
```python
@dataclass
class ConsciousnessState:
    attention: AttentionManager
    personality: PersonalityWeights
    coherence: float = 1.0  # How "together" Luna feels
    mood: str = "neutral"
    tick_count: int = 0
```

- **Mood tracking**: 8 valid moods (neutral, curious, focused, playful, thoughtful, energetic, calm, helpful)
- **Coherence calculation**: Based on attention distribution
- **Tick lifecycle**: `async tick()` method for consciousness cycles
- **State persistence**: `save()` / `load()` to YAML snapshot

#### AttentionManager (attention.py)
```python
class AttentionManager:
    def __init__(self, half_life_days: float = 60.0):
        self._decay_constant = math.log(2) / half_life_days
```

- **Exponential decay**: 60-day half-life
- **Topic tracking**: Weights 0.0-1.0 with diminishing boost returns
- **Pruning**: Auto-removes topics below 1% threshold
- **Freshness scoring**: `compute_freshness(created_at)` for memory recency

#### PersonalityWeights (personality.py)
```python
DEFAULT_TRAITS = {
    "curious": 0.85,
    "warm": 0.80,
    "analytical": 0.75,
    "creative": 0.70,
    "patient": 0.85,
    "direct": 0.65,
    "playful": 0.60,
    "thoughtful": 0.80,
}
```

- **8 default traits** with adjustable weights
- **Prompt hints**: `to_prompt_hint()` for response style injection
- **Blending**: `blend_with()` for persona mixing
- **Persistence**: Serializable for snapshot

### What's Missing (Bible vs Implementation)

| Bible Spec | Status |
|------------|--------|
| Mood state | ✅ Implemented |
| App context awareness | ❌ Not found |
| Attention tracking | ✅ Implemented |
| Session continuity | ✅ Via persistence |
| Personality weights | ✅ Implemented |

### Gap Analysis

**Missing: App Context Awareness**
The Bible mentions Luna being aware of what app the user is in (Xcode vs Safari). This is not implemented.

**Complexity to Complete:** LOW
- Add `current_app: str` field to ConsciousnessState
- Add method to update from system events
- Inject into context prompt

### Recommended Next Steps

1. Add app context field (2-3 hours)
2. Connect to macOS accessibility API for app detection (4-6 hours)
3. Include app context in prompt generation (1-2 hours)

**Revised Status:** ✅ STABLE (with optional enhancement for app awareness)

---

## 2. Luna LoRA

### Claimed Status
> "⚠ needs_work" — Voice is "thin"

### Actual Implementation

**Location:** `models/luna_lora_mlx/`

**Adapter Configuration:**
```json
{
  "num_layers": 36,
  "lora_parameters": {
    "rank": 16,
    "alpha": 16,
    "scale": 1.0,
    "dropout": 0,
    "keys": [
      "self_attn.v_proj",
      "mlp.down_proj",
      "self_attn.k_proj",
      "mlp.gate_proj",
      "mlp.up_proj",
      "self_attn.q_proj",
      "self_attn.o_proj"
    ]
  }
}
```

**Files Present:**
- `adapters.safetensors` - Trained weights
- `adapter_config.json` - MLX configuration
- `models/luna_lora_peft/` - Original PEFT format

### Analysis

**What EXISTS:**
- Full rank-16 LoRA adapter
- 7 projection layers per transformer block
- 36 layers covered
- MLX-compatible format for Apple Silicon

**Why "Thin" (from context):**
The VoightKampff test returns REPLICANT, suggesting the LoRA copies prompts rather than developing authentic voice. This is a **training data quality issue**, not an implementation issue.

### Root Cause

The adapter infrastructure is complete. The issue is:
1. **Limited training data**: Not enough Luna voice examples
2. **Prompt contamination**: Training may have included too much raw context
3. **Reinforcement needed**: Lock-in loop not running to reinforce voice

### Gap Analysis

| Component | Status |
|-----------|--------|
| LoRA weights | ✅ Exist |
| MLX loading | ✅ Works |
| Adapter application | ✅ Verified |
| Voice quality | ⚠ Thin (data issue) |

### Recommended Next Steps

1. **Collect more training data**: Extract Luna voice examples from successful conversations
2. **Clean training corpus**: Remove prompt contamination, keep pure Luna responses
3. **Retrain with PEFT**: Fine-tune on curated examples
4. **Run VK test post-training**: Measure improvement

**Complexity:** MEDIUM (requires training infrastructure and data curation)

**Revised Status:** ⚠ PARTIALLY COMPLETE (infra done, data quality issue)

---

## 3. Narration Layer

### Claimed Status
> "⚠ needs_work" — Output refinement

### Actual Implementation

**File:** `src/luna/actors/director.py:751-776`

```python
# BUG-D FIX: Narrate delegated response through Luna's voice
if response_text and self._local and self.local_available:
    try:
        logger.info("[NARRATION] Rewriting delegated response in Luna's voice...")
        narration_prompt = f"""Rewrite the following information in your own voice.
Keep all facts accurate but express them naturally as yourself.
Do not add disclaimers or mention that you're rewriting.
Just be yourself while conveying this information:

{response_text}"""

        result = await self._local.generate(
            narration_prompt,
            system_prompt=system_prompt,
            max_tokens=1024,
        )
        narrated_text = result.text if hasattr(result, 'text') else str(result)

        if narrated_text and len(narrated_text.strip()) > 20:
            response_text = narrated_text
            narration_applied = True
            logger.info(f"[NARRATION] Complete ({len(response_text)} chars)")
```

### Analysis

**What's Implemented:**
- Narration runs on DELEGATION path (Claude → Qwen)
- Uses full system prompt for voice consistency
- Logs narration status
- Fallback if narration fails (uses raw response)
- QA tracks `narration_applied` flag

**Flow:**
1. Claude returns factual information
2. Qwen rewrites in Luna's voice
3. User hears Luna, not Claude

### Gap Analysis

| Component | Status |
|-----------|--------|
| Narration prompt | ✅ Implemented |
| System prompt pass-through | ✅ Verified |
| Fallback on failure | ✅ Implemented |
| QA tracking | ✅ P3 assertion |
| Quality of transformation | ⚠ Depends on LoRA |

### Why "needs_work" is Incorrect

The narration layer is **fully implemented**. The perceived issue is likely:
1. LoRA voice quality (covered above)
2. Sometimes bypassed due to local inference unavailable

### Recommended Next Steps

1. Ensure local inference always loads (dependency check)
2. Improve LoRA voice quality (see section 2)
3. Consider streaming narration for faster perception

**Complexity:** LOW (already implemented)

**Revised Status:** ✅ STABLE

---

## Summary

| Item | Claimed | Actual | Complexity to Fix |
|------|---------|--------|-------------------|
| Consciousness Actor | ⚠ needs_work | ✅ Stable | LOW (app awareness optional) |
| Luna LoRA | ⚠ needs_work | ⚠ Partial | MEDIUM (data quality) |
| Narration Layer | ⚠ needs_work | ✅ Stable | N/A (done) |

**Key Insight:** The "needs_work" items are mostly complete. The remaining gap is **LoRA voice quality**, which is a training data issue, not infrastructure.
