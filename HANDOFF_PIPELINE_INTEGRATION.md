# Handoff: Luna Engine Full Pipeline Integration

**Created:** 2025-01-19
**For:** Claude Code
**Priority:** High

---

## Goal

Verify the complete extraction pipeline works end-to-end:
1. Engine boots with actors registered
2. Conversation turn → Scribe → extraction
3. Extraction → Librarian → filed to DB
4. Lock-in tracking works on access/retrieval
5. Pruning respects lock-in states

---

## Recent Changes (Context)

Lock-in coefficient system was added to substrate:

```
src/luna/substrate/lock_in.py      # NEW - core lock-in computation
src/luna/substrate/schema.sql      # Added: reinforcement_count, lock_in, lock_in_state columns
src/luna/substrate/memory.py       # Updated: MemoryNode dataclass, record_access(), reinforce_node(), get_drifting_nodes()
src/luna/substrate/__init__.py     # Exports lock-in functions
src/luna/actors/librarian.py       # Updated: _prune_drifting_nodes(), _handle_prune()
tests/test_lock_in.py              # Unit tests for lock_in.py (13/13 passing)
```

---

## Deliverable 1: DB Bootstrap Script

**File:** `scripts/bootstrap_db.py`

**Purpose:** Initialize fresh Luna Engine database with schema + sqlite-vec

**Spec:**
```python
# Input: path to create DB (default: data/luna_engine.db)
# Output: initialized SQLite DB with:
#   - All tables from schema.sql
#   - sqlite-vec extension loaded
#   - memory_embeddings virtual table created
#   - Empty but ready for use

# CLI usage:
#   python scripts/bootstrap_db.py
#   python scripts/bootstrap_db.py --path /custom/path.db
#   python scripts/bootstrap_db.py --path :memory:  # for testing
```

**Verification:**
- Tables exist: `memory_nodes`, `conversation_turns`, `graph_edges`, `sessions`, `consciousness_snapshots`
- Columns exist on `memory_nodes`: `reinforcement_count`, `lock_in`, `lock_in_state`
- Indexes exist: `idx_nodes_lock_in`, `idx_nodes_lock_in_state`
- sqlite-vec loadable, `memory_embeddings` virtual table works

---

## Deliverable 2: Actor Registration Test

**File:** `tests/test_actor_registration.py`

**Verify:**
```python
# 1. Engine initialization
engine = LunaEngine(config)
await engine.start()

# 2. Core actors registered
assert engine.get_actor("scribe") is not None
assert engine.get_actor("librarian") is not None
assert engine.get_actor("matrix") is not None

# 3. Actor types correct
from luna.actors.scribe import ScribeActor
from luna.actors.librarian import LibrarianActor
from luna.actors.matrix import MatrixActor

assert isinstance(engine.get_actor("scribe"), ScribeActor)
assert isinstance(engine.get_actor("librarian"), LibrarianActor)
assert isinstance(engine.get_actor("matrix"), MatrixActor)

# 4. Actors can receive messages (basic smoke test)
# Send ping, expect no crash

await engine.stop()
```

**Reference files to check registration:**
- `src/luna/engine.py` — where actors get registered
- `src/luna/actors/__init__.py` — actor exports

---

## Deliverable 3: Wire Test (Scribe → Librarian → DB)

**File:** `tests/test_extraction_pipeline.py`

**Test Flow:**

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────┐
│ Test sends  │───▶│   Scribe    │───▶│  Librarian  │───▶│    DB    │
│ conv turn   │    │ (extracts)  │    │  (files)    │    │ (verify) │
└─────────────┘    └─────────────┘    └─────────────┘    └──────────┘
```

**Test Input:**
```python
test_turn = {
    "session_id": "test_session_001",
    "role": "user",
    "content": "I decided to use sqlite-vec instead of FAISS for the Memory Matrix. This keeps everything in a single file which supports data sovereignty."
}
```

**Expected Extraction (approximate):**
```python
# Scribe should extract something like:
expected_objects = [
    {"type": "DECISION", "content": "..sqlite-vec instead of FAISS.."},
    {"type": "FACT", "content": "..single file.."},
    {"type": "ASSUMPTION", "content": "..supports data sovereignty.."},
]
expected_edges = [
    {"from": "sqlite-vec", "to": "FAISS", "type": "replaces"},
]
```

**Verification Steps:**
1. Send turn to Scribe via engine message
2. Wait for processing (poll or event)
3. Query DB for new nodes
4. Assert nodes exist with correct `node_type`
5. Assert edges created in `graph_edges`
6. Assert `lock_in` defaults correct (0.15, 'drifting')

**Edge Cases to Test:**
- Empty content → no extraction, no crash
- Very long content → chunked properly
- Duplicate entity → resolved, not duplicated

---

## Deliverable 4: Lock-In Integration Test

**File:** `tests/test_lock_in_integration.py`

**Test 1: Access Updates Lock-In**
```python
# Create node via Librarian filing
node_id = await matrix.add_node(type="FACT", content="test")

# Initial state
node = await matrix.get_node(node_id)
assert node.lock_in == 0.15
assert node.lock_in_state == "drifting"

# Access 10 times
for _ in range(10):
    await matrix.record_access(node_id)

# Verify lock-in increased
node = await matrix.get_node(node_id)
assert node.lock_in > 0.30  # Should be fluid now
assert node.access_count == 10
```

**Test 2: Reinforcement Boosts Lock-In**
```python
node_id = await matrix.add_node(type="FACT", content="test")
await matrix.reinforce_node(node_id)

node = await matrix.get_node(node_id)
assert node.reinforcement_count == 1
assert node.lock_in > 0.15  # Boosted
```

**Test 3: Pruning Respects Lock-In**
```python
# Create drifting node (old, no access)
drifting_id = await matrix.add_node(type="FACT", content="will drift")
# Manually backdate created_at to 60 days ago

# Create settled node (high access)
settled_id = await matrix.add_node(type="FACT", content="important")
for _ in range(20):
    await matrix.record_access(settled_id)

# Create reinforced node (even if drifting)
reinforced_id = await matrix.add_node(type="FACT", content="user marked")
await matrix.reinforce_node(reinforced_id)

# Run prune via Librarian
await engine.send_message("librarian", "prune", {
    "age_days": 30,
    "prune_nodes": True
})

# Verify
assert await matrix.get_node(drifting_id) is None  # Pruned
assert await matrix.get_node(settled_id) is not None  # Preserved
assert await matrix.get_node(reinforced_id) is not None  # Never prune reinforced
```

**Test 4: Stats Include Lock-In Distribution**
```python
stats = await matrix.get_stats()
assert "nodes_by_lock_in" in stats
assert "avg_lock_in" in stats
```

---

## File Structure After Implementation

```
scripts/
  bootstrap_db.py               # NEW

tests/
  test_actor_registration.py    # NEW
  test_extraction_pipeline.py   # NEW
  test_lock_in_integration.py   # NEW
  test_lock_in.py               # EXISTS (unit tests, passing)
```

---

## Dependencies / Blockers

| Dependency | Status | Notes |
|------------|--------|-------|
| Scribe needs Claude API key | ⚠️ | Mock for tests, or use env var |
| Engine startup sequence | Check | Verify actors register in right order |
| sqlite-vec extension | Check | Must be loadable in test env |
| Async test fixtures | Need | pytest-asyncio, temp DB per test |

---

## Run Order

1. `bootstrap_db.py` — verify DB creation works
2. `test_actor_registration.py` — verify engine boots
3. `test_lock_in_integration.py` — verify lock-in mechanics
4. `test_extraction_pipeline.py` — full wire test

---

## Success Criteria

All tests pass:
```bash
python scripts/bootstrap_db.py --path :memory:  # exits 0
pytest tests/test_actor_registration.py -v      # all green
pytest tests/test_lock_in_integration.py -v     # all green
pytest tests/test_extraction_pipeline.py -v     # all green
```

---

## Notes

- Scribe uses Claude Haiku for extraction — mock in tests or set `ANTHROPIC_API_KEY`
- New nodes start as "drifting" (lock_in = 0.15) — they become "fluid" after access/reinforcement
- Reinforced nodes are NEVER pruned, even if otherwise drifting

---

## Reference Section

### File Paths

```
# Schema
src/luna/substrate/schema.sql

# Core substrate
src/luna/substrate/database.py      # MemoryDatabase class
src/luna/substrate/memory.py        # MemoryMatrix class
src/luna/substrate/embeddings.py    # EmbeddingStore, EmbeddingGenerator
src/luna/substrate/graph.py         # MemoryGraph class
src/luna/substrate/lock_in.py       # Lock-in coefficient computation

# Actors
src/luna/actors/base.py             # Actor, Message base classes
src/luna/actors/scribe.py           # ScribeActor (Ben Franklin)
src/luna/actors/librarian.py        # LibrarianActor (The Dude)
src/luna/actors/matrix.py           # MatrixActor
src/luna/actors/director.py         # DirectorActor

# Engine
src/luna/engine.py                  # LunaEngine, EngineConfig

# Existing test fixtures
tests/conftest.py                   # Fixtures: temp_data_dir, engine_config, mock_actor
```

---

### Engine Config

```python
from luna.engine import LunaEngine, EngineConfig
from pathlib import Path

# Test config
config = EngineConfig(
    cognitive_interval=0.1,      # Fast ticks for tests
    reflective_interval=60,
    data_dir=Path("/tmp/luna_test"),
    enable_local_inference=False,  # Skip local model loading
)

engine = LunaEngine(config)
await engine._boot()  # Registers actors
await engine.wait_ready(timeout=5.0)
```

---

### Actor Registration (Automatic in _boot)

Engine auto-registers on boot if not present:
```python
# From engine.py _boot():
if "matrix" not in self.actors:
    matrix = MatrixActor()
    self.register_actor(matrix)
    await matrix.initialize()

if "director" not in self.actors:
    self.register_actor(DirectorActor(enable_local=self.config.enable_local_inference))

if "scribe" not in self.actors:
    from luna.actors.scribe import ScribeActor
    self.register_actor(ScribeActor())

if "librarian" not in self.actors:
    from luna.actors.librarian import LibrarianActor
    self.register_actor(LibrarianActor())
```

---

### Message Types & Payloads

**Scribe (Ben Franklin):**
```python
# extract_turn - Extract from conversation turn
await engine.send_message("scribe", Message(
    type="extract_turn",
    payload={
        "role": "user",           # or "assistant"
        "content": "The message text...",
        "turn_id": 123,           # Optional
        "session_id": "sess_001", # Optional
    }
))

# extract_text - Extract from raw text
await engine.send_message("scribe", Message(
    type="extract_text",
    payload={
        "text": "Raw text to extract from...",
        "source": "document",     # Optional
    }
))

# flush_stack - Force process pending chunks
await engine.send_message("scribe", Message(type="flush_stack"))

# get_stats - Get extraction statistics
await engine.send_message("scribe", Message(type="get_stats"))
```

**Librarian (The Dude):**
```python
# file - File an extraction (usually sent by Scribe)
await engine.send_message("librarian", Message(
    type="file",
    payload={
        "objects": [
            {"type": "FACT", "content": "...", "confidence": 0.9, "entities": ["..."]},
        ],
        "edges": [
            {"from_ref": "A", "to_ref": "B", "edge_type": "relates_to"},
        ],
        "source": "conversation",
        "session_id": "sess_001",
    }
))

# get_context - Retrieve context for query
await engine.send_message("librarian", Message(
    type="get_context",
    payload={
        "query": "What do I know about X?",
        "budget": "balanced",      # or "minimal", "rich", or int
        "node_types": ["FACT", "DECISION"],  # Optional filter
    }
))

# prune - Run synaptic pruning
await engine.send_message("librarian", Message(
    type="prune",
    payload={
        "confidence_threshold": 0.3,  # Min edge confidence to keep
        "age_days": 30,               # Min age to consider for pruning
        "prune_nodes": True,          # Also prune drifting nodes
        "max_prune_nodes": 100,       # Max nodes to prune per pass
    }
))

# resolve_entity - Resolve entity name to node ID
await engine.send_message("librarian", Message(
    type="resolve_entity",
    payload={
        "name": "sqlite-vec",
        "entity_type": "TECHNOLOGY",  # Optional
    }
))

# get_stats - Get filing statistics
await engine.send_message("librarian", Message(type="get_stats"))
```

---

### sqlite-vec Setup

```python
from luna.substrate.database import MemoryDatabase
from luna.substrate.embeddings import EmbeddingStore

# Initialize database
db = MemoryDatabase(db_path=Path("/tmp/test.db"))
await db.connect()  # Creates tables from schema.sql

# Initialize embeddings (loads sqlite-vec extension)
embeddings = EmbeddingStore(db, dim=1536)
success = await embeddings.initialize()

if success:
    # Store embedding
    await embeddings.store("node_123", [0.1, 0.2, ...])  # 1536-dim vector

    # Search similar
    results = await embeddings.search(query_vector, limit=10)
    # Returns: [(node_id, similarity_score), ...]
```

**Note:** sqlite-vec requires the `sqlite-vec` pip package:
```bash
pip install sqlite-vec
```

---

### Existing Test Fixtures (conftest.py)

```python
@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def engine_config(temp_data_dir, monkeypatch):
    """Create test engine configuration with Eclissi mocked out."""
    import luna.actors.matrix as matrix_module
    monkeypatch.setattr(matrix_module, "ECLISSI_AVAILABLE", False)

    return EngineConfig(
        cognitive_interval=0.1,
        reflective_interval=60,
        data_dir=temp_data_dir,
    )

@pytest.fixture
def mock_actor():
    """Create a mock actor for testing."""
    return MockActor("test_actor")
```

---

### Mocking Scribe's Claude Calls

Scribe uses Anthropic client for extraction. To mock in tests:

```python
from unittest.mock import AsyncMock, MagicMock, patch

# Mock extraction response
mock_response = MagicMock()
mock_response.content = [MagicMock(text=json.dumps({
    "objects": [
        {"type": "DECISION", "content": "Use sqlite-vec", "confidence": 0.95, "entities": ["sqlite-vec"]},
    ],
    "edges": []
}))]

# Patch the Anthropic client
with patch.object(scribe_actor, 'client') as mock_client:
    mock_client.messages.create.return_value = mock_response
    # Now scribe will use mock response
```

Or set `ANTHROPIC_API_KEY` env var for real API calls in integration tests.

---

### Database Schema Columns (memory_nodes)

```sql
CREATE TABLE IF NOT EXISTS memory_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,          -- FACT, DECISION, PROBLEM, ACTION, etc.
    content TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    confidence REAL DEFAULT 1.0,
    importance REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    reinforcement_count INTEGER DEFAULT 0,  -- NEW
    lock_in REAL DEFAULT 0.15,              -- NEW
    lock_in_state TEXT DEFAULT 'drifting',  -- NEW: drifting, fluid, settled
    last_accessed TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT
);
```

---

### Lock-In States

| State | Lock-In Range | Meaning |
|-------|---------------|---------|
| 🟠 drifting | L < 0.30 | Rarely accessed, pruning candidate |
| 🔵 fluid | 0.30 ≤ L < 0.70 | Active but not settled |
| 🟢 settled | L ≥ 0.70 | Core knowledge, persistent |

**Note:** New nodes start as "drifting" (0.15). They become "fluid" through access/reinforcement, then drift back if unused.

---

### Quick Verification Commands

```bash
# Run unit tests
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
source .venv/bin/activate

# Lock-in unit tests (already passing)
pytest tests/test_lock_in.py -v

# Check imports work
python -c "from luna.substrate import compute_lock_in, LockInState; print('OK')"

# Check engine boots
python -c "
import asyncio
from luna.engine import LunaEngine, EngineConfig
async def test():
    engine = LunaEngine()
    await engine._boot()
    print('Actors:', list(engine.actors.keys()))
asyncio.run(test())
"
```
