# Observatory Sandbox — Claude Code Config

## What This Is
Sandboxed Memory Matrix prototyping tool. Separate MCP server, own DB, own frontend.
NOT connected to Luna Hub production.

## Running
python -m mcp_server.server          # MCP mode (+ HTTP on :8100)
python mcp_server/server.py --http   # HTTP-only for frontend dev
cd frontend && npm run dev           # Frontend on :5173

## Key Decisions
- Embedding model: all-MiniLM-L6-v2 (384d) — same as Luna Hub
- DB: sqlite + FTS5 + sqlite-vec
- Event bus: in-memory, no persistence
- Frontend: React + Vite on :5173, connects to :8100
