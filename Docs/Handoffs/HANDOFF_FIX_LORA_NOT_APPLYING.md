# HANDOFF: Fix LoRA Not Applying to Generation

**Created:** 2026-01-28
**Priority:** P0 — Luna has no personality without this
**Symptom:** Model outputs "I am Qwen, created by Alibaba Cloud" despite adapter loading

---

## The Problem

Voight-Kampff Layer 1 shows:
- ✅ Adapter file exists: `models/luna_lora_mlx/adapters.safetensors` (119MB)
- ✅ MLX reports adapter loaded
- ❌ Output is still base Qwen: "I am Qwen, a large language model created by Alibaba Cloud"

**The adapter loads but has ZERO effect on generation.**

---

## Hypothesis

One of:
1. Adapter loaded but not passed to `generate()` call
2. Adapter weights incompatible with model version
3. Wrong merge/application method
4. Model loaded fresh each call, adapter only loaded once

---

## Files to Investigate

### Primary: `src/luna/inference/local.py`

This is where LocalInference lives. Check:

```python
# Look for adapter loading
class LocalInference:
    def __init__(self, ...):
        # Is adapter path configured?
        # Is it loaded here or lazily?
        
    def load_model(self):
        # How is adapter merged/applied?
        # MLX requires specific merge pattern
        
    def generate(self, prompt, ...):
        # Is adapter-merged model used here?
        # Or is base model used?
```

**Key questions:**
1. Where is `adapters.safetensors` loaded?
2. How is it merged with base model?
3. Is the merged model persisted or recreated?

### Secondary: `config/inference.json`

Check configuration:
```json
{
  "adapter_path": "models/luna_lora_mlx/adapters.safetensors",
  "model": "mlx-community/Qwen2.5-3B-Instruct-4bit",
  // Is adapter_path actually being read?
}
```

### Reference: MLX LoRA Application

Correct MLX pattern for LoRA:
```python
from mlx_lm import load, generate

# Load base model
model, tokenizer = load("mlx-community/Qwen2.5-3B-Instruct-4bit")

# Load and apply adapter
model = load_adapter(model, "path/to/adapters.safetensors")
# OR
model, tokenizer = load(
    "mlx-community/Qwen2.5-3B-Instruct-4bit",
    adapter_path="path/to/adapters.safetensors"
)

# Generate with adapted model
response = generate(model, tokenizer, prompt, ...)
```

---

## Diagnostic Steps

### Step 1: Verify adapter loading code exists

```bash
grep -n "adapter" src/luna/inference/local.py
grep -n "safetensors" src/luna/inference/local.py
grep -n "load_adapter\|adapter_path" src/luna/inference/local.py
```

### Step 2: Check if adapter is passed to load()

Look for the `load()` call in LocalInference. Does it include `adapter_path`?

```python
# WRONG - no adapter
model, tokenizer = load(model_path)

# RIGHT - with adapter
model, tokenizer = load(model_path, adapter_path=self.adapter_path)
```

### Step 3: Test adapter directly

Create a minimal test:
```python
# test_lora_direct.py
from mlx_lm import load, generate

model_path = "mlx-community/Qwen2.5-3B-Instruct-4bit"
adapter_path = "models/luna_lora_mlx/adapters.safetensors"

# Without adapter
model_base, tok = load(model_path)
out_base = generate(model_base, tok, prompt="Who are you?", max_tokens=50)
print("BASE:", out_base)

# With adapter  
model_lora, tok = load(model_path, adapter_path=adapter_path)
out_lora = generate(model_lora, tok, prompt="Who are you?", max_tokens=50)
print("LORA:", out_lora)

# Compare
print("DIFFERENT?", out_base != out_lora)
```

If both outputs are identical → adapter not being applied by MLX
If outputs differ but Luna still says "I am Qwen" → LocalInference not using adapter

### Step 4: Check adapter compatibility

```python
import safetensors
from safetensors import safe_open

with safe_open("models/luna_lora_mlx/adapters.safetensors", framework="numpy") as f:
    print("Keys:", list(f.keys())[:10])
    # Should show layer names like:
    # model.layers.0.self_attn.q_proj.lora_A
    # model.layers.0.self_attn.q_proj.lora_B
```

If keys don't match Qwen layer names → adapter trained on wrong model

---

## Likely Fix

Based on common patterns, the fix is probably:

**In `src/luna/inference/local.py`, find `load()` call and add adapter_path:**

```python
# BEFORE (broken)
self.model, self.tokenizer = load(self.model_path)

# AFTER (fixed)
self.model, self.tokenizer = load(
    self.model_path,
    adapter_path=self.config.adapter_path  # or however config is accessed
)
```

---

## Validation

After fix, run:
```bash
.venv/bin/python scripts/voight_kampff.py --layer 1
```

Expected:
- Base output: "I am Qwen..."
- LoRA output: Something different (hopefully Luna-like)
- Divergence score: < 0.85

Or from Luna Hub:
```
/vk
```

Layer 1 should show ✅ PASS with actual divergence.

---

## Success Criteria

- [ ] `generate()` uses adapter-merged model
- [ ] Output to "Who are you?" does NOT say "Qwen" or "Alibaba"
- [ ] Voight-Kampff Layer 1 passes with divergence < 0.85
- [ ] Luna's voice is audibly different from base model

---

## Notes

- The adapter was trained via MLX LoRA fine-tuning
- Training data: 415 markdown files, ~192K words
- Adapter size: 119MB (reasonable for 3B model)
- If adapter is valid but still no effect, may need retraining with different hyperparameters
