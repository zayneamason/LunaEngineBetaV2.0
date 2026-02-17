# Claude Code Handoff: Memory Matrix Observatory Sandbox

## Executive Summary

Build **Observatory MCP** — a self-contained, sandboxed Memory Matrix system with its own MCP server and live visualization frontend. This is a **prototyping tool** for testing retrieval algorithms, spreading activation, clustering, and lock-in mechanics WITHOUT touching Luna Hub's production data.

**This is NOT an extension of Luna Hub.** It is a completely separate MCP server with its own database, its own event bus, and its own frontend. It shares zero code with Luna Hub — it reimplements the core memory algorithms in isolation.

**Project Location:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/MemoryMatrix_SandBox/`

---

## Context

### Why This Exists

Luna Hub's Memory Matrix has complex retrieval behavior — FTS5 keyword search, sqlite-vec vector similarity, RRF fusion, spreading activation, cluster-based assembly, token budgeting. When something goes wrong with retrieval (Luna gets scattered facts without connecting threads), there's no way to SEE what happened. No way to replay the pipeline. No way to tweak parameters and compare results.

The Observatory is a **microscope for memory retrieval.** You put data in, run queries, and watch every phase of the pipeline unfold in real time.

### What It Is

1. **Separate MCP Server** — Claude Desktop talks to it via MCP tools (sandbox_reset, sandbox_recall, etc.)
2. **Sandboxed Memory Matrix** — Its own `sandbox_matrix.db`, disposable, resettable
3. **Event Bus** — Every operation emits events (node_created, search_fts5_done, activation_hop, etc.)
4. **WebSocket Server** — Streams events to the frontend in real time
5. **React Frontend** — Force-directed graph, event timeline, retrieval replay visualization

### What It Is NOT

- Not a replacement for Luna Hub
- Not connected to Luna Hub's database (except optional read-only snapshot import)
- Not running Luna's actors (Scribe, Librarian, Director)
- Not doing LLM inference
- Not production code — it's a prototyping sandbox

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   CLAUDE DESKTOP                         │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │  Luna Hub    │  │  Observatory │                     │
│  │  MCP (prod)  │  │  MCP (sand)  │ ← YOU ARE HERE     │
│  └──────────────┘  └──────┬───────┘                     │
└──────────────────────────┼───────────────────────────────┘
                           │ MCP tools
┌──────────────────────────┼───────────────────────────────┐
│           OBSERVATORY MCP SERVER (FastMCP)                │
│                                                           │
│  MCP Tools:                Internal Components:           │
│  ├─ sandbox_reset          ├─ SandboxMatrix               │
│  ├─ sandbox_seed           │   ├─ sqlite + FTS5           │
│  ├─ sandbox_add_node       │   ├─ sqlite-vec (384d)       │
│  ├─ sandbox_add_edge       │   └─ LockInCalculator        │
│  ├─ sandbox_search         ├─ EventBus (in-memory)        │
│  ├─ sandbox_recall         ├─ SpreadingActivation         │
│  ├─ sandbox_replay         └─ EmbeddingGenerator          │
│  ├─ sandbox_graph_dump                                    │
│  ├─ sandbox_stats          HTTP + WebSocket (:8100):      │
│  ├─ sandbox_tune           ├─ GET  /api/graph-dump        │
│  └─ sandbox_import         ├─ GET  /api/stats             │
│                            ├─ POST /api/replay            │
│                            ├─ GET  /api/events/recent     │
│                            └─ WS   /ws/events             │
│                                                           │
│  Database: sandbox_matrix.db (disposable, resettable)     │
│  Config:   sandbox_config.json (tuning params)            │
└──────────────────┬────────────────────────────────────────┘
                   │ WebSocket + REST
┌──────────────────┴────────────────────────────────────────┐
│              OBSERVATORY FRONTEND (React + Vite)           │
│              localhost:5173                                 │
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐   │
│  │  Graph   │  │ Timeline │  │  Retrieval Replay      │   │
│  │  View    │  │  (events)│  │  (phase-by-phase)      │   │
│  └──────────┘  └──────────┘  └────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
MemoryMatrix_SandBox/
├── CLAUDE.md                    # Claude Code project config
├── pyproject.toml               # Python project config
├── README.md                    # Quick start guide
│
├── mcp_server/                  # MCP Server (Python)
│   ├── __init__.py
│   ├── server.py                # FastMCP entry point + HTTP/WS server
│   ├── tools.py                 # MCP tool implementations (10 tools)
│   ├── sandbox_matrix.py        # Core: sqlite + FTS5 + sqlite-vec
│   ├── event_bus.py             # In-memory pub/sub
│   ├── search.py                # FTS5, vector, hybrid, RRF fusion
│   ├── activation.py            # Spreading activation algorithm
│   ├── clusters.py              # Cluster computation + lock-in states
│   ├── lock_in.py               # Lock-in calculator (4-factor formula)
│   ├── embeddings.py            # Local embeddings (all-MiniLM-L6-v2)
│   ├── schema.sql               # Database schema
│   ├── config.py                # Default tuning params + config model
│   └── seeds/                   # Preset datasets
│       ├── small_graph.json     # 20 nodes, 5 clusters — basic testing
│       ├── luna_snapshot.json   # Template for imported prod data
│       ├── stress_test.json     # 500 nodes — performance testing
│       └── pathological.json    # Edge cases: orphans, mega-clusters, etc.
│
├── frontend/                    # React Frontend
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx              # Main app with tab routing
│       ├── store.js             # Zustand state management
│       ├── ws.js                # WebSocket client
│       ├── api.js               # REST client for /api/*
│       ├── views/
│       │   ├── GraphView.jsx    # Force-directed graph
│       │   ├── Timeline.jsx     # Event stream (newest first)
│       │   └── Replay.jsx       # Retrieval phase-by-phase viewer
│       └── components/
│           ├── NodeCard.jsx     # Node detail panel
│           ├── ClusterHull.jsx  # Cluster visualization overlay
│           ├── LockInRing.jsx   # Circular lock-in indicator
│           ├── TuningPanel.jsx  # Parameter adjustment sliders
│           └── EventCard.jsx    # Single event in timeline
│
├── sandbox_matrix.db            # Created at runtime — DISPOSABLE
└── sandbox_config.json          # Tuning params — persisted between runs
```

---

## Implementation Specifications

### Database Schema (`mcp_server/schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    lock_in REAL DEFAULT 0.0,
    access_count INTEGER DEFAULT 0,
    cluster_id TEXT,
    tags TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (cluster_id) REFERENCES clusters(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    strength REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (to_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clusters (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lock_in REAL DEFAULT 0.0,
    state TEXT DEFAULT 'drifting',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_members (
    cluster_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    PRIMARY KEY (cluster_id, node_id),
    FOREIGN KEY (cluster_id) REFERENCES clusters(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- FTS5 full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    content, content_rowid='rowid', tokenize='porter'
);

-- FTS5 sync triggers
CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
    INSERT INTO nodes_fts(rowid, content) VALUES (NEW.rowid, NEW.content);
END;
CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, content) VALUES('delete', OLD.rowid, OLD.content);
END;
CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, content) VALUES('delete', OLD.rowid, OLD.content);
    INSERT INTO nodes_fts(rowid, content) VALUES (NEW.rowid, NEW.content);
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_lock_in ON nodes(lock_in);
CREATE INDEX IF NOT EXISTS idx_nodes_cluster ON nodes(cluster_id);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(relationship);
```

**NOTE:** The `node_embeddings` vec0 table is created programmatically after loading the sqlite-vec extension:
```python
CREATE VIRTUAL TABLE IF NOT EXISTS node_embeddings USING vec0(
    node_id TEXT PRIMARY KEY, embedding FLOAT[384]
)
```

**CRITICAL:** nodes table must NOT use WITHOUT ROWID — FTS5 triggers depend on implicit rowid.

---

### Config Model (`mcp_server/config.py`)

```python
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json

CONFIG_PATH = Path(__file__).parent.parent / "sandbox_config.json"

@dataclass
class RetrievalParams:
    decay: float = 0.5
    min_activation: float = 0.15
    max_hops: int = 2
    token_budget: int = 3000
    sim_threshold: float = 0.3
    fts5_limit: int = 20
    vector_limit: int = 20
    rrf_k: int = 60
    lock_in_node_weight: float = 0.4
    lock_in_access_weight: float = 0.3
    lock_in_edge_weight: float = 0.2
    lock_in_age_weight: float = 0.1
    cluster_sim_threshold: float = 0.82

    def save(self, path: Path = CONFIG_PATH):
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "RetrievalParams":
        if path.exists():
            data = json.loads(path.read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls()
```

---

### Event Bus (`mcp_server/event_bus.py`)

In-memory pub/sub. Every memory operation emits events. WebSocket and timeline subscribe.

```python
from dataclasses import dataclass, field, asdict
from typing import Callable, Awaitable, Optional
from collections import deque
import time, asyncio, json

@dataclass
class MemoryEvent:
    type: str
    actor: str
    payload: dict
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

class EventBus:
    def __init__(self, max_history: int = 2000):
        self._subscribers: list[Callable[[MemoryEvent], Awaitable[None]]] = []
        self._history: deque[MemoryEvent] = deque(maxlen=max_history)

    async def emit(self, event: MemoryEvent):
        self._history.append(event)
        for sub in self._subscribers:
            try:
                await sub(event)
            except Exception:
                pass

    def subscribe(self, callback) -> Callable:
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def recent(self, n: int = 50, type_filter: Optional[str] = None) -> list[dict]:
        events = list(self._history)
        if type_filter:
            events = [e for e in events if e.type == type_filter]
        return [asdict(e) for e in events[-n:]]

    def clear(self):
        self._history.clear()
```

**Event types emitted:**
- `node_created`, `edge_added`, `access_recorded`, `lock_in_changed`
- `search_fts5_done`, `search_vector_done`, `search_fusion_done`
- `activation_started`, `activation_hop`, `activation_done`
- `constellation_assembled`
- `sandbox_reset`, `sandbox_seeded`

---

### Embeddings (`mcp_server/embeddings.py`)

Same model as Luna Hub production: **all-MiniLM-L6-v2** (384 dimensions). Lazy-loaded.

```python
import threading, struct

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

def vector_to_blob(vector: list[float]) -> bytes:
    return struct.pack(f'{len(vector)}f', *vector)

def blob_to_vector(blob: bytes) -> list[float]:
    return list(struct.unpack(f'{len(blob)//4}f', blob))

class EmbeddingGenerator:
    def __init__(self):
        self._model = None
        self._load_lock = threading.Lock()
        self.dim = EMBEDDING_DIM

    def _load(self):
        if self._model is not None: return
        with self._load_lock:
            if self._model is not None: return
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(MODEL_NAME)

    def encode(self, text: str) -> list[float]:
        if not text or not text.strip(): return [0.0] * self.dim
        self._load()
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts: return []
        self._load()
        results = [[0.0] * self.dim] * len(texts)
        non_empty = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
        if non_empty:
            indices, clean_texts = zip(*non_empty)
            embeddings = self._model.encode(list(clean_texts), normalize_embeddings=True)
            for idx, emb in zip(indices, embeddings):
                results[idx] = emb.tolist()
        return results

_instance = None
_lock = threading.Lock()

def get_embedder() -> EmbeddingGenerator:
    global _instance
    with _lock:
        if _instance is None: _instance = EmbeddingGenerator()
        return _instance
```

**NOTE:** First encode() call downloads ~90MB model. Cached in `~/.cache/huggingface/`. Subsequent calls ~50ms.

---

### SandboxMatrix Core (`mcp_server/sandbox_matrix.py`)

The central class. Wraps sqlite + FTS5 + sqlite-vec. Every operation emits events.

Key methods:
- `initialize()` — open DB, load extensions, create schema
- `add_node(type, content, confidence, tags, node_id)` → str (node_id)
- `add_edge(from_id, to_id, relationship, strength)` → int (edge_id)
- `get_node(node_id)` → dict | None
- `get_neighbors(node_id, depth)` → list[dict]
- `record_access(node_id)` — increment access_count, emit event
- `graph_dump(limit, min_lock_in)` → full graph snapshot for frontend
- `stats()` → counts, type distribution, lock-in distribution
- `reset()` — DROP all data, clear events
- `seed(preset)` — load JSON preset, reset first

**Implementation pattern:** See the full reference implementation in the detailed handoff file at `/home/claude/CLAUDE-CODE-HANDOFF-MEMORY-OBSERVATORY-SANDBOX.md`. The key contract is:
1. Every mutating operation emits a MemoryEvent via `self.bus.emit()`
2. Embeddings generated on node creation via `self.embedder.encode()`
3. FTS5 stays in sync via SQLite triggers (no manual management)
4. All methods are async (aiosqlite)

---

### Search (`mcp_server/search.py`)

Three search implementations + RRF fusion:

1. **`search_fts5(matrix, query, params)`** — FTS5 keyword search. Emits `search_fts5_done` with results and timing.
2. **`search_vector(matrix, query, params)`** — sqlite-vec cosine similarity. Emits `search_vector_done`.
3. **`search_hybrid(matrix, query, params)`** — Calls both, applies Reciprocal Rank Fusion (RRF). Emits `search_fusion_done`.

**RRF Formula:** `score(d) = Σ 1/(k + rank_i)` where k=60 (configurable via `params.rrf_k`)

Each function returns `list[dict]` where each dict has `{"node": {...}, "score": float, "method": str}`.

---

### Spreading Activation (`mcp_server/activation.py`)

Graph traversal from seed nodes with decaying signal.

**`spreading_activation(matrix, seed_ids, params)`** → list of activated nodes

Algorithm:
1. Initialize seeds at activation=1.0, hop=0
2. For each hop (1..max_hops):
   - Get edges from current frontier
   - Compute `new_activation = source_activation * decay * edge_strength`
   - If `new_activation >= min_activation`, activate target
3. Emit `activation_hop` event per hop (with all newly activated nodes)
4. Emit `activation_done` with totals

Returns: `list[dict]` with `{node_id, activation, hop, source_id, edge_type, node}` sorted by activation desc.

---

### Lock-In Calculator (`mcp_server/lock_in.py`)

4-factor weighted formula:
```
lock_in = (confidence * 0.4) + (log_access_freq * 0.3) + (avg_edge_strength * 0.2) + (age_stability * 0.1)
```

States: drifting [0, 0.30), fluid [0.30, 0.70), settled [0.70, 0.85), crystallized [0.85, 1.0]

`recompute_all_lock_ins(matrix, params)` — recalculates all nodes, emits `lock_in_changed` for state transitions.

---

### MCP Tools (`mcp_server/tools.py`)

10 tools registered in server.py:

| Tool | Description | Key Behavior |
|------|-------------|--------------|
| `sandbox_reset()` | Wipe DB | Drops all tables, clears events |
| `sandbox_seed(preset)` | Load test data | Resets first, then loads JSON |
| `sandbox_add_node(type, content, ...)` | Create node | Generates embedding, emits event |
| `sandbox_add_edge(from, to, rel, strength)` | Create edge | Emits event |
| `sandbox_search(query, method)` | Search | Methods: fts5, vector, hybrid, all |
| `sandbox_recall(query)` | Full pipeline | search → activate → assemble constellation |
| `sandbox_replay(query)` | Pipeline with trace | Returns every phase with scores/timing |
| `sandbox_graph_dump()` | Full graph JSON | All nodes, edges, clusters |
| `sandbox_stats()` | Database stats | Counts, distributions |
| `sandbox_tune(param, value)` | Adjust params | Persists to sandbox_config.json |

---

### MCP Server Entry Point (`mcp_server/server.py`)

Dual-mode server:
- **MCP mode** (default): FastMCP for Claude Desktop + HTTP/WS in background thread on :8100
- **HTTP-only mode** (`--http` flag): Just the HTTP/WS server for frontend dev

HTTP endpoints:
- `GET /api/graph-dump` — full graph snapshot
- `GET /api/stats` — database statistics
- `GET /api/events/recent?n=50` — recent events
- `GET /api/config` — current tuning params
- `WS /ws/events` — real-time event stream

WebSocket broadcasts all EventBus events to all connected clients.

**Thread model:** HTTP server runs in daemon thread. MCP runs in main thread. Both share the same `matrix` and `event_bus` instances.

---

### Seed Data (`mcp_server/seeds/small_graph.json`)

20 nodes, 21 edges, 5 clusters using Luna project concepts. See the full JSON in the detailed spec. Key structure:

- 6 entity nodes (Luna, Ahab, Mars College, Robot, Memory Matrix, Orb)
- 14 memory nodes across types (FACT, DECISION, INSIGHT, PROBLEM, ACTION, OUTCOME, OBSERVATION)
- Edges: CREATED, DEPENDS_ON, REPRESENTS, RELATED_TO, MENTIONS, CLARIFIES, ENABLES, CAUSED_BY
- Clusters: Engine Architecture (crystallized), Mars College (fluid), Robot Embodiment (fluid), Consciousness & Memory (settled), Pipeline Health (fluid)

Also create:
- **stress_test.json** — 200+ nodes, 500+ edges, 15+ clusters. Performance testing.
- **pathological.json** — orphan nodes, mega-cluster (50+ members), zero lock-in, circular edges, duplicate content. Robustness testing.

---

## Frontend Specifications

### Tech Stack
- React 18 + JSX
- Vite dev server
- Zustand for state
- react-force-graph-2d for graph
- Dark monospace aesthetic matching luna_memory_explorer_v2.jsx

### Visual Design Reference
See `luna_memory_explorer_v2.jsx` in project files for the visual language:
- Background: #06060e
- Font: SF Mono / Fira Code monospace
- Node colors by type: cyan=FACT, purple=DECISION, red=PROBLEM, green=ACTION, yellow=INSIGHT
- Lock-in rings (circular progress)
- Cluster hulls (translucent circles)
- Activation glow (pulsing rings)

### State Management (Zustand)

Single store with:
- `nodes, edges, clusters` — from /api/graph-dump
- `selectedNodeId` — click selection
- `events` — from WebSocket, most recent first, max 500
- `recallResult, activatedNodeIds` — from replay
- `params` — from /api/config
- `wsConnected` — connection state
- `handleEvent(event)` — incremental graph updates from events

### Views

**GraphView** — Force-directed graph. Nodes colored by type, sized by lock_in. Lock-in rings. Cluster hulls. Activated nodes glow on recall. Click for detail panel.

**Timeline** — Vertical event stream. Color-coded by actor. Filterable by event type. Auto-scrolls.

**Replay** — Phase-by-phase retrieval visualization. Step through FTS5 → Vector → Fusion → Activation → Assembly. Nodes highlight in graph at each phase. Token budget progress bar.

---

## Configuration

### Claude Desktop Config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "Observatory-Sandbox": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/MemoryMatrix_SandBox",
      "env": {}
    }
  }
}
```

Keep existing Luna-Hub-MCP-V1 entry. They run side by side.

### pyproject.toml

```toml
[project]
name = "observatory-sandbox"
version = "0.1.0"
description = "Memory Matrix Observatory — sandboxed prototyping tool"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "aiosqlite>=0.19.0",
    "sqlite-vec>=0.1.0",
    "sentence-transformers>=2.2.0",
]
[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "httpx"]
```

### CLAUDE.md

```markdown
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
```

---

## Port Allocation

| Service | Port | Purpose |
|---------|------|---------|
| Luna Hub Main API | 8000 | Production — DON'T TOUCH |
| Luna Hub MCP API | 8001 | Production MCP — DON'T TOUCH |
| **Observatory HTTP+WS** | **8100** | Sandbox API + events |
| **Observatory Frontend** | **5173** | Vite dev server |

---

## Build Order

| Phase | What | Validation |
|-------|------|-----------|
| 1A | Schema + config + event bus + embeddings | Unit tests pass |
| 1B | SandboxMatrix (CRUD, reset, seed, stats) | sandbox_reset, sandbox_seed("small_graph"), sandbox_stats work |
| 1C | Search (FTS5 + vector + hybrid) | sandbox_search("Luna", "all") returns results |
| 1D | Spreading activation + lock-in | sandbox_recall("robot body") returns constellation |
| 1E | MCP server + tool registration | All 10 tools visible in Claude Desktop |
| 1F | HTTP + WebSocket server | curl localhost:8100/api/stats works |
| 2 | Seed data (all 3 presets) | All load without errors |
| 3A | Frontend scaffold (Vite + React + Zustand + WS) | App loads, WebSocket connects |
| 3B | GraphView (force-directed, live updates) | Nodes render, update on events |
| 3C | Timeline (event stream) | Events appear in real time |
| 3D | Replay view | Full retrieval trace visualized |
| 4 | Claude Desktop config + CLAUDE.md | MCP tools work from Claude Desktop |

**Phase 1 is the critical path.** Get matrix + search + activation working first.

---

## Validation Checklist

### MCP Tools
- [ ] sandbox_reset — clears DB, events show reset
- [ ] sandbox_seed("small_graph") — loads 20 nodes, 21 edges, 5 clusters
- [ ] sandbox_add_node — creates node, generates embedding, emits event
- [ ] sandbox_add_edge — creates edge, emits event
- [ ] sandbox_search("Luna", "all") — returns FTS5 + vector + hybrid results
- [ ] sandbox_recall("robot body") — full pipeline, constellation assembled
- [ ] sandbox_replay("sovereignty") — shows all 5 phases with timing
- [ ] sandbox_graph_dump — returns full graph as JSON
- [ ] sandbox_stats — shows counts and distributions
- [ ] sandbox_tune("decay", 0.3) — persists to config file

### HTTP API
- [ ] GET /api/graph-dump returns nodes, edges, clusters
- [ ] GET /api/stats returns counts
- [ ] GET /api/events/recent returns event history
- [ ] WS /ws/events connects, receives events in real time

### Frontend
- [ ] Loads and connects to WebSocket
- [ ] Graph renders nodes with correct colors
- [ ] New nodes/edges animate in on events
- [ ] Timeline shows events in real time
- [ ] Replay view shows phase-by-phase trace

### Integration
- [ ] Claude Desktop sees Observatory-Sandbox MCP
- [ ] Running sandbox_recall in Claude → events appear in frontend
- [ ] Both MCPs (Luna Hub + Observatory) work simultaneously

---

## Critical Implementation Notes

1. **FTS5 triggers use rowid** — nodes table must NOT use WITHOUT ROWID
2. **sqlite-vec loading** — use `sqlite_vec.loadable_path()` for extension path
3. **aiosqlite Row factory** — set `self._db.row_factory = aiosqlite.Row`
4. **Event bus is async** — all subscribers are async def
5. **WebSocket + MCP same process** — HTTP in background thread, MCP in main thread, shared matrix/event_bus
6. **Embedding model lazy-loads** — first encode() downloads ~90MB, cached in ~/.cache/huggingface/
7. **sandbox_matrix.db is disposable** — created at runtime, deletable anytime
8. **Config persists** — sandbox_config.json survives resets (intentional)

---

## Dependencies

```bash
pip install mcp fastapi uvicorn aiosqlite sqlite-vec sentence-transformers

cd frontend
npm init -y
npm install react react-dom zustand react-force-graph-2d
npm install -D vite @vitejs/plugin-react tailwindcss
```