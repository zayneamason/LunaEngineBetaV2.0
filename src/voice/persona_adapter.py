"""
PersonaCore Adapter - Direct integration for Luna Engine Voice backend.

Replaces HTTP-based HubClient with direct Luna Engine integration.
No network overhead, direct method invocation through the engine.
"""
import asyncio
import logging
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from luna.agentic import ExecutionPath

logger = logging.getLogger(__name__)

# Safety net: detect "I don't know" responses so we can retry through the agent loop
_SURRENDER_PATTERN = re.compile(
    r"i don.t have (any |specific )?(information|memory|memories|context|knowledge|details)"
    r"|tell me (more|a bit more)"
    r"|i.m not (sure|familiar)"
    r"|i don.t know (about|anything)"
    r"|not in my (memory|records|context)",
    re.IGNORECASE,
)


@dataclass
class VoiceResponse:
    """Response from Luna Engine for voice queries."""
    response: str                         # Luna's text response
    memory_context: List[Dict]            # Retrieved memories
    personality_state: Dict               # Personality context
    debug: Optional[Dict] = None          # Debug info


class PersonaAdapter:
    """
    Direct integration with Luna Engine.

    Replaces HubClient HTTP calls with direct Engine method calls.
    Compatible with HubClient API for minimal backend changes.

    This adapter interfaces with Luna Engine's:
    - Director actor (for LLM inference)
    - Librarian actor (for memory retrieval)
    - Entity system (for personality)
    """

    def __init__(self, engine=None):
        """
        Initialize adapter.

        Args:
            engine: Luna Engine instance (optional - can be set later)
        """
        self._engine = engine
        self._available = engine is not None
        self._connected = False
        self._search_config = None  # Per-project search chain config

        if engine:
            logger.info("PersonaAdapter initialized with Luna Engine")
        else:
            logger.info("PersonaAdapter initialized (engine not yet connected)")

    def set_engine(self, engine):
        """
        Set or update the engine reference.

        Args:
            engine: Luna Engine instance
        """
        self._engine = engine
        self._available = engine is not None
        if engine:
            logger.info("PersonaAdapter connected to Luna Engine")

    def set_search_config(self, config) -> None:
        """Update the search chain config (called on project activation)."""
        self._search_config = config
        if config:
            sources = [s.type for s in config.sources]
            logger.info(f"[VOICE] Search chain updated: {sources}")
        else:
            logger.info("[VOICE] Search chain reset to defaults")

    def is_available(self) -> bool:
        """Check if Luna Engine is available."""
        return self._available and self._engine is not None

    async def connect(self) -> bool:
        """
        Connect to Luna Engine (compatibility with HubClient API).

        Since we're using direct integration, this checks engine readiness.
        """
        if not self._engine:
            logger.error("No engine configured")
            return False

        try:
            # Check if engine is running
            # Luna Engine uses state machine, check if we're in a valid state
            if hasattr(self._engine, 'state'):
                from luna.core.state import EngineState
                if self._engine.state == EngineState.RUNNING:
                    self._connected = True
                    logger.info("PersonaAdapter connected to running engine")
                    return True
                else:
                    logger.warning(f"Engine not running (state: {self._engine.state})")
                    return False
            else:
                # Fallback: assume available if engine exists
                self._connected = True
                return True

        except Exception as e:
            logger.error(f"Failed to connect to engine: {e}")
            return False

    async def process_message(
        self,
        message: str,
        interface: str = "voice",
        session_id: Optional[str] = None,
        generate_response: bool = True,
        conversation_history: Optional[List[Dict]] = None,  # NEW: Conversation history
    ) -> Optional[VoiceResponse]:
        """
        Process a message through Luna Engine.

        Args:
            message: User message
            interface: Interface type (voice | desktop)
            session_id: Optional session ID
            generate_response: If True, generates LLM response
            conversation_history: List of {"role": "user"|"assistant", "content": str}

        Returns:
            VoiceResponse with Luna's response and context
        """
        # [HISTORY-TRACE] Log what PersonaAdapter receives
        if conversation_history:
            logger.info(f"[HISTORY-TRACE] PersonaAdapter.process_message RECEIVED {len(conversation_history)} history turns")
            for i, turn in enumerate(conversation_history):
                logger.info(f"[HISTORY-TRACE] PersonaAdapter: Turn {i}: {turn['role']}: '{turn['content'][:50]}...'")
        else:
            logger.info("[HISTORY-TRACE] PersonaAdapter.process_message RECEIVED NO HISTORY (conversation_history is None or empty)")

        if not self.is_available():
            logger.error("Luna Engine not available")
            return None

        try:
            # Route through engine's input buffer
            # The engine uses a pull-based model - we submit to the buffer
            # and the engine processes during its tick loop

            # For voice, we want immediate response, so we'll call Director directly
            # if available, otherwise use the event system

            response_text = ""
            memory_context = []
            personality_state = {}
            route_decision = "unknown"
            route_reason = "unknown"
            system_prompt_tokens = 0
            agent_loop_used = False
            surrender_intercepted = False
            confabulation_flagged = False

            # ── Reconcile: check for pending self-correction instruction ──
            reconcile = getattr(self._engine, 'reconcile', None)
            reconcile_instruction = reconcile.tick() if reconcile else None
            if reconcile_instruction:
                logger.info("[VOICE] Reconcile instruction active for this turn")

            # Format conversation history as context window for Director
            context_window = ""
            if conversation_history:
                for turn in conversation_history:
                    role = "Luna" if turn["role"] == "assistant" else "User"
                    context_window += f"{role}: {turn['content']}\n\n"
                logger.info(f"[HISTORY-TRACE] PersonaAdapter: Built context_window with {len(conversation_history)} turns ({len(context_window)} chars)")

            # ── Route through QueryRouter before hitting LLM ──
            router = getattr(self._engine, 'router', None)
            routing = None
            if router:
                try:
                    routing = router.analyze(message)
                    route_decision = routing.path.name
                    route_reason = routing.reason
                    logger.info(
                        f"[VOICE-ROUTE] path={routing.path.name} "
                        f"complexity={routing.complexity:.2f} "
                        f"signals={routing.signals} "
                        f"tools={routing.suggested_tools}"
                    )
                except Exception as e:
                    logger.error(f"[VOICE-ROUTE] Router failed, falling back to DIRECT: {e}")
                    routing = None

            # ── Non-DIRECT paths: use AgentLoop for tool access ──
            if routing and routing.path != ExecutionPath.DIRECT:
                loop_result = await self._run_agent_loop_with_timeout(message, timeout=10.0)
                if loop_result and loop_result.success and loop_result.response:
                    response_text = loop_result.response
                    agent_loop_used = True
                    logger.info(
                        f"[VOICE-ROUTE] AgentLoop succeeded "
                        f"(iterations={loop_result.iterations}, "
                        f"duration={loop_result.duration_ms:.0f}ms)"
                    )
                else:
                    logger.warning("[VOICE-ROUTE] AgentLoop failed/timed out, falling back to DIRECT")

            # ── DIRECT path (or fallback): prefetch + Director ──
            if not agent_loop_used:
                if hasattr(self._engine, 'director') and self._engine.director:
                    director = self._engine.director
                    memory_context = await self._prefetch_knowledge(message)

                    if generate_response:
                        try:
                            director_context = {
                                "interface": interface,
                                "memories": memory_context,
                                "session_id": session_id,
                                "context_window": context_window,
                                "conversation_history": conversation_history or [],
                            }
                            if reconcile_instruction:
                                director_context["reconcile_instruction"] = reconcile_instruction
                            result = await director.process(
                                message=message,
                                context=director_context,
                            )
                            response_text = result.get("response", "") if result else ""
                            if not routing:
                                route_decision = result.get("route_decision", "delegated") if result else "unknown"
                                route_reason = result.get("route_reason", "Director") if result else "unknown"
                            system_prompt_tokens = result.get("system_prompt_tokens", 0) if result else 0
                        except Exception as e:
                            logger.error(f"Director processing failed: {e}")
                            response_text = "I'm having trouble processing that right now."

            # ── Scout inspection: blockage + confabulation detection ──
            scout = self._engine.get_actor("scout") if hasattr(self._engine, 'get_actor') else None
            watchdog = getattr(self._engine, 'watchdog', None)
            scout_report = None

            if scout and response_text:
                context_size = sum(len(m.get("content", "")) for m in memory_context) if memory_context else 0
                retrieved_context_text = "\n".join(
                    m.get("content", "") for m in memory_context
                ) if memory_context else ""

                scout_report = scout.inspect(
                    draft=response_text,
                    query=message,
                    context_size=context_size,
                    retrieved_context=retrieved_context_text,
                )

                # ── Confabulation → Reconcile path ──
                if scout_report.blocked and scout_report.recommendation == "reconcile":
                    confabulation_flagged = True
                    if reconcile and scout_report.confabulation_data:
                        reconcile.flag_confabulation(
                            claims=scout_report.confabulation_data.get("unsupported_claims", []),
                            original_query=message,
                        )
                        logger.warning(
                            f"[VOICE] Confabulation flagged for reconcile — "
                            f"{len(scout_report.confabulation_data.get('unsupported_claims', []))} unsupported claims"
                        )

                # ── Blockage → Overdrive path ──
                elif scout_report.blocked and scout_report.overdrive_tier > 0:
                    if watchdog and not watchdog.enter_recursion():
                        logger.warning("[VOICE] Watchdog blocked Scout recursion")
                    else:
                        if watchdog:
                            watchdog.start_operation("overdrive")
                        try:
                            overdrive_response = await scout.overdrive(
                                query=message,
                                tier=scout_report.overdrive_tier,
                                engine=self._engine,
                            )
                            if overdrive_response:
                                response_text = overdrive_response
                                surrender_intercepted = True
                        except Exception as e:
                            logger.error(f"[OVERDRIVE] Failed: {e}")
                        finally:
                            if watchdog:
                                watchdog.end_operation("overdrive")
                                watchdog.exit_recursion()

            # ── Reconcile: check if Luna self-corrected ──
            if reconcile and response_text and reconcile.did_reconcile(response_text):
                logger.info("[VOICE] Luna reconciled — notifying Scribe for CORRECTION extraction")
                scribe = self._engine.get_actor("scribe") if hasattr(self._engine, 'get_actor') else None
                if scribe:
                    from luna.actors.base import Message as ActorMessage
                    await scribe.handle(ActorMessage(
                        type="extract_correction",
                        payload={
                            "original_query": reconcile._state.original_query,
                            "flagged_claims": reconcile._state.flagged_claims,
                            "correction_response": response_text,
                            "session_id": session_id,
                        }
                    ))
                reconcile.clear()

            # Fallback: surrender_intercept for cases where Scout isn't available
            if not scout and response_text and not agent_loop_used:
                original = response_text
                response_text = await self._surrender_intercept(message, response_text)
                if response_text != original:
                    surrender_intercepted = True

            # Record conversation turns through unified engine API
            if self._engine and hasattr(self._engine, 'record_conversation_turn'):
                try:
                    await self._engine.record_conversation_turn(
                        role="user",
                        content=message,
                        source="voice",
                    )
                    if response_text:
                        await self._engine.record_conversation_turn(
                            role="assistant",
                            content=response_text,
                            source="voice",
                        )
                except Exception as e:
                    logger.error(f"Failed to record voice turns: {e}")

            # Get personality state if entity system available
            if hasattr(self._engine, 'get_personality_state'):
                try:
                    personality_state = self._engine.get_personality_state()
                except Exception as e:
                    logger.warning(f"Personality state unavailable: {e}")

            return VoiceResponse(
                response=response_text,
                memory_context=memory_context,
                personality_state=personality_state,
                debug={
                    "interface": interface,
                    "memories_retrieved": len(memory_context),
                    "engine_connected": self._connected,
                    "route_path": route_decision,
                    "route_reason": route_reason,
                    "route_signals": routing.signals if routing else [],
                    "route_complexity": round(routing.complexity, 2) if routing else 0,
                    "agent_loop_used": agent_loop_used,
                    "surrender_intercepted": surrender_intercepted,
                    "system_prompt_tokens": system_prompt_tokens,
                    "conversation_history_length": len(conversation_history) if conversation_history else 0,
                    "confabulation_flagged": confabulation_flagged,
                    "scout_report": scout_report.__dict__ if scout_report else None,
                    "scout_status": scout.get_status() if scout else None,
                    "watchdog_status": watchdog.get_status() if watchdog else None,
                    "reconcile_status": reconcile.get_status() if reconcile else None,
                }
            )

        except Exception as e:
            logger.error(f"PersonaAdapter processing failed: {e}", exc_info=True)
            return None

    async def _prefetch_knowledge(self, query: str) -> List[Dict]:
        """
        Pre-fetch relevant knowledge using the configured search chain.

        Uses project-specific config if active, otherwise default (matrix + dataroom).
        Config is set via set_search_config() when a project is activated.
        """
        from luna.tools.search_chain import SearchChainConfig, run_search_chain

        config = self._search_config or SearchChainConfig.default()
        return await run_search_chain(config, query, self._engine)

    async def _run_agent_loop_with_timeout(self, goal: str, timeout: float = 10.0):
        """Run the engine's AgentLoop with a timeout, returning None on failure."""
        agent_loop = getattr(self._engine, 'agent_loop', None)
        if not agent_loop:
            logger.warning("[VOICE-ROUTE] Engine has no agent_loop, skipping")
            return None
        try:
            result = await asyncio.wait_for(agent_loop.run(goal), timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"[VOICE-ROUTE] AgentLoop timed out after {timeout}s for: {goal[:50]}")
            return None
        except Exception as e:
            logger.error(f"[VOICE-ROUTE] AgentLoop failed: {e}")
            return None

    async def _surrender_intercept(self, query: str, draft_response: str) -> str:
        """If Luna's draft says 'I don't know', force a tool search via AgentLoop."""
        if not draft_response or not _SURRENDER_PATTERN.search(draft_response):
            return draft_response

        logger.warning(f"[SURRENDER-INTERCEPT] Detected knowledge surrender for: {query[:50]}")

        result = await self._run_agent_loop_with_timeout(query, timeout=8.0)
        if result and result.success and result.response:
            logger.info("[SURRENDER-INTERCEPT] Re-generation succeeded via AgentLoop")
            return result.response

        return draft_response  # keep original if retry also fails

    async def get_personality(self) -> Optional[Dict]:
        """
        Get current personality state from engine.

        Returns:
            Personality dict or None
        """
        if not self.is_available():
            return None

        try:
            if hasattr(self._engine, 'get_personality_state'):
                return self._engine.get_personality_state()
            return None
        except Exception as e:
            logger.error(f"Failed to get personality: {e}")
            return None

    async def close(self):
        """Close adapter (compatibility with HubClient API)."""
        self._connected = False
        logger.info("PersonaAdapter closed")


class MockPersonaAdapter(PersonaAdapter):
    """
    Mock adapter for testing without Luna Engine.

    Returns predefined responses for testing the voice pipeline.
    """

    def __init__(self, default_response: str = "I hear you. Let me think about that."):
        super().__init__(engine=None)
        self._default_response = default_response
        self._available = True
        self._connected = True

    def is_available(self) -> bool:
        return True

    async def connect(self) -> bool:
        return True

    async def process_message(
        self,
        message: str,
        interface: str = "voice",
        session_id: Optional[str] = None,
        generate_response: bool = True
    ) -> Optional[VoiceResponse]:
        """Return mock response."""
        return VoiceResponse(
            response=self._default_response,
            memory_context=[],
            personality_state={
                "energy": 0.6,
                "warmth": 0.7,
                "playfulness": 0.4,
                "directness": 0.8,
            },
            debug={"mock": True}
        )

    async def get_personality(self) -> Optional[Dict]:
        return {
            "energy": 0.6,
            "warmth": 0.7,
            "playfulness": 0.4,
            "directness": 0.8,
        }
