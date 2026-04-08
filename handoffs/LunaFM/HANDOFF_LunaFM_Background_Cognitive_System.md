# HANDOFF: LunaFM — Background Cognitive Broadcast System

**Priority:** ARCHITECTURE — This is Luna's inner life. Not a bug fix. Build it right.
**Scope:** Daemon infrastructure, YAML channel system, spectral engine, LunaScript coupling
**Project Root:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root`
**Python:** `.venv/bin/python3`
**Prerequisite:** L1 composite scoring working (Handoff #47 — done)

---

## WHAT IS LUNAFM

LunaFM is Luna's background cognitive system. It runs as an always-on daemon alongside the conversation pipeline, giving Luna the ability to think between conversations — noticing patterns, finding cross-domain connections, consolidating memory, and pre-loading insights that feed into real-time conversation through existing infrastructure.

Modeled after a radio station: the **station** is the scheduler, **channels** are programs running on different frequency bands, and **YAML** is the program guide. Everything is inspectable and editable by the user — sovereign cognition.

LunaFM does NOT add stages to the conversation pipeline. It pre-loads the stages that already exist. Memory search already runs. Revolving context already assembles. LunaScript already measures traits. LunaFM makes sure there's something worth finding when those stages fire.

---

## WHAT PROBLEM THIS SOLVES

1. **Luna has no thought between conversations.** She's a stateless function that pretends to have memory. When you ask "what have you been thinking about?" — there's no real answer. With LunaFM, there is.

2. **Retrieval is reactive, never proactive.** You ask about water temples, the pipeline scrambles for 10-20s to find context. With LunaFM, the Entertainment channel already found the Kinoni governance ↔ Balinese subak resonance pair last night. It's sitting in the revolving context. The retrieval becomes a cache hit.

3. **Memory pollution compounds unchecked.** 325 marzipan nodes accumulated because nothing was looking. The History channel runs continuous dedup, decay analysis, and consolidation — catching pollution before it compounds.

4. **The spectral retrieval layer (V3) has no runtime.** The eigendecomposition exists as a concept but has no process to keep spectral coordinates fresh. LunaFM's spectral engine runs it on a schedule, so V3 retrieval is always ready.

5. **LunaScript measures but never acts.** The trait system detects curiosity, depth, warmth — but nothing responds to those measurements between turns. LunaFM channels modulate their behavior based on cognitive state, and nudge traits back, creating a feedback loop that makes Luna feel responsive rather than mechanical.

---

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────┐
│ LunaFM Daemon (always running, preemptible by conversation) │
│                                                             │
│  ┌─────────┐  ┌──────────────┐  ┌─────────┐               │
│  │  News   │  │Entertainment │  │ History │  ... more      │
│  │ (15s)   │  │   (2min)     │  │ (10min) │  channels      │
│  └────┬────┘  └──────┬───────┘  └────┬────┘               │
│       │              │               │                      │
│  ┌────┴──────────────┴───────────────┴────┐                │
│  │         Spectral Engine (V3)           │                │
│  │    Eigendecomposition on schedule      │                │
│  └────────────────────────────────────────┘                │
│       │              │               │                      │
│  ┌────┴──────────────┴───────────────┴────┐                │
│  │      LunaScript Frequency Coupling     │                │
│  │   Traits → aperture, channels → nudge  │                │
│  └────────────────────────────────────────┘                │
└───────────────────────┬─────────────────────────────────────┘
                        │
            7 INTEGRATION POINTS
            (all to existing infrastructure)
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  Memory Matrix   Revolving Ctx   LunaScript
  (nodes+edges)   (OUTER ring)   (trait vector)
        │               │               │
        ▼               ▼               ▼
  ┌─────────────────────────────────────────┐
  │     Existing Conversation Pipeline      │
  │  (no changes — reads from same tables)  │
  └─────────────────────────────────────────┘
```

---

## 7 INTEGRATION POINTS (all existing infrastructure)

Each touchpoint writes to or reads from something that already exists. No conversation pipeline code changes.

### 1. LunaScript ↔ LunaFM (bidirectional)
- **Read:** LunaScript trait measurements (curiosity, depth, warmth, etc.) from `lunascript_state` table
- **Write:** Trait nudges back to `lunascript_state` when channels produce insights
- **Effect:** High curiosity → Entertainment channel widens aperture (σ). Channel finds resonance pair → bumps curiosity +0.05 → response geometry shifts toward EXPLORING
- **Table:** `lunascript_state` (existing)

### 2. Memory Matrix nodes
- **Write:** FLAG, SYNTHESIS, CONSOLIDATION, QUESTION nodes to `memory_nodes` table
- **Tags:** `source='lunafm:{channel_id}'`, low `lock_in` (0.15-0.25)
- **Effect:** Normal L1 composite scoring finds these nodes at query time. No retrieval code changes.
- **Table:** `memory_nodes` (existing)

### 3. Spectral coordinates (V3)
- **Write:** Pre-computed spectral coordinates to `spectral_coordinates` table (new table, but V3 spec already defines it)
- **Read:** `graph_edges` table for Laplacian construction
- **Effect:** V3 spectral retrieval (Section 5.3) becomes a lookup instead of a computation
- **Tables:** `graph_edges` (existing), `spectral_coordinates` (new, per V3 spec)

### 4. Revolving context OUTER ring
- **Write:** Up to 5 items deposited via `engine.context.add(content, source=MEMORY, relevance=score)`
- **Effect:** Insights are available at lowest priority. If used in conversation, `promotion_on_access` bumps relevance.
- **Interface:** `RevolvingContext.add()` (existing)

### 5. Response geometry via trait modulation
- **Mechanism:** Trait nudges change the LunaScript trait vector → `position.py` reads traits → response geometry adjusts (more questions, longer responses, tangent permission)
- **Effect:** Luna naturally asks "whatever happened with X?" because curiosity was nudged, not because it was scripted
- **Code:** `lunascript/position.py` (existing, reads from `lunascript_state`)

### 6. Scribe hints
- **Write:** Tagged messages to scribe mailbox: `await scribe.mailbox.put(Message(type="hint", payload={...}))`
- **Effect:** Pre-loaded context for next relevant conversation turn
- **Interface:** `scribe.mailbox` (existing)

### 7. Edge delta triggers spectral recompute
- **Read:** Count of new edges since last eigendecomposition
- **Effect:** When edge delta > 5%, spectral engine recomputes on next cycle
- **Table:** `graph_edges` (existing)

---

## PHASE 1: DAEMON INFRASTRUCTURE

### 1A. Station scheduler

Create `src/luna/lunafm/__init__.py`, `src/luna/lunafm/station.py`:

```python
"""
LunaFM Station — background cognitive broadcast scheduler.

Manages channel lifecycle, resource budget, and conversation preemption.
Runs as an asyncio task alongside the Luna engine event loop.
"""
import asyncio
import logging
import time
import yaml
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Station:
    def __init__(self, engine, config_path: Path):
        self._engine = engine
        self._config = self._load_config(config_path)
        self._channels: dict[str, Channel] = {}
        self._running = False
        self._preempted = False
        self._task: Optional[asyncio.Task] = None

    def _load_config(self, path: Path) -> dict:
        with open(path) as f:
            return yaml.safe_load(f)

    async def start(self):
        """Start the station. Load channels from YAML, begin scheduling."""
        channels_dir = Path(self._config['station']['channels_dir'])
        for yaml_file in channels_dir.glob('*.yaml'):
            channel = Channel.from_yaml(yaml_file, self._engine, self)
            self._channels[channel.id] = channel
            logger.info(f"[LUNAFM] Loaded channel: {channel.id} ({channel.name})")

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[LUNAFM] Station on air. {len(self._channels)} channels loaded.")

    async def stop(self):
        """Graceful shutdown."""
        self._running = False
        for channel in self._channels.values():
            await channel.pause()
        if self._task:
            self._task.cancel()

    async def preempt(self):
        """User message arrived. Pause all channels within grace period."""
        self._preempted = True
        grace_ms = self._config['station']['budget']['preempt_grace_ms']
        for channel in self._channels.values():
            await channel.pause(grace_ms=grace_ms)
        logger.debug("[LUNAFM] All channels preempted for conversation")

    async def resume(self):
        """Conversation ended. Resume channels after cooldown."""
        cooldown = self._config['station']['budget']['cooldown_after_conversation_ms']
        await asyncio.sleep(cooldown / 1000.0)
        self._preempted = False
        logger.debug("[LUNAFM] Channels resuming after conversation cooldown")

    async def _run_loop(self):
        """Main scheduling loop. Runs channels by priority."""
        priority = self._config['station']['priority_order']
        max_concurrent = self._config['station']['budget']['max_concurrent_channels']

        while self._running:
            if self._preempted:
                await asyncio.sleep(0.5)
                continue

            # Run channels in priority order, respecting concurrency limit
            active = sum(1 for c in self._channels.values() if c.is_active)
            for channel_id in priority:
                if active >= max_concurrent:
                    break
                channel = self._channels.get(channel_id)
                if channel and channel.should_tick():
                    asyncio.create_task(channel.tick())
                    active += 1

            await asyncio.sleep(1.0)  # Station tick rate: 1s
```

### 1B. Channel state machine

Create `src/luna/lunafm/channel.py`:

```python
"""
LunaFM Channel — a single mode of background attention.

Each channel is a YAML-driven state machine with states:
idle → scanning → processing → emitting → cooldown

States map to Python coroutines defined in channel-specific modules.
"""
import asyncio
import logging
import time
import yaml
from enum import Enum
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)


class ChannelState(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    PROCESSING = "processing"
    EMITTING = "emitting"
    COOLDOWN = "cooldown"
    PAUSED = "paused"


class Channel:
    def __init__(self, config: dict, engine, station):
        self._config = config['channel']
        self._engine = engine
        self._station = station
        self.id = self._config['id']
        self.name = self._config['name']
        self._state = ChannelState.IDLE
        self._last_tick = 0.0
        self._is_active = False
        self._cache = LRUCache(self._config.get('cache', {}).get('max_items', 50))

        # Load process handlers from channel-specific module
        self._handlers = self._load_handlers()

    @classmethod
    def from_yaml(cls, path: Path, engine, station) -> 'Channel':
        with open(path) as f:
            config = yaml.safe_load(f)
        return cls(config, engine, station)

    @property
    def is_active(self) -> bool:
        return self._is_active

    def should_tick(self) -> bool:
        """Check if this channel should run based on schedule."""
        if self._state == ChannelState.PAUSED:
            return False
        interval = self._config['frequency']['interval_s']
        if time.time() - self._last_tick < interval:
            return False
        # Check only_when constraint
        only_when = self._config['frequency'].get('only_when')
        if only_when == 'idle' and self._engine_is_in_conversation():
            return False
        return True

    async def tick(self):
        """Run one cycle of the channel state machine."""
        self._is_active = True
        self._last_tick = time.time()

        try:
            # Walk the state machine
            self._state = ChannelState.SCANNING
            scan_result = await self._run_process('scanning')

            if scan_result.get('signal'):
                self._state = ChannelState.PROCESSING
                process_result = await self._run_process('processing', scan_result)

                if process_result.get('emit'):
                    self._state = ChannelState.EMITTING
                    await self._run_process('emitting', process_result)

            # Cooldown
            self._state = ChannelState.COOLDOWN
            cooldown = self._get_state_config('cooldown').get('duration_ms', 5000)
            await asyncio.sleep(cooldown / 1000.0)

        except asyncio.CancelledError:
            logger.debug(f"[LUNAFM:{self.id}] Preempted during {self._state.value}")
        except Exception as e:
            logger.warning(f"[LUNAFM:{self.id}] Error in {self._state.value}: {e}")
        finally:
            self._state = ChannelState.IDLE
            self._is_active = False

    async def pause(self, grace_ms: int = 500):
        """Pause the channel. Current state gets grace period to checkpoint."""
        self._state = ChannelState.PAUSED
        # The running tick() will catch CancelledError on next await

    async def _run_process(self, state_name: str, context: dict = None) -> dict:
        """Execute the process defined for a given state."""
        state_config = self._get_state_config(state_name)
        process_name = state_config.get('process')
        timeout_ms = state_config.get('timeout_ms', 5000)

        handler = self._handlers.get(process_name)
        if not handler:
            logger.warning(f"[LUNAFM:{self.id}] No handler for process '{process_name}'")
            return {}

        try:
            return await asyncio.wait_for(
                handler(self._engine, context or {}, self._config),
                timeout=timeout_ms / 1000.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"[LUNAFM:{self.id}] Process '{process_name}' timed out ({timeout_ms}ms)")
            return {}

    def _get_state_config(self, state_name: str) -> dict:
        return self._config.get('states', {}).get(state_name, {})

    def _load_handlers(self) -> dict:
        """Load process handlers from the channel's Python module."""
        # Maps process names from YAML to Python coroutines
        # e.g., news.yaml's "scan_recent_activity" → news_handlers.scan_recent_activity()
        module_name = f"luna.lunafm.handlers.{self.id}"
        try:
            import importlib
            module = importlib.import_module(module_name)
            return {name: getattr(module, name) for name in dir(module)
                    if not name.startswith('_') and callable(getattr(module, name))}
        except ImportError:
            logger.warning(f"[LUNAFM:{self.id}] No handler module '{module_name}'")
            return {}

    def _engine_is_in_conversation(self) -> bool:
        """Check if the engine is actively in a conversation turn."""
        return getattr(self._engine, '_is_processing', False)
```

### 1C. YAML config files

Copy the 4 YAML files from this handoff's attachments into:
- `config/lunafm/station.yaml`
- `config/lunafm/channels/news.yaml`
- `config/lunafm/channels/entertainment.yaml`
- `config/lunafm/channels/history.yaml`

(Files are provided separately — see station.yaml, news.yaml, entertainment.yaml, history.yaml)

---

## PHASE 2: CHANNEL HANDLERS

### 2A. News channel handlers

Create `src/luna/lunafm/handlers/news.py`:

```python
"""News channel handlers — present-tense awareness."""
import sqlite3
import logging

logger = logging.getLogger(__name__)


async def scan_recent_activity(engine, context: dict, config: dict) -> dict:
    """Scan recent conversation turns and memory events. No LLM call."""
    db = engine.db  # or however the engine exposes the DB connection
    
    recent_turns = db.execute("""
        SELECT content, created_at FROM conversation_turns
        WHERE created_at > datetime('now', '-5 minutes')
        ORDER BY created_at DESC LIMIT 10
    """).fetchall()
    
    recent_nodes = db.execute("""
        SELECT node_type, content, created_at FROM memory_nodes
        WHERE created_at > datetime('now', '-5 minutes')
        AND source NOT LIKE 'lunafm:%'
        ORDER BY created_at DESC LIMIT 10
    """).fetchall()
    
    if recent_turns or recent_nodes:
        return {
            'signal': True,
            'turns': recent_turns,
            'nodes': recent_nodes
        }
    return {'signal': False}


async def evaluate_signal(engine, context: dict, config: dict) -> dict:
    """LLM call to assess whether recent activity contains notable patterns."""
    provider = await engine.get_llm_provider()  # Use station default model
    
    scan_summary = _format_scan_results(context)
    prompt = config['processes']['evaluate_signal']['prompt_template'].format(
        scan_results=scan_summary
    )
    
    response = await provider.generate(
        prompt=prompt,
        system="You are Luna's News channel.",
        max_tokens=100
    )
    
    text = response.text.strip()
    if text == "NOTHING_NOTABLE":
        return {'emit': False}
    
    return {'emit': True, 'insight': text, 'signal_type': _parse_signal_type(text)}


async def write_artifact(engine, context: dict, config: dict) -> dict:
    """Write a FLAG node to the Memory Matrix."""
    engine.db.execute("""
        INSERT INTO memory_nodes (id, node_type, content, source, lock_in, confidence, 
                                   importance, access_count, created_at, updated_at)
        VALUES (?, 'FLAG', ?, 'lunafm:news', 0.15, 0.5, 0.3, 0, datetime('now'), datetime('now'))
    """, (_generate_id(), context['insight']))
    engine.db.commit()
    
    logger.info(f"[LUNAFM:news] Emitted FLAG: {context['insight'][:60]}...")
    return {'artifact_written': True}
```

### 2B. Entertainment channel handlers

Create `src/luna/lunafm/handlers/entertainment.py`:

```python
"""Entertainment channel handlers — lateral creative thinking."""
import logging

logger = logging.getLogger(__name__)


async def sample_nodes(engine, context: dict, config: dict) -> dict:
    """Sample two random nodes from different clusters."""
    db = engine.db
    
    node_a = db.execute("""
        SELECT id, node_type, content, cluster_id FROM memory_nodes
        WHERE node_type IN ('FACT', 'ENTITY', 'MEMORY', 'DECISION')
        AND lock_in > 0.3 AND source NOT LIKE 'lunafm:%'
        ORDER BY RANDOM() LIMIT 1
    """).fetchone()
    
    if not node_a:
        return {'pair_selected': False}
    
    node_b = db.execute("""
        SELECT id, node_type, content, cluster_id FROM memory_nodes
        WHERE node_type IN ('FACT', 'ENTITY', 'MEMORY', 'DECISION')
        AND lock_in > 0.3 AND source NOT LIKE 'lunafm:%'
        AND cluster_id != ? AND id != ?
        ORDER BY RANDOM() LIMIT 1
    """, (node_a['cluster_id'], node_a['id'])).fetchone()
    
    if not node_b:
        return {'pair_selected': False}
    
    return {
        'pair_selected': True,
        'node_a': dict(node_a),
        'node_b': dict(node_b)
    }


async def find_connection(engine, context: dict, config: dict) -> dict:
    """The creative leap — find structural connection between two nodes."""
    provider = await engine.get_llm_provider()
    
    prompt = config['processes']['find_connection']['prompt_template'].format(
        node_a_type=context['node_a']['node_type'],
        node_a_content=context['node_a']['content'][:300],
        node_b_type=context['node_b']['node_type'],
        node_b_content=context['node_b']['content'][:300]
    )
    
    response = await provider.generate(
        prompt=prompt,
        system="You are Luna's creative subconscious.",
        max_tokens=200,
        temperature=0.9
    )
    
    text = response.text.strip()
    if text == "NO_CONNECTION":
        return {'connection_found': False}
    
    return {
        'connection_found': True,
        'connection': text,
        'connection_type': _parse_connection_type(text)
    }


async def assess_novelty(engine, context: dict, config: dict) -> dict:
    """Check if this connection already exists in the graph."""
    db = engine.db
    
    existing = db.execute("""
        SELECT COUNT(*) FROM graph_edges
        WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?)
    """, (context['node_a']['id'], context['node_b']['id'],
          context['node_b']['id'], context['node_a']['id'])).fetchone()[0]
    
    if existing > 0:
        return {'novel_insight': False, 'already_known': True}
    
    return {'novel_insight': True, 'emit': True}


async def write_synthesis(engine, context: dict, config: dict) -> dict:
    """Write a SYNTHESIS node and graph edge."""
    db = engine.db
    node_id = _generate_id()
    
    # Write synthesis node
    db.execute("""
        INSERT INTO memory_nodes (id, node_type, content, source, lock_in, confidence,
                                   importance, access_count, created_at, updated_at, metadata)
        VALUES (?, 'SYNTHESIS', ?, 'lunafm:entertainment', 0.2, 0.5, 0.4, 0,
                datetime('now'), datetime('now'), ?)
    """, (node_id, context['connection'], 
          json.dumps({
              'node_a_id': context['node_a']['id'],
              'node_b_id': context['node_b']['id'],
              'connection_type': context['connection_type']
          })))
    
    # Write graph edge
    db.execute("""
        INSERT INTO graph_edges (from_id, to_id, relationship, strength, created_at, origin)
        VALUES (?, ?, 'SYNTHESIZED_CONNECTION', 0.3, datetime('now'), 'lunafm:entertainment')
    """, (context['node_a']['id'], context['node_b']['id']))
    
    db.commit()
    logger.info(f"[LUNAFM:entertainment] Synthesis: {context['connection'][:80]}...")
    return {'artifact_written': True}
```

### 2C. History channel handlers

Create `src/luna/lunafm/handlers/history.py` — follows the same pattern. Key operations:
- `survey_memory_health()` — SQL queries for duplicates, fading nodes, abandoned topics (no LLM)
- `analyze_temporal_patterns()` — LLM call at temperature 0.3 to recommend ONE action
- `consolidate_memories()` — execute merge/archive/question based on LLM recommendation
- `write_consolidation()` — write CONSOLIDATION node

The history channel's merge operation:
```python
async def _merge_nodes(db, id_a, id_b):
    """Merge two duplicate nodes. Keep higher lock_in, combine content."""
    a = db.execute("SELECT * FROM memory_nodes WHERE id=?", (id_a,)).fetchone()
    b = db.execute("SELECT * FROM memory_nodes WHERE id=?", (id_b,)).fetchone()
    
    # Keep the one with higher lock_in
    keeper, discard = (a, b) if a['lock_in'] >= b['lock_in'] else (b, a)
    
    # Redirect edges from discard to keeper
    db.execute("UPDATE graph_edges SET from_id=? WHERE from_id=?",
               (keeper['id'], discard['id']))
    db.execute("UPDATE graph_edges SET to_id=? WHERE to_id=?",
               (keeper['id'], discard['id']))
    
    # Soft-delete the discard (set lock_in near zero, it will decay)
    db.execute("UPDATE memory_nodes SET lock_in=0.01, source='lunafm:history:merged' WHERE id=?",
               (discard['id'],))
    db.commit()
```

---

## PHASE 3: SPECTRAL ENGINE

### 3A. Eigendecomposition service

Create `src/luna/lunafm/spectral.py`:

```python
"""
Spectral engine — eigendecomposition of the Memory Matrix graph Laplacian.

Computes spectral coordinates for all memory nodes, enabling V3 resonance
retrieval. Runs on a schedule managed by the History channel.

Reference: Luna_Protocol_V3_Spectral_Retrieval_Layer.docx
"""
import numpy as np
import logging
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import eigsh

logger = logging.getLogger(__name__)

# Edge type weights from V3 spec Section 5.1
EDGE_WEIGHTS = {
    'CONTRADICTS': 1.0,
    'DEPENDS_ON': 0.9, 'SUPERSEDES': 0.9,
    'SUPPORTS': 0.85, 'ENABLES': 0.85,
    'INVOLVES': 0.7, 'CLARIFIES': 0.7,
    'SYNTHESIZED_CONNECTION': 0.6,  # LunaFM-generated edges
    'RELATES_TO': 0.3,
    'MENTIONS': 0.2,
}

K_EIGENVECTORS = 30  # Number of spectral dimensions


class SpectralEngine:
    def __init__(self, db):
        self._db = db
        self._last_edge_count = 0
        self._spectral_coords = {}  # node_id → np.array of K floats

    def should_recompute(self) -> bool:
        """Check if edge count changed enough to warrant recomputation."""
        current = self._db.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
        if self._last_edge_count == 0:
            return True
        delta_pct = abs(current - self._last_edge_count) / max(self._last_edge_count, 1)
        return delta_pct > 0.05  # 5% threshold per V3 spec

    async def compute(self):
        """Run eigendecomposition on the graph Laplacian."""
        # 1. Load nodes and edges
        nodes = [r[0] for r in self._db.execute(
            "SELECT id FROM memory_nodes WHERE lock_in > 0.3"
        ).fetchall()]
        
        if len(nodes) < K_EIGENVECTORS + 1:
            logger.info(f"[SPECTRAL] Not enough nodes ({len(nodes)}) for decomposition")
            return

        node_idx = {nid: i for i, nid in enumerate(nodes)}
        n = len(nodes)

        # 2. Build adjacency matrix
        edges = self._db.execute("""
            SELECT from_id, to_id, relationship FROM graph_edges
            WHERE from_id IN ({}) AND to_id IN ({})
        """.format(','.join('?' * n), ','.join('?' * n)), nodes + nodes).fetchall()

        rows, cols, vals = [], [], []
        for from_id, to_id, rel in edges:
            if from_id in node_idx and to_id in node_idx:
                w = EDGE_WEIGHTS.get(rel, 0.3)
                i, j = node_idx[from_id], node_idx[to_id]
                rows.extend([i, j])
                cols.extend([j, i])
                vals.extend([w, w])

        A = csr_matrix((vals, (rows, cols)), shape=(n, n))

        # 3. Build Laplacian: L = D - A
        degrees = np.array(A.sum(axis=1)).flatten()
        D = csr_matrix((degrees, (range(n), range(n))), shape=(n, n))
        L = D - A

        # 4. Eigendecomposition (Lanczos, per V3 spec Section 5.2)
        k = min(K_EIGENVECTORS, n - 2)
        eigenvalues, eigenvectors = eigsh(L, k=k, which='SM')

        # 5. Store spectral coordinates
        self._spectral_coords = {}
        for node_id, idx in node_idx.items():
            self._spectral_coords[node_id] = eigenvectors[idx].tolist()

        # 6. Persist to database
        self._db.execute("CREATE TABLE IF NOT EXISTS spectral_coordinates "
                         "(node_id TEXT PRIMARY KEY, coords TEXT, computed_at TEXT)")
        self._db.execute("DELETE FROM spectral_coordinates")
        for node_id, coords in self._spectral_coords.items():
            self._db.execute(
                "INSERT INTO spectral_coordinates (node_id, coords, computed_at) VALUES (?, ?, datetime('now'))",
                (node_id, json.dumps(coords))
            )
        self._db.commit()

        self._last_edge_count = len(edges)
        logger.info(
            f"[SPECTRAL] Decomposition complete: {n} nodes, {len(edges)} edges, "
            f"{k} eigenvectors, λ₁={eigenvalues[1]:.4f} (Fiedler)"
        )

    def find_resonance_pairs(self, node_id: str, sigma: float = 0.05) -> list:
        """Find nodes spectrally close to the given node (V3 Section 5.3)."""
        if node_id not in self._spectral_coords:
            return []
        
        target = np.array(self._spectral_coords[node_id])
        pairs = []
        
        for other_id, coords in self._spectral_coords.items():
            if other_id == node_id:
                continue
            distance = np.linalg.norm(target - np.array(coords))
            if distance < sigma:
                pairs.append({'node_id': other_id, 'spectral_distance': distance})
        
        return sorted(pairs, key=lambda x: x['spectral_distance'])
```

---

## PHASE 4: LUNASCRIPT FREQUENCY COUPLING

### 4A. Trait-to-aperture mapping

Create `src/luna/lunafm/frequency_coupling.py`:

```python
"""
Frequency coupling — bidirectional link between LunaScript traits
and LunaFM channel behavior.

Cognitive frequencies (LunaScript traits) modulate how deeply
Luna listens to her knowledge frequencies (spectral harmonics).
"""

# Aperture mapping: trait value → spectral search radius (sigma)
# Per V3 spec Section 5.4
APERTURE_MAP = {
    'TUNNEL': 0.01,
    'NARROW': 0.02,
    'BALANCED': 0.05,
    'WIDE': 0.10,
    'OPEN': 0.20,
}

def trait_to_aperture(curiosity: float) -> float:
    """Map curiosity trait to spectral search radius."""
    if curiosity >= 0.9:
        return APERTURE_MAP['OPEN']
    elif curiosity >= 0.7:
        return APERTURE_MAP['WIDE']
    elif curiosity >= 0.5:
        return APERTURE_MAP['BALANCED']
    elif curiosity >= 0.3:
        return APERTURE_MAP['NARROW']
    else:
        return APERTURE_MAP['TUNNEL']


def nudge_trait(db, trait_name: str, delta: float):
    """Nudge a LunaScript trait value. Clamped to 0-1."""
    current = db.execute(
        "SELECT trait_vector FROM lunascript_state WHERE id=1"
    ).fetchone()
    if not current:
        return
    
    import json
    vector = json.loads(current[0])
    old_val = vector.get(trait_name, 0.5)
    new_val = max(0.0, min(1.0, old_val + delta))
    vector[trait_name] = new_val
    
    db.execute(
        "UPDATE lunascript_state SET trait_vector=?, updated_at=? WHERE id=1",
        (json.dumps(vector), time.time())
    )
    db.commit()
    
    logger.debug(f"[LUNAFM] Nudged {trait_name}: {old_val:.2f} → {new_val:.2f} (Δ{delta:+.2f})")
```

### 4B. Coupling config in channel YAML

Each channel's YAML can define `cognitive_coupling`:

```yaml
cognitive_coupling:
  listen_to:
    - trait: curiosity
      action: modulate_aperture
      # Maps curiosity 0-1 → sigma via APERTURE_MAP
    - trait: depth
      action: prefer_deep_resonance
      # When depth is high, favor lower eigenvalues
  
  emit_to:
    - trait: curiosity
      nudge: 0.05
      on: resonance_pair_found
    - trait: warmth
      nudge: 0.03
      on: personal_memory_surfaced
```

The channel state machine reads `listen_to` before each tick to set parameters, and fires `emit_to` nudges after emitting an artifact.

---

## PHASE 5: ENGINE INTEGRATION

### 5A. Register LunaFM as an engine service

In `src/luna/engine.py`, at boot (after actors are initialized):

```python
from luna.lunafm.station import Station

# After actor initialization
self._lunafm = Station(self, Path("config/lunafm/station.yaml"))
await self._lunafm.start()
```

### 5B. Wire conversation preemption

In `_handle_user_message()` (engine.py ~line 1062):

```python
async def _handle_user_message(self, user_message, ...):
    # Preempt LunaFM
    if self._lunafm:
        await self._lunafm.preempt()
    
    # ... existing pipeline ...
    
    # Resume LunaFM after response
    if self._lunafm:
        asyncio.create_task(self._lunafm.resume())
```

### 5C. Wire spectral recompute trigger

In the post-turn memory write path (engine.py ~line 1350, Phase 5 Bridge):

```python
# After writing new edges to memory matrix
if self._lunafm and hasattr(self._lunafm, '_spectral_engine'):
    # Don't block — just flag for next cycle
    self._lunafm._spectral_engine_dirty = True
```

---

## VERIFICATION

### Phase 1 verification (daemon runs)
1. Start Luna. Check logs for `[LUNAFM] Station on air. 3 channels loaded.`
2. Wait 15 seconds. Check for `[LUNAFM:news]` log lines (scanning).
3. Wait 2 minutes. Check for `[LUNAFM:entertainment]` log lines (sampling).
4. Send a user message. Check for `[LUNAFM] All channels preempted`.
5. After response, check for `[LUNAFM] Channels resuming`.

### Phase 2 verification (channels produce artifacts)
1. After 5+ minutes of idle time, check:
   ```sql
   SELECT node_type, source, content, created_at 
   FROM memory_nodes WHERE source LIKE 'lunafm:%'
   ORDER BY created_at DESC LIMIT 10
   ```
2. Entertainment should produce SYNTHESIS nodes.
3. History should produce CONSOLIDATION nodes.
4. News should produce FLAG nodes.

### Phase 3 verification (spectral engine)
1. Check for `[SPECTRAL] Decomposition complete` in logs.
2. Check `spectral_coordinates` table has entries.
3. Test resonance: call `spectral_engine.find_resonance_pairs(node_id, sigma=0.05)`

### Phase 4 verification (frequency coupling)
1. Set curiosity high via LunaScript: update trait to 0.9
2. Check Entertainment channel logs show wider aperture (σ=0.20)
3. After a SYNTHESIS emit, check LunaScript state for curiosity nudge

### Integration verification
1. Have a conversation. Ask "what have you been thinking about?"
2. Luna should reference actual LunaFM artifacts — not hallucinate.
3. Check grounding metadata: `source=lunafm:entertainment` in cited nodes.

---

## DO NOT

- Do NOT modify the conversation pipeline (engine.py retrieval stages)
- Do NOT modify LunaScript measurement/features (21 features stay as-is)
- Do NOT modify the Memory Matrix schema (memory_nodes, graph_edges stay as-is)
- Do NOT add LunaFM as a required dependency for Luna to boot — if YAML is missing, Luna works fine without it
- Do NOT run LunaFM during active conversation turns — preemption is non-negotiable
- Do NOT let LunaFM nodes have lock_in above 0.5 — they're provisional until conversation confirms them
- Do NOT let the scribe extract FACT nodes from LunaFM-generated content — source='lunafm:*' content is inferred, not stated
- Do NOT run the spectral engine on every tick — schedule or edge-delta triggered only

---

## FILES TO CREATE

```
src/luna/lunafm/
├── __init__.py
├── station.py              # Station scheduler
├── channel.py              # Channel state machine
├── spectral.py             # Eigendecomposition engine (V3)
├── frequency_coupling.py   # LunaScript ↔ channel coupling
├── cache.py                # LRU cache for channels
└── handlers/
    ├── __init__.py
    ├── news.py             # News channel handlers
    ├── entertainment.py    # Entertainment channel handlers
    └── history.py          # History channel handlers

config/lunafm/
├── station.yaml            # Master station config
└── channels/
    ├── news.yaml           # News channel definition
    ├── entertainment.yaml  # Entertainment channel definition
    └── history.yaml        # History channel definition
```

## FILES TO MODIFY

- `src/luna/engine.py` — Register LunaFM at boot, wire preempt/resume
- `requirements.txt` — Add `pyyaml`, `scipy` (if not present)

---

## IMPLEMENTATION ORDER

1. **Station + Channel infrastructure** (Phase 1) — get the daemon running, YAML loading, state machine ticking
2. **News handlers** (Phase 2A) — simplest channel, mostly SQL, validates the full loop
3. **History handlers** (Phase 2C) — immediately useful (catches marzipan-style pollution)
4. **Entertainment handlers** (Phase 2B) — the creative channel, needs LLM calls
5. **Spectral engine** (Phase 3) — eigendecomposition, requires scipy
6. **Frequency coupling** (Phase 4) — bidirectional LunaScript link
7. **Engine integration** (Phase 5) — wire into boot, preemption, edge triggers

Steps 1-3 are the MVP. Luna thinks between conversations, catches pollution, and produces artifacts that show up in retrieval. Steps 4-7 add depth — spectral resonance, cognitive coupling, the full inner life.
