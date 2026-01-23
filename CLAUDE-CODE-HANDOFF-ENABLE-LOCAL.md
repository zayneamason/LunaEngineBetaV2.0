# Claude Code Handoff: Enable Local Inference

**Date:** 2026-01-17  
**Priority:** High  
**Effort:** ~5 minutes  

---

## The Problem

Local inference is hardcoded OFF in `engine.py`:

```python
self.register_actor(DirectorActor(enable_local=False))
```

This means ALL queries go to Claude, even simple ones like "hey luna" that should hit local Qwen.

The planning layer is working correctly — it routes based on complexity. But the local model never loads because it's disabled at boot.

---

## The Fix

### 1. Update `src/luna/engine.py`

**Find this block (~line 174):**
```python
if "director" not in self.actors:
    # Use Claude for real Luna experience (set enable_local=False)
    # For fast local mode, change to enable_local=True
    self.register_actor(DirectorActor(enable_local=False))
```

**Replace with:**
```python
if "director" not in self.actors:
    # Local-first: Qwen 3B + Luna LoRA for fast responses
    # Falls back to Claude for complex queries via planning layer
    self.register_actor(DirectorActor(enable_local=self.config.enable_local_inference))
```

### 2. Update `EngineConfig` dataclass (~line 45)

**Add this field:**
```python
@dataclass
class EngineConfig:
    """Engine configuration."""
    # Tick intervals
    cognitive_interval: float = 0.5  # 500ms
    reflective_interval: float = 300  # 5 minutes

    # Buffer settings
    input_buffer_max: int = 100
    stale_threshold_seconds: float = 5.0

    # Inference settings
    enable_local_inference: bool = True  # Local-first architecture

    # Paths
    data_dir: Path = field(default_factory=lambda: Path.home() / ".luna")
    snapshot_path: Optional[Path] = None
```

---

## Verification

After the change:

```bash
# Start the console
python scripts/run.py

# Simple query - should show ⚡ local (not ☁ cloud)
> Hey Luna, how are you?

# Complex query - should still show ⚡ delegated
> What are the latest developments in AI?
```

**Expected indicators:**
| Query Type | Before Fix | After Fix |
|------------|------------|-----------|
| "hey luna" | ☁ cloud | ⚡ local |
| "tell me a joke" | ☁ cloud | ⚡ local |
| "latest AI news" | ⚡ delegated | ⚡ delegated |

---

## Why This Matters

The whole architecture is local-first:

```
User → Luna (Qwen local) → Simple? Answer directly
                        → Complex? Delegate to Claude
```

With `enable_local=False`, Luna's brain is bypassed entirely. She's just a Claude wrapper with extra steps.

With `enable_local=True`, Luna thinks locally and only calls Claude when she actually needs help.

---

## Summary

| File | Change | Lines |
|------|--------|-------|
| `src/luna/engine.py` | Add `enable_local_inference` to EngineConfig | 1 |
| `src/luna/engine.py` | Use config flag in DirectorActor init | 1 |

**Total: 2 lines changed, 5 minutes work.**
