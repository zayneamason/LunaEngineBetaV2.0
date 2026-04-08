# Bite 3 — Vite Proxy Config

Fix `vite.config.js` to proxy ALL backend route prefixes to `localhost:8000`.

Add proxy entries for every route prefix the backend serves:
- `/api`
- `/qa`
- `/slash`
- `/studio`
- `/health`
- `/message`
- `/voice`
- `/ws` (WebSocket — needs `ws: true`)
- `/consciousness`
- `/history`
- `/tuning`
- `/extraction`
- `/clusters`
- `/constellation`
- `/llm`

Rules:
- NO prefix rewriting — pass paths through as-is
- `/api/nexus/list` on the frontend should hit `http://localhost:8000/api/nexus/list` on the backend
- WebSocket routes need `ws: true` in the proxy config
- Target is always `http://localhost:8000`

Test by hitting `http://localhost:5173/api/nexus/list` in a browser and confirming it returns data.

Do this and nothing else.
