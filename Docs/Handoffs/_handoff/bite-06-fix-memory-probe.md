# Bite 6 — Fix luna_memory_probe Bug

The `luna_memory_probe` MCP tool returns this error:

```
MatrixActor.get_context() got an unexpected keyword argument 'token_budget'
```

## What to do

1. Find where `luna_memory_probe` calls `MatrixActor.get_context()` — likely in the `/api/diagnostics/trigger/memory-probe` endpoint or in `engine_client.py`
2. Check `MatrixActor.get_context()` method signature in the actual class
3. Fix the call to match the actual signature — remove or rename the `token_budget` kwarg

This is a one-line fix. Do this and nothing else.
