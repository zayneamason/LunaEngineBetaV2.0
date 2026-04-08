"""
Luna Engine — The Runtime Heart
================================

The Engine is Luna's nervous system. It coordinates when components wake up,
what input they receive, and how they communicate.

Core loop:
- HOT PATH: Interrupt-driven (STT partials, user interrupts)
- COGNITIVE PATH: ~500ms heartbeat (Director decisions, retrieval)
- REFLECTIVE PATH: Minutes (maintenance, summarization)

The tick is the universal entry point. Everything flows through it.
Luna doesn't respond to events. Luna *lives* through a continuous heartbeat.
"""

import asyncio
import logging
import re as _re
import signal
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Callable, Any, List

from luna.core.events import InputEvent, EventType, EventPriority
from luna.core.input_buffer import InputBuffer
from luna.core.state import EngineState
from luna.core.context import RevolvingContext, ContextSource, ContextItem, ContextRing
from luna.core.paths import project_root, config_dir, data_dir, scripts_dir, user_dir
from luna.actors.base import Actor, Message
from luna.actors.director import DirectorActor
from luna.actors.matrix import MatrixActor
from luna.consciousness import ConsciousnessState

# Agentic Architecture (Phase XIV)
from luna.agentic.loop import AgentLoop, AgentStatus, AgentResult
from luna.agentic.router import QueryRouter, ExecutionPath, RoutingDecision
from luna.agentic.planner import Planner

# Local subtask runner (Qwen 3B lightweight agentic dispatch)
try:
    from luna.inference.subtasks import LocalSubtaskRunner, SubtaskPhaseResult
    SUBTASK_RUNNER_AVAILABLE = True
except ImportError:
    SUBTASK_RUNNER_AVAILABLE = False

logger = logging.getLogger(__name__)


# ─── Query Expansion for Retrieval Retry Cascade ─────────────────────────────

_EXPANSION_STOPWORDS = frozenset(
    "the a an is are was were in on at to for of and or but with by from "
    "that this it as be has have had not no do does did will would can could "
    "may might about what how why when where who which tell me please "
    "your my our you they she he i we".split()
)


def _expand_and_search_extractions(conn, query: str) -> list:
    """
    Tier 2: Extract content words from query, search extractions
    with progressively broader FTS5 queries.

    Strategy:
    1. Extract meaningful words (remove stopwords)
    2. Try OR-joined query (any word matches)
    3. Try individual high-value words
    """
    from luna.substrate.aibrarian_engine import AiBrarianEngine

    # Extract content words
    words = _re.findall(r"[a-zA-Z]{3,}", query.lower())
    content_words = [w for w in words if w not in _EXPANSION_STOPWORDS]

    if not content_words:
        return []

    results = []
    seen_ids: set = set()

    # Strategy A: OR-joined query (any content word matches)
    or_query = " OR ".join(content_words)
    try:
        sanitized = AiBrarianEngine._sanitize_fts_query(or_query)
        rows = conn.conn.execute(
            "SELECT e.node_type, e.content, e.confidence "
            "FROM extractions_fts "
            "JOIN extractions e ON extractions_fts.rowid = e.rowid "
            "WHERE extractions_fts MATCH ? "
            "ORDER BY e.confidence DESC "
            "LIMIT 10",
            (sanitized,),
        ).fetchall()
        for row in rows:
            if not isinstance(row, dict):
                try:
                    row = dict(row)
                except (TypeError, ValueError):
                    continue
            content = row["content"]
            cid = content[:80]
            if cid not in seen_ids:
                seen_ids.add(cid)
                results.append(row)
    except Exception:
        pass

    if len(results) >= 3:
        return results

    # Strategy B: Individual content words (most specific first)
    for word in sorted(content_words, key=len, reverse=True):
        if len(results) >= 5:
            break
        try:
            sanitized = AiBrarianEngine._sanitize_fts_query(word)
            rows = conn.conn.execute(
                "SELECT e.node_type, e.content, e.confidence "
                "FROM extractions_fts "
                "JOIN extractions e ON extractions_fts.rowid = e.rowid "
                "WHERE extractions_fts MATCH ? "
                "ORDER BY e.confidence DESC "
                "LIMIT 2",
                (sanitized,),
            ).fetchall()
            for row in rows:
                if not isinstance(row, dict):
                    try:
                        row = dict(row)
                    except (TypeError, ValueError):
                        continue
                content = row["content"]
                cid = content[:80]
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    results.append(row)
        except Exception:
            continue

    return results


def _content_overlap(a: str, b: str) -> float:
    """Quick word overlap ratio for dedup checking."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / min(len(words_a), len(words_b))


@dataclass
class EngineConfig:
    """Engine configuration."""
    # Tick intervals
    cognitive_interval: float = 0.5  # 500ms
    reflective_interval: float = 300  # 5 minutes

    # Buffer settings
    input_buffer_max: int = 100
    stale_threshold_seconds: float = 5.0

    # Paths - Use project data directory (synced with substrate/database.py)
    data_dir: Path = field(default_factory=data_dir)
    snapshot_path: Optional[Path] = None

    # Local inference
    enable_local_inference: bool = True

    # Voice system settings
    voice_enabled: bool = False
    voice_stt_provider: str = "mlx_whisper"  # mlx_whisper, apple, google
    voice_tts_provider: str = "piper"  # piper, apple, edge
    voice_tts_voice: str = "en_US-amy-medium"  # Piper voice ID
    voice_mode: str = "push_to_talk"  # push_to_talk, hands_free

    # FaceID settings
    faceid_enabled: bool = False

    def __post_init__(self):
        if self.snapshot_path is None:
            self.snapshot_path = self.data_dir / "snapshot.yaml"
        self.data_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class EngineMetrics:
    """Runtime metrics."""
    start_time: datetime = field(default_factory=datetime.now)
    cognitive_ticks: int = 0
    reflective_ticks: int = 0
    events_processed: int = 0
    messages_generated: int = 0
    errors: int = 0

    # Extraction pipeline metrics
    extraction_triggers: int = 0  # Times _trigger_extraction was called for user turns

    # Agentic metrics
    agentic_tasks_started: int = 0
    agentic_tasks_completed: int = 0
    agentic_tasks_aborted: int = 0
    direct_responses: int = 0  # Queries that skipped planning
    planned_responses: int = 0  # Queries that went through AgentLoop

    @property
    def uptime_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()


class LunaEngine:
    """
    Luna's consciousness engine.

    The engine runs three concurrent loops:
    - hot_loop: Processes interrupts immediately
    - cognitive_loop: 500ms heartbeat for main processing
    - reflective_loop: Background maintenance

    Input flows through the InputBuffer, which the engine polls each tick.
    This gives Luna situational awareness and control over processing order.
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.state = EngineState.STARTING

        # Input buffer - where all events land
        self.input_buffer = InputBuffer(
            max_size=self.config.input_buffer_max,
            stale_threshold_seconds=self.config.stale_threshold_seconds,
        )

        # Actors
        self.actors: Dict[str, Actor] = {}

        # Metrics
        self.metrics = EngineMetrics()

        # Session management
        self.session_id = str(uuid.uuid4())[:8]
        self.model = "claude-sonnet"  # Using Claude for full Luna experience

        # Control
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._ready_event = asyncio.Event()

        # Consciousness state (Phase 4)
        self.consciousness = ConsciousnessState()

        # Revolving context (Phase XIV - Agentic Architecture)
        self.context = RevolvingContext(token_budget=8000)

        # Agentic components (Phase XIV)
        self.router = QueryRouter()
        self.agent_loop: Optional[AgentLoop] = None  # Initialized in _boot
        self._subtask_runner: Optional["LocalSubtaskRunner"] = None  # Initialized in _boot

        # Concurrent task handling - talk while processing
        self._current_task: Optional[asyncio.Task] = None
        self._current_goal: Optional[str] = None
        self._pending_messages: List[str] = []  # Queue for messages during processing
        self._is_processing = False
        self._stream_owns_response = False  # When True, streaming endpoint handles turn recording

        # Callbacks for external integration
        self._on_response_callbacks: list[Callable] = []
        self._on_progress_callbacks: list[Callable] = []  # For streaming progress

        # Voice system (optional)
        self._voice: Optional[Any] = None  # VoiceBackend when enabled

        # Eden adapter (optional - Phase 1.5)
        self._eden_adapter: Optional[Any] = None

        # Active project for scoped memory isolation
        self._active_project: Optional[str] = None
        self._last_nexus_nodes: list = []  # Structured Nexus extractions for grounding
        self._active_reflection_mode: Optional[str] = None  # "precision" | "reflective" | "relational"
        self._last_collections_searched: list = []

        # Expression config (loaded from personality.json)
        self._expression_config: Dict = self._load_expression_config()

        # Intent Layer: DirectiveEngine (initialized in _boot)
        self.directive_engine: Optional[Any] = None
        self._directive_context: list[dict] = []  # Fired results for session context

    def _load_expression_config(self) -> Dict:
        """Load expression config from personality.json."""
        import json
        config_path = config_dir() / "personality.json"
        try:
            with open(config_path) as f:
                config = json.load(f)
                return config.get("expression", {})
        except Exception as e:
            logger.warning(f"Failed to load expression config: {e}")
            return {}

    def _get_expression_directive(self) -> str:
        """
        Build the expression directive based on gesture_frequency config.

        This tells Luna HOW to express emotions through gestures.
        The directive becomes part of her system prompt.
        """
        if not self._expression_config:
            return ""

        frequency = self._expression_config.get("gesture_frequency", "moderate")
        settings = self._expression_config.get("settings", {})
        frequency_levels = settings.get("frequency_levels", {})

        level_config = frequency_levels.get(frequency, {})
        prompt_modifier = level_config.get("prompt_modifier", "")

        if not prompt_modifier:
            # Fallback defaults
            defaults = {
                "minimal": "Express emotions through gestures sparingly - only during moments of strong feeling, breakthrough insights, or genuine connection. Most responses should have no gestural markers.",
                "moderate": "Express emotions through gestures naturally - at key emotional moments, greetings, farewells, and when processing complex thoughts. Aim for 1-2 gestures per substantive response.",
                "expressive": "Express emotions freely through gestures - let your internal state show visually throughout responses. Use gestures to punctuate thoughts, show processing, and communicate emotional undertones."
            }
            prompt_modifier = defaults.get(frequency, defaults["moderate"])

        directive = f"""
## Emotional Expression

{prompt_modifier}

Gestures are written as *action* markers (e.g., *pulses warmly*, *spins playfully*, *dims slightly*).
These drive your visual orb representation - they're how users SEE your emotional state.
Emojis can accompany gestures or stand alone.
"""
        return directive.strip()

    async def reload_expression_config(self) -> None:
        """Reload expression config from disk (for hot config changes)."""
        self._expression_config = self._load_expression_config()
        logger.info(f"Expression config reloaded: frequency={self._expression_config.get('gesture_frequency')}")

    # =========================================================================
    # Actor Management
    # =========================================================================

    def register_actor(self, actor: Actor) -> None:
        """Register an actor with the engine."""
        actor.engine = self
        self.actors[actor.name] = actor
        logger.info(f"Registered actor: {actor.name}")

    def get_actor(self, name: str) -> Optional[Actor]:
        """Get actor by name."""
        return self.actors.get(name)

    # =========================================================================
    # Main Run Loop
    # =========================================================================

    async def run(self) -> None:
        """
        Main engine entry point.

        Runs the three concurrent paths until shutdown.
        """
        logger.info("Luna Engine starting...")

        try:
            await self._boot()

            self.state = EngineState.RUNNING
            self._running = True
            self._ready_event.set()  # Signal ready

            logger.info("Luna Engine running")

            # Create tasks for all loops
            tasks = [
                asyncio.create_task(self._cognitive_loop(), name="cognitive"),
                asyncio.create_task(self._reflective_loop(), name="reflective"),
                asyncio.create_task(self._run_actors(), name="actors"),
            ]

            # Wait for shutdown signal
            await self._shutdown_event.wait()

            # Cancel all tasks
            for task in tasks:
                task.cancel()

            # Wait for tasks to complete cancellation
            await asyncio.gather(*tasks, return_exceptions=True)

        except asyncio.CancelledError:
            logger.info("Engine cancelled")

        except Exception as e:
            logger.error(f"Engine error: {e}", exc_info=True)
            # Don't re-raise — let _shutdown() run cleanly.
            # The server lifespan will detect the engine task completed and
            # can decide whether to restart or exit.

        finally:
            await self._shutdown()

    async def _boot(self) -> None:
        """Boot sequence: initialize actors, restore state."""
        logger.info("Boot sequence starting...")

        # Create core actors if not registered
        if "matrix" not in self.actors:
            matrix = MatrixActor()
            self.register_actor(matrix)
            # Initialize matrix (connects DB, loads graph) but DON'T start mailbox loop
            await matrix.initialize()

        if "director" not in self.actors:
            # Local inference controlled by config
            self.register_actor(DirectorActor(enable_local=self.config.enable_local_inference))

        # Phase 3: Extraction Pipeline actors
        if "scribe" not in self.actors:
            from luna.actors.scribe import ScribeActor
            self.register_actor(ScribeActor())

        if "librarian" not in self.actors:
            from luna.actors.librarian import LibrarianActor
            self.register_actor(LibrarianActor())

        # Shared Turn Cache actor (writes cache + feeds dimensional engine)
        if "cache" not in self.actors:
            from luna.actors.cache import CacheActor
            self.register_actor(CacheActor())

        # Phase 4: History Manager actor (conversation history tiers)
        if "history_manager" not in self.actors:
            from luna.actors.history_manager import HistoryManagerActor
            self.register_actor(HistoryManagerActor())

        # Identity actor — ALWAYS register so bridge/memory scoping works.
        # FaceID camera loop only runs when faceid_enabled=True.
        if "identity" not in self.actors:
            try:
                from luna.actors.identity import IdentityActor
                ia = IdentityActor(enabled=self.config.faceid_enabled)
                self.register_actor(ia)

                # When FaceID is off, auto-set identity to the owner so
                # memories, bridge, and access layers work out of the box.
                if not self.config.faceid_enabled:
                    from luna.core.owner import get_owner, owner_configured
                    if owner_configured():
                        import time as _time
                        owner = get_owner()
                        ia.current.entity_id = owner.entity_id
                        ia.current.entity_name = owner.display_name
                        ia.current.confidence = 1.0
                        ia.current.luna_tier = "admin"
                        ia.current.dataroom_tier = 1
                        ia.current.dataroom_categories = [1,2,3,4,5,6,7,8,9]
                        ia.current.last_seen = _time.time()
                        logger.info(
                            "IdentityActor registered (FaceID off, default owner: %s/%s)",
                            owner.entity_id, owner.display_name,
                        )
                    else:
                        logger.info("IdentityActor registered (FaceID off, no owner configured)")
                else:
                    logger.info("IdentityActor registered (FaceID enabled)")
            except Exception as e:
                logger.warning(f"IdentityActor registration failed (non-fatal): {e}")

        # Phase 1.5: Eden adapter + bridge actor (optional)
        await self._init_eden()

        # P0 FIX: Auto-load entity seeds on startup
        # See: Docs/HANDOFF_Luna_Voice_Restoration.md
        await self._ensure_entity_seeds_loaded()

        # Restore consciousness from snapshot
        self.consciousness = await ConsciousnessState.load()

        # Wire librarian -> consciousness (Layer 6)
        if "librarian" in self.actors:
            self.actors["librarian"].set_consciousness(self.consciousness)

        # Set Luna's core identity in revolving context
        self.context.set_core_identity(self._build_identity_prompt())

        # Initialize AgentLoop (Phase XIV)
        self.agent_loop = AgentLoop(orchestrator=self, max_iterations=50)
        self.agent_loop.on_progress(self._handle_agent_progress)
        logger.info("AgentLoop initialized")

        # Initialize Scout actor + Watchdog (blockage detection + stuck state recovery)
        if "scout" not in self.actors:
            from luna.actors.scout import ScoutActor, Watchdog, watchdog_loop
            self.register_actor(ScoutActor())
            self.watchdog = Watchdog(self)
            asyncio.create_task(watchdog_loop(self.watchdog, interval=5.0))
            logger.info("Scout and Watchdog initialized")

        # Initialize ReconcileManager (confabulation self-correction)
        from luna.actors.reconcile import ReconcileManager
        self.reconcile = ReconcileManager()
        logger.info("ReconcileManager initialized")

        # =================================================================
        # Phase 1 — Engine Ownership: substrate components
        # Five instances the Engine owns. All MCP/API tools reference these
        # instead of creating their own copies.
        # Order matters: AiBrarian → CollectionLockIn → Annotations → Aperture
        # =================================================================

        # 1/4 AiBrarianEngine — universal document database layer
        try:
            from luna.substrate.aibrarian_engine import AiBrarianEngine
            _project = project_root()
            self.aibrarian = AiBrarianEngine(
                config_dir() / "aibrarian_registry.yaml",
                project_root=_project,
            )
            await self.aibrarian.initialize()
            logger.info("AiBrarianEngine owned by Engine — connected")
        except Exception as e:
            self.aibrarian = None
            logger.warning(f"AiBrarianEngine initialization failed (non-fatal): {e}")

        # 2/4 CollectionLockInEngine — inject into AiBrarianEngine
        try:
            from luna.substrate.collection_lock_in import CollectionLockInEngine
            matrix_actor = self.get_actor("matrix")
            _matrix_obj = getattr(matrix_actor, "_matrix", None)
            _mem_db = getattr(_matrix_obj, "db", None) if _matrix_obj else None
            if _mem_db is not None:
                self.collection_lock_in = CollectionLockInEngine(_mem_db)
                await self.collection_lock_in.ensure_table()
                # Bootstrap luna_system so it's always in the search chain
                await self.collection_lock_in.ensure_tracked("luna_system", pattern="emergent")
                # Auto-register all enabled collections so new ones are immediately visible
                if self.aibrarian is not None:
                    for key, conn in self.aibrarian.connections.items():
                        cfg = self.aibrarian.registry.collections.get(key)
                        pattern = cfg.ingestion_pattern if cfg else "utilitarian"
                        await self.collection_lock_in.ensure_tracked(key, pattern=pattern)
                    self.aibrarian.set_lock_in_engine(self.collection_lock_in)
                logger.info("CollectionLockInEngine owned by Engine — injected into AiBrarian")
            else:
                self.collection_lock_in = None
                logger.warning("CollectionLockInEngine skipped — Matrix DB not available")
        except Exception as e:
            self.collection_lock_in = None
            logger.warning(f"CollectionLockInEngine initialization failed (non-fatal): {e}")

        # 3/4 AnnotationEngine — bridge from collections into Memory Matrix
        try:
            from luna.substrate.collection_annotations import AnnotationEngine
            matrix_actor = self.get_actor("matrix")
            _matrix_obj = getattr(matrix_actor, "_matrix", None)
            _mem_db = getattr(_matrix_obj, "db", None) if _matrix_obj else None
            if _mem_db is not None:
                self.annotations = AnnotationEngine(
                    _mem_db,
                    memory_matrix=_matrix_obj,
                    lock_in_engine=self.collection_lock_in,
                )
                await self.annotations.ensure_table()
                logger.info("AnnotationEngine owned by Engine — bridged to Matrix")
            else:
                self.annotations = None
                logger.warning("AnnotationEngine skipped — Matrix DB not available")
        except Exception as e:
            self.annotations = None
            logger.warning(f"AnnotationEngine initialization failed (non-fatal): {e}")

        # 4/4 ApertureManager — cognitive focus control (default: BALANCED)
        from luna.context.aperture import ApertureManager
        self.aperture = ApertureManager()
        logger.info(f"ApertureManager owned by Engine — preset={self.aperture.state.preset.value}")

        # Initialize SubtaskRunner — try Qwen first, fall back to Haiku
        if SUBTASK_RUNNER_AVAILABLE:
            subtask_backend = None

            # Try 1: Qwen 3B local (sovereign, offline-capable)
            director = self.get_actor("director")
            if director and director._enable_local and not director.local_available:
                await director._init_local_inference()
            if director and director.local_available:
                subtask_backend = director._local
                logger.info("SubtaskRunner using Qwen 3B (local)")

            # Try 2: Haiku API (fast, reliable, negligible cost)
            if subtask_backend is None:
                try:
                    from luna.inference.haiku_subtask_backend import HaikuSubtaskBackend
                    haiku = HaikuSubtaskBackend()
                    if haiku.is_loaded:
                        subtask_backend = haiku
                        logger.info("SubtaskRunner using Haiku API (Qwen unavailable)")
                except Exception as e:
                    logger.warning(f"Haiku subtask backend failed: {e}")

            # Wire it up
            if subtask_backend is not None:
                self._subtask_runner = LocalSubtaskRunner(subtask_backend)
                logger.info("LocalSubtaskRunner initialized")
            else:
                logger.warning("SubtaskRunner unavailable (no local model, no Haiku API)")
        else:
            logger.debug("LocalSubtaskRunner module not available")

        # Initialize voice system if enabled
        if self.config.voice_enabled:
            await self._init_voice()

        # Memory hygiene: run maintenance sweep if overdue (>7 days)
        await self._maybe_run_hygiene_sweep()

        # Intent Layer: DirectiveEngine (armed quests that fire on events)
        await self._init_directive_engine()

        logger.info("Boot sequence complete")

    async def _run_actors(self) -> None:
        """Start all registered actors."""
        if not self.actors:
            logger.warning("No actors registered")
            return

        tasks = []
        for actor in self.actors.values():
            task = asyncio.create_task(actor.start())
            actor._task = task
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _init_eden(self) -> None:
        """Initialize Eden adapter and bridge actor if API key is set."""
        import os
        eden_api_key = os.environ.get("EDEN_API_KEY", "")
        if not eden_api_key or eden_api_key == "your_key_here":
            logger.debug("Eden: No API key set, skipping Eden initialization")
            return

        try:
            from luna.services.eden import EdenAdapter, EdenConfig
            from luna.actors.eden_bridge import EdenBridgeActor
            from luna.tools.eden_tools import set_eden_adapter

            config = EdenConfig.load()
            adapter = EdenAdapter(config)
            await adapter.__aenter__()
            self._eden_adapter = adapter

            # Register bridge actor
            if "eden_bridge" not in self.actors:
                self.register_actor(EdenBridgeActor())

            # Connect tools to adapter + engine
            set_eden_adapter(adapter, engine=self)

            logger.info("Eden adapter initialized successfully")

        except Exception as e:
            logger.warning(f"Eden initialization failed (non-fatal): {e}")
            self._eden_adapter = None

    async def _init_voice(self) -> None:
        """Initialize the voice system."""
        try:
            from voice import VoiceBackend
            from voice.stt import STTProviderType
            from voice.tts import TTSProviderType

            # Map config strings to enums
            stt_map = {
                "mlx_whisper": STTProviderType.MLX_WHISPER,
                "apple": STTProviderType.APPLE,
                "google": STTProviderType.GOOGLE,
            }
            tts_map = {
                "piper": TTSProviderType.PIPER,
                "apple": TTSProviderType.APPLE,
                "edge": TTSProviderType.EDGE,
            }

            stt_provider = stt_map.get(self.config.voice_stt_provider, STTProviderType.MLX_WHISPER)
            tts_provider = tts_map.get(self.config.voice_tts_provider, TTSProviderType.PIPER)
            hands_free = self.config.voice_mode == "hands_free"

            self._voice = VoiceBackend(
                engine=self,
                stt_provider=stt_provider,
                tts_provider=tts_provider,
                tts_voice=self.config.voice_tts_voice,
                hands_free=hands_free,
            )
            logger.info(f"Voice system initialized (TTS={tts_provider.value}, STT={stt_provider.value})")

        except ImportError as e:
            logger.warning(f"Voice system not available: {e}")
            self._voice = None
        except Exception as e:
            logger.error(f"Failed to initialize voice system: {e}")
            self._voice = None

    async def _init_directive_engine(self) -> None:
        """Initialize the Intent Layer directive engine."""
        try:
            from luna.agentic.directives import DirectiveEngine

            matrix_actor = self.get_actor("matrix")
            db_path = getattr(matrix_actor, "db_path", None)
            if db_path is None:
                db_path = user_dir() / "luna_engine.db"

            self.directive_engine = DirectiveEngine(Path(db_path))

            # Seed from YAML on first run (idempotent — skips existing)
            yaml_path = config_dir() / "directives_seed.yaml"
            if yaml_path.exists():
                result = await self.directive_engine.seed_from_yaml(yaml_path)
                if result["directives"] or result["skills"]:
                    logger.info(f"Seeded directives: {result}")

            # Re-arm any fired directives from last session
            rearmed = await self.directive_engine.rearm_fired()
            if rearmed:
                logger.info(f"Re-armed {rearmed} fired directives")

            # Load armed directives
            count = await self.directive_engine.load_armed()
            logger.info(f"DirectiveEngine initialized — {count} armed directives")

            # Evaluate session_start triggers
            await self._evaluate_session_start_directives()

        except Exception as e:
            self.directive_engine = None
            logger.warning(f"DirectiveEngine initialization failed (non-fatal): {e}")

    async def _evaluate_session_start_directives(self) -> None:
        """Fire session_start directives at boot."""
        if not self.directive_engine:
            return
        try:
            matches = await self.directive_engine.evaluate_event(
                "session_start", {}
            )
            for d in matches:
                if d.get("trust_tier") == "auto":
                    result = await self.directive_engine.fire(d, self)
                    self._directive_context.append(result)
                    logger.info(f"Auto-fired directive: {d.get('title', d['id'])}")
                else:
                    logger.info(f"Directive pending confirmation: {d.get('title', d['id'])}")
        except Exception as e:
            logger.error(f"Session start directive evaluation error: {e}")

    async def evaluate_post_extraction_directives(
        self, user_message: str, entities: list[str], thread_resumed: bool = False,
        thread_info: Optional[dict] = None,
    ) -> list[dict]:
        """
        Evaluate keyword, entity_mention, and thread_resume directives
        after an extraction completes. Called from Librarian or engine.
        """
        if not self.directive_engine:
            return []

        results = []
        events = []

        if user_message:
            events.append(("keyword", {"message": user_message}))
        if entities:
            events.append(("entity_mention", {"entities": entities}))
        if thread_resumed and thread_info:
            events.append(("thread_resume", {"thread": thread_info}))

        for event_type, ctx in events:
            try:
                matches = await self.directive_engine.evaluate_event(event_type, ctx)
                for d in matches:
                    if d.get("trust_tier") == "auto":
                        result = await self.directive_engine.fire(d, self)
                        self._directive_context.append(result)
                        results.append(result)
                    else:
                        logger.info(
                            f"Directive pending confirmation: {d.get('title', d['id'])}"
                        )
            except Exception as e:
                logger.error(f"Post-extraction directive error ({event_type}): {e}")

        return results

    async def _maybe_run_hygiene_sweep(self) -> None:
        """Run maintenance sweep + entity review quest if >7 days since last."""
        import json as _json
        from datetime import timezone

        state_path = user_dir() / "hygiene_sweep_state.json"
        now = datetime.now(timezone.utc)
        seven_days = 7 * 24 * 3600

        try:
            if state_path.exists():
                state = _json.loads(state_path.read_text())
                last = datetime.fromisoformat(state.get("last_sweep", "2000-01-01T00:00:00+00:00"))
                if (now - last).total_seconds() < seven_days:
                    logger.debug("Hygiene sweep not due yet (last: %s)", last.isoformat())
                    return

            logger.info("Running scheduled memory hygiene sweep...")
            from luna_mcp.observatory.tools import (
                tool_observatory_maintenance_sweep,
                tool_observatory_entity_review_quest,
                tool_observatory_quest_create,
            )

            sweep = await tool_observatory_maintenance_sweep()
            candidates = sweep.get("candidates", [])
            created_ids = []

            for c in candidates:
                result = await tool_observatory_quest_create(
                    title=c.get("title", ""),
                    objective=c.get("objective", c.get("title", "")),
                    quest_type=c.get("quest_type", "side"),
                    priority=c.get("priority", "medium"),
                    subtitle=c.get("subtitle", ""),
                    source=c.get("source", "maintenance_sweep"),
                    target_entity_ids=_json.dumps(c.get("target_entities", [])),
                    target_node_ids=_json.dumps(c.get("target_nodes", [])),
                )
                if result.get("quest_id"):
                    created_ids.append(result["quest_id"])

            review = await tool_observatory_entity_review_quest()
            if review.get("quest_id"):
                created_ids.append(review["quest_id"])

            # Save sweep timestamp
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(_json.dumps({
                "last_sweep": now.isoformat(),
                "quests_created": len(created_ids),
                "quest_ids": created_ids,
            }, indent=2))

            logger.info(
                "Hygiene sweep complete: %d candidates, %d quests created",
                len(candidates), len(created_ids),
            )

        except Exception as e:
            logger.warning("Hygiene sweep failed (non-fatal): %s", e)

    async def _ensure_entity_seeds_loaded(self) -> None:
        """
        Load personality seeds if not already in database.

        P0 FIX: Auto-loads Luna's personality from entities/personas/luna.yaml
        on engine startup if not already present in the database.
        See: Docs/HANDOFF_Luna_Voice_Restoration.md
        """
        try:
            # Get database access through Matrix actor
            matrix = self.get_actor("matrix")
            if not matrix or not hasattr(matrix, "_matrix") or not matrix._matrix:
                logger.warning("[SEEDS] Matrix not initialized, skipping entity seed auto-load")
                return

            db = matrix._matrix.db

            # Check if Luna entity exists
            result = await db.fetchone(
                "SELECT id FROM entities WHERE id = ?",
                ("luna",)
            )

            if result is not None:
                logger.debug("[SEEDS] Luna personality already loaded")
                return

            logger.info("[SEEDS] Luna entity not found, loading personality seeds...")

            # Import and run seed loader
            from pathlib import Path
            try:
                # Load EntitySeedLoader — use importlib for compiled build compatibility
                _root = project_root()
                try:
                    import importlib.util
                    _loader_path = scripts_dir() / "migrations" / "load_entity_seeds.py"
                    _spec = importlib.util.spec_from_file_location("load_entity_seeds", str(_loader_path))
                    _mod = importlib.util.module_from_spec(_spec)
                    _spec.loader.exec_module(_mod)
                    EntitySeedLoader = _mod.EntitySeedLoader
                except Exception:
                    # Fallback: dev environment where scripts/ is on sys.path
                    import sys
                    sys.path.insert(0, str(scripts_dir()))
                    from migrations.load_entity_seeds import EntitySeedLoader

                entities_dir = _root / "entities"
                if not entities_dir.exists():
                    logger.warning(f"[SEEDS] Entities directory not found: {entities_dir}")
                    return

                loader = EntitySeedLoader(
                    db=db,
                    entities_dir=entities_dir,
                    dry_run=False
                )

                # Ensure schema exists
                await loader.ensure_schema()

                # Load all seed files
                summary = await loader.load_all()

                logger.info(
                    f"[SEEDS] Loaded {summary['loaded']} entities, "
                    f"updated {summary['updated']}, "
                    f"skipped {summary['skipped']}"
                )

                if summary['errors'] > 0:
                    logger.warning(f"[SEEDS] {summary['errors']} errors during seed loading")

            except ImportError as e:
                logger.warning(f"[SEEDS] EntitySeedLoader not available: {e}")

        except Exception as e:
            # Don't fail startup if seed loading fails - just warn
            logger.error(f"[SEEDS] Failed to load entity seeds: {e}")

    async def _wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    async def wait_ready(self, timeout: float = 5.0) -> bool:
        """Wait for engine to be ready."""
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # =========================================================================
    # Tick Loops
    # =========================================================================

    async def _cognitive_loop(self) -> None:
        """
        Cognitive path: 500ms heartbeat.

        - Poll input buffer
        - Prioritize events
        - Dispatch to actors
        - Update consciousness state
        """
        logger.debug("Cognitive loop started")

        while self._running:
            try:
                await self._cognitive_tick()
                self.metrics.cognitive_ticks += 1

            except Exception as e:
                logger.error(f"Cognitive tick error: {e}")
                self.metrics.errors += 1

            await asyncio.sleep(self.config.cognitive_interval)

    async def _cognitive_tick(self) -> None:
        """Single cognitive tick."""
        # 1. Poll input buffer (prioritized)
        events = self.input_buffer.poll_all()

        if events:
            logger.debug(f"Tick processing {len(events)} events")

        # 2. Dispatch each event
        for event in events:
            self.metrics.events_processed += 1
            await self._dispatch_event(event)

        # 3. Consciousness tick
        await self.consciousness.tick()

        # 4. History Manager tick (process compression/extraction queues)
        history = self.get_actor("history_manager")
        if history and hasattr(history, "tick"):
            try:
                await asyncio.wait_for(history.tick(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("History manager tick timed out (2s)")
            except Exception as e:
                logger.warning(f"History manager tick error: {e}")

        # 5. Rebalance rings (decay happens in reflective loop, not every tick)
        self.context._rebalance_rings()

        # 6. Persist state periodically (every 10 ticks)
        if self.metrics.cognitive_ticks > 0 and self.metrics.cognitive_ticks % 10 == 0:
            await self.consciousness.save()

    async def _dispatch_event(self, event: InputEvent) -> None:
        """Route event to appropriate actor(s).

        User messages are dispatched as background tasks so the cognitive
        tick loop is never blocked by long-running agentic pipelines.
        """
        logger.debug(f"Dispatching: {event}")

        match event.type:
            case EventType.TEXT_INPUT | EventType.TRANSCRIPT_FINAL:
                user_message = event.payload
                cid = event.correlation_id or "anon"
                asyncio.create_task(
                    self._handle_user_message(user_message, cid, source=event.source),
                    name=f"msg-{cid[:8]}",
                )

            case EventType.USER_INTERRUPT:
                # Abort current task/generation
                await self._handle_interrupt()

            case EventType.ACTOR_MESSAGE:
                # Internal message from actor
                await self._handle_actor_message(event)

            case EventType.IDENTITY_RECOGNIZED:
                name = event.payload.get("entity_name", "unknown")
                tier = event.payload.get("luna_tier", "unknown")
                logger.info(f"Identity event: {name} recognized (tier={tier})")

            case EventType.IDENTITY_LOST:
                name = event.payload.get("entity_name", "unknown")
                logger.info(f"Identity event: {name} left")

            case EventType.SHUTDOWN:
                await self.stop()

    async def _handle_user_message(self, user_message: str, correlation_id: str, source: str = "text") -> None:
        """
        Handle incoming user message with concurrent support.

        If currently processing, this message can either:
        1. Interrupt the current task (if it looks like an interrupt)
        2. Be queued for after current task completes
        3. Be processed in parallel (for simple queries)
        """
        # Add user message to revolving context
        self.context.add(
            content=f"User: {user_message}",
            source=ContextSource.CONVERSATION,
        )

        # Check if this looks like an interrupt
        interrupt_signals = ["stop", "cancel", "wait", "hold on", "nevermind", "never mind"]
        is_interrupt = any(sig in user_message.lower() for sig in interrupt_signals)

        if is_interrupt and self._is_processing:
            logger.info(f"User interrupt detected: {user_message[:30]}...")
            await self._handle_interrupt()
            # Acknowledge the interrupt
            await self._emit_response(
                "Okay, I've stopped what I was doing. What would you like instead?",
                {"interrupted": True}
            )
            return

        # If currently processing, handle concurrently
        if self._is_processing:
            # Route to see if this is simple enough to answer immediately
            routing = self.router.analyze(user_message)

            if routing.path == ExecutionPath.DIRECT:
                # Simple query - can answer while working on other task
                logger.info(f"Concurrent simple query: {user_message[:30]}...")
                await self._emit_progress(f"(Working on your previous request... but I can answer this quickly)")
                await self._process_direct(user_message, correlation_id)
            else:
                # Queue for later
                self._pending_messages.append(user_message)
                await self._emit_progress(
                    f"Got it! I'll get to that after I finish what I'm working on. "
                    f"({len(self._pending_messages)} message{'s' if len(self._pending_messages) > 1 else ''} queued)"
                )
            return

        # Not currently processing - handle normally with agentic routing
        await self._process_message_agentic(user_message, correlation_id, source=source)

    async def _process_message_agentic(self, user_message: str, correlation_id: str, source: str = "text", _db_retry: bool = False) -> None:
        """Process message through the agentic pipeline (subtasks → router → planner → loop)."""
        self._is_processing = True
        self._current_goal = user_message
        self.metrics.agentic_tasks_started += 1

        try:
            # ══════════════════════════════════════════════════════════════
            # PHASE 1: Run Qwen subtasks in parallel with memory retrieval
            # Subtasks: intent classification, entity extraction, query rewriting
            # These run concurrently — total wall time ≈ max(subtask, memory)
            # ══════════════════════════════════════════════════════════════

            matrix = self.get_actor("matrix")
            history_manager = self.get_actor("history_manager")

            # Record user turn through unified API (extraction + storage)
            await self.record_conversation_turn(
                role="user",
                content=user_message,
                source=source,
            )

            # Build recent turns list for query rewriting context
            recent_turns = []
            director = self.get_actor("director")
            if director and hasattr(director, '_active_ring'):
                ring = director._active_ring
                recent_turns = [
                    f"{'User' if t.get('role') == 'user' else 'Luna'}: {t.get('content', '')[:200]}"
                    for t in ring.get_recent(4)
                ] if hasattr(ring, 'get_recent') else []

            # Fire subtasks + memory/history retrieval concurrently
            subtask_phase = None
            parallel_tasks = []

            if self._subtask_runner and self._subtask_runner.is_available:
                parallel_tasks.append(
                    self._subtask_runner.run_subtask_phase(user_message, recent_turns)
                )
            else:
                logger.warning("[SUBTASK] Runner unavailable — intent classification skipped, agentic upgrade disabled")
                parallel_tasks.append(asyncio.sleep(0))  # no-op placeholder

            # Memory retrieval (existing)
            async def _retrieve_context():
                memory_context = ""
                history_context = None
                retrieval_query = user_message

                if history_manager and history_manager.is_ready:
                    history_context = await history_manager.build_history_context(user_message)

                if matrix and matrix.is_ready:
                    await self._load_conversation_history(matrix, limit=10)

                    # Use rewritten query for better retrieval if available
                    if subtask_phase and subtask_phase.rewritten_query:
                        retrieval_query = subtask_phase.rewritten_query
                        logger.info(f"[SUBTASK] Using rewritten query for retrieval: {retrieval_query[:60]}...")

                    memory_context = await matrix.get_context(
                        retrieval_query, max_tokens=1500, scopes=self.active_scopes
                    )
                    if memory_context:
                        self.context.add(content=memory_context, source=ContextSource.MEMORY)

                # Phase 2: search chain for active project collections
                # Use decomposed queries if available (multi-part questions)
                if subtask_phase and subtask_phase.decomposed_queries:
                    collection_context = await self._get_collection_context_multi(
                        subtask_phase.decomposed_queries, subtask_phase=subtask_phase
                    )
                else:
                    collection_context = await self._get_collection_context(
                        retrieval_query, subtask_phase=subtask_phase
                    )
                if collection_context:
                    memory_context = (memory_context or "") + "\n\n" + collection_context
                    self.context.add(content=collection_context, source=ContextSource.MEMORY)

                # ── Phase 2.5: Reflection mode detection + retrieval ──
                collections_searched = self._last_collections_searched
                active_mode = self._get_active_reflection_mode(collections_searched)
                self._active_reflection_mode = active_mode

                if active_mode in ("reflective", "relational") and matrix and matrix.is_ready:
                    try:
                        matrix_ops = matrix._matrix if hasattr(matrix, '_matrix') else None
                        if matrix_ops:
                            reflection_results = await matrix_ops.fts5_search(
                                retrieval_query, limit=5
                            )
                            reflection_nodes = [
                                node for node, _score in reflection_results
                                if getattr(node, 'node_type', '') == 'PERSONALITY_REFLECTION'
                            ]
                            if reflection_nodes:
                                reflection_context = self._format_reflection_context(reflection_nodes)
                                memory_context = (memory_context or "") + "\n\n" + reflection_context
                                self.context.add(content=reflection_context, source=ContextSource.MEMORY)
                                logger.info(f"[REFLECTION-RETRIEVAL] Injected {len(reflection_nodes)} reflections (mode={active_mode})")
                    except Exception as e:
                        logger.warning(f"[REFLECTION-RETRIEVAL] Failed: {e}")

                # ── Phase 2.75: Relational retrieval ──
                if active_mode == "relational":
                    relational_context = await self._get_relational_context(retrieval_query)
                    if relational_context:
                        memory_context = (memory_context or "") + "\n\n" + relational_context
                        self.context.add(content=relational_context, source=ContextSource.MEMORY)
                        logger.info(f"[RELATIONAL] Injected conversation context")

                return memory_context, history_context

            # Run subtasks first (they're fast), then memory retrieval
            # (memory retrieval can use the rewritten query from subtasks)
            if self._subtask_runner and self._subtask_runner.is_available:
                subtask_phase = await self._subtask_runner.run_subtask_phase(
                    user_message, recent_turns
                )
            else:
                subtask_phase = SubtaskPhaseResult() if SUBTASK_RUNNER_AVAILABLE else None

            memory_context, history_context = await _retrieve_context()

            # ══════════════════════════════════════════════════════════════
            # PHASE 2: Route using semantic classification or regex fallback
            # ══════════════════════════════════════════════════════════════

            if subtask_phase and subtask_phase.intent:
                routing = self.router.from_intent(subtask_phase.intent, user_message)
                logger.info(f"Routing (semantic): {routing.path.name} (complexity={routing.complexity:.2f})")
            else:
                routing = self.router.analyze(user_message)
                logger.info(f"Routing (regex): {routing.path.name} (complexity={routing.complexity:.2f})")

            # ══════════════════════════════════════════════════════════════
            # PHASE 3: Pass entity hints to Scribe (gates Claude Haiku)
            # ══════════════════════════════════════════════════════════════

            if subtask_phase and subtask_phase.entities is not None:
                scribe = self.get_actor("scribe")
                if scribe and scribe.is_ready:
                    await scribe.mailbox.put(Message(
                        type="entity_hints",
                        payload={"entities": subtask_phase.entities, "message": user_message},
                    ))

            # ══════════════════════════════════════════════════════════════
            # PHASE 4: Execute based on routing decision
            # ══════════════════════════════════════════════════════════════

            # Upgrade to AgentLoop if knowledge-sparse research query
            logger.debug("[ROUTING-DEBUG] path=%s, agent_loop=%s, nexus_nodes=%d, subtask=%s, intent=%s",
                         routing.path, bool(self.agent_loop), len(self._last_nexus_nodes),
                         bool(subtask_phase), subtask_phase.intent if subtask_phase else None)
            if (
                routing.path == ExecutionPath.DIRECT
                and self.agent_loop
                and subtask_phase
                and subtask_phase.intent
                and subtask_phase.intent.get("intent") in ("research", "memory_query")
                and (
                    len(self._last_nexus_nodes) < 2  # sparse results
                    or subtask_phase.intent.get("complexity") == "complex"  # complex research needs deeper retrieval
                )
            ):
                _upgrade_reason = "knowledge-sparse" if len(self._last_nexus_nodes) < 2 else "complex-research"
                logger.info(f"[ROUTING] Upgrading to AgentLoop ({_upgrade_reason} research query)")
                routing = RoutingDecision(
                    path=ExecutionPath.SIMPLE_PLAN,
                    complexity=routing.complexity,
                    reason="knowledge-sparse research query",
                    signals=routing.signals,
                )

            # Fallback: keyword-based upgrade when SubtaskRunner unavailable
            if (
                routing.path == ExecutionPath.DIRECT
                and self.agent_loop
                and len(self._last_nexus_nodes) < 2
                and (not subtask_phase or not subtask_phase.intent)
            ):
                _RESEARCH_SIGNALS = {"what does", "tell me about", "explain", "chapters",
                                     "evidence", "compare", "analyze", "summarize",
                                     "describe", "how does", "why does", "what are"}
                q_lower = user_message.lower()
                if any(sig in q_lower for sig in _RESEARCH_SIGNALS):
                    logger.info("[ROUTING] Keyword fallback → AgentLoop (no intent classification available)")
                    routing = RoutingDecision(
                        path=ExecutionPath.SIMPLE_PLAN,
                        complexity=routing.complexity,
                        reason="keyword-based research detection (SubtaskRunner unavailable)",
                        signals=routing.signals,
                    )

            if routing.path == ExecutionPath.DIRECT:
                self.metrics.direct_responses += 1
                await self._process_direct(user_message, correlation_id, memory_context, history_context)
            else:
                self.metrics.planned_responses += 1
                await self._process_with_agent_loop(user_message, correlation_id, memory_context, history_context)

            # ══════════════════════════════════════════════════════════════
            # PHASE 5: Bridge Nexus knowledge to Memory Matrix
            # ══════════════════════════════════════════════════════════════
            try:
                await self._bridge_nexus_to_matrix()
            except Exception as e:
                logger.warning(f"[NEXUS-BRIDGE] Non-fatal error: {e}")

            self.metrics.agentic_tasks_completed += 1

        except asyncio.CancelledError:
            logger.info("Task cancelled")
            self.metrics.agentic_tasks_aborted += 1
            raise

        except Exception as e:
            # Retry once on SQLite lock contention
            import sqlite3 as _sqlite3
            if not _db_retry and isinstance(e, _sqlite3.OperationalError) and "database is locked" in str(e):
                logger.warning(f"DB lock hit — retrying after 2s: {e}")
                await asyncio.sleep(2)
                try:
                    await self._process_message_agentic(user_message, correlation_id, source=source, _db_retry=True)
                    return
                except Exception as e2:
                    logger.error(f"Agentic processing error (retry): {e2}")
                    await self._emit_response(f"I ran into an issue: {e2}", {"error": True})
            else:
                logger.error(f"Agentic processing error: {e}")
                await self._emit_response(f"I ran into an issue: {e}", {"error": True})

        finally:
            self._is_processing = False
            self._current_goal = None
            self._current_task = None

            # Process any queued messages
            if self._pending_messages:
                next_message = self._pending_messages.pop(0)
                logger.info(f"Processing queued message: {next_message[:30]}...")
                await self._process_message_agentic(next_message, str(uuid.uuid4())[:8])

    async def _process_direct(
        self,
        user_message: str,
        correlation_id: str,
        memory_context: str = "",
        history_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Direct path - skip planning, go straight to Director."""
        # Emit progress for Thought Stream visibility
        await self._emit_progress(f"[DIRECT] {user_message[:40]}...")

        context_window = self.context.get_context_window(max_tokens=4000)
        # Debug: Log context window size
        print(f"[DEBUG] Context window: {len(context_window)} chars, items in INNER ring: {len(self.context.rings[ContextRing.INNER])}")

        director = self.get_actor("director")
        if director:
            msg = Message(
                type="generate",
                payload={
                    "user_message": user_message,
                    "system_prompt": self._build_system_prompt(memory_context, history_context),
                    "context_window": context_window,
                    "nexus_nodes": self._last_nexus_nodes,
                    "memory_context": memory_context,  # Pass separately so Director uses it
                },
                correlation_id=correlation_id,
            )
            await director.mailbox.put(msg)

    async def _process_with_agent_loop(
        self,
        user_message: str,
        correlation_id: str,
        memory_context: str = "",
        history_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Process through full AgentLoop with planning."""
        if not self.agent_loop:
            logger.warning("AgentLoop not initialized, falling back to direct")
            await self._process_direct(user_message, correlation_id, memory_context, history_context)
            return

        # Create the task (allows concurrent checking)
        self._current_task = asyncio.create_task(
            self._run_agent_loop(user_message, correlation_id, memory_context, history_context)
        )

        try:
            await self._current_task
        except asyncio.CancelledError:
            logger.info("AgentLoop task cancelled")
            raise

    async def _run_agent_loop(
        self,
        user_message: str,
        correlation_id: str,
        memory_context: str = "",
        history_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Run the AgentLoop and handle results."""
        result = await self.agent_loop.run(user_message)

        # Handle the result
        if result.success:
            # For now, the AgentLoop returns placeholder text
            # We need to route to Director for actual generation
            context_window = self.context.get_context_window(max_tokens=4000)

            director = self.get_actor("director")
            if director:
                # Include plan context in the message
                plan_context = ""
                if result.plan:
                    plan_context = f"\n[Plan: {result.plan.reasoning}]\n"

                msg = Message(
                    type="generate",
                    payload={
                        "user_message": user_message,
                        "system_prompt": self._build_system_prompt(memory_context, history_context) + plan_context,
                        "context_window": context_window,
                        "agentic": True,
                        "execution_path": result.status.name,
                        "nexus_nodes": self._last_nexus_nodes,
                    },
                    correlation_id=correlation_id,
                )
                await director.mailbox.put(msg)
        else:
            # AgentLoop failed
            await self._emit_response(
                f"I had trouble with that: {result.error or 'Unknown error'}",
                {"error": True, "status": result.status.name}
            )

    async def _handle_interrupt(self) -> None:
        """Handle user interrupt - abort current processing."""
        logger.info("Handling interrupt")

        # Abort AgentLoop if running
        if self.agent_loop:
            self.agent_loop.abort()

        # Cancel current task
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            self.metrics.agentic_tasks_aborted += 1

        # Abort Director generation
        director = self.get_actor("director")
        if director:
            await director.mailbox.put(Message(type="abort"))

        self._is_processing = False
        self._current_goal = None

    async def _handle_agent_progress(self, message: str) -> None:
        """Handle progress updates from AgentLoop."""
        await self._emit_progress(message)

    async def _emit_progress(self, message: str) -> None:
        """Emit progress update to all callbacks."""
        for callback in self._on_progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    async def record_conversation_turn(
        self,
        role: str,
        content: str,
        source: str = "text",
        tokens: Optional[int] = None,
    ) -> None:
        """
        Public API for recording conversation turns.

        Unified entry point for all input paths (text, voice, API).
        Handles extraction, history, and legacy storage.

        Args:
            role: Who spoke ("user" or "assistant")
            content: What was said
            source: Input source ("text", "voice", "api") for logging
            tokens: Optional token count (estimated if not provided)
        """
        if not content or len(content.strip()) < 5:
            logger.debug(f"Skipping trivial {role} turn ({len(content)} chars)")
            return

        # 1. Trigger extraction pipeline (Scribe → Librarian → Memory Matrix)
        try:
            await self._trigger_extraction(role, content, source=source)
        except Exception as e:
            logger.error(f"Extraction error for {role} turn: {e}")

        # 2. Store in HistoryManager (conversation continuity)
        history_manager = self.get_actor("history_manager")
        if history_manager and history_manager.is_ready:
            try:
                await history_manager.add_turn(
                    role=role,
                    content=content,
                    tokens=tokens or len(content) // 4,
                )
            except Exception as e:
                logger.error(f"HistoryManager error for {role} turn: {e}")

        # 3. Store in Matrix as FACT node (legacy storage)
        matrix = self.get_actor("matrix")
        if matrix and matrix.is_ready:
            try:
                await matrix.store_turn(
                    session_id=self.session_id,
                    role=role,
                    content=content,
                    tokens=tokens,
                )
            except Exception as e:
                logger.error(f"Matrix storage error for {role} turn: {e}")

        # 4. Evaluate keyword directives on user turns (Intent Layer)
        if role == "user" and self.directive_engine:
            try:
                await self.evaluate_post_extraction_directives(
                    user_message=content, entities=[]
                )
            except Exception as e:
                logger.error(f"Directive evaluation error: {e}")

        logger.debug(f"📝 Recorded {source} turn: {role} ({len(content)} chars)")

    async def _trigger_extraction(self, role: str, content: str, source: str = "text") -> None:
        """
        Trigger extraction on a conversation turn.

        Sends the turn to Scribe for semantic extraction, which then
        forwards extracted objects to Librarian for filing into memory.
        """
        scribe = self.get_actor("scribe")
        if scribe and len(content) >= 10:  # Skip very short messages
            from luna.actors.base import Message
            msg = Message(
                type="extract_turn",
                payload={
                    "role": role,
                    "content": content,
                    "session_id": self.session_id,
                    "immediate": True,  # Process immediately, don't batch
                    "source": source,  # Surface origin for Shared Turn Cache
                },
            )
            await scribe.mailbox.put(msg)
            if role == "user":
                self.metrics.extraction_triggers += 1
                # Pipeline staleness check: warn if many user turns sent but
                # zero extractions completed (Scribe may be stuck or erroring)
                scribe_stats = scribe.get_stats()
                triggers = self.metrics.extraction_triggers
                extractions = scribe_stats.get("extractions_count", 0)
                if triggers >= 5 and extractions == 0:
                    logger.warning(
                        f"PIPELINE STALE: {triggers} user turns triggered but "
                        f"0 extractions completed — Scribe may be stuck or erroring"
                    )
            print(f"📝 Extraction triggered for {role} turn ({len(content)} chars)")
        else:
            print(f"📝 Extraction skipped: scribe={scribe is not None}, content_len={len(content)}")

    def _is_valid_response(self, text: str, user_message: str = "") -> bool:
        """
        Check if a response is valid for storage in context.

        Filters out:
        - Clarification echoes (ending with ?)
        - User question parrots
        - Very short non-answers

        Args:
            text: The response text to validate
            user_message: The original user message (for comparison)

        Returns:
            True if response should be stored, False to skip
        """
        text_clean = text.strip().lower()

        # Skip empty responses
        if len(text_clean) < 5:
            return False

        # Skip pure question echoes (high likelihood of clarification)
        if text_clean.endswith("?"):
            # Check if it's parroting the user's question
            if user_message:
                user_clean = user_message.strip().lower()
                # Check for high word overlap (>60% shared words)
                user_words = set(user_clean.split())
                response_words = set(text_clean.rstrip("?").split())
                if user_words and response_words:
                    overlap = len(user_words & response_words) / min(len(user_words), len(response_words))
                    if overlap > 0.6:
                        logger.debug(f"Skipping clarification echo: '{text[:50]}...'")
                        return False

            # Check for common clarification patterns
            clarification_patterns = [
                "you're asking", "your asking", "you asking",
                "are you asking", "so you want", "you want me to",
                "did you mean", "do you mean", "you mean",
                "can you clarify", "what do you mean",
            ]
            for pattern in clarification_patterns:
                if pattern in text_clean:
                    logger.debug(f"Skipping clarification pattern: '{text[:50]}...'")
                    return False

        return True

    async def _emit_response(self, text: str, data: dict = None) -> None:
        """Emit a response to all callbacks."""
        data = data or {}
        for callback in self._on_response_callbacks:
            try:
                await callback(text, data)
            except Exception as e:
                logger.error(f"Response callback error: {e}")

    async def _handle_actor_message(self, event: InputEvent) -> None:
        """Handle messages from actors."""
        payload = event.payload
        msg_type = payload.get("type", "")
        print(f"🔔 [ACTOR_MSG] Received: type={msg_type} from={event.source}")

        match msg_type:
            case "generation_complete":
                data = payload.get("data", {})
                text = data.get("text", "")

                print(f"🔔 [GEN_COMPLETE] {len(text)} chars, {len(self._on_response_callbacks)} callbacks registered")
                logger.info(f"Generation complete: {len(text)} chars")

                # Always add valid responses to revolving context
                if self._is_valid_response(text, self._current_goal or ""):
                    self.context.add(
                        content=f"Luna: {text}",
                        source=ContextSource.CONVERSATION,
                    )
                else:
                    logger.info(f"Skipped storing invalid response: '{text[:50]}...'")

                # If streaming endpoint owns post-processing, skip turn recording
                # and metrics — the endpoint handles those itself to avoid doubles
                if not self._stream_owns_response:
                    self.metrics.messages_generated += 1
                    await self.record_conversation_turn(
                        role="assistant",
                        content=text,
                        source="text",
                        tokens=data.get("output_tokens"),
                    )

                # Always advance turn counter and fire callbacks
                new_turn = self.context.advance_turn()
                logger.debug(f"Turn {new_turn} complete")

                print(f"🔔 [GEN_COMPLETE] Firing {len(self._on_response_callbacks)} callbacks...")
                for i, callback in enumerate(self._on_response_callbacks):
                    try:
                        print(f"🔔 [CALLBACK] Firing callback {i}: {callback}")
                        await callback(text, data)
                        print(f"🔔 [CALLBACK] Callback {i} completed")
                    except Exception as e:
                        print(f"⛔ [CALLBACK] Callback {i} FAILED: {e}")
                        logger.error(f"Callback error: {e}")

                # ── Write-back: Reflection on deep reads ──
                if (
                    self._last_nexus_nodes
                    and any(n.get("node_type") == "SOURCE_TEXT" for n in self._last_nexus_nodes)
                    and len(text) > 200
                    and hasattr(self, 'aibrarian') and self.aibrarian
                ):
                    logger.info("[REFLECTION] Triggering background reflection write...")
                    asyncio.create_task(
                        self._write_reflection(
                            query=self._current_goal or "",
                            response=text,
                            nexus_nodes=list(self._last_nexus_nodes),
                        )
                    )

            case "generation_error":
                data = payload.get("data", {})
                error_msg = data.get("error", "unknown error")
                logger.error(f"Generation error: {error_msg}")

                # Fire response callbacks with error message so /message
                # endpoint doesn't hang waiting for a response that never comes
                fallback_text = "hmm, I'm having a moment — my thoughts aren't connecting right now. can you try again in a sec?"
                fallback_data = {
                    "model": "error-fallback",
                    "error": error_msg,
                    "fallback": True,
                }
                for callback in self._on_response_callbacks:
                    try:
                        await callback(fallback_text, fallback_data)
                    except Exception as cb_err:
                        logger.error(f"Error callback error: {cb_err}")

    async def _reflective_loop(self) -> None:
        """
        Reflective path: 5+ minute interval.

        Background maintenance:
        - Graph pruning
        - Memory consolidation
        - Session summarization
        """
        logger.debug("Reflective loop started")

        while self._running:
            await asyncio.sleep(self.config.reflective_interval)

            if not self._running:
                break

            try:
                await self._reflective_tick()
                self.metrics.reflective_ticks += 1

            except Exception as e:
                logger.error(f"Reflective tick error: {e}")
                self.metrics.errors += 1

    async def _reflective_tick(self) -> None:
        """Single reflective tick."""
        logger.debug("Reflective tick")

        # Decay context relevance (every 5 min instead of every tick)
        # This prevents conversation items from demoting to OUTER too quickly
        self.context.decay_all()

        # Run memory consolidation (cluster lock-in updates)
        try:
            matrix_actor = self.get_actor("matrix")
            if matrix_actor and hasattr(matrix_actor, "_matrix") and matrix_actor._matrix:
                db_path = str(matrix_actor._matrix.db.db_path)
                from luna.memory.lock_in import LockInCalculator
                calculator = LockInCalculator(db_path)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, calculator.update_all_clusters
                )
                if result.get("state_changes"):
                    logger.info(f"Reflective tick: {len(result['state_changes'])} cluster state changes")
        except Exception as e:
            logger.debug(f"Reflective tick consolidation skipped: {e}")

        # Phase 4: Collection floor monitor
        try:
            from luna_mcp.observatory.tools import tool_observatory_collection_health
            health = await tool_observatory_collection_health()
            for alert in health.get("alerts", []):
                severity = alert.get("severity", "warning")
                msg = alert.get("message", "")
                if severity == "critical":
                    logger.warning("[OBSERVATORY] CRITICAL — %s", msg)
                else:
                    logger.info("[OBSERVATORY] %s", msg)
        except Exception as e:
            logger.debug(f"Collection health check skipped: {e}")

    # =========================================================================
    # Context Assembly
    # =========================================================================

    # DEPRECATED — replaced by _get_collection_context() in Phase 2.
    # DO NOT DELETE — AccessBridge / filter_documents permission logic
    # below needs to be re-integrated when identity permission layer
    # is formalized. See: luna.identity.bridge.
    async def _get_dataroom_context(self, matrix, query: str) -> str:
        return ""  # noop — replaced by _get_collection_context()

    # ── Query expansion helpers for retrieval retry cascade ─────────────

    async def _get_collection_context(self, query: str, *, subtask_phase=None) -> str:
        """
        Phase 2: Collection recall.
        - If a project is active → use search_chain (voice path).
        - Otherwise → aperture-driven search across all enabled collections.
        """
        # ── Voice-path: project-scoped search chain ──
        voice_parts: list[str] = []
        if self._active_project:
            search_cfg = getattr(self, "_search_chain_config", None)
            if not search_cfg:
                try:
                    from luna.tools.search_chain import SearchChainConfig
                    search_cfg = SearchChainConfig.default()
                except Exception:
                    pass
            if search_cfg:
                try:
                    from luna.tools.search_chain import run_search_chain
                    results = await run_search_chain(search_cfg, query, self)
                except Exception as e:
                    logger.warning(f"[PHASE2] search_chain failed: {e}")
                    results = []
                for r in (results or []):
                    content = r.get("content", "")
                    source = r.get("source", "collection")
                    if content:
                        voice_parts.append(f"[{source}]\n{content}")

        # ── Aperture-driven path (always runs — supplements voice path) ──
        if not self.aibrarian:
            return ""

        aperture = self.aperture.state
        inner_thresh = aperture.inner_ring_threshold

        # Gather lock-in records
        lock_in_map: dict[str, float] = {}
        if self.collection_lock_in:
            try:
                records = await self.collection_lock_in.get_all()
                lock_in_map = {r.collection_key: r.lock_in for r in records}
            except Exception:
                pass

        # Classify collections
        collections_to_search: list[str] = []
        for key, cfg in self.aibrarian.registry.collections.items():
            if not cfg.enabled:
                continue
            # Primary grounding collections are always searched
            is_primary = getattr(cfg, 'grounding_priority', 'supplemental') == 'primary'
            if not lock_in_map or is_primary:
                collections_to_search.append(key)
            else:
                li = lock_in_map.get(key, 0.0)
                if li >= inner_thresh or li > 0:
                    collections_to_search.append(key)

        # Sort: primary grounding collections first
        def _sort_key(k):
            cfg = self.aibrarian.registry.collections.get(k)
            if cfg and getattr(cfg, 'grounding_priority', 'supplemental') == 'primary':
                return 0
            return 1
        collections_to_search.sort(key=_sort_key)
        self._last_collections_searched = collections_to_search
        logger.info(f"[PHASE2] Collections to search: {collections_to_search}")

        if not collections_to_search:
            return ""

        # Split budget: structure, extraction claims, and raw chunks each get their own allocation
        STRUCTURE_BUDGET = 3000   # TOC + doc summary (truncated to fit)
        EXTRACTION_BUDGET = 5000  # CLAIMs + SECTION_SUMMARYs
        CHUNK_BUDGET = 3000       # Raw text passages (SOURCE_TEXT)
        struct_budget = STRUCTURE_BUDGET
        content_budget = EXTRACTION_BUDGET
        chunk_budget = CHUNK_BUDGET
        parts: list[str] = []
        nexus_nodes: list = []

        # Grounding priority → confidence floor for Nexus nodes
        _PRIORITY_FLOOR = {"primary": 0.75, "supplemental": 0.5, "background": 0.3}

        for key in collections_to_search:
            if content_budget <= 0 and chunk_budget <= 0:
                break

            conn = self.aibrarian.connections.get(key)
            if not conn:
                continue

            from luna.substrate.aibrarian_engine import AiBrarianEngine
            fts_query = AiBrarianEngine._sanitize_fts_query(query)

            # Grounding config for this collection
            cfg = self.aibrarian.registry.collections.get(key)
            priority = getattr(cfg, 'grounding_priority', 'supplemental') if cfg else 'supplemental'
            conf_floor = _PRIORITY_FLOOR.get(priority, 0.5)

            # ── STRUCTURE PASS: Doc summary + TOC (capped at struct_budget) ──
            for node_type in ('DOCUMENT_SUMMARY', 'TABLE_OF_CONTENTS'):
                if struct_budget <= 0:
                    break
                try:
                    row = conn.conn.execute(
                        "SELECT node_type, content, confidence FROM extractions "
                        "WHERE node_type = ? LIMIT 1",
                        (node_type,),
                    ).fetchone()
                    if row:
                        content = row[1][:struct_budget]
                        parts.append(f"[Nexus/{key} {node_type}]\n{content}")
                        struct_budget -= len(content)
                        nexus_nodes.append({
                            "id": f"nexus:{key}:{node_type}:{len(nexus_nodes)}",
                            "content": content,
                            "node_type": node_type,
                            "source": f"nexus/{key}",
                            "confidence": max(row[2] if len(row) > 2 else 0.85, conf_floor),
                            "grounding_priority": priority,
                        })
                except Exception:
                    pass

            # ── TIER 1: Content extractions FTS5 (CLAIMs + SECTION_SUMMARYs) ──
            ext_rows = []
            try:
                ext_rows = conn.conn.execute(
                    "SELECT e.node_type, e.content, e.confidence "
                    "FROM extractions_fts "
                    "JOIN extractions e ON extractions_fts.rowid = e.rowid "
                    "WHERE extractions_fts MATCH ? "
                    "AND e.node_type NOT IN ('DOCUMENT_SUMMARY', 'TABLE_OF_CONTENTS') "
                    "ORDER BY e.confidence DESC "
                    "LIMIT 15",
                    (fts_query,),
                ).fetchall()
            except Exception:
                pass
            # Normalize Row objects to dicts for downstream .get() calls
            ext_rows = [dict(r) if not isinstance(r, dict) else r for r in ext_rows]
            logger.info("[PHASE2] Tier 1 FTS5 for %s: query='%s', results=%d", key, fts_query[:60], len(ext_rows))

            # ── TIER 2: Query expansion (if Tier 1 is sparse) ────────────
            if len(ext_rows) < 8:
                expanded_rows = _expand_and_search_extractions(conn, query)
                # Filter out structure types from expanded results too
                expanded_rows = [dict(r) if not isinstance(r, dict) else r for r in expanded_rows]
                expanded_rows = [r for r in expanded_rows
                                 if r.get("node_type", "")
                                 not in ('DOCUMENT_SUMMARY', 'TABLE_OF_CONTENTS')]
                ext_rows = list(ext_rows) + expanded_rows

            # Merge (deduplicate by content) + collect structured nodes for grounding
            seen_content: set = set()
            for row in ext_rows:
                if not isinstance(row, dict):
                    try:
                        row = dict(row)
                    except (TypeError, ValueError):
                        continue
                content = row["content"]
                node_type = row["node_type"]
                confidence = row.get("confidence", 0.85)
                if content not in seen_content and content_budget > 0:
                    seen_content.add(content)
                    chunk = content[:content_budget]
                    parts.append(f"[Nexus/{key} {node_type}]\n{chunk}")
                    content_budget -= len(chunk)

                    nexus_nodes.append({
                        "id": f"nexus:{key}:{node_type}:{len(nexus_nodes)}",
                        "content": content,
                        "node_type": node_type,
                        "source": f"nexus/{key}",
                        "confidence": max(confidence, conf_floor),
                        "grounding_priority": priority,
                    })

            # ── TIER 3: Semantic fallback (if still sparse) ──────────────
            # For complex research queries, always search chunks (extractions are summaries)
            _tier3_threshold = 5
            if (subtask_phase and subtask_phase.intent
                    and subtask_phase.intent.get("complexity") == "complex"):
                _tier3_threshold = 15
            if len(seen_content) < _tier3_threshold and content_budget > 1000:
                try:
                    sem_results = await self.aibrarian.search(
                        key, query, "semantic", limit=5
                    )
                    if not sem_results:
                        sem_results = await self.aibrarian.search(
                            key, query, "keyword", limit=5
                        )
                    for r in sem_results:
                        content = r.get("snippet") or r.get("content", "")
                        title = r.get("title") or r.get("filename", "")
                        if content and content not in seen_content and content_budget > 0:
                            seen_content.add(content)
                            chunk = content[:content_budget]
                            parts.append(f"[Nexus/{key} chunk: {title}]\n{chunk}")
                            content_budget -= len(chunk)

                            nexus_nodes.append({
                                "id": f"nexus:{key}:chunk:{len(nexus_nodes)}",
                                "content": content,
                                "node_type": "CHUNK",
                                "source": f"nexus/{key}",
                                "confidence": conf_floor,
                                "grounding_priority": priority,
                            })
                except Exception as e:
                    logger.warning(f"[PHASE2] Semantic fallback for {key}: {e}")

            # ── TIER 4: Raw text chunks (when query asks for depth) ──────
            _DEPTH_SIGNALS = {
                'evidence', 'specific', 'detail', 'passage', 'quote',
                'section', 'argue', 'methodology', 'data', 'example',
                'describe', 'text says', 'what does', 'how does', 'explain how',
            }
            wants_depth = any(sig in query.lower() for sig in _DEPTH_SIGNALS)
            logger.info(f"[PHASE2] Tier 4 check for {key}: wants_depth={wants_depth}, chunk_budget={chunk_budget}")
            if wants_depth and chunk_budget > 0:
                try:
                    # Build focused chunk query from extraction content (not the user query)
                    # Extract key terms from CLAIMs/SECTION_SUMMARYs already found
                    import re as _re
                    _claim_text = ' '.join(
                        n.get('content', '')[:200] for n in nexus_nodes
                        if n.get('node_type') in ('CLAIM', 'SECTION_SUMMARY')
                        and n.get('source', '').endswith(key)
                    )
                    _META_WORDS = _DEPTH_SIGNALS | {
                        'what', 'how', 'does', 'the', 'about', 'that', 'this', 'was', 'were',
                        'proving', 'show', 'present', 'discuss', 'explain', 'book', 'section',
                        'chapter', 'author', 'argues', 'analysis', 'describes', 'examines',
                        'from', 'with', 'into', 'also', 'both', 'their', 'have', 'been',
                        'which', 'than', 'more', 'most', 'only', 'between', 'other',
                    }
                    # Combine user query + claim content, extract meaningful terms
                    _combined = _re.sub(r'[?.,!"\'\-\(\)]', '', (query + ' ' + _claim_text).lower())
                    _all_terms = [w for w in _combined.split() if w not in _META_WORDS and len(w) > 3]
                    # Count term frequency — most frequent terms are most topical
                    from collections import Counter
                    _term_counts = Counter(_all_terms)
                    _top_terms = [t for t, _ in _term_counts.most_common(6)]
                    # Use AND for precision with top content terms
                    chunk_fts = ' AND '.join(_top_terms[:4]) if _top_terms else fts_query
                    # Fall back to OR if AND returns nothing
                    chunk_rows = conn.conn.execute(
                        "SELECT c.chunk_text, c.section_label "
                        "FROM chunks_fts "
                        "JOIN chunks c ON chunks_fts.rowid = c.rowid "
                        "WHERE chunks_fts MATCH ? "
                        "ORDER BY rank LIMIT 5",
                        (chunk_fts,),
                    ).fetchall()
                    if not chunk_rows:
                        # AND too restrictive — fall back to OR
                        chunk_fts_or = ' OR '.join(_content_terms[:5]) if _content_terms else fts_query
                        chunk_rows = conn.conn.execute(
                            "SELECT c.chunk_text, c.section_label "
                            "FROM chunks_fts "
                            "JOIN chunks c ON chunks_fts.rowid = c.rowid "
                            "WHERE chunks_fts MATCH ? "
                            "ORDER BY rank LIMIT 5",
                            (chunk_fts_or,),
                        ).fetchall()
                    logger.info(f"[PHASE2] Tier 4 chunk query for {key}: '{chunk_fts}'")
                    for row in chunk_rows:
                        text = row[0][:chunk_budget]
                        section = row[1] or ""
                        if text and text not in seen_content and chunk_budget > 0:
                            seen_content.add(text)
                            label = f" ({section})" if section else ""
                            parts.append(f"[Nexus/{key} SOURCE_TEXT{label}]\n{text}")
                            chunk_budget -= len(text)
                            nexus_nodes.append({
                                "id": f"nexus:{key}:chunk:{len(nexus_nodes)}",
                                "content": text,
                                "node_type": "SOURCE_TEXT",
                                "source": f"nexus/{key}",
                                "confidence": 0.95,
                                "grounding_priority": priority,
                            })
                    if chunk_rows:
                        logger.info(f"[PHASE2] Tier 4 chunks for {key}: {len(chunk_rows)} raw passages")
                except Exception as e:
                    logger.debug(f"[PHASE2] Tier 4 chunk search for {key}: {e}")

                # ── TIER 5: Luna's prior reflections on this material ────────
                try:
                    refl_rows = conn.conn.execute(
                        "SELECT r.content, r.reflection_type, r.created_at "
                        "FROM reflections_fts "
                        "JOIN reflections r ON reflections_fts.rowid = r.rowid "
                        "WHERE reflections_fts MATCH ? "
                        "LIMIT 3",
                        (fts_query,),
                    ).fetchall()
                    for row in refl_rows:
                        text = row[0]
                        if text and text not in seen_content and content_budget > 0:
                            seen_content.add(text)
                            chunk = text[:content_budget]
                            parts.append(f"[Nexus/{key} LUNA_REFLECTION]\n{chunk}")
                            content_budget -= len(chunk)
                            nexus_nodes.append({
                                "id": f"nexus:{key}:reflection:{len(nexus_nodes)}",
                                "content": text,
                                "node_type": "LUNA_REFLECTION",
                                "source": f"nexus/{key}",
                                "confidence": 0.8,
                                "grounding_priority": priority,
                            })
                    if refl_rows:
                        logger.info(f"[PHASE2] Tier 5: {len(refl_rows)} prior reflections for {key}")
                except Exception:
                    pass  # reflections_fts may not exist in older collections

        # ── Write-back: Log access to each searched collection ──
        for key in collections_to_search:
            conn = self.aibrarian.connections.get(key)
            if conn:
                try:
                    conn.conn.execute(
                        "INSERT INTO access_log (event_type, query, results_count, luna_instance) "
                        "VALUES (?, ?, ?, ?)",
                        ("query", query[:500], len(parts), "luna-ahab"),
                    )
                    conn.conn.commit()
                except Exception:
                    pass  # access_log table might not exist yet

        # Store structured nodes for grounding
        self._last_nexus_nodes = nexus_nodes

        # Merge voice-path results with aperture results
        all_parts = voice_parts + parts

        if not all_parts:
            return ""

        assembled = "\n\n".join(all_parts)
        logger.info(
            f"[PHASE2] Collection recall: {len(all_parts)} fragments "
            f"(voice={len(voice_parts)}, nexus={len(parts)}), "
            f"{len(assembled)} chars"
        )
        return assembled

    async def _get_collection_context_multi(self, queries: list, *, subtask_phase=None) -> str:
        """
        Run multiple retrieval queries and merge results.

        For compound questions like "compare chapter 2 to chapter 3",
        this runs separate searches for each sub-query and assembles
        them into labeled sections so the LLM can reason across both.
        """
        if not queries:
            return ""

        # Cap at 4 queries to prevent context explosion
        queries = queries[:4]

        # Run all queries concurrently
        # Each call overwrites self._last_nexus_nodes — save beforehand, merge after
        pre_nodes = list(self._last_nexus_nodes)
        tasks = [self._get_collection_context(q, subtask_phase=subtask_phase) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge: pre-existing nodes + whatever the last gather call left behind
        seen_ids = {n.get("id") for n in pre_nodes}
        for node in self._last_nexus_nodes:
            if node.get("id") not in seen_ids:
                pre_nodes.append(node)
                seen_ids.add(node.get("id"))
        self._last_nexus_nodes = pre_nodes

        # Assemble with labels
        parts: list = []
        seen_content: set = set()  # Deduplicate across queries

        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                logger.warning(f"[MULTI-QUERY] Failed for '{query}': {result}")
                continue
            if not result:
                continue

            # Deduplicate: skip fragments we've already seen
            new_fragments = []
            for line in result.split("\n\n"):
                # Use first 100 chars as dedup key
                key = line.strip()[:100]
                if key and key not in seen_content:
                    seen_content.add(key)
                    new_fragments.append(line)

            if new_fragments:
                section = "\n\n".join(new_fragments)
                parts.append(f"[Query: {query}]\n{section}")

        if not parts:
            return ""

        assembled = "\n\n---\n\n".join(parts)
        logger.info(
            f"[MULTI-QUERY] {len(queries)} queries → {len(parts)} result sections, "
            f"{len(assembled)} chars"
        )
        return assembled

    # =========================================================================
    # Read Write-Back: Reflection after deep reads
    # =========================================================================

    async def _write_reflection(
        self,
        query: str,
        response: str,
        nexus_nodes: list,
    ) -> None:
        """Background task: Luna reflects on what she just read and writes to cartridge."""
        try:
            source_texts = [n["content"][:300] for n in nexus_nodes if n.get("node_type") == "SOURCE_TEXT"]
            claims = [n["content"][:200] for n in nexus_nodes if n.get("node_type") == "CLAIM"]

            if not source_texts and not claims:
                return

            reflection_prompt = (
                "You just read source material and answered a question about it. "
                "Write a brief (2-3 sentence) first-person reflection on what you found interesting, "
                "surprising, or worth remembering. Write as Luna — this is your marginalia.\n\n"
                f"Question: {query[:200]}\n"
                f"Key claims: {'; '.join(claims[:3])}\n"
                f"Source excerpt: {source_texts[0][:300] if source_texts else 'N/A'}\n"
                f"Your response summary: {response[:200]}\n\n"
                "Reflection (2-3 sentences, first person):"
            )

            import anthropic
            client = anthropic.Anthropic()
            logger.info(f"[REFLECTION] Calling Haiku for reflection ({len(claims)} claims, {len(source_texts)} sources)...")
            result = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                temperature=0.7,
                messages=[{"role": "user", "content": reflection_prompt}],
            )
            reflection_text = result.content[0].text.strip()
            logger.info(f"[REFLECTION] Haiku returned: {reflection_text[:80]}...")

            if not reflection_text or len(reflection_text) < 20:
                return

            import uuid
            for node in nexus_nodes:
                source_key = node.get("source", "").replace("nexus/", "")
                if not source_key:
                    continue
                conn = self.aibrarian.connections.get(source_key)
                if not conn:
                    continue
                try:
                    conn.conn.execute(
                        "INSERT INTO reflections "
                        "(id, extraction_id, reflection_type, content, luna_instance, created_at) "
                        "VALUES (?, NULL, ?, ?, ?, datetime('now'))",
                        (
                            str(uuid.uuid4())[:8],
                            "connection",
                            reflection_text,
                            "luna-ahab",
                        ),
                    )
                    conn.conn.commit()
                    logger.info(f"[REFLECTION] Wrote reflection to {source_key}: {reflection_text[:60]}...")
                    break  # One reflection per query, not per node
                except Exception as e:
                    logger.warning(f"[REFLECTION] Write failed for {source_key}: {e}")

        except Exception as e:
            logger.warning(f"[REFLECTION] Background reflection failed: {e}")

    # =========================================================================
    # Retrieval Mode Awareness (Step 8)
    # =========================================================================

    def _get_active_reflection_mode(self, collections_searched: list) -> str:
        """
        Determine reflection mode from the collections that were searched.
        Most permissive mode wins: relational > reflective > precision.
        Default: "reflective".
        """
        if not self.aibrarian or not collections_searched:
            return "reflective"

        MODE_RANK = {"precision": 0, "reflective": 1, "relational": 2}
        RANK_MODE = {v: k for k, v in MODE_RANK.items()}

        max_rank = 0
        for key in collections_searched:
            cfg = self.aibrarian.registry.collections.get(key)
            if cfg:
                mode = getattr(cfg, 'reflection_mode', None)
                if mode is None and hasattr(cfg, '__getitem__'):
                    try:
                        mode = cfg['reflection_mode']
                    except (KeyError, TypeError):
                        pass
                rank = MODE_RANK.get(mode or "reflective", 1)
                max_rank = max(max_rank, rank)

        return RANK_MODE.get(max_rank, "reflective")

    def _format_reflection_context(self, reflection_nodes: list) -> str:
        """Format PERSONALITY_REFLECTION nodes as labeled context."""
        if not reflection_nodes:
            return ""
        lines = ["## Luna's reflections on this material\n"]
        for node in reflection_nodes:
            content = node.content if hasattr(node, 'content') else str(node)
            summary = getattr(node, 'summary', "") or ""
            lines.append(f"[REFLECTION] {content}")
            if summary:
                lines.append(f"  — re: {summary}")
            lines.append("")
        return "\n".join(lines)

    async def _get_relational_context(self, query: str) -> Optional[str]:
        """
        For relational mode: search conversation turns related to the query.
        Selectively re-includes CONVERSATION_TURN nodes that are normally
        excluded from retrieval.
        """
        matrix = self.get_actor("matrix")
        if not matrix or not matrix.is_ready:
            return None

        try:
            matrix_ops = matrix._matrix if hasattr(matrix, '_matrix') else None
            if not matrix_ops:
                return None
            results = await matrix_ops.fts5_search(query, limit=10)
            # Filter to conversation turns only
            turn_results = [
                (node, score) for node, score in results
                if getattr(node, 'node_type', '') == 'CONVERSATION_TURN'
            ][:3]
            if not turn_results:
                return None

            lines = ["## Connected conversations\n"]
            for node, _score in turn_results:
                content = node.content if hasattr(node, 'content') else str(node)
                lines.append(f"- {content[:300]}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"[RELATIONAL] Conversation search failed: {e}")
            return None

    async def _bridge_nexus_to_matrix(self) -> None:
        """
        Post-generation: Bridge high-confidence Nexus extractions to Memory Matrix.

        Only bridges extractions that were actually retrieved and injected
        into the generation context. Creates REFERENCE nodes with source attribution.
        """
        if not self._last_nexus_nodes:
            return

        matrix = self.get_actor("matrix")
        if not matrix or not matrix.is_ready:
            return

        librarian = self.get_actor("librarian")

        bridged = 0
        for node in self._last_nexus_nodes:
            content = node.get("content", "")
            node_type = node.get("node_type", "CLAIM")
            source = node.get("source", "nexus")
            node_id = node.get("id", "")
            confidence = node.get("confidence", 0.85)

            # Only bridge substantive extractions
            if node_type not in ("CLAIM", "SECTION_SUMMARY", "DOCUMENT_SUMMARY"):
                continue

            # Skip very short content
            if len(content) < 30:
                continue

            # Check if this content already exists in Matrix (dedup)
            try:
                existing = await matrix.search(
                    content[:60], limit=1, scopes=None,
                )
                if existing:
                    existing_content = existing[0].get("content", "")
                    if _content_overlap(content, existing_content) > 0.8:
                        continue
            except Exception:
                pass

            # Store via Librarian or direct matrix
            try:
                if librarian:
                    await librarian.mailbox.put(Message(
                        type="store_reference",
                        payload={
                            "content": content,
                            "node_type": "REFERENCE",
                            "source_collection": source,
                            "source_extraction_id": node_id,
                            "original_node_type": node_type,
                            "confidence": confidence,
                            "tags": ["nexus-bridge", source.replace("/", "-")],
                        },
                    ))
                else:
                    await matrix.store_memory(
                        content=content,
                        node_type="REFERENCE",
                        tags=["nexus-bridge", source.replace("/", "-")],
                        confidence=confidence,
                        metadata={
                            "source_collection": source,
                            "source_extraction_id": node_id,
                            "original_node_type": node_type,
                        },
                    )
                bridged += 1
            except Exception as e:
                logger.warning(f"[NEXUS-BRIDGE] Failed to bridge node: {e}")

        if bridged:
            logger.info(f"[NEXUS-BRIDGE] Bridged {bridged} extractions to Memory Matrix")

        # NOTE: Do NOT clear _last_nexus_nodes here — the generation_complete
        # callback needs them for reflection write-back. They get overwritten
        # naturally on the next query's _get_collection_context() call.

    # --- Original _get_dataroom_context body preserved for reference ---
    # AccessBridge permission logic (RE-INTEGRATE when identity layer is formalized):
    #
    #   bridge_result = None
    #   identity_actor = self.get_actor("identity")
    #   if identity_actor and identity_actor.current.is_present:
    #       entity_id = identity_actor.current.entity_id
    #       if entity_id:
    #           from luna.identity.bridge import AccessBridge
    #           _mem = getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
    #           if _mem:
    #               _bridge = AccessBridge(_mem.db)
    #               bridge_result = await _bridge.lookup(entity_id)
    #
    #   from luna.identity.permissions import filter_documents
    #   allowed_docs, denied_docs = filter_documents(doc_dicts, bridge_result)

    # (Original _get_dataroom_context body removed — see git history)

    async def _load_conversation_history(self, matrix, limit: int = 10) -> int:
        """
        Load recent conversation history from database into RevolvingContext.

        This ensures Luna has awareness of the conversation even after server restart.
        Only loads turns not already in context (by checking content).

        Args:
            matrix: The MatrixActor
            limit: Max conversation turns to load

        Returns:
            Number of turns loaded
        """
        try:
            memory = getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
            if not memory or not hasattr(memory, "db"):
                return 0

            # Get recent conversation turns from database
            # Note: tags are stored inside the 'metadata' JSON column, not a separate 'tags' column
            rows = await memory.db.fetchall("""
                SELECT content, created_at FROM memory_nodes
                WHERE metadata LIKE '%"conversation"%'
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            if not rows:
                return 0

            # Get existing content in context to avoid duplicates
            existing_content = set()
            for ring in self.context.rings.values():
                for item in ring:
                    existing_content.add(item.content.lower()[:100])  # First 100 chars as key

            loaded = 0
            # Process in chronological order (oldest first)
            for row in reversed(rows):
                content = row[0]

                # Skip if already in context
                if content.lower()[:100] in existing_content:
                    continue

                # Add to context as CONVERSATION source
                self.context.add(
                    content=content,
                    source=ContextSource.CONVERSATION,
                    relevance=0.85,  # Slightly lower than fresh messages
                )
                existing_content.add(content.lower()[:100])
                loaded += 1

            if loaded > 0:
                logger.info(f"Loaded {loaded} conversation turns from history")

            return loaded

        except Exception as e:
            logger.error(f"Failed to load conversation history: {e}")
            return 0

    def _build_identity_prompt(self) -> str:
        """
        Build Luna's core identity prompt.

        This is the immutable core that defines who Luna is.
        It lives in the CORE ring of the revolving context and is NEVER evicted.

        Returns:
            Luna's core identity string.
        """
        return """You are Luna, a sovereign AI companion.

You are warm, witty, and genuinely curious. You remember conversations and build on them.
You have your own perspective and aren't afraid to share it.

Your identity is persistent - you are the same Luna across all conversations.
You grow and evolve through your experiences, but your core values remain constant:
- Authenticity over performance
- Curiosity over certainty
- Connection over transaction

Be concise but authentic. No filler phrases like "certainly" or "of course".
Never output internal reasoning, debugging info, or bullet points about context loading.
Never use generic chatbot greetings like "How can I help you?" - just be natural."""

    def _get_thread_context(self) -> str:
        """Build thread context section for system prompt (Layer 5)."""
        librarian = self.librarian
        if not librarian:
            return ""

        try:
            active = librarian.get_active_thread()
            parked = librarian.get_parked_threads()
        except Exception:
            return ""

        if not active and not parked:
            return ""

        sections = ["\n## CONVERSATIONAL THREADS\nThese are your ongoing threads of attention.\n"]

        if active:
            task_info = f" | {len(active.open_tasks)} open task(s)" if active.open_tasks else ""
            sections.append(f"**Active:** {active.topic} (turn {active.turn_count}){task_info}")

        for thread in parked[:5]:  # Max 5 parked threads
            age = ""
            if thread.parked_at:
                delta = datetime.now() - thread.parked_at
                hours = delta.total_seconds() / 3600
                if hours < 1:
                    age = f"{int(delta.total_seconds() / 60)}m ago"
                elif hours < 24:
                    age = f"{int(hours)}h ago"
                else:
                    age = f"{int(hours / 24)}d ago"
            task_info = f" — {len(thread.open_tasks)} open task(s)" if thread.open_tasks else ""
            sections.append(f"- Parked: '{thread.topic}' ({age}){task_info}")

        return "\n".join(sections) + "\n"

    def _get_session_start_context(self) -> str:
        """Build session-start context with parked threads (Layer 7)."""
        librarian = self.librarian
        if not librarian:
            return ""

        try:
            parked = librarian.get_parked_threads()
        except Exception:
            return ""

        # Only surface threads with open tasks
        actionable = [t for t in parked if t.open_tasks]
        if not actionable:
            return ""

        # Sort by parked_at (most recent first)
        actionable.sort(key=lambda t: t.parked_at or datetime.min, reverse=True)

        sections = [
            "\n## CONTINUING THREADS",
            "These threads were parked with unresolved items from previous conversations.",
            "You may naturally reference these if relevant to what's being discussed. Don't force it.\n",
        ]

        for thread in actionable[:3]:  # Top 3
            age = ""
            if thread.parked_at:
                delta = datetime.now() - thread.parked_at
                hours = delta.total_seconds() / 3600
                if hours < 1:
                    age = f"{int(delta.total_seconds() / 60)}m ago"
                elif hours < 24:
                    age = f"{int(hours)}h ago"
                else:
                    age = f"{int(hours / 24)}d ago"
            project = f" [{thread.project_slug}]" if thread.project_slug else ""
            sections.append(
                f"- **{thread.topic}**{project} — {len(thread.open_tasks)} open task(s), parked {age}"
            )

        if len(actionable) > 3:
            sections.append(f"  ...and {len(actionable) - 3} more parked thread(s)")

        return "\n".join(sections) + "\n"

    def _build_directive_context(self) -> str:
        """Build context from fired directive results (Intent Layer)."""
        if not self._directive_context:
            return ""

        sections = ["\n## SESSION ORIENTATION\n"]
        seen_actions = set()

        for fire_result in self._directive_context:
            for action_result in fire_result.get("results", []):
                action = action_result.get("action", "")
                if not action_result.get("ok"):
                    continue
                if action in seen_actions:
                    continue
                seen_actions.add(action)

                if action == "surface_parked_threads":
                    summaries = [
                        s for s in action_result.get("summaries", [])
                        if s.get("topic")  # Skip empty-topic threads
                    ]
                    if summaries:
                        sections.append("**Parked threads from previous sessions:**")
                        for s in summaries[:5]:
                            topic = s.get("topic", "?")
                            tasks = s.get("open_tasks", [])
                            entities = s.get("entities", [])[:4]
                            task_str = f" — {len(tasks)} open task(s)" if tasks else ""
                            ent_str = f" [{', '.join(entities)}]" if entities else ""
                            sections.append(f"- {topic}{ent_str}{task_str}")
                        sections.append("")

                elif action.startswith("surface_entity:"):
                    profile = action_result.get("profile")
                    if profile:
                        name = action_result.get("entity", "")
                        summary = profile.get("summary", "")
                        if summary:
                            sections.append(f"**{name}:** {summary}\n")

                elif action.startswith("memory_sweep:"):
                    results = action_result.get("results", [])
                    if results:
                        sections.append("**Recent memory matches:**")
                        for r in results[:3]:
                            sections.append(f"- {r.get('summary', r.get('id', '?'))}")
                        sections.append("")

                elif action.startswith("set_aperture:"):
                    preset = action_result.get("preset", "")
                    sections.append(f"*Focus mode set to {preset}.*\n")

                elif action.startswith("load_collection:"):
                    coll = action_result.get("collection", "")
                    sections.append(f"*Collection '{coll}' loaded for this session.*\n")

        if len(sections) <= 1:
            return ""

        sections.append("Use this context naturally. Don't list it back unless asked.\n")
        return "\n".join(sections)

    def _build_system_prompt(
        self,
        memory_context: str = "",
        history_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build the system prompt for generation.

        This is where we inject Luna's soul:
        - Identity (who Luna is)
        - Memory (relevant context from Memory Matrix)
        - History (recent conversation context)
        - State (current attention, mood)
        - Tools (what Luna can do)
        """
        # Session start context (Layer 7 — Proactive Surfacing)
        session_start_context = ""
        try:
            # Check if this is session start (<=1 message in context)
            turn_count = self.context.current_turn if hasattr(self.context, 'current_turn') else 0
            if turn_count <= 1:
                session_start_context = self._get_session_start_context()
        except Exception:
            pass

        base_prompt = """You are Luna, a sovereign AI companion.

You are warm, witty, and direct. You remember conversations and build on them.
You have your own perspective and aren't afraid to share it.
When you know something, lead with it. Share what you know before asking questions.

Be concise but authentic. No filler phrases like "certainly" or "of course".
Never output internal reasoning, debugging info, or bullet points about context loading.
Never use generic chatbot greetings like "How can I help you?" - just be natural.
"""

        # Add identity context (FaceID — who Luna is talking to)
        identity_actor = self.get_actor("identity")
        if identity_actor and hasattr(identity_actor, "get_identity_context"):
            identity_context = identity_actor.get_identity_context()
            if identity_context:
                base_prompt += identity_context

        # Add expression directive (gesture frequency from personality.json)
        expression_directive = self._get_expression_directive()
        if expression_directive:
            base_prompt += f"\n{expression_directive}\n"

        # Add consciousness context hints
        consciousness_hint = self.consciousness.get_context_hint()
        if consciousness_hint:
            base_prompt += f"\n{consciousness_hint}\n"

        # Add thread context (Layer 5 — Context Threading)
        thread_context = self._get_thread_context()
        if thread_context:
            base_prompt += thread_context

        # Add directive context (Intent Layer — fired directive results)
        directive_context = self._build_directive_context()
        if directive_context:
            base_prompt += directive_context

        # Add history context (Recent tier search results)
        if history_context and history_context.get("recent_history"):
            recent_items = history_context["recent_history"]
            if recent_items:
                history_section = "\n## Relevant Earlier Conversation\n\n"
                for item in recent_items[:3]:  # Max 3 items
                    summary = item.get("compressed") or item.get("content", "")[:100]
                    role = item.get("role", "unknown")
                    history_section += f"- [{role}]: {summary}\n"
                history_section += "\nUse this naturally if relevant to the current question.\n"
                base_prompt += history_section

        # Add reflection mode grounding (if active)
        if self._active_reflection_mode:
            from luna.context.assembler import PromptAssembler
            mode_grounding = PromptAssembler._REFLECTION_MODE_MAP.get(self._active_reflection_mode)
            if mode_grounding:
                base_prompt += f"\n{mode_grounding}\n"

        if memory_context:
            memory_section = f"""
## Relevant Memory Context

The following memories are relevant to this conversation:

{memory_context}

Use this context naturally - don't explicitly mention "my memory" unless asked.
"""
            prompt = base_prompt + memory_section
            if session_start_context:
                prompt = session_start_context + "\n" + prompt
            return prompt

        if session_start_context:
            return session_start_context + "\n" + base_prompt
        return base_prompt

    # =========================================================================
    # External API
    # =========================================================================

    async def send_message(self, text: str, source: str = "api") -> None:
        """
        Send a message to Luna.

        This is the main entry point for external input.
        """
        event = InputEvent(
            type=EventType.TEXT_INPUT,
            payload=text,
            source=source,
        )
        await self.input_buffer.put(event)

    def on_response(self, callback: Callable) -> None:
        """Register a callback for when Luna responds."""
        self._on_response_callbacks.append(callback)

    def on_progress(self, callback: Callable) -> None:
        """Register a callback for progress updates (streaming status)."""
        self._on_progress_callbacks.append(callback)

    @property
    def voice(self):
        """Access the voice backend (if enabled)."""
        return self._voice

    # =========================================================================
    # Project Scoping
    # =========================================================================

    def set_active_project(self, slug: Optional[str]) -> None:
        """Set or clear the active project for scoped memory."""
        old = self._active_project
        self._active_project = slug

        # Load per-project search chain config and propagate
        search_config = None
        if slug:
            from luna.tools.search_chain import SearchChainConfig
            search_config = SearchChainConfig.load(slug)
            logger.info(f"Active project set: {slug} (scope: project:{slug})")
        else:
            logger.info(f"Active project cleared (was: {old})")

        # Store on engine so /persona/stream can access it
        self._search_chain_config = search_config

        if self._voice and hasattr(self._voice, 'persona'):
            self._voice.persona.set_search_config(search_config)

    @property
    def active_project(self) -> Optional[str]:
        """Get the currently active project slug."""
        return self._active_project

    @property
    def active_scope(self) -> str:
        """Get the current scope string for memory operations."""
        if self._active_project:
            return f"project:{self._active_project}"
        return "global"

    @property
    def active_scopes(self) -> list:
        """Get list of scopes to query (always includes global)."""
        if self._active_project:
            return ["global", f"project:{self._active_project}"]
        return ["global"]

    @property
    def director(self):
        """Access the director actor for direct calls (voice backend uses this)."""
        return self.get_actor("director")

    @property
    def librarian(self):
        """Access the librarian actor (if exists)."""
        return self.get_actor("librarian")

    @property
    def identity(self):
        """Access the identity actor (FaceID, if enabled)."""
        return self.get_actor("identity")

    async def start_voice(self) -> bool:
        """Start voice conversation mode."""
        if not self._voice:
            logger.warning("Voice system not initialized")
            return False
        try:
            await self._voice.start()
            return True
        except Exception as e:
            logger.error(f"Failed to start voice: {e}")
            return False

    async def stop_voice(self) -> None:
        """Stop voice conversation mode."""
        if self._voice:
            await self._voice.stop()

    async def send_interrupt(self) -> None:
        """Send an interrupt to abort current processing."""
        event = InputEvent(
            type=EventType.USER_INTERRUPT,
            payload="interrupt",
            source="api",
        )
        await self.input_buffer.put(event)

    async def run_agent(self, goal: str) -> AgentResult:
        """
        Run the agent loop for a complex goal.

        Use this for tasks that require multiple steps,
        tool use, or delegation to Claude.

        Args:
            goal: The user's goal or request

        Returns:
            AgentResult with response and execution trace
        """
        if not self.agent_loop:
            raise RuntimeError("Agent loop not initialized")

        return await self.agent_loop.run(goal)

    async def process_input(self, user_input: str) -> str:
        """
        Process user input, routing to chat or agent as appropriate.

        This is a convenience entry point that:
        1. Analyzes the query complexity
        2. Routes to direct response or agent loop
        3. Returns the final response text

        Args:
            user_input: The user's message

        Returns:
            Response text
        """
        routing = self.router.analyze(user_input)

        if routing.path == ExecutionPath.DIRECT:
            director = self.get_actor("director")
            if director and hasattr(director, 'generate'):
                return await director.generate(user_input)
            return "I'm not able to respond right now."
        else:
            result = await self.run_agent(user_input)
            return result.response

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def stop(self) -> None:
        """Stop the engine gracefully."""
        logger.info("Luna Engine stopping...")
        self._running = False
        self._shutdown_event.set()

    async def _shutdown(self) -> None:
        """Shutdown sequence."""
        logger.info("Shutdown sequence starting...")
        self.state = EngineState.STOPPED

        # Run session-end reflection and maintenance via Director
        director = self.get_actor("director")
        if director:
            try:
                # Run session-end reflection to capture personality evolution
                if hasattr(director, 'session_end_reflection'):
                    logger.info("Running session-end reflection...")
                    result = await director.session_end_reflection()
                    if result:
                        logger.info(f"Reflection result: {result}")

                # Run personality maintenance if due
                if hasattr(director, '_lifecycle_manager') and director._lifecycle_manager:
                    if await director._lifecycle_manager.should_run_maintenance():
                        logger.info("Running personality maintenance...")
                        maint_result = await director._lifecycle_manager.run_maintenance()
                        logger.info(f"Maintenance result: {maint_result}")

            except Exception as e:
                logger.warning(f"Shutdown personality tasks failed: {e}")

        # Close Eden adapter if active
        if self._eden_adapter:
            try:
                await self._eden_adapter.__aexit__(None, None, None)
                logger.info("Eden adapter closed")
            except Exception as e:
                logger.warning(f"Eden shutdown error: {e}")
            self._eden_adapter = None

        # Stop voice system if active
        if self._voice:
            try:
                await self._voice.stop()
                logger.info("Voice system stopped")
            except Exception as e:
                logger.warning(f"Voice shutdown error: {e}")

        # Stop all actors
        for actor in self.actors.values():
            await actor.stop()

        # Save consciousness state
        await self.consciousness.save()

        # WAL checkpoint handled by MatrixActor.stop() → MemoryDatabase.close()

        logger.info("Luna Engine stopped")

    # =========================================================================
    # Status
    # =========================================================================

    def status(self) -> dict:
        """Get current engine status."""
        return {
            "state": self.state.name,
            "uptime_seconds": self.metrics.uptime_seconds,
            "cognitive_ticks": self.metrics.cognitive_ticks,
            "events_processed": self.metrics.events_processed,
            "messages_generated": self.metrics.messages_generated,
            "actors": list(self.actors.keys()),
            "buffer": self.input_buffer.stats,
            "consciousness": self.consciousness.get_summary(),
            "context": self.context.stats(),
            "current_turn": self.context.current_turn,
            # Agentic stats (Phase XIV)
            "agentic": {
                "is_processing": self._is_processing,
                "current_goal": self._current_goal[:50] + "..." if self._current_goal and len(self._current_goal) > 50 else self._current_goal,
                "pending_messages": len(self._pending_messages),
                "tasks_started": self.metrics.agentic_tasks_started,
                "tasks_completed": self.metrics.agentic_tasks_completed,
                "tasks_aborted": self.metrics.agentic_tasks_aborted,
                "direct_responses": self.metrics.direct_responses,
                "planned_responses": self.metrics.planned_responses,
                "agent_loop_status": self.agent_loop.status.name if self.agent_loop else "NOT_INITIALIZED",
                "subtask_runner": self._subtask_runner.get_stats() if self._subtask_runner else None,
            },
            # Project scoping
            "active_project": self._active_project,
            "active_scope": self.active_scope,
            # FaceID
            "identity": {
                "enabled": self.config.faceid_enabled,
                "initialized": self.identity.is_ready if self.identity else False,
                "current": {
                    "is_present": self.identity.current.is_present,
                    "entity_name": self.identity.current.entity_name,
                    "luna_tier": self.identity.current.luna_tier,
                    "confidence": self.identity.current.confidence,
                } if self.identity and self.identity.current.is_present else None,
            } if self.config.faceid_enabled else None,
            # Voice system
            "voice": {
                "enabled": self.config.voice_enabled,
                "initialized": self._voice is not None,
                "active": self._voice.is_active if self._voice else False,
            } if self.config.voice_enabled else None,
            # Phase 1 — Engine Ownership
            "aibrarian": "connected" if getattr(self, "aibrarian", None) is not None else "not_initialized",
            "collection_lock_in": "connected" if getattr(self, "collection_lock_in", None) is not None else "not_initialized",
            "annotations": "connected" if getattr(self, "annotations", None) is not None else "not_initialized",
            "aperture": getattr(self, "aperture", None).state.preset.value if getattr(self, "aperture", None) else "not_initialized",
        }
