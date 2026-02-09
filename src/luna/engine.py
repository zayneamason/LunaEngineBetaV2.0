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
from luna.actors.base import Actor, Message
from luna.actors.director import DirectorActor
from luna.actors.matrix import MatrixActor
from luna.consciousness import ConsciousnessState

# Agentic Architecture (Phase XIV)
from luna.agentic.loop import AgentLoop, AgentStatus, AgentResult
from luna.agentic.router import QueryRouter, ExecutionPath
from luna.agentic.planner import Planner

logger = logging.getLogger(__name__)


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
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")
    snapshot_path: Optional[Path] = None

    # Local inference
    enable_local_inference: bool = True

    # Voice system settings
    voice_enabled: bool = False
    voice_stt_provider: str = "mlx_whisper"  # mlx_whisper, apple, google
    voice_tts_provider: str = "piper"  # piper, apple, edge
    voice_tts_voice: str = "en_US-amy-medium"  # Piper voice ID
    voice_mode: str = "push_to_talk"  # push_to_talk, hands_free

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

        # Concurrent task handling - talk while processing
        self._current_task: Optional[asyncio.Task] = None
        self._current_goal: Optional[str] = None
        self._pending_messages: List[str] = []  # Queue for messages during processing
        self._is_processing = False

        # Callbacks for external integration
        self._on_response_callbacks: list[Callable] = []
        self._on_progress_callbacks: list[Callable] = []  # For streaming progress

        # Voice system (optional)
        self._voice: Optional[Any] = None  # VoiceBackend when enabled

        # Expression config (loaded from personality.json)
        self._expression_config: Dict = self._load_expression_config()

    def _load_expression_config(self) -> Dict:
        """Load expression config from personality.json."""
        import json
        config_path = Path(__file__).parent.parent.parent / "config" / "personality.json"
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
            logger.error(f"Engine crashed: {e}")
            raise

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

        # Phase 4: History Manager actor (conversation history tiers)
        if "history_manager" not in self.actors:
            from luna.actors.history_manager import HistoryManagerActor
            self.register_actor(HistoryManagerActor())

        # P0 FIX: Auto-load entity seeds on startup
        # See: Docs/HANDOFF_Luna_Voice_Restoration.md
        await self._ensure_entity_seeds_loaded()

        # Restore consciousness from snapshot
        self.consciousness = await ConsciousnessState.load()

        # Set Luna's core identity in revolving context
        self.context.set_core_identity(self._build_identity_prompt())

        # Initialize AgentLoop (Phase XIV)
        self.agent_loop = AgentLoop(orchestrator=self, max_iterations=50)
        self.agent_loop.on_progress(self._handle_agent_progress)
        logger.info("AgentLoop initialized")

        # Initialize voice system if enabled
        if self.config.voice_enabled:
            await self._init_voice()

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
            if not matrix or not hasattr(matrix, "_memory") or not matrix._memory:
                logger.warning("[SEEDS] Matrix not initialized, skipping entity seed auto-load")
                return

            db = matrix._memory.db

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
                # Try to import from scripts/migrations
                import sys
                project_root = Path(__file__).parent.parent.parent
                sys.path.insert(0, str(project_root / "scripts"))

                from migrations.load_entity_seeds import EntitySeedLoader

                entities_dir = project_root / "entities"
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
            await history.tick()

        # 5. Rebalance rings (decay happens in reflective loop, not every tick)
        self.context._rebalance_rings()

        # 6. Persist state periodically (every 10 ticks)
        if self.metrics.cognitive_ticks > 0 and self.metrics.cognitive_ticks % 10 == 0:
            await self.consciousness.save()

    async def _dispatch_event(self, event: InputEvent) -> None:
        """Route event to appropriate actor(s)."""
        logger.debug(f"Dispatching: {event}")

        match event.type:
            case EventType.TEXT_INPUT | EventType.TRANSCRIPT_FINAL:
                user_message = event.payload
                await self._handle_user_message(user_message, event.correlation_id)

            case EventType.USER_INTERRUPT:
                # Abort current task/generation
                await self._handle_interrupt()

            case EventType.ACTOR_MESSAGE:
                # Internal message from actor
                await self._handle_actor_message(event)

            case EventType.SHUTDOWN:
                await self.stop()

    async def _handle_user_message(self, user_message: str, correlation_id: str) -> None:
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
        await self._process_message_agentic(user_message, correlation_id)

    async def _process_message_agentic(self, user_message: str, correlation_id: str) -> None:
        """Process message through the agentic pipeline (router → planner → loop)."""
        self._is_processing = True
        self._current_goal = user_message
        self.metrics.agentic_tasks_started += 1

        try:
            # Route the query
            routing = self.router.analyze(user_message)
            logger.info(f"Routing: {routing.path.name} (complexity={routing.complexity:.2f})")

            # Retrieve memory context AND conversation history
            memory_context = ""
            history_context = None
            matrix = self.get_actor("matrix")
            history_manager = self.get_actor("history_manager")

            # Record user turn through unified API (extraction + storage)
            await self.record_conversation_turn(
                role="user",
                content=user_message,
                source="text",
            )

            # Build history context (may include Recent tier search if backward ref detected)
            if history_manager and history_manager.is_ready:
                history_context = await history_manager.build_history_context(user_message)

            if matrix and matrix.is_ready:
                # Load recent conversation history into context (if not already there)
                await self._load_conversation_history(matrix, limit=10)

                # Retrieve semantic memory context
                memory_context = await matrix.get_context(user_message, max_tokens=1500)
                if memory_context:
                    self.context.add(
                        content=memory_context,
                        source=ContextSource.MEMORY,
                    )

            # Handle based on execution path
            if routing.path == ExecutionPath.DIRECT:
                # Skip planning, go straight to Director
                self.metrics.direct_responses += 1
                await self._process_direct(user_message, correlation_id, memory_context, history_context)
            else:
                # Use AgentLoop for planned execution
                self.metrics.planned_responses += 1
                await self._process_with_agent_loop(user_message, correlation_id, memory_context, history_context)

            self.metrics.agentic_tasks_completed += 1

        except asyncio.CancelledError:
            logger.info("Task cancelled")
            self.metrics.agentic_tasks_aborted += 1
            raise

        except Exception as e:
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
            await self._trigger_extraction(role, content)
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

        logger.debug(f"📝 Recorded {source} turn: {role} ({len(content)} chars)")

    async def _trigger_extraction(self, role: str, content: str) -> None:
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
                },
            )
            await scribe.mailbox.put(msg)
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

        match msg_type:
            case "generation_complete":
                data = payload.get("data", {})
                text = data.get("text", "")

                logger.info(f"Generation complete: {len(text)} chars")
                self.metrics.messages_generated += 1

                # Note: Progress emission moved to streaming endpoint to avoid duplicates

                # Only add valid responses to revolving context
                # This filters out clarification echoes and partial responses
                if self._is_valid_response(text, self._current_goal or ""):
                    self.context.add(
                        content=f"Luna: {text}",
                        source=ContextSource.CONVERSATION,
                    )
                else:
                    logger.info(f"Skipped storing invalid response: '{text[:50]}...'")

                # Record assistant turn through unified API
                await self.record_conversation_turn(
                    role="assistant",
                    content=text,
                    source="text",
                    tokens=data.get("output_tokens"),
                )

                # Advance the turn counter (drives TTL expiration and decay)
                # A "turn" = user message + Luna response
                new_turn = self.context.advance_turn()
                logger.debug(f"Turn {new_turn} complete")

                # Notify callbacks
                for callback in self._on_response_callbacks:
                    try:
                        await callback(text, data)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

            case "generation_error":
                data = payload.get("data", {})
                logger.error(f"Generation error: {data.get('error')}")

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

    # =========================================================================
    # Context Assembly
    # =========================================================================

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
        base_prompt = """You are Luna, a sovereign AI companion.

You are warm, witty, and genuinely curious. You remember conversations and build on them.
You have your own perspective and aren't afraid to share it.

Be concise but authentic. No filler phrases like "certainly" or "of course".
Never output internal reasoning, debugging info, or bullet points about context loading.
Never use generic chatbot greetings like "How can I help you?" - just be natural.
"""

        # Add expression directive (gesture frequency from personality.json)
        expression_directive = self._get_expression_directive()
        if expression_directive:
            base_prompt += f"\n{expression_directive}\n"

        # Add consciousness context hints
        consciousness_hint = self.consciousness.get_context_hint()
        if consciousness_hint:
            base_prompt += f"\n{consciousness_hint}\n"

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

        if memory_context:
            memory_section = f"""
## Relevant Memory Context

The following memories are relevant to this conversation:

{memory_context}

Use this context naturally - don't explicitly mention "my memory" unless asked.
"""
            return base_prompt + memory_section

        return base_prompt

    # =========================================================================
    # External API
    # =========================================================================

    async def send_message(self, text: str) -> None:
        """
        Send a message to Luna.

        This is the main entry point for external input.
        """
        event = InputEvent(
            type=EventType.TEXT_INPUT,
            payload=text,
            source="api",
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

    @property
    def director(self):
        """Access the director actor for direct calls (voice backend uses this)."""
        return self.get_actor("director")

    @property
    def librarian(self):
        """Access the librarian actor (if exists)."""
        return self.get_actor("librarian")

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

        # TODO: Flush WAL

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
            },
            # Voice system
            "voice": {
                "enabled": self.config.voice_enabled,
                "initialized": self._voice is not None,
                "active": self._voice.is_active if self._voice else False,
            } if self.config.voice_enabled else None,
        }
