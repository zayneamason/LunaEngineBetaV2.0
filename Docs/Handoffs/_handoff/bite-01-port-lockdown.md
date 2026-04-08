# Bite 1 — Port Lockdown

Grep the entire project for port numbers: 8001, 3000, 5174, or any port that isn't 8000 (backend) or 5173 (frontend dev server). Fix any wrong ones.

- Backend is ALWAYS port 8000
- Frontend dev server is ALWAYS port 5173
- These are not configurable, not dynamic, not environment-variable'd
- If you see any other port number anywhere, that's a bug — fix it

Do this and nothing else.
