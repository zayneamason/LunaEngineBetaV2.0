# HANDOFF: Qwen Local Inference — Status Check Feb 19 2026
## Written by: CC (Architecture Session)
## For: CC (Implementation)
## Priority: P2 — not blocking, but API compat is broken

---

## Current State

### What's There
- **Base model:** Qwen2.5-3B-Instruct-MLX-4bit (1.6GB, 36 layers, group_size=64)
- **LoRA adapter:** luna_lora_mlx (114MB, rank 16, alpha 16, 7 projection keys)
- **Old contaminated adapter:** luna_lora_mlx_OLD_CONTAMINATED (preserved, don't use)
- **PEFT format backup:** luna_lora_peft/

### Performance (measured live, M1 8GB)
| Test | Tokens | Time | Speed |
|------|--------|------|-------|
| With LoRA, short | 100 tok | 6.1s | 16.5 tok/s |
| With LoRA, long | 152 tok | 8.6s | 17.6 tok/s |
| Without LoRA, long | 300 tok | 12.7s | 23.7 tok/s |
| Model load (with LoRA) | — | 1.6s | — |

**This is WAY better than the 2-3 tok/s previously reported.** Either something was fixed, or the previous measurements were under full engine memory pressure. 16-17 tok/s with LoRA is usable for hot path responses.

LoRA adds ~30% overhead (24 → 17 tok/s), expected for rank-16 across 7 projections.

### Voice Quality
**With LoRA:** Has personality — emotive, uses recognition markers, warm tone. But still has bad patterns:
- "Let me look into that..." (delegation language from training data)
- Asterisk emotes (*eyes lighting up*)
- Hallucinated shared history ("you asked me yesterday!")

**Without LoRA:** Generic assistant — "Certainly, I'd be happy to explain..." Flat, no personality.

The LoRA is working. The training data just needs refinement to remove delegation phrases and asterisk action markers.

### API Compatibility Bug
`mlx_lm` API has changed. The current `local.py` likely passes `temp` or `temperature` as kwargs to `generate()`. These no longer work — `generate_step()` now uses a `sampler` parameter instead.

**Broken call:** `generate(model, tokenizer, prompt=prompt, max_tokens=100, temp=0.7)` → TypeError
**Working call:** `generate(model, tokenizer, prompt=prompt, max_tokens=100)` (uses default sampler)

To set temperature, you need to construct a sampler:
```python
from mlx_lm.sample_utils import make_sampler
sampler = make_sampler(temp=0.7, top_p=0.9)
# Then pass to generate_step or stream_generate
```

Check `src/luna/inference/local.py` — every call that passes temperature/top_p kwargs needs updating.

---

## Action Items

1. **Fix mlx_lm API compat** in `src/luna/inference/local.py` — update to sampler pattern
2. **Training data cleanup** — remove delegation phrases ("Let me look into that"), asterisk emotes, hallucinated history from training examples
3. **Benchmark under load** — test inference speed while full engine is running (memory pressure may drop us back toward the 2-3 tok/s range on 8GB)

---

## Files
| File | Issue |
|------|-------|
| `src/luna/inference/local.py` | API compat broken — temp/temperature kwargs no longer valid in mlx_lm |
| `models/luna_lora_mlx/` | Working adapter, 114MB, rank 16 |
| `models/Qwen2.5-3B-Instruct-MLX-4bit/` | Base model, 1.6GB, 4-bit quantized |
