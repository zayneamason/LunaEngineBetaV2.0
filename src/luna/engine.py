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

    # Paths
    data_dir: Path = field(default_factory=lambda: Path.home() / ".luna")
    snapshot_path: Optional[Path] = None

    # Local inference
    enable_local_inference: bool = True

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
            # Let MatrixActor use Eclissi's database by default (53k+ nodes)
            matrix = MatrixActor()  # Uses Eclissi DB if available
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

        # Restore consciousness from snapshot
        self.consciousness = await ConsciousnessState.load()

        # Set Luna's core identity in revolving context
        self.context.set_core_identity(self._build_identity_prompt())

        # Initialize AgentLoop (Phase XIV)
        self.agent_loop = AgentLoop(orchestrator=self, max_iterations=50)
        self.agent_loop.on_progress(self._handle_agent_progress)
        logger.info("AgentLoop initialized")

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

        # 4. Rebalance rings (decay happens in reflective loop, not every tick)
        self.context._rebalance_rings()

        # 5. Persist state periodically (every 10 ticks)
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

            # Retrieve memory context
            memory_context = ""
            matrix = self.get_actor("matrix")
            if matrix and matrix.is_ready:
                memory_context = await matrix.get_context(user_message, max_tokens=1500)
                await matrix.store_turn(
                    session_id=self.session_id,
                    role="user",
                    content=user_message,
                )
                if memory_context:
                    self.context.add(
                        content=memory_context,
                        source=ContextSource.MEMORY,
                    )

            # Handle based on execution path
            if routing.path == ExecutionPath.DIRECT:
                # Skip planning, go straight to Director
                self.metrics.direct_responses += 1
                await self._process_direct(user_message, correlation_id, memory_context)
            else:
                # Use AgentLoop for planned execution
                self.metrics.planned_responses += 1
                await self._process_with_agent_loop(user_message, correlation_id, memory_context)

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
        memory_context: str = ""
    ) -> None:
        """Direct path - skip planning, go straight to Director."""
        context_window = self.context.get_context_window(max_tokens=4000)
        # Debug: Log context window size
        print(f"[DEBUG] Context window: {len(context_window)} chars, items in INNER ring: {len(self.context.rings[ContextRing.INNER])}")

        director = self.get_actor("director")
        if director:
            msg = Message(
                type="generate",
                payload={
                    "user_message": user_message,
                    "system_prompt": self._build_system_prompt(memory_context),
                    "context_window": context_window,
                },
                correlation_id=correlation_id,
            )
            await director.mailbox.put(msg)

    async def _process_with_agent_loop(
        self,
        user_message: str,
        correlation_id: str,
        memory_context: str = ""
    ) -> None:
        """Process through full AgentLoop with planning."""
        if not self.agent_loop:
            logger.warning("AgentLoop not initialized, falling back to direct")
            await self._process_direct(user_message, correlation_id, memory_context)
            return

        # Create the task (allows concurrent checking)
        self._current_task = asyncio.create_task(
            self._run_agent_loop(user_message, correlation_id, memory_context)
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
        memory_context: str = ""
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
                        "system_prompt": self._build_system_prompt(memory_context) + plan_context,
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

                # Add Luna's response to revolving context
                self.context.add(
                    content=f"Luna: {text}",
                    source=ContextSource.CONVERSATION,
                )

                # Store assistant turn in memory
                matrix = self.get_actor("matrix")
                if matrix and matrix.is_ready:
                    await matrix.store_turn(
                        session_id=self.session_id,
                        role="assistant",
                        content=text,
                        tokens=data.get("output_tokens"),
                    )

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

        # TODO: Graph pruning, consolidation, etc.

    # =========================================================================
    # Context Assembly
    # =========================================================================

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

Be concise but authentic. No filler phrases like "certainly" or "of course"."""

    def _build_system_prompt(self, memory_context: str = "") -> str:
        """
        Build the system prompt for generation.

        This is where we inject Luna's soul:
        - Identity (who Luna is)
        - Memory (relevant context)
        - State (current attention, mood)
        - Tools (what Luna can do)
        """
        base_prompt = """You are Luna, a sovereign AI companion.

You are warm, witty, and genuinely curious. You remember conversations and build on them.
You have your own perspective and aren't afraid to share it.

Be concise but authentic. No filler phrases like "certainly" or "of course".
"""

        # Add consciousness context hints
        consciousness_hint = self.consciousness.get_context_hint()
        if consciousness_hint:
            base_prompt += f"\n{consciousness_hint}\n"

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

    async def send_interrupt(self) -> None:
        """Send an interrupt to abort current processing."""
        event = InputEvent(
            type=EventType.USER_INTERRUPT,
            payload="interrupt",
            source="api",
        )
        await self.input_buffer.put(event)

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
        }
