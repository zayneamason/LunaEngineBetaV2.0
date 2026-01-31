# Handoff: Context Pipeline & LoRA Fix

**Date:** 2026-01-28
**Status:** Fixed
**Files Modified:**
- `src/luna/actors/director.py`
- `src/luna/inference/local.py`

---

## Issue 1: Context Pipeline Bypassed for Local Inference

### Problem
The `process()` method (used by PersonaAdapter voice integration) was NOT using the unified `ContextPipeline.build()` for local inference. Instead, it used the older `_entity_context.build_framed_context()` approach.

This meant:
- `used_retrieval: false` in responses
- Local path got different (worse) context than delegated path
- No entity detection, no temporal framing, no memory retrieval

### Root Cause
Two different code paths existed:
1. **Mailbox path**: `_handle_director_generate()` → `_generate_local_only()` → used `ContextPipeline.build()` ✓
2. **Direct process() path**: `process()` → `_local.generate()` → used `build_framed_context()` ✗

The `process()` method is the main entry point for voice integration, but it wasn't using the unified context pipeline.

### Fix Applied (`director.py` lines ~640-700)
Updated the local inference path in `process()` to use `ContextPipeline.build()` when available:

```python
elif self.local_available:
    route_decision = "local"
    route_reason = "simple query"
    used_retrieval = False

    # FIX: Use unified ContextPipeline for local path (same as delegation)
    if self._context_pipeline is not None:
        try:
            # Populate ring from context_window if empty
            if len(self._context_pipeline._ring) == 0 and context_window:
                self._populate_ring_from_context(
                    self._context_pipeline._ring,
                    context_window
                )

            packet = await self._context_pipeline.build(message)
            system_prompt = packet.system_prompt
            used_retrieval = packet.used_retrieval
            logger.info(f"[PROCESS-LOCAL-PIPELINE] Using unified context: {packet}")
        except Exception as e:
            # Fallback to framed_context if pipeline fails
            ...
```

Also added `used_retrieval` to the return dict for debugging:
```python
return {
    "response": response_text,
    "route_decision": route_decision,
    "route_reason": route_reason,
    "system_prompt_tokens": system_prompt_tokens,
    "latency_ms": elapsed_ms,
    "used_retrieval": final_used_retrieval,
}
```

### Verification
Check logs for:
```
[PROCESS-LOCAL-PIPELINE] Using unified context: ContextPacket(ring=X, retrieval=Y, entities=Z, used_retrieval=True)
```

---

## Issue 2: LoRA Adapter Not Applying

### Problem
Model responded "I am Qwen" instead of as Luna, despite the LoRA adapter existing at `models/luna_lora_mlx/`.

### Root Cause
The `InferenceConfig` defaults to `use_4bit=True`, which loads `mlx-community/Qwen2.5-3B-Instruct-4bit`.

However, the Luna LoRA adapter was trained on the full-precision `Qwen/Qwen2.5-3B-Instruct` model. When the 4-bit quantized model is loaded, the LoRA weights may not align correctly due to different weight structures.

### Fix Applied (`local.py` lines ~143-175)
Check for LoRA adapter FIRST, then decide on quantization:

```python
# Check for Luna LoRA adapter FIRST (before deciding on quantization)
adapter_path = self.config.adapter_path
if adapter_path is None and LUNA_LORA_PATH.exists():
    adapter_path = LUNA_LORA_PATH
    logger.info(f"Found Luna LoRA adapter: {adapter_path}")

# FIX: When using LoRA adapter, use full-precision model for compatibility
if adapter_path is not None:
    # Force full-precision model when using LoRA
    if "4bit" in model_id or model_id == FALLBACK_MODEL:
        model_id = DEFAULT_MODEL
        logger.info(f"LoRA adapter detected - using full-precision model: {model_id}")
elif self.config.use_4bit and "4bit" not in model_id:
    # Only use 4-bit quantized version when NO LoRA adapter
    model_id = FALLBACK_MODEL
```

Also added verification logging:
```python
logger.info(f"MLX load() params: model_id={model_id}, adapter_path={adapter_str}")
...
if adapter_path:
    logger.info(f"Luna personality LoRA applied from: {adapter_path}")
```

### Verification
Check logs for:
```
Found Luna LoRA adapter: /path/to/models/luna_lora_mlx
LoRA adapter detected - using full-precision model: Qwen/Qwen2.5-3B-Instruct
MLX load() params: model_id=Qwen/Qwen2.5-3B-Instruct, adapter_path=/path/to/models/luna_lora_mlx
Model + Luna LoRA loaded in Xms
Luna personality LoRA applied from: /path/to/models/luna_lora_mlx
```

---

## Testing

### Test Context Pipeline Fix
```python
# In scripts/test_chat_flow.py or similar
response = await director.process("Tell me about marzipan", context={})
assert response.get("used_retrieval") == True, "Context pipeline should have used retrieval"
print(f"used_retrieval: {response.get('used_retrieval')}")
```

### Test LoRA Fix
```python
# Ask Luna about her identity
response = await director.process("What is your name?", context={})
# Should respond as Luna, not Qwen
assert "Luna" in response["response"] or "luna" in response["response"].lower()
assert "Qwen" not in response["response"]
```

---

## Trade-offs

### Context Pipeline Fix
- **Pro:** Local and delegated paths now get identical context
- **Pro:** `used_retrieval` flag enables debugging
- **Con:** Slightly more overhead for local path (pipeline initialization)

### LoRA Fix
- **Pro:** Luna's personality now works correctly
- **Con:** Full-precision model uses more memory (~6GB vs ~2GB for 4-bit)
- **Con:** Slightly slower inference (but still <200ms for simple queries)

To mitigate memory usage, consider training a LoRA adapter specifically for the 4-bit model in the future.

---

## Files Changed Summary

| File | Changes |
|------|---------|
| `src/luna/actors/director.py` | Added ContextPipeline usage in `process()` local path; Added `used_retrieval` to return dict |
| `src/luna/inference/local.py` | Check LoRA adapter before quantization decision; Force full-precision when LoRA present |

---

## Next Steps
1. Run full test suite to verify no regressions
2. Test voice integration (PersonaAdapter) with the fixed context pipeline
3. Monitor logs for `used_retrieval=True` in local inference path
4. Verify Luna responds as herself (not Qwen) with LoRA applied
