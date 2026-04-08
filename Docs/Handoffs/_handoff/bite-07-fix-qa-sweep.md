# Bite 7 — Fix luna_qa_sweep Bug

The `luna_qa_sweep` MCP tool returns this error:

```
'QAReport' object has no attribute 'get'
```

## What to do

1. Find where `luna_qa_sweep` processes the QA report — likely in the `/api/diagnostics/trigger/qa-sweep` endpoint
2. The code is treating `QAReport` as a dict and calling `.get()` on it
3. `QAReport` is a dataclass/object — access its attributes directly (e.g. `report.passed` not `report.get('passed')`)
4. Fix the serialization so the MCP tool returns a clean JSON response

This is a small fix. Do this and nothing else.
