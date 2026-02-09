# HANDOFF: Local Inference Speed Diagnostic

**Priority:** HIGH — blocks all local personality work  
**Observed:** 3 tok/s (41 tokens in 13,592ms)  
**Expected:** 20-40 tok/s for 3B-4bit on M1  
**Estimated effort:** 2-4 hours diagnostic + fix  
**Risk:** Low — isolated to inference module  

---

## Context

Luna's local inference (Qwen2.5-3B-Instruct-MLX-4bit) is running at ~3 tokens/second. This is 7-13x slower than expected for this model on Apple Silicon. Until this is resolved, local inference is unusable for real-time conversation, and all queries route to Claude via the HybridInference router (complexity threshold 0.15).

### Hardware
- **Machine:** MacBook Air M1 (MacBookAir10,1)
- **RAM:** 8 GB unified memory
- **Chip:** Apple M1 (8-core CPU, 7-core GPU)

### Model Stack
- **Base model:** `models/Qwen2.5-3B-Instruct-MLX-4bit/` (1.62 GB, 4-bit quantized)
- **LoRA adapter:** `models/luna_lora_mlx/adapters.safetensors` (114 MB, rank 16, all 7 projection keys)
- **Framework:** mlx-lm

### Key File
- `src/luna/inference/local.py` — all inference logic lives here

---

## Suspected Root Causes (ranked by likelihood)

### 1. CRITICAL: LoRA Forces Full-Precision Model Download

**The smoking gun.** Lines 119-123 of `local.py`:

```python
if adapter_path is not None:
    # Fallback: download full-precision model for LoRA compatibility
    if "4bit" in model_id or model_id == FALLBACK_MODEL:
        model_id = DEFAULT_MODEL  # "Qwen/Qwen2.5-3B-Instruct" — FULL PRECISION
```

When the Luna LoRA is detected (and it will be — `LUNA_LORA_PATH.exists()` checks `models/luna_lora_mlx/`), the code **switches away from the local 4-bit model to download and load the full-precision Qwen2.5-3B-Instruct**. That's a ~6 GB model on an 8 GB machine. The system is almost certainly swapping to disk.

**However**, lines 114-117 run first:

```python
if LOCAL_MODEL_PATH.exists() and (LOCAL_MODEL_PATH / "model.safetensors").exists():
    model_id = str(LOCAL_MODEL_PATH)  # Uses the local 4-bit model
```

So the LOCAL path check should win... **unless `model.safetensors` doesn't exist as a single file** (some MLX models shard into multiple files). Need to verify this code path actually fires.

**Diagnostic step:** Add logging or check — which model ID actually gets passed to `mlx_lm.load()`?

### 2. HIGH: Memory Pressure (8 GB Machine)

Even with the 4-bit model (1.62 GB) + LoRA adapter (114 MB), on an 8 GB M1:
- macOS takes ~2-3 GB
- Model + adapter = ~1.74 GB
- KV cache during generation = variable but can be significant with 32K context window
- Other running processes

If total memory demand exceeds ~6-7 GB, macOS swaps to SSD. MLX operations on swapped memory are catastrophically slow — exactly the kind of "it runs but 10x slower" behavior observed.

**Diagnostic step:** Monitor memory during inference with `memory_pressure` or Activity Monitor.

### 3. MEDIUM: LoRA Application Overhead

The LoRA config targets all 7 projection layers across 36 transformer layers with rank 16. That's 252 adapter matrices being applied per forward pass. On MLX this should still be fast, but:
- If the adapter wasn't properly converted to MLX format (dtype mismatch, wrong layout), each application could involve implicit conversion
- rank 16 on all projections is generous — rank 8 on q_proj + v_proj only would be 4x fewer adapters

**Diagnostic step:** Compare generation speed with and without LoRA adapter.

### 4. LOW: Prompt Length / KV Cache

If the system prompt + entity context + memory context being injected is very long, the initial prefill can dominate latency. A 2000-token prompt on a 3B model can take several seconds for prefill alone, making the per-token rate look terrible.

**Diagnostic step:** Log prompt token count before generation.

---

## Diagnostic Protocol

Run these in order. Each step narrows the cause.

### Step 1: Verify Which Model Actually Loads

```python
# Add to load_model() or run standalone:
import logging
logging.basicConfig(level=logging.INFO)

from src.luna.inference.local import LocalInference

inf = LocalInference()
import asyncio
asyncio.run(inf.load_model())

# Check the logs — look for:
# "Using local model: ..." vs "No local model - downloading..."
# "MLX load() params: model_id=X, adapter_path=Y"
```

**Expected:** Should say "Using local model: /path/to/Qwen2.5-3B-Instruct-MLX-4bit"  
**Red flag:** If it says downloading or uses "Qwen/Qwen2.5-3B-Instruct" — that's the bug.

### Step 2: Baseline Without LoRA

```python
from src.luna.inference.local import LocalInference, InferenceConfig

# Force no adapter
config = InferenceConfig(adapter_path=None)
# Monkey-patch to skip auto-detection
import src.luna.inference.local as local_mod
original_path = local_mod.LUNA_LORA_PATH
local_mod.LUNA_LORA_PATH = Path("/nonexistent")

inf = LocalInference(config)
import asyncio

async def bench():
    await inf.load_model()
    result = await inf.generate("Tell me a joke.", max_tokens=100)
    print(f"Tokens: {result.tokens}")
    print(f"Latency: {result.latency_ms:.0f}ms")
    print(f"Speed: {result.tokens_per_second:.1f} tok/s")

asyncio.run(bench())
local_mod.LUNA_LORA_PATH = original_path  # restore
```

**Expected on M1 4-bit 3B:** 20-40 tok/s  
**If still slow (~3 tok/s):** Problem is model loading or memory, not LoRA  
**If fast (20+ tok/s):** LoRA is the bottleneck → go to Step 4

### Step 3: Memory Pressure Check

```bash
# Run DURING inference (in a separate terminal):
memory_pressure
# Look for "System-wide memory free percentage" — if <10%, that's the problem

# Also check:
vm_stat | head -5
# Look for high "Pages swapped out" or "Swapins"

# Or use Activity Monitor → Memory tab → check Memory Pressure graph
```

**Red flag:** Memory pressure "CRITICAL" or "WARN" during inference = swapping to disk.

### Step 4: LoRA Impact Isolation

If Step 2 showed fast inference without LoRA:

```python
# Load WITH adapter, same prompt
config = InferenceConfig()  # default picks up LoRA
inf = LocalInference(config)

async def bench_lora():
    await inf.load_model()
    print(f"Adapter loaded: {inf._adapter_loaded}")
    result = await inf.generate("Tell me a joke.", max_tokens=100)
    print(f"Speed: {result.tokens_per_second:.1f} tok/s")

asyncio.run(bench_lora())
```

**Compare with Step 2.** If LoRA drops speed by >50%, the adapter may need:
- Reconversion to MLX format (dtype alignment)
- Rank reduction (16 → 8)
- Fewer target layers (drop mlp projections, keep only q_proj + v_proj)

### Step 5: Prompt Length Check

```python
# In generate() method, add before generation:
prompt = self._format_prompt(user_message, system_prompt)
tokens = self._tokenizer.encode(prompt)
print(f"Prompt tokens: {len(tokens)}")
```

**If >1000 tokens:** Prefill is significant. Consider:
- Trimming system prompt
- Pre-computing KV cache for static identity prompt (the "Identity KV Cache" from the Bible spec)
- Separating prefill latency from generation latency in metrics

---

## Fix Paths (by root cause)

### If Cause = Wrong Model Loading (Suspect #1)
**Fix:** Ensure local 4-bit path wins when LoRA is present.

```python
# In load_model(), the LOCAL_MODEL_PATH check already runs first.
# But verify the LoRA adapter is COMPATIBLE with 4-bit base.
# If the LoRA was trained on full-precision Qwen2.5-3B, it may not work
# correctly with the 4-bit quantized version.
#
# Check: Was the LoRA trained against the 4-bit or full-precision base?
# If full-precision: need to retrain LoRA against 4-bit base, OR
# use the full-precision model but quantize it post-LoRA-merge.
```

### If Cause = Memory Pressure (Suspect #2)
**Fix options (pick one):**

a) **Fuse LoRA into base model** — eliminates runtime adapter overhead and reduces memory:
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python -m mlx_lm.lora.fuse \
  --model models/Qwen2.5-3B-Instruct-MLX-4bit \
  --adapter-path models/luna_lora_mlx \
  --save-path models/luna_fused_4bit \
  --de-quantize  # if needed for compatibility
```
This bakes Luna's personality into the weights — no runtime LoRA overhead.

b) **Reduce context window** — Qwen2.5-3B defaults to 32K context. If Luna only needs 4K-8K for conversation, limiting this saves significant KV cache memory.

c) **Kill background processes** — free up that 8 GB. Close browsers, IDEs, etc during local inference.

### If Cause = LoRA Overhead (Suspect #3)
**Fix:** Reduce adapter scope:

```json
// Current adapter_config.json targets ALL projections:
"keys": ["self_attn.v_proj", "mlp.down_proj", "self_attn.k_proj",
         "mlp.gate_proj", "mlp.up_proj", "self_attn.q_proj", "self_attn.o_proj"]

// Minimal effective set for personality/style (retrain with):
"keys": ["self_attn.q_proj", "self_attn.v_proj"]
// This is 2/7 the adapter matrices — significant speedup
```

This requires retraining the LoRA (which we need to do anyway for the Forge pipeline).

### If Cause = Prompt Length (Suspect #4)
**Fix:** Implement Identity KV Cache per Bible spec — pre-compute and cache the KV states for Luna's static system prompt. Only process the dynamic portion (user message + memory context) at inference time.

---

## Recommended Fix: The Fused Model Path

Given the 8 GB constraint, the highest-impact fix is likely **fusing the LoRA into the base model**:

1. Eliminates runtime adapter memory overhead (~114 MB + compute)
2. Single model file to load
3. No compatibility questions between 4-bit base and LoRA trained on different precision
4. Faster inference — no per-layer adapter application

The downside: you lose hot-swappable personality. But on 8 GB, that's a luxury you can't afford. When Luna moves to beefier hardware (Mars College rig?), unfused LoRA with hot-swap makes sense again.

**Trade-off:** Fused model = faster + simpler but locked personality. Unfused = flexible but slower on constrained hardware. On M1/8GB, fuse. Revisit when hardware changes.

---

## Success Criteria

| Metric | Current | Target | Stretch |
|--------|---------|--------|---------|
| Tokens/second | ~3 | 15-20 | 30+ |
| Time to first token | unknown | <500ms | <200ms |
| Memory during inference | unknown | <5 GB | <4 GB |
| Model load time | unknown | <3s | <1s (cached) |

---

## Files Involved

| File | Role |
|------|------|
| `src/luna/inference/local.py` | All inference logic — model loading, generation, routing |
| `models/Qwen2.5-3B-Instruct-MLX-4bit/` | Base model (1.62 GB) |
| `models/luna_lora_mlx/` | LoRA adapter (114 MB, rank 16) |
| `models/luna_lora_mlx/adapter_config.json` | LoRA config — targets all 7 projection layers |
| `src/luna/consciousness/personality.py` | Personality weights (not directly related but context) |
| `src/luna/voice/lock.py` | VoiceLock — query-based voice params (context only) |

---

## Notes

- The `luna_lora_mlx_OLD_CONTAMINATED` directory suggests a previous training attempt produced bad results. Current adapter may still be undertrained. Speed fix and retrain should be coupled.
- The `HybridInference` router has a 0.15 complexity threshold — meaning almost everything routes to Claude. This is correct behavior *given* 3 tok/s local speed. Once local speed is fixed, this threshold should be re-evaluated.
- Bible spec mentions Qwen2.5-7B as target model. On M1/8GB, 7B is not viable even at 4-bit (~4 GB model + OS overhead). Stick with 3B unless hardware changes.
- The STATUS-VS-BIBLE.md notes "Identity KV Cache" as missing. This is a significant optimization for the M1 — pre-computing the static prompt KV cache could cut first-token latency dramatically. Consider as a Phase 2 optimization after base speed is fixed.
