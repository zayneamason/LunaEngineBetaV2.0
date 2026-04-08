# Bite 2 — Kill Hardcoded Backend URLs

Grep `frontend/src/` for every instance of:
- `127.0.0.1:8000`
- `localhost:8000`
- `http://127.0.0.1:8000`
- `http://localhost:8000`

Replace every instance with relative paths. Examples:
- `http://127.0.0.1:8000/api/nexus/list` → `/api/nexus/list`
- `http://127.0.0.1:8000/slash/prompt` → `/slash/prompt`
- `http://127.0.0.1:8000/qa/health` → `/qa/health`

For WebSocket URLs (`ws://127.0.0.1:8000/ws`), use a relative approach:
```js
const wsUrl = `ws://${window.location.hostname}:8000/ws`;
```
Or better — route through the Vite proxy (bite 3 handles this).

Zero hardcoded backend URLs should remain in any frontend source file. The Vite proxy will handle forwarding.

Do this and nothing else.
